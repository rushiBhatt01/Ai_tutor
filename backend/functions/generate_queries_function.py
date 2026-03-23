import cohere
import json
import random

def generate_image_queries(topic_name, chunks):
    """
    Use Cohere to extract highly specific, 2-5 word visual search queries based on the chunks.
    """
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        selected_key = os.environ.get("COHERE_API_KEY")
        co = cohere.ClientV2(selected_key)
        
        prompt = (
            f"You are an expert visual director for a video about '{topic_name}'. "
            f"I have {len(chunks)} chunks of a script. For each chunk, provide EXACTLY ONE highly descriptive, "
            f"2-5 word image search query that perfectly visually represents the chunk without using quotes, prefixes, special characters or bullet points.\n\n"
        )
        for i, c in enumerate(chunks):
            prompt += f"[Chunk {i+1}]: {c}\n"
        
        prompt += "\nFormat your response as a simple list separated by newlines, with no extra text or numbering. EXACTLY ONE query per line. Do not write 'Query:'"

        response = co.chat(
            model="command-a-03-2025",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        
        text: str = str(response.message.content[0].text)
        queries: list[str] = [str(q).strip().strip("-").strip(".").strip("\"").strip("'").strip() for q in text.split("\n") if str(q).strip()]
        
        # Ensure we always have enough queries
        while len(queries) < len(chunks):
            queries.append(f"{topic_name} concept art")
        
        return queries[:len(chunks)]
    
    except Exception as e:
        print(f"Failed to generate queries with Cohere: {e}")
        # Fallback generic specific queries
        return [f"{topic_name} illustration {i}" for i in range(len(chunks))]
