"""No network/provider calls. Exercise queue bounds/recovery and private storage."""

import json
import sys
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from artifact_storage import LocalArtifactStorage, OCIArtifactStorage, checked_key
from deployment_settings import RuntimeSettings, redact_secrets
from job_store import IdempotencyConflict, JobStore, QueueFull


def test_queue_is_bounded_under_concurrent_submission_and_survives_reopen(tmp_path):
    store = JobStore(tmp_path, capacity=3)
    def submit(number):
        try:
            return store.submit({"topic": number})["id"]
        except QueueFull:
            return None
    with ThreadPoolExecutor(max_workers=8) as executor:
        ids = [job for job in executor.map(submit, range(15)) if job]
    assert len(ids) == 3
    reopened = JobStore(tmp_path, capacity=3)
    assert all(reopened.get(job)["status"] == "QUEUED" for job in ids)
    first = reopened.claim()
    assert reopened.claim() is None  # One active heavy job even with two callers.
    reopened.finish(first["id"], {"video_key": "test/final.mp4"})
    assert reopened.claim() is not None


def test_idempotency_and_interrupted_worker_attempt_budget(tmp_path):
    queue = JobStore(tmp_path, 1)
    job = queue.submit({"topic": "BFS"}, "request-1")
    assert queue.submit({"topic": "BFS"}, "request-1")["id"] == job["id"]
    with pytest.raises(IdempotencyConflict):
        queue.submit({"topic": "DFS"}, "request-1")
    queue.claim()
    queue.recover(2)
    assert queue.get(job["id"])["status"] == "QUEUED"
    assert queue.claim()["attempts"] == 2
    queue.recover(2)
    assert queue.get(job["id"])["status"] == "FAILED"
    assert not queue.retry(job["id"], 2)


def test_queue_backup_contains_committed_state(tmp_path):
    queue = JobStore(tmp_path / "state")
    job = queue.submit({"topic": "BFS"})
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    queue.backup(backup_dir / "jobs.sqlite3")
    assert JobStore(backup_dir).get(job["id"])["status"] == "QUEUED"


@pytest.mark.parametrize("key", ["../key", "/key", "a/../../b", "a\\b", "a//b", "a/./b", ""])
def test_storage_rejects_path_escape(key):
    with pytest.raises(ValueError):
        checked_key(key)


def test_local_artifact_roundtrip_and_failed_upload_preserves_existing(tmp_path):
    storage = LocalArtifactStorage(tmp_path / "assets")
    source = tmp_path / "input"
    source.write_bytes(b"video")
    storage.upload_file(source, "jobs/abc/final/video.mp4")
    destination = tmp_path / "output"
    storage.download_file("jobs/abc/final/video.mp4", destination)
    assert destination.read_bytes() == b"video"
    with pytest.raises(FileNotFoundError):
        storage.upload_file(tmp_path / "missing", "jobs/abc/final/video.mp4")
    assert storage.path("jobs/abc/final/video.mp4").read_bytes() == b"video"
    storage.delete_file("jobs/abc/final/video.mp4")
    assert not storage.path("jobs/abc/final/video.mp4").exists()


def test_oci_adapter_does_not_make_bucket_public_or_create_resources(tmp_path):
    client = Mock()
    storage = OCIArtifactStorage(client, "namespace", "private-bucket")
    source = tmp_path / "input"
    source.write_bytes(b"video")
    assert storage.upload_file(source, "jobs/abc/video.mp4").startswith("oci://")
    client.put_object.assert_called_once()
    client.get_object.return_value.data.raw.stream.return_value = [b"vid", b"eo"]
    storage.download_file("jobs/abc/video.mp4", tmp_path / "output")
    assert (tmp_path / "output").read_bytes() == b"video"
    storage.delete_file("jobs/abc/video.mp4")
    assert {call[0] for call in client.mock_calls} <= {"put_object", "get_object", "get_object().data.raw.stream", "get_object().data.close", "delete_object"}


def test_production_rejects_unsafe_defaults_and_secret_errors_do_not_disclose_values(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    for name in ("API_USERNAME", "API_PASSWORD", "MONGO_URI", "CEREBRAS_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="Missing production settings"):
        RuntimeSettings().validate()
    monkeypatch.setenv("API_PASSWORD", "private-value-that-must-never-be-logged")
    assert "private-value" not in redact_secrets("failed with private-value-that-must-never-be-logged")
    assert "private-value" not in repr(RuntimeSettings())


def test_local_mode_cannot_enable_oci_without_explicit_approval(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("ARTIFACT_BACKEND", "oci")
    monkeypatch.setenv("OCI_STORAGE_APPROVED", "false")
    with pytest.raises(ValueError, match="OCI storage requires explicit"):
        RuntimeSettings().validate()


def test_api_queue_status_and_video_contract_without_pipeline_import(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from jobs_api import router, store
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ARTIFACT_BACKEND", "local")
    monkeypatch.setenv("JOB_QUEUE_CAPACITY", "1")
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    payload = {"message": "BFS"}
    first = client.post("/api/jobs", json=payload, headers={"Idempotency-Key": "same"})
    assert first.status_code == 202
    job_id = first.json()["job_id"]
    assert client.post("/api/jobs", json=payload, headers={"Idempotency-Key": "same"}).json()["job_id"] == job_id
    assert client.post("/api/jobs", json={"message": "DFS"}).status_code == 429
    assert client.get(f"/api/jobs/{job_id}/video").status_code == 404
    storage = LocalArtifactStorage(tmp_path / "artifacts")
    storage.path("final.mp4").write_bytes(b"video")
    store().claim()
    store().finish(job_id, {"video_key": "final.mp4"})
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "COMPLETED"
    assert client.get(f"/api/jobs/{job_id}/video").content == b"video"
    assert client.post("/api/jobs", json={"message": "x", "characterName": "../bad"}).status_code == 422


def test_production_app_boundary_without_provider_or_database_calls(tmp_path):
    script = '''
import sys
from fastapi.testclient import TestClient
import main
assert "torch" not in sys.modules
assert main.app.openapi_url is None
client = TestClient(main.app)
assert client.get("/healthz").status_code == 200
assert client.get("/api/jobs/nope").status_code == 401
assert client.get("/api/dev/modules/script/test").status_code == 404
auth = ("test-operator", "test-password-long-enough-for-production")
assert client.get("/docs", auth=auth).status_code == 404
created = client.post("/api/jobs", json={"message": "BFS"}, auth=auth)
assert created.status_code == 202
assert client.get("/api/jobs/" + created.json()["job_id"], auth=auth).json()["status"] == "QUEUED"
assert "torch" not in sys.modules
'''
    env = {**os.environ, "ENVIRONMENT": "production", "API_USERNAME": "test-operator",
        "API_PASSWORD": "test-password-long-enough-for-production", "MONGO_URI": "mongodb://unused/video_tutorials",
        "CEREBRAS_API_KEY": "test-only-no-network", "JOB_QUEUE_ENABLED": "true", "ARTIFACT_BACKEND": "local",
        "STATE_DIR": str(tmp_path / "state"), "ARTIFACT_DIR": str(tmp_path / "artifacts"), "CUDA_VISIBLE_DEVICES": ""}
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1] / "backend",
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
