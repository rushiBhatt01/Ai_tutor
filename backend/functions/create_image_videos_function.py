import os
import re
import ffmpeg


def create_image_videos(timestamp):
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
            image_map[_chunk_id(f)] = os.path.join(image_folder, f)

    audio_map: dict[str, str] = {}
    for f in os.listdir(audio_folder):
        if f.lower().endswith(".wav"):
            audio_map[_chunk_id(f)] = os.path.join(audio_folder, f)

    # ── Match by chunk_id ──
    common_ids = sorted(set(image_map) & set(audio_map))

    # Remove orphan files (images without audio or vice-versa)
    for cid in sorted(set(image_map) - set(audio_map)):
        path = image_map[cid]
        os.remove(path)
        print(f"🗑️ Deleted orphan image: {os.path.basename(path)}")
    for cid in sorted(set(audio_map) - set(image_map)):
        path = audio_map[cid]
        os.remove(path)
        print(f"🗑️ Deleted orphan audio: {os.path.basename(path)}")

    total_files = len(common_ids)
    print(f"\n📁 Matched {total_files} chunk(s) by chunk_id.")
    print(f"🎬 Generating {total_files} image video(s)...\n")

    for idx, chunk_id in enumerate(common_ids):
        image_path = image_map[chunk_id]
        audio_path = audio_map[chunk_id]
        output_path = os.path.join(output_folder, f"{chunk_id}.mp4")

        try:
            image_input = (
                ffmpeg
                .input(image_path, loop=1, framerate=25)
                .filter('scale', 'trunc(iw/2)*2', 'trunc(ih/2)*2')
            )

            if audio_path and os.path.exists(audio_path):
                audio_input = ffmpeg.input(audio_path)
            else:
                audio_input = ffmpeg.input(
                    'anullsrc=channel_layout=stereo:sample_rate=44100',
                    f='lavfi'
                )

            (
                ffmpeg
                .output(
                    image_input, audio_input, output_path,
                    shortest=None,
                    vcodec='libx264',
                    acodec='aac',
                    pix_fmt='yuv420p',
                    r=25
                )
                .run(overwrite_output=True, quiet=False)
            )

            print(f"[{idx + 1}/{total_files}] ✅ Created: {output_path}")

        except Exception as e:
            print(f"[{idx + 1}/{total_files}] ❌ Failed on {chunk_id}")
            print(f"    Error: {e}\n")
