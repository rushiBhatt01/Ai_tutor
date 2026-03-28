from datetime import datetime
import os
import asyncio
from bson import ObjectId

from functions.create_audio_image_function import create_audio_image
from functions.create_script_function import create_script
from functions.create_video_from_audio_function import create_video_from_audio
from functions.create_image_videos_function import create_image_videos
from functions.combine_videos_function import combine_videos
from db import get_cached_video
from media_store import upload_file


import math


async def video_main(topic_name, level_of_explanation, age, creativity_level, humour_level, character_name, pipeline_delay_ms=None):
    # First, check the frontend public `prev_videos` folder for a cached MP4
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/topic2explanation/public"))
    prev_videos_path = os.path.join(base_dir, "prev_videos", f"{topic_name}.mp4")
    if os.path.exists(prev_videos_path):
        print(f"Found cached video in prev_videos for topic '{topic_name}': {prev_videos_path}")
        # If frontend provided a pipeline delay, wait before returning cached file
        if pipeline_delay_ms is not None:
            try:
                wait_s = int((int(pipeline_delay_ms) + 999) / 1000)
            except Exception:
                wait_s = None
            if wait_s and wait_s > 0:
                print(f"Delaying return of cached video for {wait_s}s to let frontend pipeline finish")
                await asyncio.sleep(wait_s)
        return f"local:{prev_videos_path}"

    # If not present locally, check DB cache (production) or local prev_videos (legacy local env)
    env = os.getenv("ENVIRONMENT", "production")
    if env == "local":
        # legacy behaviour: also check ../../frontend/topic2explanation/public/prev_videos path
        local_path = f"../../frontend/topic2explanation/public/prev_videos/{topic_name}.mp4"
        if os.path.exists(local_path):
            print(f"Found cached video in frontend for topic '{topic_name}'")
            if pipeline_delay_ms is not None:
                try:
                    wait_s = int((int(pipeline_delay_ms) + 999) / 1000)
                except Exception:
                    wait_s = None
                if wait_s and wait_s > 0:
                    print(f"Delaying return of cached video for {wait_s}s to let frontend pipeline finish")
                    await asyncio.sleep(wait_s)
            return f"local:{os.path.abspath(local_path)}"
    else:
        cached_id = await get_cached_video(topic_name)
        if cached_id:
            print(f"Found cached video in DB for topic '{topic_name}': {cached_id}")
            if pipeline_delay_ms is not None:
                try:
                    wait_s = int((int(pipeline_delay_ms) + 999) / 1000)
                except Exception:
                    wait_s = None
                if wait_s and wait_s > 0:
                    print(f"Delaying return of cached DB video for {wait_s}s to let frontend pipeline finish")
                    await asyncio.sleep(wait_s)
            return ObjectId(cached_id) if not isinstance(cached_id, ObjectId) else cached_id

    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    os.makedirs(timestamp, exist_ok=True)
    os.makedirs(f"{timestamp}/audio", exist_ok=True)
    os.makedirs(f"{timestamp}/images", exist_ok=True)
    os.makedirs(f"{timestamp}/video", exist_ok=True)
    os.makedirs(f"{timestamp}/video_temp", exist_ok=True)
    os.makedirs(f"{timestamp}/image_videos", exist_ok=True)

    script = create_script(topic_name, level_of_explanation, age, creativity_level, humour_level,character_name)
    create_audio_image(topic_name, script, character_name, timestamp)
    create_video_from_audio(timestamp, character_name)
    create_image_videos(timestamp)

    # Persist images to DB (optional, keeps local copies for ffmpeg)
    env = os.getenv("ENVIRONMENT", "production")
    if env != "local":
        images_dir = f"{timestamp}/images"
        for fname in sorted(os.listdir(images_dir)):
            fpath = os.path.join(images_dir, fname)
            if os.path.isfile(fpath):
                try:
                    await upload_file(
                        fpath,
                        filename=fname,
                        metadata={"type": "image", "topic": topic_name, "timestamp": timestamp},
                    )
                except Exception:
                    pass

    # Convert pipeline_delay_ms (ms) to seconds for combine_videos; round up
    override_delay_seconds = None
    if pipeline_delay_ms is not None:
        try:
            override_delay_seconds = int(math.ceil(int(pipeline_delay_ms) / 1000))
        except Exception:
            override_delay_seconds = None

    file_id = await combine_videos(timestamp, topic_name, override_delay_seconds)
    return file_id
