from datetime import datetime
import os
import json
import asyncio
import math
from bson import ObjectId

from functions.pipeline.create_audio_image_function import create_audio_image
from functions.script.create_script_function import create_script
from functions.script.create_storyboard_function import create_storyboard
from functions.script.langgraph_pipeline import run_script_pipeline
from functions.video.create_video_from_audio_function import create_video_from_audio
from functions.video.create_image_videos_function import create_image_videos
from functions.visual.visual_artifacts import atomic_output
from functions.visual.visual_pipeline_graph import run_visual_pipeline
from functions.video.combine_videos_function import combine_videos
from functions.pipeline.cache_utils import find_cached_video
from functions.pipeline.checkpoint_manager import (
    init_run, load_checkpoint, update_stage_status, append_event_log,
    release_lock, get_run_dir, PIPELINE_STAGES, canonical_stage
)
from functions.pipeline.dag_evaluator import evaluate_run_dag
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
        cached = find_cached_video(topic_name)
        if cached and cached.get("exists"):
            prev_videos_path = cached["path"]
            print(f"🎬 Found cached video in prev_videos for topic '{topic_name}': {prev_videos_path}")
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

    stages_order = PIPELINE_STAGES
    start_stage = canonical_stage(start_stage)
    if start_stage not in stages_order:
        release_lock(run_id)
        raise ValueError(f"Unknown pipeline stage: {start_stage}")
    start_index = stages_order.index(start_stage)
    current_stg = start_stage

    script_text = ""
    storyboard = None
    visual_plan = []
    visual_specs = []
    script_file = os.path.join(run_dir, "artifacts", "script.json")
    storyboard_file = os.path.join(run_dir, "artifacts", "storyboard.json")
    visual_plan_file = os.path.join(run_dir, "artifacts", "visual_plan.json")

    try:
        # ── 1+2. LangGraph Script + Storyboard Pipeline ──
        # Replaces the old sequential create_script() → create_storyboard()
        # with a stateful graph: classify → script → (manim plan?) → storyboard
        if start_index <= stages_order.index("storyboard"):
            current_stg = "script"
            update_stage_status(run_id, "script", "RUNNING")
            append_event_log(run_id, "script", "INFO", f"[LangGraph] Starting script+storyboard pipeline for '{topic_name}'", progress=10)

            script_text, storyboard, graph_state = run_script_pipeline(
                topic_name=topic_name,
                level_of_explanation=level_of_explanation,
                age=age,
                creativity_level=creativity_level,
                humour_level=humour_level,
                character_name=character_name,
                return_state=True,
            )
            visual_plan = graph_state.get("visual_plan", [])
            visual_specs = graph_state.get("visual_specs", [])

            # Persist script artifact
            with open(script_file, "w", encoding="utf-8") as f:
                json.dump({"topic": topic_name, "script": script_text}, f, indent=2)

            update_stage_status(run_id, "script", "COMPLETED")
            append_event_log(run_id, "script", "INFO", "Script generation completed via LangGraph", progress=15)

            # Persist storyboard artifact
            current_stg = "storyboard"
            os.makedirs(os.path.dirname(storyboard_file), exist_ok=True)
            storyboard_json = storyboard.model_dump_json(indent=2)
            with open(storyboard_file, "w", encoding="utf-8") as f:
                f.write(storyboard_json)
            with open(os.path.join(run_dir, "storyboard.json"), "w", encoding="utf-8") as f:
                f.write(storyboard_json)

            update_stage_status(run_id, "storyboard", "COMPLETED")
            append_event_log(run_id, "storyboard", "INFO", f"Storyboard planned: {len(storyboard.scenes)} scenes", progress=25)
        else:
            # Resume: reload persisted artifacts
            if os.path.exists(script_file):
                with open(script_file, "r", encoding="utf-8") as f:
                    script_text = json.load(f).get("script", "")

            target_file = storyboard_file if os.path.exists(storyboard_file) else os.path.join(run_dir, "storyboard.json")
            if os.path.exists(target_file):
                from functions.script.storyboard_schema import Storyboard as StoryboardSchema
                with open(target_file, "r", encoding="utf-8") as f:
                    storyboard = StoryboardSchema.model_validate_json(f.read())
            elif script_text:
                storyboard = create_storyboard(topic_name, script_text)

        if storyboard is not None:
            if not visual_plan:
                visual_plan = [
                    {
                        "scene_id": scene.scene_id,
                        "strategy": scene.visual_type,
                        "rationale": scene.visual_rationale,
                    }
                    for scene in storyboard.scenes
                ]
            with atomic_output(visual_plan_file) as plan_temp:
                with open(plan_temp, "w", encoding="utf-8") as stream:
                    json.dump({"schema_version": 1, "scenes": visual_plan}, stream, indent=2)
            if not visual_specs:
                from functions.script.langgraph_pipeline import _validated_visual_specs
                visual_specs = _validated_visual_specs(storyboard)
            specs_file = os.path.join(run_dir, "artifacts", "visual_specs.json")
            with atomic_output(specs_file) as specs_temp:
                with open(specs_temp, "w", encoding="utf-8") as stream:
                    json.dump({"schema_version": 1, "scenes": visual_specs}, stream, indent=2)

        # ── 3. Audio TTS & Slide Image Generation Stage ──
        if start_index <= stages_order.index("scrapling_images"):
            current_stg = "audio_tts"
            update_stage_status(run_id, "audio_tts", "RUNNING")
            update_stage_status(run_id, "scrapling_images", "RUNNING")
            append_event_log(run_id, "audio_tts", "INFO", "Synthesizing Edge-TTS audio & generating slide images", progress=35)
            
            create_audio_image(topic_name, script_text, character_name, run_dir, storyboard=storyboard)
            
            update_stage_status(run_id, "audio_tts", "COMPLETED")
            update_stage_status(run_id, "scrapling_images", "COMPLETED")
            append_event_log(run_id, "scrapling_images", "INFO", "Audio synthesis and slide image generation completed", progress=50)

        # ── 3. Parallel Stage: GPU Wav2Lip Animation + CPU Manim/Visual Generation ──
        if start_index <= stages_order.index("sadtalker"):
            current_stg = "sadtalker"
            update_stage_status(run_id, "sadtalker", "RUNNING")
            has_manim = any(getattr(s, "visual_type", "") == "manim" for s in (storyboard.scenes if storyboard else []))
            mode_desc = "GPU Wav2Lip + CPU Manim animations" if has_manim else "GPU Wav2Lip + CPU slide videos"
            append_event_log(run_id, "sadtalker", "INFO", f"Launching parallel generation: {mode_desc}", progress=65)

            # Concurrently run GPU Wav2Lip and CPU Manim/slide visual rendering
            await asyncio.gather(
                asyncio.to_thread(create_video_from_audio, run_dir, character_name, cpu_mode=force_cpu),
                asyncio.to_thread(run_visual_pipeline, run_dir, storyboard=storyboard)
            )

            update_stage_status(run_id, "sadtalker", "COMPLETED")
            append_event_log(run_id, "sadtalker", "INFO", "Parallel Wav2Lip and visual scene rendering completed", progress=80)
        elif start_index <= stages_order.index("stitching"):
            current_stg = "stitching"
            # If resuming directly from stitching stage, ensure visual scenes are rendered
            run_visual_pipeline(run_dir, storyboard=storyboard)

        # ── 4. Video Stitching & FFmpeg Concat Stage ──
        if start_index <= stages_order.index("stitching"):
            current_stg = "stitching"
            update_stage_status(run_id, "stitching", "RUNNING")
            append_event_log(run_id, "stitching", "INFO", "Stitching final MP4 tutorial video", progress=90)

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
        print(f"[ERROR] Error in stage '{current_stg}' for run {run_id}: {error_msg}")
        update_stage_status(run_id, current_stg, "FAILED", error=error_msg)
        append_event_log(run_id, current_stg, "ERROR", f"Pipeline failed in stage '{current_stg}': {error_msg}")
        release_lock(run_id)
        raise e
