import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_WORKERS = 1
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

def process_single_audio(audio_file: str, timestamp: str, character_name: str) -> str:
    audio_path = f"{timestamp}/audio/{audio_file}"
    img_path = f"characters/{character_name}.png"
    video_output_dir = f"{timestamp}/video"
    temp_output_dir = f"{timestamp}/video_temp"

    os.makedirs(video_output_dir, exist_ok=True)
    os.makedirs(temp_output_dir, exist_ok=True)

    job_output_path = os.path.join(temp_output_dir, f"{audio_file.split('.')[0]}_job")
    os.makedirs(job_output_path, exist_ok=True)

    final_output_file = os.path.join(video_output_dir, f"{audio_file.split('.')[0]}.mp4")

    linux_activate = "SadTalker/venv/bin/activate"
    win_activate = "SadTalker\\venv\\Scripts\\activate"
    if os.path.exists(linux_activate):
        activate_env_cmd = f". {linux_activate}"
    elif os.path.exists(win_activate):
        activate_env_cmd = win_activate
    else:
        activate_env_cmd = None

    if activate_env_cmd:
        command = (
            f"{activate_env_cmd} && "
            f"python ./SadTalker/inference.py "
            f"--driven_audio {audio_path} "
            f"--source_image {img_path} "
            f"--result_dir {job_output_path} "
            f"--still --preprocess full --facerender pirender"
        )
    else:
        command = (
            f"python ./SadTalker/inference.py "
            f"--driven_audio {audio_path} "
            f"--source_image {img_path} "
            f"--result_dir {job_output_path} "
            f"--still --preprocess full --facerender pirender"
        )

    try:
        subprocess.run(command, shell=True, check=True, timeout=600)

        # find generated video
        generated_video = None
        for root, _, files in os.walk(job_output_path):
            for f in files:
                if f.endswith(".mp4") and "full" in f:
                    generated_video = os.path.join(root, f)
                    break
            if generated_video:
                break

        if not generated_video:
            raise FileNotFoundError(f"No video generated for {audio_file}")

        shutil.move(generated_video, final_output_file)

        return f"✅ {audio_file} → {final_output_file}"

    finally:
        shutil.rmtree(job_output_path, ignore_errors=True)

def create_video_from_audio(timestamp: str, character_name: str):
    audio_folder = f"{timestamp}/audio"
    audio_files = os.listdir(audio_folder)

    futures = []
    for audio_file in audio_files:
        futures.append(
            executor.submit(process_single_audio, audio_file, timestamp, character_name)
        )

    results = []
    for future in as_completed(futures):
        try:
            results.append(future.result())
        except Exception as e:
            print(f"❌ SadTalker Error: {e}")
            raise RuntimeError(f"Video generation failed: {e}")

    print(f"All jobs done. Videos saved in {timestamp}/video")
    return results
