import os
import re
import json
import ffmpeg
import subprocess
from functions.visual_artifacts import atomic_output, probe_visual_video


def _load_visual_manifest(timestamp: str) -> dict:
    """Load visual manifest and return a dict keyed by chunk_id (e.g. 'seg_0')."""
    manifest_path = os.path.join(timestamp, "visual_manifest.json")
    if not os.path.exists(manifest_path):
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        return {f"seg_{e['scene_id']}": e for e in entries if "scene_id" in e}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def _create_animated_overlay_video(
    slide_path: str, animation_path: str, audio_path: str, output_path: str,
    media_type: str = "mp4",
) -> bool:
    """Composite an animated media (GIF/MP4) onto a slide background with audio.

    Uses FFmpeg filter_complex to overlay the animation at position (730, 105)
    matching the upper right-column slot dimensions (490x310).

    Args:
        slide_path: Path to the 1280x720 slide background JPEG.
        animation_path: Path to the animated MP4 or GIF file.
        audio_path: Path to the WAV/MP3 audio narration.
        output_path: Final output MP4 path.
        media_type: Either "mp4" or "gif".

    Returns:
        True if successful, False on failure.
    """
    try:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", "25", "-i", slide_path,
            "-stream_loop", "-1", "-i", animation_path,
        ]
        if audio_path and os.path.exists(audio_path):
            cmd.extend(["-i", audio_path])
            audio_map = "2:a"
        else:
            cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])
            audio_map = "2:a"

        cmd.extend([
            "-filter_complex",
            "[1:v]scale=490:310:force_original_aspect_ratio=decrease,pad=490:310:(ow-iw)/2:(oh-ih)/2[anim];"
            "[0:v]scale=1280:720[bg];"
            "[bg][anim]overlay=730:105:shortest=1[outv]",
            "-map", "[outv]",
            "-map", audio_map,
            "-shortest",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-r", "25",
            output_path,
        ])

        result = subprocess.run(cmd, check=True, timeout=60, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"    ⚠️ Animated overlay FFmpeg error: {e.stderr[-300:] if e.stderr else e}")
        return False
    except Exception as e:
        print(f"    ⚠️ Animated overlay error: {e}")
        return False


def create_image_videos(timestamp, chunk_ids=None, preserved_chunk_ids=()):
    """
    Create slide-video clips by pairing each chunk image (seg_X.jpg) with
    its matching chunk audio (seg_X.wav).

    The pairing is by *chunk_id* (the ``seg_X`` prefix), NOT by simple
    numeric index, which guarantees the correct image is shown for each
    audio segment even when files are created out of order.
    """
    base_folder = os.path.join(timestamp)
    image_folder = os.path.join(base_folder, 'images')
    audio_folder = os.path.join(base_folder, 'audio')
    output_folder = os.path.join(base_folder, 'image_videos')

    os.makedirs(output_folder, exist_ok=True)

    print("📂 Looking in:", image_folder)
    if not os.path.exists(image_folder):
        raise FileNotFoundError(f"Image folder not found: {image_folder}")
    if not os.path.exists(audio_folder):
        raise FileNotFoundError(f"Audio folder not found: {audio_folder}")

    # ── Build lookup maps keyed by chunk_id (e.g. "seg_0") ──
    def _chunk_id(filename: str) -> str:
        """Extract chunk_id like 'seg_0' from filenames like 'seg_0.jpg'."""
        return os.path.splitext(filename)[0]

    image_map: dict[str, str] = {}
    for f in os.listdir(image_folder):
        if f.lower().endswith((".jpg", ".jpeg", ".png")):
            chunk_id = _chunk_id(f)
            if chunk_id in image_map:
                raise ValueError(f"Multiple slide images found for chunk_id {chunk_id!r}")
            image_map[chunk_id] = os.path.join(image_folder, f)

    audio_map: dict[str, str] = {}
    for f in os.listdir(audio_folder):
        if f.lower().endswith((".wav", ".mp3")):
            chunk_id = _chunk_id(f)
            if chunk_id in audio_map:
                raise ValueError(f"Multiple audio files found for chunk_id {chunk_id!r}")
            audio_map[chunk_id] = os.path.join(audio_folder, f)

    # Require a complete one-to-one pairing; retain mismatched inputs for diagnosis.
    image_ids, audio_ids = set(image_map), set(audio_map)
    if chunk_ids is not None:
        requested = set(chunk_ids)
        if not requested <= image_ids & audio_ids:
            raise ValueError(f"Missing chunk inputs: {sorted(requested - (image_ids & audio_ids))}")
        image_ids, audio_ids = requested, requested
    if image_ids != audio_ids:
        raise ValueError(
            "Chunk image/audio IDs do not match; "
            f"missing images for {sorted(audio_ids - image_ids)}, "
            f"missing audio for {sorted(image_ids - audio_ids)}"
        )
    common_ids = sorted(image_ids, key=lambda value: [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)])

    total_files = len(common_ids)
    print(f"\n📁 Matched {total_files} chunk(s) by chunk_id.")
    print(f"🎬 Generating {total_files} image video(s)...\n")
    completed_ids = set()

    # Load visual manifest to detect animated scenes
    manifest = _load_visual_manifest(timestamp)

    for idx, chunk_id in enumerate(common_ids):
        image_path = image_map[chunk_id]
        audio_path = audio_map[chunk_id]
        output_path = os.path.join(output_folder, f"{chunk_id}.mp4")

        # Only the caller's successful renders from this pass may bypass conversion.
        if chunk_id in preserved_chunk_ids:
            probe_visual_video(output_path)
            completed_ids.add(chunk_id)
            print(f"[{idx + 1}/{total_files}] [OK] Reusing pre-rendered video (Manim): {output_path}")
            continue

        try:
            # ── Check for animated media overlay (hybrid_gif scenes) ──
            scene_manifest = manifest.get(chunk_id, {})
            animated_path = scene_manifest.get("animated_media_path")
            animated_type = scene_manifest.get("animated_media_type", "mp4")

            if animated_path and os.path.exists(animated_path) and scene_manifest.get("media_type") == "animated":
                print(f"  🎞️ [{chunk_id}] Compositing animated overlay...")
                with atomic_output(output_path) as temporary:
                    success = _create_animated_overlay_video(
                        slide_path=image_path,
                        animation_path=animated_path,
                        audio_path=audio_path,
                        output_path=temporary,
                        media_type=animated_type,
                    )
                    if success:
                        probe_visual_video(temporary)
                        completed_ids.add(chunk_id)
                        print(f"[{idx + 1}/{total_files}] ✅ Created (animated): {output_path}")
                        continue
                    else:
                        print(f"  ⚠️ [{chunk_id}] Animated overlay failed; falling back to static")

            image_input = (
                ffmpeg
                .input(image_path, loop=1, framerate=25)
                .filter('scale', 1280, 720, force_original_aspect_ratio='decrease')
                .filter('pad', 1280, 720, '(ow-iw)/2', '(oh-ih)/2')
            )

            if audio_path and os.path.exists(audio_path):
                audio_input = ffmpeg.input(audio_path)
            else:
                audio_input = ffmpeg.input(
                    'anullsrc=channel_layout=stereo:sample_rate=44100',
                    f='lavfi'
                )

            with atomic_output(output_path) as temporary:
                stream = (
                    ffmpeg
                    .output(
                        image_input, audio_input, temporary,
                        shortest=None,
                        vcodec='libx264',
                        acodec='aac',
                        pix_fmt='yuv420p',
                        r=25
                    )
                )
                try:
                    cmd = stream.compile(overwrite_output=True)
                    if isinstance(cmd, list) and all(isinstance(x, str) for x in cmd):
                        subprocess.run(cmd, check=True, timeout=30, capture_output=True)
                    else:
                        stream.run(overwrite_output=True, quiet=False, timeout=30)
                except (AttributeError, TypeError):
                    stream.run(overwrite_output=True, quiet=False)
                probe_visual_video(temporary)

            completed_ids.add(chunk_id)
            print(f"[{idx + 1}/{total_files}] ✅ Created: {output_path}")

        except Exception as e:
            print(f"[{idx + 1}/{total_files}] ❌ Failed on {chunk_id}")
            print(f"    Error: {e}\n")
            continue

    failed_ids = [chunk_id for chunk_id in common_ids if chunk_id not in completed_ids]
    if failed_ids:
        raise RuntimeError(f"Failed to render visual chunks: {', '.join(failed_ids)}")
