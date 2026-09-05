import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

RUNS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../runs"))

PIPELINE_STAGES = [
    "script",
    "audio_tts",
    "scrapling_images",
    "sadtalker",
    "stitching",
    "validation"
]

def get_run_dir(run_id: str) -> str:
    return os.path.join(RUNS_DIR, run_id)

def get_checkpoint_path(run_id: str) -> str:
    return os.path.join(get_run_dir(run_id), "checkpoint.json")

def init_run(topic: str, custom_run_id: Optional[str] = None) -> str:
    """Initialize a new run directory and checkpoint file."""
    run_id = custom_run_id or f"run_{uuid.uuid4().hex[:12]}"
    run_dir = get_run_dir(run_id)
    
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(os.path.join(run_dir, "audio"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "images"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "video"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "video_temp"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "image_videos"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "artifacts"), exist_ok=True)

    now = datetime.now().isoformat()
    checkpoint = {
        "run_id": run_id,
        "pipeline_version": "2.1.0",
        "created_at": now,
        "updated_at": now,
        "topic": topic,
        "current_stage": "script",
        "overall_status": "RUNNING",
        "resumability_status": "RUNNING",
        "execution_lock": True,
        "retry_count": 0,
        "error_summary": None,
        "stages": {
            stage: {"status": "PENDING", "attempts": 0, "chunks": {}}
            for stage in PIPELINE_STAGES
        }
    }

    save_checkpoint(run_id, checkpoint)
    return run_id

def load_checkpoint(run_id: str) -> Optional[Dict[str, Any]]:
    cp_path = get_checkpoint_path(run_id)
    if not os.path.exists(cp_path):
        return None
    try:
        with open(cp_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading checkpoint for {run_id}: {e}")
        return None

def save_checkpoint(run_id: str, data: Dict[str, Any]) -> bool:
    cp_path = get_checkpoint_path(run_id)
    tmp_path = cp_path + ".tmp"
    try:
        data["updated_at"] = datetime.now().isoformat()
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, cp_path)
        return True
    except Exception as e:
        print(f"Error saving checkpoint for {run_id}: {e}")
        return False

def acquire_lock(run_id: str) -> bool:
    cp = load_checkpoint(run_id)
    if not cp:
        return False
    if cp.get("execution_lock", False):
        return False
    cp["execution_lock"] = True
    save_checkpoint(run_id, cp)
    return True

def release_lock(run_id: str) -> bool:
    cp = load_checkpoint(run_id)
    if not cp:
        return False
    cp["execution_lock"] = False
    save_checkpoint(run_id, cp)
    return True

def update_stage_status(
    run_id: str,
    stage: str,
    status: str,
    error: Optional[str] = None,
    chunk_id: Optional[str] = None
):
    cp = load_checkpoint(run_id)
    if not cp:
        return
    
    stage_info = cp["stages"].setdefault(stage, {"status": "PENDING", "attempts": 0, "chunks": {}})
    
    if chunk_id:
        chunks = stage_info.setdefault("chunks", {})
        chunk_data = chunks.setdefault(chunk_id, {"status": "PENDING", "attempts": 0})
        chunk_data["status"] = status
        if error:
            chunk_data["error"] = error
        if status == "RUNNING":
            chunk_data["attempts"] = chunk_data.get("attempts", 0) + 1
    else:
        stage_info["status"] = status
        if status == "RUNNING":
            stage_info["started_at"] = datetime.now().isoformat()
            stage_info["attempts"] = stage_info.get("attempts", 0) + 1
            cp["current_stage"] = stage
        elif status in ["COMPLETED", "FAILED", "INVALID"]:
            stage_info["completed_at"] = datetime.now().isoformat()
            if error:
                stage_info["error"] = error
                cp["error_summary"] = {
                    "stage": stage,
                    "message": error,
                    "timestamp": datetime.now().isoformat()
                }

    if status == "FAILED":
        cp["overall_status"] = "FAILED"
        cp["resumability_status"] = "RESUMABLE"
        cp["execution_lock"] = False

    save_checkpoint(run_id, cp)

def append_event_log(run_id: str, stage: str, level: str, message: str, progress: Optional[int] = None, chunk_id: Optional[str] = None):
    run_dir = get_run_dir(run_id)
    log_file = os.path.join(run_dir, "logs", "events.jsonl")
    event = {
        "run_id": run_id,
        "stage": stage,
        "chunk_id": chunk_id,
        "level": level,
        "message": message,
        "progress": progress,
        "timestamp": datetime.now().isoformat()
    }
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        print(f"Error appending log for {run_id}: {e}")
