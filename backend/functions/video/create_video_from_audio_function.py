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

def _resolve_character_image(character_name: str) -> str:
    filenames = [f"{character_name}{ext}" for ext in (".png", ".jpg", ".jpeg")]
    filenames += ["face.png", "Sophia.png", "Benjamin.png"]
    for filename in filenames:
        for base in ("characters", os.path.join("backend", "characters")):
            candidate = os.path.join(base, filename)
            if os.path.exists(candidate):
                return candidate
    return os.path.join("characters", "face.png")

def _resolve_paths():
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
    return python_exe, checkpoint_path, wav2lip_script

def process_single_audio(audio_file: str, timestamp: str, character_name: str, cpu_mode: bool = False) -> str:
    cpu_mode = cpu_mode or os.getenv("CPU_ONLY", "false").lower() == "true"
    audio_path = os.path.join(timestamp, "audio", audio_file)
    
    img_path = _resolve_character_image(character_name)

    video_output_dir = os.path.join(timestamp, "video")
    os.makedirs(video_output_dir, exist_ok=True)

    final_output_file = os.path.join(video_output_dir, f"{os.path.splitext(audio_file)[0]}.mp4")

    if os.getenv("AVATAR_MODE", "wav2lip") == "static":
        # Explicit deployment mode while ARM64 Wav2Lip remains unbenchmarked.
        # Preserve narration and the presenter slot without model inference.
        if not os.path.isfile(img_path):
            from PIL import Image, ImageDraw
            img_path = os.path.join(video_output_dir, "presenter.png")
            image = Image.new("RGB", (250, 220), "#172033")
            ImageDraw.Draw(image).text((20, 100), "AI Tutor", fill="white")
            image.save(img_path)
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", img_path, "-i", audio_path,
            "-vf", "scale=250:220:force_original_aspect_ratio=increase,crop=250:220,setsar=1",
            "-r", "30", "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", final_output_file],
            check=True, capture_output=True, timeout=600)
        return f"[Static presenter; Wav2Lip disabled pending CPU benchmark] {audio_file}"

    # Command using Wav2Lip inference
    python_exe, checkpoint_path, wav2lip_script = _resolve_paths()

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

        # Force NVIDIA GTX 1650 for Wav2Lip inference.
        # nvidia-smi reports GTX 1650 as CUDA device 0 (Windows Task Manager
        # shows it as "GPU 1", but CUDA uses its own indexing).
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = "" if cpu_mode else "0"

        res = subprocess.run(command, check=True, timeout=600, capture_output=True, text=True, env=env)
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
    if not audio_files:
        return []

    # If explicit static avatar mode is set, use the single-audio ffmpeg generator
    if os.getenv("AVATAR_MODE", "wav2lip") == "static":
        futures = [executor.submit(process_single_audio, f, timestamp, character_name, cpu_mode) for f in audio_files]
        results = [future.result() for future in as_completed(futures)]
        print(f"All jobs done. Videos saved in {timestamp}/video")
        return results

    video_output_dir = os.path.join(timestamp, "video")
    os.makedirs(video_output_dir, exist_ok=True)
    img_path = _resolve_character_image(character_name)
    python_exe, checkpoint_path, wav2lip_script = _resolve_paths()

    cpu_mode = cpu_mode or os.getenv("CPU_ONLY", "false").lower() == "true"
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "" if cpu_mode else "0"

    command = [
        python_exe,
        wav2lip_script,
        "--checkpoint_path", checkpoint_path,
        "--face", img_path,
        "--audio_dir", audio_folder,
        "--outdir", video_output_dir,
        "--static", "True",
        "--nosmooth"
    ]

    print(f"[Wav2Lip] Starting batch lip sync for {len(audio_files)} files using {img_path} (cpu_mode={cpu_mode})...")
    try:
        subprocess.run(command, check=True, timeout=1200, env=env)
    except subprocess.CalledProcessError as e:
        print(f"[Wav2Lip WARNING] Batch execution returned error ({e}); falling back to per-file processing...")
        futures = [executor.submit(process_single_audio, f, timestamp, character_name, cpu_mode) for f in audio_files]
        return [future.result() for future in as_completed(futures)]

    results = []
    for audio_file in audio_files:
        stem = os.path.splitext(audio_file)[0]
        final_output_file = os.path.join(video_output_dir, f"{stem}.mp4")
        if not os.path.exists(final_output_file):
            raise FileNotFoundError(f"No video generated at {final_output_file} for {audio_file}")
        results.append(f"[Wav2Lip OK] {audio_file} -> {final_output_file}")

    print(f"All jobs done. Videos saved in {timestamp}/video")
    return results
