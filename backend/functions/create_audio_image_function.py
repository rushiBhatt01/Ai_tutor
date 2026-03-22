from langchain.text_splitter import RecursiveCharacterTextSplitter
from functions.create_speech_function import create_speech
from functions.get_image_function import get_image
from functions.subt import generate_srt
from functions.generate_queries_function import generate_image_queries

def create_audio_image(topic_name, script, character_name, timestamp):

    character_dict = {'Benjamin': "en-IE-ConnorNeural",
                      'Sophia': 'ar-SA-ZariyahNeural'}

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=250,
        chunk_overlap=0,
        length_function=len,
    )

    chunks = text_splitter.split_text(script)
    print(chunks)
   
    count = 0
   
    for i in chunks:
        create_speech(i, f'{timestamp}/audio/{count}.wav',
                      character_dict[character_name])
        
        count = count + 1

    count = 0
    generate_srt(chunks, f"{timestamp}/audio", f"{timestamp}/subtitles.srt")

    print("Generating context-aware image queries with LLM...")
    image_queries = generate_image_queries(topic_name, chunks)
    print("Queries generated:", image_queries)

    get_image(image_queries, timestamp)
