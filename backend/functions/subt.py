from pydub import AudioSegment
from datetime import timedelta

def format_time(seconds):
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    milliseconds = int((td.total_seconds() - total_seconds) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"

def generate_srt(script_chunks, audio_folder, output_srt):
    current_time = 0
    srt_content = ""

    for i, chunk_text in enumerate(script_chunks):
        audio_path = f"{audio_folder}/{i}.wav"
        audio = AudioSegment.from_file(audio_path)
        duration = len(audio) / 1000  # milliseconds → seconds

        start_time = format_time(current_time)
        end_time = format_time(current_time + duration)
        srt_content += f"{i+1}\n{start_time} --> {end_time}\n{chunk_text}\n\n"
        current_time += duration

    with open(output_srt, "w", encoding="utf-8") as f:
        f.write(srt_content)

    print(f"SRT file created: {output_srt}")
