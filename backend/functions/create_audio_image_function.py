import re
from typing import List
from functions.create_speech_function import create_speech
from functions.get_image_function import get_image
from functions.generate_queries_function import generate_image_queries


def split_script_into_smart_chunks(script: str, min_chars: int = 200, max_chars: int = 450) -> List[str]:
    """
    Splits spoken script into coherent sentence-boundary chunks.
    Guarantees zero mid-sentence cuts so TTS audio clips start and end on full sentences.
    Groups 2-3 sentences per chunk aiming for ~300-450 characters.
    """
    if not script:
        return []

    # Split text by sentence-ending punctuation (. ! ? followed by space or newline)
    raw_sentences = re.split(r'(?<=[.!?])\s+|\n+', script.strip())
    sentences = [s.strip() for s in raw_sentences if s.strip()]

    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sentence_len = len(sentence)
        # If adding sentence stays under max_chars, or current chunk is below min_chars
        if current_length == 0 or (current_length + sentence_len <= max_chars) or (current_length < min_chars):
            current_chunk.append(sentence)
            current_length += sentence_len + 1
        else:
            # Commit current chunk
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_length = sentence_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def create_audio_image(topic_name, script, character_name, timestamp):
    """
    Split the script into sentence-boundary chunks, synthesize TTS audio for each chunk
    with a chunk-id-based filename (seg_0.wav, seg_1.wav, ...),
    then generate dynamic 1280x720 HD slide images per chunk (seg_0.jpg, seg_1.jpg, ...).
    """

    character_dict = {
        'Benjamin': "en-IE-ConnorNeural",
        'Sophia': 'ar-SA-ZariyahNeural',
    }

    chunks = split_script_into_smart_chunks(script)
    print(f"Split script into {len(chunks)} sentence-aligned chunk(s)")

    # ── 1. Audio synthesis (chunk-id naming) ──
    for idx, chunk_text in enumerate(chunks):
        chunk_id = f"seg_{idx}"
        audio_path = f'{timestamp}/audio/{chunk_id}.wav'
        create_speech(chunk_text, audio_path, character_dict[character_name])

    # ── 2. LLM-powered slide spec generation (returns chunk-indexed dicts) ──
    print("Generating structured slide specs with LLM...")
    chunk_queries = generate_image_queries(topic_name, chunks)

    # ── 3. HD Slide Canvas generation (chunk-id naming) ──
    get_image(chunk_queries, timestamp, topic_name=topic_name)


