import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

MAX_WORKERS = 1
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

def process_single_audio(audio_file: str, timestamp: str, character_name: str, cpu_mode: bool = False) -> str:
    audio_path = os.path.join(timestamp, "audio", audio_file)
    
    # Support png, jpg, jpeg extensions for character image
    img_path = None
    for ext in [".png", ".jpg", ".jpeg"]:
        for base in ["characters", os.path.join("backend", "characters")]:
            candidate = os.path.join(base, f"{character_name}{ext}")
            if os.path.exists(candidate):
                img_path = candidate
                break
        if img_path:
            break
            
    if not img_path:
        # Fallback to face.png / Sophia.png / Benjamin.png if character image not found
        for fallback in ["face.png", "Sophia.png", "Benjamin.png"]:
            for base in ["characters", os.path.join("backend", "characters")]:
                candidate = os.path.join(base, fallback)
                if os.path.exists(candidate):
                    img_path = candidate
                    break
            if img_path:
                break

    if not img_path:
        img_path = os.path.join("characters", "face.png")

    video_output_dir = os.path.join(timestamp, "video")
    os.makedirs(video_output_dir, exist_ok=True)

    final_output_file = os.path.join(video_output_dir, f"{os.path.splitext(audio_file)[0]}.mp4")

    # Command using Wav2Lip inference
    python_exe = sys.executable
    checkpoint_path = os.path.join("Wav2Lip", "checkpoints", "wav2lip_gan.pth")
    if not os.path.exists(checkpoint_path):
        checkpoint_path = os.path.join("backend", "Wav2Lip", "checkpoints", "wav2lip_gan.pth")
    if not os.path.exists(checkpoint_path):
        checkpoint_path = os.path.join("Wav2Lip", "checkpoints", "wav2lip.pth")
    if not os.path.exists(checkpoint_path):
        checkpoint_path = os.path.join("backend", "Wav2Lip", "checkpoints", "wav2lip.pth")

    wav2lip_script = os.path.join("Wav2Lip", "inference.py")
    if not os.path.exists(wav2lip_script):
        wav2lip_script = os.path.join("backend", "Wav2Lip", "inference.py")

    command = [
        python_exe,
        wav2lip_script,
        "--checkpoint_path", checkpoint_path,
        "--face", img_path,
        "--audio", audio_path,
        "--outfile", final_output_file,
        "--nosmooth"
    ]

    try:
        print(f"[Wav2Lip] Starting lip sync for {audio_file} using {img_path} (cpu_mode={cpu_mode})...")
        res = subprocess.run(command, check=True, timeout=600, capture_output=True, text=True)
        if res.stdout:
            print(res.stdout)

        if not os.path.exists(final_output_file):
            raise FileNotFoundError(f"No video generated at {final_output_file} for {audio_file}")

        return f"[Wav2Lip OK] {audio_file} -> {final_output_file}"

    except subprocess.CalledProcessError as e:
        print(f"[Wav2Lip ERROR] Execution failed for {audio_file}: {e.stderr}")
        raise RuntimeError(f"Wav2Lip generation failed: {e.stderr}")
    except Exception as e:
        print(f"[Wav2Lip ERROR] {e}")
        raise RuntimeError(f"Video generation failed: {e}")

def create_video_from_audio(timestamp: str, character_name: str, cpu_mode: bool = False):
    audio_folder = os.path.join(timestamp, "audio")
    audio_files = [f for f in os.listdir(audio_folder) if f.endswith(('.wav', '.mp3'))]

    futures = []
    for audio_file in audio_files:
        futures.append(
            executor.submit(process_single_audio, audio_file, timestamp, character_name, cpu_mode)
        )


    results = []
    for future in as_completed(futures):
        try:
            results.append(future.result())
        except Exception as e:
            print(f"[Wav2Lip ERROR] Video generation failed: {e}")
            raise RuntimeError(f"Video generation failed: {e}")

    print(f"All jobs done. Videos saved in {timestamp}/video")
    return results
