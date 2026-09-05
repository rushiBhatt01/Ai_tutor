from langchain_text_splitters import RecursiveCharacterTextSplitter
from functions.create_speech_function import create_speech
from functions.get_image_function import get_image
from functions.generate_queries_function import generate_image_queries


def create_audio_image(topic_name, script, character_name, timestamp):
    """
    Split the script into chunks, synthesise TTS audio for each chunk
    with a chunk-id-based filename (seg_0.wav, seg_1.wav, ...),
    then fetch one image per chunk using Scrapling (seg_0.jpg, seg_1.jpg, ...).
    """

    character_dict = {
        'Benjamin': "en-IE-ConnorNeural",
        'Sophia': 'ar-SA-ZariyahNeural',
    }

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=250,
        chunk_overlap=0,
        length_function=len,
    )

    chunks = text_splitter.split_text(script)
    print(f"Split script into {len(chunks)} chunks")

    # ── 1. Audio synthesis (chunk-id naming) ──
    for idx, chunk_text in enumerate(chunks):
        chunk_id = f"seg_{idx}"
        audio_path = f'{timestamp}/audio/{chunk_id}.wav'
        create_speech(chunk_text, audio_path, character_dict[character_name])

    # ── 2. LLM-powered visual query generation (returns chunk-indexed dicts) ──
    print("Generating context-aware image queries with LLM...")
    chunk_queries = generate_image_queries(topic_name, chunks)
    print("Queries generated:", [q["query"] for q in chunk_queries])

    # ── 3. Image scraping via Scrapling (chunk-id naming) ──
    get_image(chunk_queries, timestamp)

