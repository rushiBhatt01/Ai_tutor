from datetime import datetime
import os
import json
import asyncio
import math
from bson import ObjectId

from functions.create_audio_image_function import create_audio_image
from functions.create_script_function import create_script
from functions.create_video_from_audio_function import create_video_from_audio
from functions.create_image_videos_function import create_image_videos
from functions.combine_videos_function import combine_videos
from functions.checkpoint_manager import (
    init_run, load_checkpoint, update_stage_status, append_event_log,
    release_lock, get_run_dir
)
from functions.dag_evaluator import evaluate_run_dag
from db import get_cached_video
from media_store import upload_file

async def video_main(
    topic_name: str,
    level_of_explanation: str,
    age: str,
    creativity_level: str,
    humour_level: str,
    character_name: str,
    pipeline_delay_ms=None,
    run_id=None,
    start_stage=None,
    force_cpu=False
):
    # Check cache first for standard runs if no explicit run_id is given
    if not run_id:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/topic2explanation/public"))
        prev_videos_path = os.path.join(base_dir, "prev_videos", f"{topic_name}.mp4")
        if os.path.exists(prev_videos_path):
            print(f"Found cached video in prev_videos for topic '{topic_name}': {prev_videos_path}")
            if pipeline_delay_ms is not None:
                try:
                    wait_s = int((int(pipeline_delay_ms) + 999) / 1000)
                except Exception:
                    wait_s = None
                if wait_s and wait_s > 0:
                    await asyncio.sleep(wait_s)
            return f"local:{prev_videos_path}"

    # Initialize or load run checkpoint
    if not run_id:
        run_id = init_run(topic_name)
    
    run_dir = get_run_dir(run_id)
    
    # Evaluate DAG to determine starting stage if resuming
    if start_stage is None:
        eval_stage, report = evaluate_run_dag(run_id)
        start_stage = eval_stage if eval_stage != "COMPLETED" else "script"
        append_event_log(run_id, start_stage, "INFO", f"Evaluated starting stage for run: {start_stage}")

    stages_order = ["script", "audio_tts", "scrapling_images", "wav2lip", "sadtalker", "stitching", "validation"]
    start_index = 0
    for idx, stg in enumerate(stages_order):
        if stg == start_stage or (start_stage == "sadtalker" and stg == "wav2lip"):
            start_index = idx
            break

    script_text = ""
    script_file = os.path.join(run_dir, "artifacts", "script.json")

    try:
        # ── 1. Script Generation Stage ──
        if start_index <= stages_order.index("script"):
            update_stage_status(run_id, "script", "RUNNING")
            append_event_log(run_id, "script", "INFO", f"Generating tutorial script for topic '{topic_name}'", progress=10)
            script_text = create_script(topic_name, level_of_explanation, age, creativity_level, humour_level, character_name)
            
            with open(script_file, "w", encoding="utf-8") as f:
                json.dump({"topic": topic_name, "script": script_text}, f, indent=2)
            
            update_stage_status(run_id, "script", "COMPLETED")
            append_event_log(run_id, "script", "INFO", "Script generation completed", progress=20)
        else:
            if os.path.exists(script_file):
                with open(script_file, "r", encoding="utf-8") as f:
                    script_text = json.load(f).get("script", "")

        # ── 2. Audio TTS & Scrapling Image Scraping Stage ──
        if start_index <= stages_order.index("scrapling_images"):
            update_stage_status(run_id, "audio_tts", "RUNNING")
            update_stage_status(run_id, "scrapling_images", "RUNNING")
            append_event_log(run_id, "audio_tts", "INFO", "Synthesizing Edge-TTS audio & scraping images with Scrapling", progress=35)
            
            create_audio_image(topic_name, script_text, character_name, run_dir)
            
            update_stage_status(run_id, "audio_tts", "COMPLETED")
            update_stage_status(run_id, "scrapling_images", "COMPLETED")
            append_event_log(run_id, "scrapling_images", "INFO", "Audio synthesis and Scrapling image scraping completed", progress=50)

        # ── 3. Wav2Lip Lip-Sync Animation Stage ──
        if start_index <= min(stages_order.index("wav2lip"), stages_order.index("sadtalker")):
            update_stage_status(run_id, "wav2lip", "RUNNING")
            append_event_log(run_id, "wav2lip", "INFO", f"Generating Wav2Lip lip-sync animation (force_cpu={force_cpu})", progress=65)
            
            create_video_from_audio(run_dir, character_name, cpu_mode=force_cpu)
            
            update_stage_status(run_id, "wav2lip", "COMPLETED")
            append_event_log(run_id, "wav2lip", "INFO", "Wav2Lip avatar generation completed", progress=80)

        # ── 4. Video Stitching & FFmpeg Concat Stage ──
        if start_index <= stages_order.index("stitching"):
            update_stage_status(run_id, "stitching", "RUNNING")
            append_event_log(run_id, "stitching", "INFO", "Creating slide videos & stitching final MP4", progress=90)
            
            create_image_videos(run_dir)
            
            override_delay_seconds = None
            if pipeline_delay_ms is not None:
                try:
                    override_delay_seconds = int(math.ceil(int(pipeline_delay_ms) / 1000))
                except Exception:
                    override_delay_seconds = None

            file_id = await combine_videos(run_dir, topic_name, override_delay_seconds)
            
            update_stage_status(run_id, "stitching", "COMPLETED")
            update_stage_status(run_id, "validation", "COMPLETED")
            append_event_log(run_id, "validation", "INFO", "Video creation and validation completed successfully", progress=100)
            
            release_lock(run_id)
            return file_id

    except Exception as e:
        error_msg = str(e)
        current_stg = stages_order[start_index]
        print(f"❌ Error in stage '{current_stg}' for run {run_id}: {error_msg}")
        update_stage_status(run_id, current_stg, "FAILED", error=error_msg)
        append_event_log(run_id, current_stg, "ERROR", f"Pipeline failed in stage '{current_stg}': {error_msg}")
        release_lock(run_id)
        raise e
