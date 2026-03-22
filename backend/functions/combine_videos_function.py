import os
import subprocess
import random
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

async def combine_videos(timestamp, topic_name):
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

        scenario = random.randint(1, 4)

        if scenario in [1, 2]:
            # Side-by-side
            subprocess.run([
                "ffmpeg", "-y",
                "-i", v1_path, "-i", v2_path,
                "-filter_complex",
                "[0:v]scale=640:720:force_original_aspect_ratio=increase,crop=640:720[v0];"
                "[1:v]scale=640:720:force_original_aspect_ratio=increase,crop=640:720[v1];" +
                ("[v0][v1]hstack=inputs=2[v]" if scenario == 1 else "[v1][v0]hstack=inputs=2[v]"),
                "-map", "[v]", "-map", "0:a",  # only audio from first video
                "-c:v", "libx264", "-c:a", "aac",
                "-shortest", out_path
            ], check=True)

        elif scenario in [3, 4]:
            # Overlay
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
    env = os.getenv("ENVIRONMENT", "production")
    if env == "local":
        os.makedirs("prev_videos", exist_ok=True)
        local_path = f"prev_videos/{topic_name}.mp4"
        shutil.copyfile(final_video_path, local_path)
        print("🎬 Final video stored LOCALLY:", local_path)
        return f"local:{local_path}"
    else:
        file_id: ObjectId = await upload_file(
            final_video_path,
            filename=f"{topic_name}.mp4",
            metadata={"type": "final_video", "topic": topic_name, "timestamp": timestamp},
        )
        await set_cached_video(topic_name, file_id)
        print("🎬 Final video stored in DB:", str(file_id))
        return file_id
