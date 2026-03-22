# import os
# import re
# import ffmpeg

# def create_image_videos(timestamp):
#     # Get absolute path to backend directory (one level up from this file's folder)

#     base_folder = os.path.join( timestamp)
#     image_folder = os.path.join(base_folder, 'images')
#     audio_folder = os.path.join(base_folder, 'audio')
#     output_folder = os.path.join(base_folder, 'image_videos')

#     os.makedirs(output_folder, exist_ok=True)

#     # Debug path checks
#     print("📂 Looking in:", image_folder)
#     if not os.path.exists(image_folder):
#         raise FileNotFoundError(f"Image folder not found: {image_folder}")
#     if not os.path.exists(audio_folder):
#         raise FileNotFoundError(f"Audio folder not found: {audio_folder}")

#     # Get and sort image files by number in filename
#     image_files = sorted(
#         [f for f in os.listdir(image_folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))],
#         key=lambda x: int(re.search(r'\d+', x).group())
#     )

#     # Get and sort audio files by number in filename
#     audio_files = sorted(
#         [f for f in os.listdir(audio_folder) if f.lower().endswith(".wav")],
#         key=lambda x: int(re.search(r'\d+', x).group())
#     )

#     total_files = min(len(image_files), len(audio_files))

#     print(f"\n📁 Found {len(image_files)} image(s) and {len(audio_files)} audio file(s).")
#     print(f"🎬 Generating {total_files} image video(s)...\n")

#     for idx in range(total_files):
#         image_file = image_files[idx]
#         audio_file = audio_files[idx]

#         image_path = os.path.join(image_folder, image_file)
#         audio_path = os.path.join(audio_folder, audio_file)
#         output_path = os.path.join(output_folder, f"{os.path.splitext(image_file)[0]}.mp4")

#         try:
#             image_input = (
#                 ffmpeg
#                 .input(image_path, loop=1, framerate=25)
#                 .filter('scale', 'trunc(iw/2)*2', 'trunc(ih/2)*2')
#             )

#             audio_input = ffmpeg.input(audio_path)

#             (
#                 ffmpeg
#                 .output(
#                     image_input, audio_input, output_path,
#                     shortest=None,
#                     vcodec='libx264',
#                     acodec='aac',
#                     pix_fmt='yuv420p',
#                     r=25
#                 )
#                 .run(overwrite_output=True)
#             )

#             print(f"[{idx + 1}/{total_files}] ✅ Created: {output_path}")

#         except Exception as e:
#             print(f"[{idx + 1}/{total_files}] ❌ Failed on {image_file} + {audio_file}")
#             print(f"    Error: {e}\n")

import os
import re
import ffmpeg

def create_image_videos(timestamp):
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

    # Sort images
    image_files = sorted(
        [f for f in os.listdir(image_folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))],
        key=lambda x: int(re.search(r'\d+', x).group())
    )

    # Sort audio
    audio_files = sorted(
        [f for f in os.listdir(audio_folder) if f.lower().endswith(".wav")],
        key=lambda x: int(re.search(r'\d+', x).group())
    )

    # Balance counts: delete extra files
    if len(image_files) > len(audio_files):
        extras = image_files[len(audio_files):]
        for extra in extras:
            os.remove(os.path.join(image_folder, extra))
            print(f"🗑️ Deleted extra image: {extra}")
        image_files = image_files[:len(audio_files)]

    elif len(audio_files) > len(image_files):
        extras = audio_files[len(image_files):]
        for extra in extras:
            os.remove(os.path.join(audio_folder, extra))
            print(f"🗑️ Deleted extra audio: {extra}")
        audio_files = audio_files[:len(image_files)]

    total_files = len(image_files)
    print(f"\n📁 Synced: {len(image_files)} image(s) and {len(audio_files)} audio file(s).")
    print(f"🎬 Generating {total_files} image video(s)...\n")

    for idx, (image_file, audio_file) in enumerate(zip(image_files, audio_files)):
        image_path = os.path.join(image_folder, image_file)
        audio_path = os.path.join(audio_folder, audio_file)
        output_path = os.path.join(output_folder, f"{os.path.splitext(image_file)[0]}.mp4")

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
            print(f"[{idx + 1}/{total_files}] ❌ Failed on {image_file}")
            print(f"    Error: {e}\n")
