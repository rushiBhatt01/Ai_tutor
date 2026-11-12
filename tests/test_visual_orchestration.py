"""Focused checks for VIS-08 visual worker bounds and result ordering."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from types import SimpleNamespace

from functions.manim_renderer import visual_worker_limit, validate_visual_spec_alignment
from functions.visual_artifacts import (
    MediaInfo, VisualArtifact, VisualManifest, VisualValidation,
    load_visual_manifest, save_visual_manifest,
)
from functions.visual_acceptance import AcceptanceResult, Decision, Verdict
from functions.visual_pipeline_graph import collect_visual_manifest


def test_worker_limit_defaults_and_caps(monkeypatch):
    monkeypatch.delenv("VISUAL_RENDER_WORKERS", raising=False)
    assert visual_worker_limit() == 2
    assert visual_worker_limit("1") == 1
    assert visual_worker_limit("4") == 4
    assert visual_worker_limit("99") == 4
    assert visual_worker_limit("invalid") == 2


def test_worker_limit_never_returns_zero_or_negative():
    assert visual_worker_limit("0") == 1
    assert visual_worker_limit("-3") == 1


def test_validated_specs_must_match_scene_ids_and_routes():
    scene = SimpleNamespace(scene_id=0, visual_type="pillow")
    spec = {
        "scene_id": 0, "topic": "Concept", "visual_goal": "Explain concept",
        "visual_type": "pillow", "duration_seconds": 8,
        "width": 1280, "height": 720, "fps": 25,
    }
    assert validate_visual_spec_alignment({0: scene}, [spec])[0].scene_id == 0
    with pytest.raises(ValueError, match="scene IDs"):
        validate_visual_spec_alignment({0: scene}, [])
    with pytest.raises(ValueError, match="strategy mismatch"):
        validate_visual_spec_alignment({0: scene}, [{**spec, "visual_type": "manim"}])
    with pytest.raises(ValueError, match="Duplicate visual specification"):
        validate_visual_spec_alignment({0: scene}, [spec, spec])
    with pytest.raises(ValueError, match="conflicting requirements"):
        validate_visual_spec_alignment({0: scene}, [{
            **spec, "must_show": ["plant cell"], "must_not_show": ["plant cell"],
        }])


def _accepted_artifact(scene_id):
    result = AcceptanceResult(
        verdict=Verdict.ACCEPTED, decision=Decision.ACCEPT,
        reason_codes=[], evidence=["semantic and media checks passed"],
        retryable=False, attempt=1, elapsed_seconds=0,
    )
    return VisualArtifact(
        scene_id=scene_id, artifact_id=f"seg_{scene_id}",
        requested_strategy="pillow", actual_strategy="pillow", status="accepted",
        output_path=f"image_videos/seg_{scene_id}.mp4",
        media=MediaInfo(duration_seconds=4, width=1280, height=720, fps=25,
                        codec="h264", pixel_format="yuv420p"),
        sha256="a" * 64,
        validation=VisualValidation(media="passed", semantic="passed", acceptance=result),
        attempt_count=1, attempts=[result],
    )


def test_visual_graph_manifest_gate_accepts_complete_ordered_manifest(tmp_path):
    save_visual_manifest(tmp_path, VisualManifest(scenes=[_accepted_artifact(0), _accepted_artifact(1)]))
    result = collect_visual_manifest({
        "run_dir": str(tmp_path),
        "visual_specs": [{"scene_id": 0}, {"scene_id": 1}],
        "video_paths": ["image_videos/seg_0.mp4", "image_videos/seg_1.mp4"],
    })
    assert result["status"] == "complete"
    assert result["manifest_path"].endswith("artifacts/visual_manifest.json")


def test_visual_graph_manifest_gate_rejects_unaccepted_scene(tmp_path):
    save_visual_manifest(tmp_path, VisualManifest(scenes=[
        _accepted_artifact(0),
        VisualArtifact(scene_id=1, artifact_id="seg_1", requested_strategy="pillow",
                       status="failed", error="render failed"),
    ]))
    with pytest.raises(RuntimeError, match="unaccepted scenes"):
        collect_visual_manifest({
            "run_dir": str(tmp_path),
            "visual_specs": [{"scene_id": 0}, {"scene_id": 1}],
            "video_paths": ["image_videos/seg_0.mp4", "image_videos/seg_1.mp4"],
        })


def test_visual_graph_manifest_gate_rejects_missing_or_reordered_dispatch_paths(tmp_path):
    save_visual_manifest(tmp_path, VisualManifest(scenes=[_accepted_artifact(0), _accepted_artifact(1)]))
    state = {"run_dir": str(tmp_path), "visual_specs": [{"scene_id": 0}, {"scene_id": 1}]}
    with pytest.raises(RuntimeError, match="dispatch paths"):
        collect_visual_manifest({**state, "video_paths": ["image_videos/seg_0.mp4"]})
    with pytest.raises(RuntimeError, match="dispatch paths"):
        collect_visual_manifest({**state, "video_paths": ["image_videos/seg_1.mp4", "image_videos/seg_0.mp4"]})


def test_visual_graph_runs_mixed_strategy_lesson_to_ordered_manifest(tmp_path, monkeypatch):
    from functions.storyboard_schema import Scene, Storyboard
    import functions.manim_renderer as renderer
    from functions.visual_pipeline_graph import run_visual_pipeline

    monkeypatch.setenv("IMAGE_SEARCH_ENABLED", "true")
    monkeypatch.setenv("MANIM_ENABLED", "false")
    storyboard = Storyboard(title="Mixed visuals", scenes=[
        Scene(scene_id=0, key_concept="An introductory lesson",
              narration="This scene explains a general concept in a clear way.",
              visual_query="An introductory concept", on_screen_text="Introduction",
              estimated_seconds=8),
        Scene(scene_id=1, key_concept="Plants use sunlight for photosynthesis",
              learning_objective="Explain photosynthesis",
              narration="Plants use sunlight to make sugars from water and carbon dioxide.",
              visual_query="A plant leaf using sunlight", on_screen_text="Photosynthesis",
              estimated_seconds=9),
    ])
    observed = {}

    def mock_render(run_dir, *, storyboard, visual_specs):
        observed["strategies"] = [spec["visual_type"] for spec in visual_specs]
        save_visual_manifest(run_dir, VisualManifest(scenes=[
            _accepted_artifact(spec["scene_id"]) for spec in visual_specs
        ]))
        return [f"image_videos/seg_{spec['scene_id']}.mp4" for spec in visual_specs]

    monkeypatch.setattr(renderer, "render_all_visual_scenes", mock_render)
    result = run_visual_pipeline(str(tmp_path), storyboard=storyboard)
    assert observed["strategies"] == ["pillow", "web_image"]
    assert [spec["scene_id"] for spec in result["visual_specs"]] == [0, 1]
    assert result["status"] == "complete"


@pytest.mark.parametrize("failure", ["provider outage", "Pillow fallback failure"])
def test_visual_graph_keeps_failed_dispatch_auditable(tmp_path, monkeypatch, failure):
    from functions.storyboard_schema import Scene, Storyboard
    import functions.manim_renderer as renderer
    from functions.visual_pipeline_graph import run_visual_pipeline

    monkeypatch.setenv("IMAGE_SEARCH_ENABLED", "true")
    monkeypatch.setenv("MANIM_ENABLED", "false")
    storyboard = Storyboard(title="Failed scene", scenes=[
        Scene(scene_id=0, key_concept="Photosynthesis",
              narration="A leaf uses sunlight, water, and carbon dioxide to make sugars.",
              visual_query="A real plant leaf using sunlight", on_screen_text="Photosynthesis",
              estimated_seconds=8),
    ])

    def fail_dispatch(run_dir, *, storyboard, visual_specs):
        assert len(visual_specs) == 1
        save_visual_manifest(run_dir, VisualManifest(scenes=[VisualArtifact(
            scene_id=0, artifact_id="seg_0", requested_strategy="web_image",
            status="failed", fallback_reason="Pillow fallback could not produce a clip",
            error=failure,
        )]))
        raise RuntimeError(failure)

    monkeypatch.setattr(renderer, "render_all_visual_scenes", fail_dispatch)
    with pytest.raises(RuntimeError, match=failure):
        run_visual_pipeline(str(tmp_path), storyboard=storyboard)

    manifest = load_visual_manifest(tmp_path)
    assert manifest.scenes[0].status == "failed"
    assert manifest.scenes[0].error == failure
    assert manifest.scenes[0].fallback_reason


def test_visual_graph_renderer_fallback_failure_does_not_erase_successful_scene(tmp_path, monkeypatch):
    from functions import create_image_videos_function as slides
    from functions import manim_renderer as renderer
    from functions import visual_routing
    from functions.storyboard_schema import Scene, Storyboard
    from functions.visual_pipeline_graph import run_visual_pipeline

    monkeypatch.setenv("VISUAL_RENDER_WORKERS", "2")
    monkeypatch.setattr(visual_routing, "route_storyboard", lambda _storyboard: None)
    (tmp_path / "images").mkdir()
    for scene_id in (0, 1):
        (tmp_path / "images" / f"seg_{scene_id}.jpg").write_bytes(b"fallback slide")

    storyboard = Storyboard(title="Partial visual failure", scenes=[
        Scene(scene_id=0, key_concept="Breadth-first search",
              narration="Breadth-first search explores graph neighbors level by level.",
              visual_query="A breadth-first search traversal", on_screen_text="BFS",
              estimated_seconds=8, visual_type="manim",
              manim_spec={"topic_type": "bfs", "steps": ["A", "B"]}),
        Scene(scene_id=1, key_concept="A second lesson concept",
              narration="This second scene explains another lesson concept clearly.",
              visual_query="A simple diagram for the second concept", on_screen_text="Next",
              estimated_seconds=8, visual_type="pillow"),
    ])

    def fallback_from_manim(spec, chunk_id, run_dir, **kwargs):
        spec["_fallback_reason"] = "Manim worker failed; Pillow fallback selected"
        return str(Path(run_dir) / "images" / f"{chunk_id}.jpg")

    monkeypatch.setattr(renderer, "render_scene_manim", fallback_from_manim)
    media = MediaInfo(duration_seconds=8, width=1280, height=720, fps=25,
                      codec="h264", pixel_format="yuv420p")
    monkeypatch.setattr(renderer, "probe_visual_video", lambda _path: media)

    def convert(run_dir, *, chunk_ids, preserved_chunk_ids):
        if chunk_ids == ["seg_0"]:
            raise RuntimeError("fallback video conversion failed")
        output = Path(run_dir) / "image_videos" / f"{chunk_ids[0]}.mp4"
        output.parent.mkdir(exist_ok=True)
        output.write_bytes(b"accepted second-scene video")

    monkeypatch.setattr(slides, "create_image_videos", convert)
    with pytest.raises(RuntimeError, match="seg_0"):
        run_visual_pipeline(str(tmp_path), storyboard=storyboard)

    manifest = load_visual_manifest(tmp_path)
    assert [(item.scene_id, item.status) for item in manifest.scenes] == [
        (0, "failed"), (1, "accepted"),
    ]
    assert manifest.scenes[0].fallback_reason == "Manim worker failed; Pillow fallback selected"
    assert "fallback video conversion failed" in manifest.scenes[0].error


def test_visual_resume_reuses_accepted_scene_and_invalidates_when_audio_changes(tmp_path, monkeypatch):
    from functions import create_image_videos_function as slides
    from functions import manim_renderer as renderer
    from functions import visual_routing
    from functions.storyboard_schema import Scene, Storyboard
    from functions.visual_artifacts import file_sha256, visual_cache_key
    from functions.visual_spec import VisualSpec

    (tmp_path / "audio").mkdir()
    (tmp_path / "images").mkdir()
    audio_path = tmp_path / "audio" / "seg_0.wav"
    image_path = tmp_path / "images" / "seg_0.jpg"
    output_path = tmp_path / "image_videos" / "seg_0.mp4"
    audio_path.write_bytes(b"audio-v1")
    image_path.write_bytes(b"slide")
    output_path.parent.mkdir()
    output_path.write_bytes(b"accepted clip")
    scene = Scene(
        scene_id=0, key_concept="A clear educational concept",
        narration="This narration explains the concept in enough detail for a lesson.",
        visual_query="A simple educational concept", on_screen_text="Concept",
        estimated_seconds=8, visual_type="pillow",
    )
    storyboard = Storyboard(title="Resume", scenes=[scene])
    spec = VisualSpec(
        scene_id=0, topic=scene.key_concept, visual_goal=scene.visual_query,
        visual_type="pillow", duration_seconds=8, width=1280, height=720, fps=25,
    )
    media = MediaInfo(duration_seconds=8, width=1280, height=720, fps=25,
                      codec="h264", pixel_format="yuv420p")
    accepted = AcceptanceResult(
        verdict=Verdict.ACCEPTED, decision=Decision.ACCEPT,
        reason_codes=[], evidence=["accepted clip"], retryable=False,
        attempt=1, elapsed_seconds=0,
    )
    cached = VisualArtifact(
        scene_id=0, artifact_id="seg_0", requested_strategy="pillow",
        actual_strategy="pillow", status="accepted", output_path="image_videos/seg_0.mp4",
        media=media, sha256=file_sha256(output_path), attempt_count=1,
        attempts=[accepted], cache_key=visual_cache_key(
            scene=scene, audio_path=audio_path, image_path=image_path, strategy="pillow",
        ),
        validation=VisualValidation(media="passed", semantic="passed", acceptance=accepted),
    )
    save_visual_manifest(tmp_path, VisualManifest(scenes=[cached]))
    monkeypatch.setattr(visual_routing, "route_storyboard", lambda _storyboard: None)
    monkeypatch.setattr(renderer, "probe_visual_video", lambda _path: media)
    conversions = []

    def convert(run_dir, *, chunk_ids, preserved_chunk_ids):
        conversions.append(tuple(chunk_ids))
        (Path(run_dir) / "image_videos" / f"{chunk_ids[0]}.mp4").write_bytes(b"rerendered clip")

    monkeypatch.setattr(slides, "create_image_videos", convert)
    paths = renderer.render_all_visual_scenes(
        str(tmp_path), storyboard=storyboard, visual_specs=[spec.model_dump()],
    )
    assert [Path(path) for path in paths] == [output_path]
    assert conversions == []
    assert load_visual_manifest(tmp_path).scenes[0].cache_status == "hit"

    audio_path.write_bytes(b"audio-v2")
    paths = renderer.render_all_visual_scenes(
        str(tmp_path), storyboard=storyboard, visual_specs=[spec.model_dump()],
    )
    assert [Path(path) for path in paths] == [output_path]
    assert conversions == [("seg_0",)]
    refreshed = load_visual_manifest(tmp_path).scenes[0]
    assert refreshed.cache_status == "miss"
    assert refreshed.status == "accepted"


def test_pipeline_resume_at_stitching_revalidates_visuals_without_repeating_audio_or_avatar(tmp_path, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock

    from functions import video_main_function as pipeline
    from functions.storyboard_schema import Scene, Storyboard

    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    storyboard = Storyboard(title="Resumed lesson", scenes=[
        Scene(scene_id=0, key_concept="A concise lesson concept",
              narration="The saved narration explains this lesson concept clearly.",
              visual_query="A clear illustration of the lesson concept",
              on_screen_text="The concept", estimated_seconds=8),
    ])
    (artifact_dir / "storyboard.json").write_text(storyboard.model_dump_json(), encoding="utf-8")
    (artifact_dir / "script.json").write_text(
        '{"topic":"Resumed lesson","script":"saved script"}', encoding="utf-8",
    )
    monkeypatch.setattr(pipeline, "get_run_dir", lambda _run_id: str(tmp_path))
    visual_calls = []
    monkeypatch.setattr(
        pipeline, "run_visual_pipeline",
        lambda run_dir, *, storyboard: visual_calls.append((run_dir, [s.scene_id for s in storyboard.scenes])),
    )
    monkeypatch.setattr(pipeline, "combine_videos", AsyncMock(return_value="resumed-file"))
    stage_updates = []
    monkeypatch.setattr(
        pipeline, "update_stage_status",
        lambda _run_id, stage, status, **kwargs: stage_updates.append((stage, status)),
    )
    monkeypatch.setattr(pipeline, "append_event_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "release_lock", lambda _run_id: None)

    result = asyncio.run(pipeline.video_main(
        topic_name="Resumed lesson", level_of_explanation="Intermediate", age="18",
        creativity_level="High", humour_level="Medium", character_name="Benjamin",
        run_id="resume-run", start_stage="stitching",
    ))

    assert result == "resumed-file"
    assert visual_calls == [(str(tmp_path), [0])]
    assert not any(stage in {"audio_tts", "scrapling_images", "sadtalker"} for stage, _ in stage_updates)
    assert ("stitching", "RUNNING") in stage_updates
    assert ("stitching", "COMPLETED") in stage_updates
    assert ("validation", "COMPLETED") in stage_updates
