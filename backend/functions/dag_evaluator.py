import os
import wave
import json
import subprocess
from PIL import Image
from typing import Dict, Any, Tuple, Optional
from functions.checkpoint_manager import load_checkpoint, save_checkpoint, get_run_dir, PIPELINE_STAGES

MIN_AUDIO_BYTES = 1000
MIN_IMAGE_BYTES = 6000
MIN_VIDEO_BYTES = 50000

def validate_audio_file(filepath: str) -> bool:
    if not os.path.isfile(filepath) or os.path.getsize(filepath) < MIN_AUDIO_BYTES:
        return False
    try:
        with wave.open(filepath, 'rb') as w:
            if w.getnframes() <= 0:
                return False
        return True
    except Exception:
        return False

def validate_image_file(filepath: str) -> bool:
    if not os.path.isfile(filepath) or os.path.getsize(filepath) < MIN_IMAGE_BYTES:
        return False
    try:
        with Image.open(filepath) as img:
            img.verify()
        return True
    except Exception:
        return False

def validate_video_file(filepath: str) -> bool:
    if not os.path.isfile(filepath) or os.path.getsize(filepath) < MIN_VIDEO_BYTES:
        return False
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height",
            "-of", "json",
            filepath
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            return False
        data = json.loads(res.stdout)
        return len(data.get("streams", [])) > 0
    except Exception:
        return False

def evaluate_run_dag(run_id: str) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Scans runs/{run_id} artifacts, verifies container integrity,
    applies cascading invalidation to downstream nodes,
    and returns (earliest_start_stage, integrity_report).
    """
    cp = load_checkpoint(run_id)
    if not cp:
        return None, {"error": f"Run {run_id} not found"}

    run_dir = get_run_dir(run_id)
    stages = cp.get("stages", {})
    report = {"run_id": run_id, "stage_checks": {}, "cascading_invalidation": False}

    first_invalid_or_incomplete: Optional[str] = None
    cascading_triggered = False

    for stage_name in PIPELINE_STAGES:
        stage_info = stages.get(stage_name, {"status": "PENDING"})
        current_status = stage_info.get("status", "PENDING")

        # If an earlier stage was invalidated, cascade invalidation downstream
        if cascading_triggered:
            stage_info["status"] = "INVALID"
            report["stage_checks"][stage_name] = {"valid": False, "reason": "Cascading invalidation from upstream failure"}
            if not first_invalid_or_incomplete:
                first_invalid_or_incomplete = stage_name
            continue

        if current_status == "PENDING":
            if not first_invalid_or_incomplete:
                first_invalid_or_incomplete = stage_name
            report["stage_checks"][stage_name] = {"valid": False, "reason": "Pending execution"}
            continue

        if current_status == "FAILED":
            if not first_invalid_or_incomplete:
                first_invalid_or_incomplete = stage_name
            cascading_triggered = True
            report["stage_checks"][stage_name] = {"valid": False, "reason": "Previous execution failed"}
            continue

        # For COMPLETED stages, perform physical container integrity verification
        stage_valid = True
        reason = "Artifact integrity valid"

        if stage_name == "script":
            script_file = os.path.join(run_dir, "artifacts", "script.json")
            if not os.path.isfile(script_file) or os.path.getsize(script_file) < 20:
                stage_valid = False
                reason = "Script artifact missing or empty"

        elif stage_name == "audio_tts":
            audio_dir = os.path.join(run_dir, "audio")
            chunks = [f for f in os.listdir(audio_dir) if f.endswith(".wav")] if os.path.exists(audio_dir) else []
            if not chunks:
                stage_valid = False
                reason = "No audio chunk files found"
            else:
                for cfile in chunks:
                    if not validate_audio_file(os.path.join(audio_dir, cfile)):
                        stage_valid = False
                        reason = f"Corrupt or missing audio file {cfile}"
                        break

        elif stage_name == "scrapling_images":
            img_dir = os.path.join(run_dir, "images")
            images = [f for f in os.listdir(img_dir) if f.endswith((".jpg", ".jpeg", ".png"))] if os.path.exists(img_dir) else []
            if not images:
                stage_valid = False
                reason = "No slide image files found"
            else:
                for ifile in images:
                    if not validate_image_file(os.path.join(img_dir, ifile)):
                        stage_valid = False
                        reason = f"Corrupt or unreadable image file {ifile}"
                        break

        elif stage_name == "sadtalker":
            video_dir = os.path.join(run_dir, "video")
            videos = [f for f in os.listdir(video_dir) if f.endswith(".mp4")] if os.path.exists(video_dir) else []
            if not videos:
                stage_valid = False
                reason = "No SadTalker avatar clips found"
            else:
                for vfile in videos:
                    if not validate_video_file(os.path.join(video_dir, vfile)):
                        stage_valid = False
                        reason = f"Corrupt SadTalker video clip {vfile}"
                        break

        elif stage_name == "stitching":
            slide_video_dir = os.path.join(run_dir, "image_videos")
            svideos = [f for f in os.listdir(slide_video_dir) if f.endswith(".mp4")] if os.path.exists(slide_video_dir) else []
            if not svideos:
                stage_valid = False
                reason = "No slide video clips found"
            else:
                for sv in svideos:
                    if not validate_video_file(os.path.join(slide_video_dir, sv)):
                        stage_valid = False
                        reason = f"Corrupt slide video clip {sv}"
                        break

        elif stage_name == "validation":
            final_mp4 = os.path.join(run_dir, "final_video.mp4")
            if not validate_video_file(final_mp4):
                stage_valid = False
                reason = "Final video MP4 missing or corrupt"

        if not stage_valid:
            stage_info["status"] = "INVALID"
            cascading_triggered = True
            report["cascading_invalidation"] = True
            if not first_invalid_or_incomplete:
                first_invalid_or_incomplete = stage_name

        report["stage_checks"][stage_name] = {"valid": stage_valid, "reason": reason}

    # Save updated DAG status to checkpoint
    save_checkpoint(run_id, cp)

    return first_invalid_or_incomplete or "COMPLETED", report
