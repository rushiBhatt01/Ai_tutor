"""Versioned visual artifacts and compatibility with existing seg_N files."""

import hashlib
import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from functions.visual.visual_acceptance import AcceptanceResult, Verdict


MANIFEST_PATH = Path("artifacts/visual_manifest.json")
Strategy = Literal["manim", "web_image", "pillow", "hybrid_image", "hybrid_gif"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class MediaInfo(ContractModel):
    duration_seconds: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: float = Field(gt=0)
    codec: str
    pixel_format: str


class VisualValidation(ContractModel):
    media: Literal["not_checked", "passed", "failed"] = "not_checked"
    semantic: Literal["not_checked", "passed", "failed", "uncertain"] = "not_checked"
    evaluator_version: str = "media-v1"
    evidence: list[str] = Field(default_factory=list)
    acceptance: Optional[AcceptanceResult] = None


class ImageSource(ContractModel):
    source_url: str
    asset_url: str
    creator: Optional[str] = None
    license_id: Optional[str] = None
    license_url: Optional[str] = None
    attribution: Optional[str] = None
    retrieved_at: Optional[str] = None
    semantic_score: Optional[float] = None
    quality_score: Optional[float] = None
    required_feature_scores: dict[str, float] = Field(default_factory=dict)
    excluded_feature_scores: dict[str, float] = Field(default_factory=dict)


class VisualSpecSummary(ContractModel):
    """Validated specification snapshot attached to its scene artifact."""
    schema_version: Literal[1] = 1
    scene_id: int = Field(ge=0)
    topic: str
    visual_goal: str
    visual_type: Strategy
    duration_seconds: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: int = Field(gt=0)
    input_data: dict = Field(default_factory=dict)
    trace: list[dict] = Field(default_factory=list)
    must_show: list[str] = Field(default_factory=list)
    must_not_show: list[str] = Field(default_factory=list)


class VisualArtifact(ContractModel):
    scene_id: int = Field(ge=0)
    artifact_id: str
    requested_strategy: Strategy
    actual_strategy: Optional[Strategy] = None
    status: Literal["pending", "rendered", "accepted", "failed"] = "pending"
    media_type: Literal["video/mp4"] = "video/mp4"
    output_path: Optional[str] = None
    media: Optional[MediaInfo] = None
    attempt_count: int = Field(default=0, ge=0)
    attempts: list[AcceptanceResult] = Field(default_factory=list)
    fallback_reason: Optional[str] = None
    routing_rationale: Optional[str] = None
    trace_events: list[dict] = Field(default_factory=list)
    validation: VisualValidation = Field(default_factory=VisualValidation)
    source: Optional[ImageSource] = None
    spec: Optional[VisualSpecSummary] = None
    sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    cache_key: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    cache_status: Literal["not_checked", "miss", "hit"] = "not_checked"
    elapsed_seconds: Optional[float] = Field(default=None, ge=0)
    error: Optional[str] = None

    @model_validator(mode="after")
    def consistent_result(self):
        if self.artifact_id != f"seg_{self.scene_id}":
            raise ValueError("artifact_id must preserve seg_{scene_id}")
        if self.spec is not None:
            if self.spec.scene_id != self.scene_id:
                raise ValueError("Artifact specification must match its scene ID")
            if self.spec.visual_type != self.requested_strategy:
                raise ValueError("Artifact specification must match its requested strategy")
        if self.output_path is not None and self.output_path != f"image_videos/{self.artifact_id}.mp4":
            raise ValueError("output_path must use the existing scene video location")
        if self.status in ("rendered", "accepted"):
            if not all((self.output_path, self.media, self.actual_strategy, self.sha256)):
                raise ValueError("Completed visual artifacts require output and media evidence")
            if self.validation.media != "passed" or self.validation.semantic == "failed":
                raise ValueError("Rejected visuals cannot be completed artifacts")
            if self.status == "accepted" and self.validation.semantic != "passed":
                raise ValueError("Acceptance requires semantic validation")
        if self.status == "accepted" and self.validation.acceptance is not None:
            if self.validation.acceptance.verdict != Verdict.ACCEPTED:
                raise ValueError("Accepted artifacts require an accepted common validation result")
        if self.status == "rendered" and self.validation.acceptance is not None:
            if self.validation.acceptance.verdict != Verdict.ACCEPTED:
                raise ValueError("Rejected or uncertain artifacts cannot be marked rendered")
        if self.attempts and self.attempt_count < len(self.attempts):
            raise ValueError("attempt_count cannot be less than recorded attempts")
        return self


class VisualManifest(ContractModel):
    schema_version: Literal[1] = 1
    scenes: list[VisualArtifact]

    @model_validator(mode="after")
    def unique_ordered_scenes(self):
        ids = [scene.scene_id for scene in self.scenes]
        if not ids or ids != sorted(set(ids)):
            raise ValueError("Manifest requires unique scenes in numeric order")
        return self


@contextmanager
def atomic_output(destination):
    """Keep incomplete writes outside directories scanned for final artifacts."""
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".visual-", dir=target.parent) as directory:
        temporary = Path(directory) / target.name
        yield str(temporary)
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise ValueError(f"No output produced for {target.name}")
        os.replace(temporary, target)


def save_visual_manifest(run_dir, manifest: VisualManifest):
    # Revalidate mutable records before committing the whole document.
    validated = VisualManifest.model_validate(manifest.model_dump())
    with atomic_output(Path(run_dir) / MANIFEST_PATH) as temporary:
        Path(temporary).write_text(validated.model_dump_json(indent=2), encoding="utf-8")


def load_visual_manifest(run_dir) -> Optional[VisualManifest]:
    path = Path(run_dir) / MANIFEST_PATH
    if not path.exists():
        return None
    return VisualManifest.model_validate_json(path.read_text(encoding="utf-8"))


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def visual_scene_fingerprint(scene) -> str:
    """Hash the storyboard fields that determine a scene's visual content."""
    fields = (
        "scene_id", "key_concept", "learning_objective", "narration",
        "visual_query", "on_screen_text", "visual_type", "manim_spec",
        "must_show", "must_not_show",
    )
    if isinstance(scene, dict):
        content = {name: scene.get(name) for name in fields}
    else:
        content = {name: getattr(scene, name, None) for name in fields}
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def visual_cache_key(*, scene, audio_path, image_path=None, image_identity=None, strategy=None,
                     renderer_version="visual-renderer-v2", evaluator_version="visual-acceptance-v3") -> Optional[str]:
    """Fingerprint all scene inputs and renderer/evaluator versions that affect reuse."""
    audio = Path(audio_path)
    if not audio.is_file():
        return None
    image = Path(image_path) if image_path else None
    if hasattr(scene, "model_dump"):
        scene_payload = scene.model_dump(mode="json")
    elif isinstance(scene, dict):
        scene_payload = scene
    elif hasattr(scene, "__dict__"):
        scene_payload = vars(scene)
    else:
        scene_payload = scene
    payload = {
        "scene": scene_payload,
        "strategy": strategy,
        "renderer_version": renderer_version,
        "evaluator_version": evaluator_version,
        "settings": {"width": 1280, "height": 720, "fps": 25, "codec": "h264", "pixel_format": "yuv420p"},
        "audio_sha256": file_sha256(audio),
        "image_sha256": file_sha256(image) if image and image.is_file() else None,
        "image_identity": image_identity,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def probe_visual_video(path) -> MediaInfo:
    """Check the encoded media contract; this does not check visual semantics."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name,pix_fmt,width,height,avg_frame_rate,duration:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True, timeout=10,
    )
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    duration = stream.get("duration")
    if duration in (None, "N/A"):
        duration = data.get("format", {}).get("duration")
    media = MediaInfo(
        duration_seconds=float(duration), width=stream["width"], height=stream["height"],
        fps=float(Fraction(stream["avg_frame_rate"])), codec=stream["codec_name"],
        pixel_format=stream["pix_fmt"],
    )
    if (media.width, media.height, media.codec, media.pixel_format) != (1280, 720, "h264", "yuv420p") or abs(media.fps - 25) > 0.001:
        raise ValueError("Visual clip must be 1280x720 H.264/yuv420p at 25 FPS")
    return media


def manifest_video_paths(run_dir, expected_ids=None) -> Optional[list[str]]:
    """Guard composition/resume when a manifest exists; allow legacy runs."""
    manifest = load_visual_manifest(run_dir)
    if manifest is None:
        return None
    ids = {scene.artifact_id for scene in manifest.scenes}
    if expected_ids is not None and ids != set(expected_ids):
        raise ValueError("Visual manifest scene IDs do not match pipeline inputs")
    paths = []
    root = Path(run_dir).resolve()
    for scene in manifest.scenes:
        if scene.status not in ("rendered", "accepted"):
            raise ValueError(f"Visual artifact {scene.artifact_id} is {scene.status}")
        path = (root / scene.output_path).resolve()
        if not path.is_relative_to(root) or not path.is_file() or file_sha256(path) != scene.sha256:
            raise ValueError(f"Visual artifact {scene.artifact_id} is missing or changed")
        if probe_visual_video(path) != scene.media:
            raise ValueError(f"Visual artifact {scene.artifact_id} media metadata changed")
        paths.append(str(path))
    return paths
