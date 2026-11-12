"""Single-host durable CPU worker. Start with python -m cpu_worker.

No cloud resources are provisioned here. OCI artifact access is opt-in only.
"""

import asyncio
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import ctypes
from contextlib import contextmanager
from pathlib import Path

from deployment_settings import RuntimeSettings
from job_store import JobStore


@contextmanager
def exclusive_worker(directory):
    # Single-host POSIX deployment; never share this queue across network mounts.
    import fcntl
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / "worker.lock", "a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another CPU worker already owns this queue") from None
        yield


def directory_bytes(root):
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file() and not p.is_symlink())


def stop_process(proc):
    # Manim starts its own process sessions. Enumerate descendants too: killing
    # only the initial process group would leave those renderers alive. Linux
    # subreaper mode reparents orphan grandchildren to this supervisor.
    parents = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "status").read_text().splitlines()
            parents[int(entry.name)] = int(next(line.split()[1] for line in fields if line.startswith("PPid:")))
        except (OSError, StopIteration, ValueError):
            continue
    descendants = {os.getpid()}
    while True:
        extended = descendants | {pid for pid, parent in parents.items() if parent in descendants}
        if extended == descendants:
            break
        descendants = extended
    descendants.discard(os.getpid())
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in descendants:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        if sig == signal.SIGTERM:
            time.sleep(2)
    proc.wait(timeout=5)
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
        except ChildProcessError:
            break


def run_child(job_id):
    """Executed in a separate process so render timeouts can kill the tree."""
    settings = RuntimeSettings().validate()
    store = JobStore(settings.state_dir, settings.capacity)
    job = store.get(job_id)
    from functions.checkpoint_manager import init_run, load_checkpoint, get_run_dir, release_lock
    from functions.video_main_function import video_main
    payload = json.loads(job["payload"])
    if not load_checkpoint(job_id):
        init_run(payload["message"], custom_run_id=job_id)
    release_lock(job_id)
    run_dir = Path(get_run_dir(job_id))
    final = run_dir / "final_video.mp4"
    checkpoint = load_checkpoint(job_id)
    if not (final.is_file() and checkpoint.get("stages", {}).get("validation", {}).get("status") == "COMPLETED"):
        result = asyncio.run(video_main(payload["message"], payload["level"], str(payload["age"]),
            str(payload["creative"]), str(payload["humour"]), payload["characterName"],
            pipeline_delay_ms=0, run_id=job_id, force_cpu=True))
        if not isinstance(result, str) or not result.startswith("local:"):
            raise RuntimeError("Worker expected a local final artifact")
    # Validate the final container/audio/video before publishing it.
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(final)],
                           capture_output=True, text=True, check=True, timeout=30)
    media = json.loads(probe.stdout)
    if not {"video", "audio"}.issubset({s["codec_type"] for s in media["streams"]}) or float(media["format"]["duration"]) <= 0:
        raise RuntimeError("Final video validation failed")
    result = publish_job(job_id)
    receipt = settings.state_dir / f"{job_id}.result.json"
    temp = receipt.with_suffix(".tmp")
    temp.write_text(json.dumps(result), encoding="utf-8")
    os.replace(temp, receipt)


def publish_job(job_id):
    from artifact_storage import get_artifact_storage
    from functions.checkpoint_manager import get_run_dir
    storage = get_artifact_storage()
    run_dir = Path(get_run_dir(job_id)).resolve()
    prefix = os.getenv("ARTIFACT_PREFIX", "ai-tutor").strip("/") + f"/jobs/{job_id}"
    manifest = {"schema_version": 1, "job_id": job_id, "artifacts": []}
    # Retain intermediate assets and checkpoint state; exclude disposable render
    # cache/temp trees and any symlink. Cleanup is a separate explicit operation.
    for file in sorted(run_dir.rglob("*")):
        if not file.is_file() or file.is_symlink() or not file.resolve().is_relative_to(run_dir):
            continue
        relative = file.relative_to(run_dir)
        if any(part in {"video_temp", "media", "Tex", "partial_movie_files"} for part in relative.parts) or file.name.startswith("temp_"):
            continue
        key = f"{prefix}/{relative.as_posix()}"
        storage.upload_file(str(file), key)
        digest = hashlib.sha256()
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        manifest["artifacts"].append({"key": key, "size": file.stat().st_size, "sha256": digest.hexdigest()})
    manifest_path = run_dir / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    storage.upload_file(str(manifest_path), f"{prefix}/manifest.json")
    return {"video_key": f"{prefix}/final_video.mp4", "manifest_key": f"{prefix}/manifest.json"}


def main():
    if not sys.platform.startswith("linux"):
        raise RuntimeError("The deployment CPU supervisor requires Linux process limits")
    if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise RuntimeError("Cannot enable child-process recovery")
    settings = RuntimeSettings().validate()
    store = JobStore(settings.state_dir, settings.capacity)
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    runs = Path(os.getenv("RUNS_DIR", str(Path(__file__).parent / "runs")))
    runs.mkdir(parents=True, exist_ok=True)
    stopping = False

    def request_stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    with exclusive_worker(settings.state_dir):
        store.recover(settings.max_attempts)
        while not stopping:
            (settings.state_dir / "worker.heartbeat").touch()
            max_bytes = int(os.getenv("TEMP_MAX_MB", "4096")) * 1024 * 1024
            if directory_bytes(runs) >= max_bytes or shutil.disk_usage(runs).free < 1024 * 1024 * 1024:
                time.sleep(2)
                continue  # Leave queued work durable; do not allocate more disk.
            job = store.claim()
            if not job:
                time.sleep(1)
                continue
            env = {**os.environ, "PIPELINE_JOB_MODE": "true", "CPU_ONLY": "true", "CUDA_VISIBLE_DEVICES": ""}
            proc = subprocess.Popen([sys.executable, "-m", "cpu_worker", "--job", job["id"]],
                env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            started, error = time.monotonic(), None
            try:
                while proc.poll() is None:
                    (settings.state_dir / "worker.heartbeat").touch()
                    if stopping:
                        error = "worker_interrupted"
                        break
                    if time.monotonic() - started > settings.job_timeout:
                        error = "job_timeout"
                        break
                    if directory_bytes(runs) > max_bytes:
                        error = "temporary_disk_limit"
                        break
                    time.sleep(1)
                if error:
                    stop_process(proc)
                elif proc.returncode:
                    error = "pipeline_failed"
                    stop_process(proc)
                if error:
                    store.finish(job["id"], error=error)
                else:
                    receipt = settings.state_dir / f"{job['id']}.result.json"
                    result = json.loads(receipt.read_text(encoding="utf-8"))
                    store.finish(job["id"], result=result)
            except Exception:
                stop_process(proc)
                store.finish(job["id"], error="artifact_or_worker_failure")
            if stopping:
                # Safe to retry only after the complete child tree has exited.
                store.retry(job["id"], settings.max_attempts)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--job":
        run_child(sys.argv[2])
    else:
        main()
