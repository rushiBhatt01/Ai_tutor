"""Fast API endpoints; expensive generation runs only in the CPU worker."""

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask

from artifact_storage import get_artifact_storage
from deployment_settings import RuntimeSettings
from job_store import IdempotencyConflict, JobStore, QueueFull

router = APIRouter(prefix="/api/jobs")


class LessonRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str = Field(min_length=1, max_length=300)
    level: str = Field(default="beginner", max_length=50)
    age: int = Field(default=18, ge=1, le=120)
    creative: int = Field(default=5, ge=0, le=10)
    humour: int = Field(default=5, ge=0, le=10)
    characterName: str = Field(default="Benjamin", pattern=r"^[A-Za-z0-9_-]{1,40}$")


def store():
    settings = RuntimeSettings().validate()
    return JobStore(settings.state_dir, settings.capacity)


def submit_lesson(data, request_key=None):
    try:
        job = store().submit(LessonRequest.model_validate(data).model_dump(), request_key)
        return {"job_id": job["id"], "status": job["status"], "status_url": f"/api/jobs/{job['id']}"}
    except QueueFull:
        raise HTTPException(429, "Render queue is full; retry later", headers={"Retry-After": "30"})
    except IdempotencyConflict:
        raise HTTPException(409, "Idempotency key already belongs to another request")
    except ValueError:
        raise HTTPException(422, "Invalid lesson request or idempotency key")


@router.post("", status_code=202)
def create_job(data: LessonRequest, idempotency_key: str | None = Header(None)):
    return submit_lesson(data.model_dump(), idempotency_key)


@router.get("/{job_id}")
def job_status(job_id: str):
    job = store().get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {"job_id": job_id, "status": job["status"], "created_at": job["created"],
            "updated_at": job["updated"], "attempts": job["attempts"], "error": job["error"],
            "video_url": f"/api/jobs/{job_id}/video" if job["status"] == "COMPLETED" else None}


@router.post("/{job_id}/retry", status_code=202)
def retry_job(job_id: str):
    try:
        if not store().retry(job_id, RuntimeSettings().max_attempts):
            raise HTTPException(409, "Job cannot be retried or its attempt budget is exhausted")
    except QueueFull:
        raise HTTPException(429, "Render queue is full", headers={"Retry-After": "30"})
    return {"job_id": job_id, "status": "QUEUED"}


@router.get("/{job_id}/video")
def job_video(job_id: str):
    job = store().get(job_id)
    if not job or job["status"] != "COMPLETED":
        raise HTTPException(404, "Completed video not found")
    result = json.loads(job["result"])
    artifact_store = get_artifact_storage()
    # Local files can stream directly. OCI objects remain private and go through
    # this authenticated API; no public bucket or pre-authenticated URL is used.
    from artifact_storage import LocalArtifactStorage
    if isinstance(artifact_store, LocalArtifactStorage):
        return FileResponse(artifact_store.path(result["video_key"]), media_type="video/mp4", filename="lesson.mp4")
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as stream:
        path = Path(stream.name)
    try:
        artifact_store.download_file(result["video_key"], str(path))
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(503, "Artifact storage unavailable")
    return FileResponse(path, media_type="video/mp4", filename="lesson.mp4", background=BackgroundTask(path.unlink, missing_ok=True))
