import os
import subprocess
import random
import asyncio
import shutil
import json
from bson import ObjectId
from db import set_cached_video
from media_store import upload_file

def get_video_resolution(video_path):
    """Get width and height of video using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    width = info["streams"][0]["width"]
    height = info["streams"][0]["height"]
    return width, height

def ensure_16_9(video_path, resolution="1280x720"):
    """
    Convert video to 16:9 only if it's wider than 16:9.
    Returns the path to the processed video.
    """
    width, height = get_video_resolution(video_path)
    aspect_ratio = width / height
    target_ratio = 16 / 9

    if aspect_ratio > target_ratio:
        fixed_path = video_path.replace(".mp4", "_16_9.mp4")
        print(f"📐 Fixing aspect ratio for {video_path} (AR={aspect_ratio:.2f}) → {fixed_path}")

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"scale=w=iw*min({resolution.split('x')[0]}/iw\\,{resolution.split('x')[1]}/ih):"
                   f"h=ih*min({resolution.split('x')[0]}/iw\\,{resolution.split('x')[1]}/ih),"
                   f"pad={resolution.split('x')[0]}:{resolution.split('x')[1]}:(ow-iw)/2:(oh-ih)/2",
            "-c:a", "copy",
            fixed_path
        ]
        subprocess.run(cmd, check=True)
        return fixed_path
    else:
        print(f"✅ Aspect ratio OK for {video_path} (AR={aspect_ratio:.2f})")
        return video_path

async def combine_videos(timestamp, topic_name, override_delay_seconds=None):
    print("Combining videos with FFmpeg...")

    video1_folder = f"{timestamp}/video"
    video2_folder = f"{timestamp}/image_videos"

    video1_files = sorted(os.listdir(video1_folder), key=lambda x: int(x.split(".")[0]))
    video2_files = sorted(os.listdir(video2_folder), key=lambda x: int(x.split(".")[0]))

    min_len = min(len(video1_files), len(video2_files))
    video1_files = video1_files[:min_len]
    video2_files = video2_files[:min_len]

    clips = []
    for i in range(min_len):
        v1_path = os.path.join(video1_folder, video1_files[i])
        v2_path = os.path.join(video2_folder, video2_files[i])
        out_path = f"{timestamp}/temp_{i}.mp4"

        # Always use overlay placement for the character/video instead of side-by-side.
        # Keep a small foreground (character) over the main background image video.
        scenario = random.choice([3, 4])
        overlay_pos = "x=0:y=H-h" if scenario == 3 else "x=W-w-10:y=H-h"
        subprocess.run([
            "ffmpeg", "-y",
            "-i", v2_path, "-i", v1_path,  # big first, small second
            "-filter_complex",
            "[0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720[bg];"
            "[1:v]scale=320:360:force_original_aspect_ratio=increase,crop=320:360[fg];" +
            f"[bg][fg]overlay={overlay_pos}[v]",
            "-map", "[v]", "-map", "1:a",  # only audio from video1 (second input here)
            "-c:v", "libx264", "-c:a", "aac",
            "-shortest", out_path
        ], check=True)

        # Ensure each output clip is 16:9 (only if too wide)
        fixed_clip = ensure_16_9(out_path, resolution="1280x720")
        clips.append(fixed_clip)

    # Concatenate all clips
    concat_list_path = f"{timestamp}/concat_list.txt"
    with open(concat_list_path, "w") as f:
        for clip in clips:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    final_video_path = f"{timestamp}/final_video.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy", final_video_path
    ], check=True)
    env = os.getenv("ENVIRONMENT", "local")
    # Delay (in seconds) before making the cache entry visible to frontend
    if override_delay_seconds is not None:
        try:
            delay_seconds = int(override_delay_seconds)
        except Exception:
            delay_seconds = int(os.getenv("CACHE_POST_DELAY", "3"))
    else:
        delay_seconds = int(os.getenv("CACHE_POST_DELAY", "3"))
    if env == "local":
        # Save to frontend's public/prev_videos folder
        frontend_cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/topic2explanation/public/prev_videos"))
        os.makedirs(frontend_cache_dir, exist_ok=True)
        temp_name = f".{topic_name}.tmp.mp4"
        temp_path = os.path.join(frontend_cache_dir, temp_name)
        final_dest = os.path.join(frontend_cache_dir, f"{topic_name}.mp4")
        shutil.copyfile(final_video_path, temp_path)
        temp_abs = os.path.abspath(temp_path)
        print("🎬 Final video copied to temp location:", temp_abs)
        if delay_seconds > 0:
            print(f"Waiting {delay_seconds}s before exposing cached video...")
            await asyncio.sleep(delay_seconds)
        # Move temp file to final destination atomically
        os.replace(temp_path, final_dest)
        final_abs = os.path.abspath(final_dest)
        print("🎬 Cached video now exposed at:", final_abs)
        return f"local:{final_abs}"
    else:
        file_id: ObjectId = await upload_file(
            final_video_path,
            filename=f"{topic_name}.mp4",
            metadata={"type": "final_video", "topic": topic_name, "timestamp": timestamp},
        )
        # Wait a short period to ensure storage/backends have completed processing
        if delay_seconds > 0:
            print(f"Waiting {delay_seconds}s before writing DB cache entry...")
            await asyncio.sleep(delay_seconds)
        await set_cached_video(topic_name, file_id)
        print("🎬 Final video stored in DB:", str(file_id))
        return file_id
