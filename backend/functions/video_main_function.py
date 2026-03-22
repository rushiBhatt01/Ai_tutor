from datetime import datetime
import os
from bson import ObjectId

from functions.create_audio_image_function import create_audio_image
from functions.create_script_function import create_script
from functions.create_video_from_audio_function import create_video_from_audio
from functions.create_image_videos_function import create_image_videos
from functions.combine_videos_function import combine_videos
from db import get_cached_video
from media_store import upload_file


async def video_main(topic_name, level_of_explanation, age, creativity_level, humour_level, character_name):
    env = os.getenv("ENVIRONMENT", "production")
    if env == "local":
        local_path = f"prev_videos/{topic_name}.mp4"
        if os.path.exists(local_path):
            print(f"Found cached video LOCALLY for topic '{topic_name}'")
            return f"local:{local_path}"
    else:
        cached_id = await get_cached_video(topic_name)
        if cached_id:
            print(f"Found cached video in DB for topic '{topic_name}': {cached_id}")
            return ObjectId(cached_id) if not isinstance(cached_id, ObjectId) else cached_id

    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    os.makedirs(timestamp, exist_ok=True)
    os.makedirs(f"{timestamp}/audio", exist_ok=True)
    os.makedirs(f"{timestamp}/images", exist_ok=True)
    os.makedirs(f"{timestamp}/video", exist_ok=True)
    os.makedirs(f"{timestamp}/video_temp", exist_ok=True)
    os.makedirs(f"{timestamp}/image_videos", exist_ok=True)

    script = create_script(topic_name, level_of_explanation, age, creativity_level, humour_level)
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

    file_id = await combine_videos(timestamp, topic_name)
    return file_id
