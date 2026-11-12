"""VIS-07 artifact integrity, legacy compatibility, and real media checks."""

import asyncio
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import wave

import pytest
from PIL import Image
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from functions import checkpoint_manager as checkpoints
from functions import dag_evaluator as dag
from functions import manim_renderer as renderer
from functions import visual_artifacts as artifacts
from functions.create_image_videos_function import create_image_videos


def media():
    return artifacts.MediaInfo(duration_seconds=1, width=1280, height=720,
                               fps=25, codec="h264", pixel_format="yuv420p")


def completed(run_dir, scene_id=0):
    path = run_dir / "image_videos" / f"seg_{scene_id}.mp4"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(b"mock encoded media")
    return artifacts.VisualArtifact(
        scene_id=scene_id, artifact_id=f"seg_{scene_id}", requested_strategy="pillow",
        actual_strategy="pillow", status="rendered", attempt_count=1,
        output_path=f"image_videos/seg_{scene_id}.mp4", media=media(),
        sha256=artifacts.file_sha256(path),
        validation=artifacts.VisualValidation(media="passed"),
    )


def test_manifest_roundtrip_preserves_ids_and_does_not_claim_semantic_acceptance(tmp_path, monkeypatch):
    records = [completed(tmp_path, scene_id) for scene_id in (2, 10)]
    manifest = artifacts.VisualManifest(scenes=records)
    artifacts.save_visual_manifest(tmp_path, manifest)
    restored = artifacts.load_visual_manifest(tmp_path)
    assert [record.artifact_id for record in restored.scenes] == ["seg_2", "seg_10"]
    assert all(record.validation.semantic == "not_checked" for record in restored.scenes)
    monkeypatch.setattr(artifacts, "probe_visual_video", lambda path: media())
    paths = artifacts.manifest_video_paths(tmp_path, ["seg_10", "seg_2"])
    assert [Path(path).name for path in paths] == ["seg_2.mp4", "seg_10.mp4"]


@pytest.mark.parametrize("change", [
    {"artifact_id": "seg_9"}, {"output_path": "../outside.mp4"},
    {"status": "accepted"}, {"sha256": None},
    {"validation": {"media": "passed", "semantic": "failed"}},
])
def test_manifest_rejects_inconsistent_success(tmp_path, change):
    record = completed(tmp_path).model_dump()
    record.update(change)
    with pytest.raises(ValidationError):
        artifacts.VisualArtifact.model_validate(record)


def test_rejected_or_uncertain_acceptance_cannot_be_marked_rendered(tmp_path):
    from functions.visual_acceptance import AcceptanceResult, Decision, Verdict

    record = completed(tmp_path).model_dump()
    record["validation"] = {
        "media": "passed", "semantic": "uncertain",
        "evaluator_version": "visual-acceptance-v1", "evidence": [],
        "acceptance": AcceptanceResult(
            verdict=Verdict.UNCERTAIN, decision=Decision.FALLBACK,
            reason_codes=["semantic_uncertain"], evidence=[], retryable=True,
            attempt=1, elapsed_seconds=0,
        ).model_dump(),
    }
    with pytest.raises(ValidationError, match="cannot be marked rendered"):
        artifacts.VisualArtifact.model_validate(record)


def test_manifest_rejects_duplicate_or_out_of_order_scenes(tmp_path):
    first, second = completed(tmp_path, 2), completed(tmp_path, 10)
    for records in ([first, first], [second, first], []):
        with pytest.raises(ValidationError):
            artifacts.VisualManifest(scenes=records)


def test_failed_atomic_write_preserves_previous_output_and_cleans_temporary(tmp_path):
    target = tmp_path / "seg_0.mp4"
    target.write_bytes(b"previous output")
    with pytest.raises(RuntimeError):
        with artifacts.atomic_output(target) as temporary:
            Path(temporary).write_bytes(b"incomplete replacement")
            raise RuntimeError("encoder crashed")
    assert target.read_bytes() == b"previous output"
    assert list(tmp_path.iterdir()) == [target]


def test_invalid_manifest_update_preserves_last_document(tmp_path):
    manifest = artifacts.VisualManifest(scenes=[completed(tmp_path)])
    artifacts.save_visual_manifest(tmp_path, manifest)
    previous = (tmp_path / artifacts.MANIFEST_PATH).read_bytes()
    manifest.scenes[0].status = "accepted"
    with pytest.raises(ValidationError):
        artifacts.save_visual_manifest(tmp_path, manifest)
    assert (tmp_path / artifacts.MANIFEST_PATH).read_bytes() == previous


@pytest.mark.parametrize("failure", ["missing", "changed", "failed", "wrong_ids", "malformed", "metadata"])
def test_manifest_blocks_stale_or_incomplete_composition(tmp_path, monkeypatch, failure):
    record = completed(tmp_path)
    if failure == "failed":
        record.status = "failed"
    if failure == "metadata":
        record.media.duration_seconds = 99
    artifacts.save_visual_manifest(tmp_path, artifacts.VisualManifest(scenes=[record]))
    video = tmp_path / record.output_path
    if failure == "missing":
        video.unlink()
    elif failure == "changed":
        video.write_bytes(b"corruption or replacement")
    elif failure == "malformed":
        (tmp_path / artifacts.MANIFEST_PATH).write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(artifacts, "probe_visual_video", lambda path: media())
    with pytest.raises(ValueError):
        artifacts.manifest_video_paths(tmp_path, ["seg_1" if failure == "wrong_ids" else "seg_0"])


def test_legacy_runs_without_manifest_remain_supported(tmp_path):
    assert artifacts.manifest_video_paths(tmp_path, ["seg_0"]) is None


def test_composition_stops_before_ffmpeg_for_failed_manifest(tmp_path, monkeypatch):
    from functions import combine_videos_function as compositor

    record = completed(tmp_path)
    record.status = "failed"
    artifacts.save_visual_manifest(tmp_path, artifacts.VisualManifest(scenes=[record]))
    (tmp_path / "video").mkdir()
    (tmp_path / "video/seg_0.mp4").write_bytes(b"avatar")

    def unexpected_run(*args, **kwargs):
        pytest.fail("Composition must reject failed artifacts before invoking FFmpeg")

    monkeypatch.setattr(compositor.subprocess, "run", unexpected_run)
    with pytest.raises(ValueError, match="seg_0 is failed"):
        asyncio.run(compositor.combine_videos(str(tmp_path), "example"))


def test_dag_invalidates_stitching_for_failed_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoints, "RUNS_DIR", str(tmp_path))
    run_id = checkpoints.init_run("Example", "failed-visual")
    run_dir = Path(checkpoints.get_run_dir(run_id))
    checkpoint = checkpoints.load_checkpoint(run_id)
    checkpoint["stages"]["stitching"]["status"] = "COMPLETED"
    checkpoint["stages"]["validation"]["status"] = "COMPLETED"
    checkpoints.save_checkpoint(run_id, checkpoint)
    record = completed(run_dir)
    record.status = "failed"
    artifacts.save_visual_manifest(run_dir, artifacts.VisualManifest(scenes=[record]))
    monkeypatch.setattr(dag, "validate_video_file", lambda path: True)
    _, report = dag.evaluate_run_dag(run_id)
    assert report["stage_checks"]["stitching"]["valid"] is False
    assert "manifest" in report["stage_checks"]["stitching"]["reason"]
    assert checkpoints.load_checkpoint(run_id)["stages"]["validation"]["status"] == "INVALID"


def scene(scene_id, strategy="slide"):
    algorithm = strategy == "manim"
    concept = "Breadth-first search" if algorithm else "A simple lesson concept"
    narration = (
        "Breadth-first search visits graph neighbors level by level in queue order."
        if algorithm else "This scene explains a simple lesson concept clearly and carefully."
    )
    return SimpleNamespace(
        scene_id=scene_id, visual_type=strategy, learning_objective="Explain the main idea",
        narration=narration, visual_query=concept, estimated_seconds=8,
        manim_spec={"topic_type": "bfs", "steps": ["A", "B"]},
        on_screen_text="Demo", key_concept=concept,
        must_show=[], must_not_show=[],
    )


def test_one_scene_failure_records_manifest_and_keeps_other_scenes(tmp_path, monkeypatch):
    from functions import create_image_videos_function as slides

    def render_slide(run_dir, chunk_ids, preserved_chunk_ids):
        if chunk_ids == ["seg_2"]:
            raise RuntimeError("conversion failed")
        path = Path(run_dir) / "image_videos" / f"{chunk_ids[0]}.mp4"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"rendered")

    monkeypatch.setattr(slides, "create_image_videos", render_slide)
    monkeypatch.setattr(renderer, "probe_visual_video", lambda path: media())
    with pytest.raises(RuntimeError, match="seg_2"):
        renderer.render_all_visual_scenes(str(tmp_path), SimpleNamespace(scenes=[scene(10), scene(2)]))
    manifest = artifacts.load_visual_manifest(tmp_path)
    assert [(item.scene_id, item.status) for item in manifest.scenes] == [(2, "failed"), (10, "accepted")]
    assert manifest.scenes[0].output_path is None


def test_single_scene_conversion_ignores_unrelated_missing_inputs(tmp_path, monkeypatch):
    from functions import create_image_videos_function as slides

    write_inputs(tmp_path, [0, 1])
    completed(tmp_path)
    (tmp_path / "images/seg_1.jpg").unlink()
    # This pass has already rendered Manim scene 0. Scene 1's missing image
    # must not prevent scene 0 from keeping its successfully rendered clip.
    monkeypatch.setattr(slides, "probe_visual_video", lambda path: media())
    create_image_videos(str(tmp_path), chunk_ids=["seg_0"], preserved_chunk_ids=["seg_0"])


def test_fallback_records_actual_strategy_and_keeps_legacy_return_type(tmp_path, monkeypatch):
    from functions import create_image_videos_function as slides
    record = completed(tmp_path)
    calls = []
    monkeypatch.setattr(renderer, "render_scene_manim", lambda *args, **kwargs: "images/seg_0.jpg")
    monkeypatch.setattr(renderer, "probe_visual_video", lambda path: media())
    monkeypatch.setattr(slides, "create_image_videos", lambda *args, **kwargs: calls.append(kwargs))
    result = renderer.render_all_visual_scenes(str(tmp_path), SimpleNamespace(scenes=[scene(0, "manim")]))
    assert result == [os.path.join(str(tmp_path), record.output_path)]
    manifest = artifacts.load_visual_manifest(tmp_path)
    assert manifest.scenes[0].actual_strategy == "pillow"
    assert manifest.scenes[0].fallback_reason
    assert calls[0]["preserved_chunk_ids"] == []


def test_checkpoint_alias_preserves_attempts_and_stage_order(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoints, "RUNS_DIR", str(tmp_path))
    run_id = checkpoints.init_run("Example", "legacy")
    checkpoint = checkpoints.load_checkpoint(run_id)
    checkpoint["stages"]["wav2lip"] = {"status": "COMPLETED", "attempts": 3, "chunks": {}}
    checkpoint["current_stage"] = "wav2lip"
    checkpoints.save_checkpoint(run_id, checkpoint)
    loaded = checkpoints.load_checkpoint(run_id)
    assert loaded["current_stage"] == "sadtalker"
    assert loaded["stages"]["sadtalker"]["attempts"] == 3
    checkpoints.update_stage_status(run_id, "wav2lip", "RUNNING")
    loaded = checkpoints.load_checkpoint(run_id)
    assert loaded["stages"]["sadtalker"]["attempts"] == 4
    assert loaded["stages"]["wav2lip"] == loaded["stages"]["sadtalker"]
    assert checkpoints.PIPELINE_STAGES == ["script", "storyboard", "audio_tts", "scrapling_images", "sadtalker", "stitching", "validation"]


@pytest.mark.parametrize("status", ["RUNNING", "INVALID"])
def test_dag_does_not_treat_unfinished_stage_as_complete(tmp_path, monkeypatch, status):
    monkeypatch.setattr(checkpoints, "RUNS_DIR", str(tmp_path))
    run_id = checkpoints.init_run("Example", "unfinished")
    checkpoint = checkpoints.load_checkpoint(run_id)
    checkpoint["stages"]["script"]["status"] = status
    checkpoints.save_checkpoint(run_id, checkpoint)
    stage, report = dag.evaluate_run_dag(run_id)
    assert stage == "script"
    assert report["stage_checks"]["script"]["valid"] is False


def write_inputs(run_dir, ids):
    for folder in ("images", "audio"):
        (run_dir / folder).mkdir(exist_ok=True)
    for scene_id in ids:
        Image.new("RGB", (640, 360), "navy").save(run_dir / "images" / f"seg_{scene_id}.jpg")
        with wave.open(str(run_dir / "audio" / f"seg_{scene_id}.wav"), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x00\x00" * 6400)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_real_slide_and_manim_fallback_media_roundtrip(tmp_path, monkeypatch):
    write_inputs(tmp_path, [2, 10])
    # A large stale clip must be replaced, never reused by its size.
    (tmp_path / "image_videos").mkdir()
    (tmp_path / "image_videos/seg_2.mp4").write_bytes(b"bad media" * 10000)
    monkeypatch.setattr(renderer, "resolve_manim_python", lambda: None)
    paths = renderer.render_all_visual_scenes(str(tmp_path), SimpleNamespace(scenes=[scene(10, "manim"), scene(2)]))
    assert [Path(path).name for path in paths] == ["seg_2.mp4", "seg_10.mp4"]
    manifest = artifacts.load_visual_manifest(tmp_path)
    assert all(item.status in {"rendered", "accepted"} and item.media.fps == 25 for item in manifest.scenes)
    assert manifest.scenes[1].fallback_reason
    assert len(artifacts.manifest_video_paths(tmp_path, ["seg_2", "seg_10"])) == 2
    assert not list(tmp_path.rglob(".visual-*"))

    # Simple valid clips can be much smaller than the old 50 KB heuristic.
    monkeypatch.setattr(checkpoints, "RUNS_DIR", str(tmp_path.parent))
    checkpoint = {"stages": {"stitching": {"status": "COMPLETED"}}}
    checkpoints.save_checkpoint(tmp_path.name, checkpoint)
    _, report = dag.evaluate_run_dag(tmp_path.name)
    assert report["stage_checks"]["stitching"]["valid"] is True


def test_normalization_failure_never_publishes_raw_manim_output(tmp_path, monkeypatch):
    destination = tmp_path / "image_videos/seg_0.mp4"
    destination.parent.mkdir()
    destination.write_bytes(b"previous valid artifact")
    monkeypatch.setattr(renderer, "resolve_manim_python", lambda: sys.executable)

    def run(command, **kwargs):
        if "--media_dir" in command:
            directory = Path(command[command.index("--media_dir") + 1])
            directory.mkdir()
            (directory / "render.mp4").write_bytes(b"raw unnormalized output")
            return SimpleNamespace(returncode=0, stderr="")
        return SimpleNamespace(returncode=1, stderr="normalization failed")

    monkeypatch.setattr(renderer.subprocess, "run", run)
    assert renderer.render_manim_to_mp4("# template", str(destination), 1) is False
    assert destination.read_bytes() == b"previous valid artifact"
