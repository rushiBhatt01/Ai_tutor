import os
import json
import random
import re
from typing import List, Dict, Any
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Common English stopwords to filter out when extracting technical keywords
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "can", "could", "may", "might", "must", "and", "but", "or",
    "nor", "for", "yet", "so", "in", "on", "at", "to", "from", "by", "with",
    "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "up", "down", "out", "off", "over", "under",
    "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "any", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "not", "only", "own", "same", "than",
    "too", "very", "this", "that", "these", "those", "sincerely", "welcome",
    "hello", "today", "let", "lets", "going", "understand", "explore", "learn"
}

CATEGORY_TAXONOMY = [
    ("INTRO_OVERVIEW", "Introduction & Overview"),
    ("KEY_CONCEPTS", "Key Concepts"),
    ("ARCHITECTURE_STRUCTURE", "Architecture & Structure"),
    ("WORKFLOW_PROCESS", "Workflow & Process"),
    ("PRACTICAL_EXAMPLE", "Practical Example"),
    ("BENEFITS_COMPARISON", "Benefits & Advantages"),
    ("SUMMARY_CONCLUSION", "Summary & Conclusion")
]

def extract_key_nouns(chunk_text: str, limit: int = 3) -> str:
    """Extract top technical nouns/keywords from chunk text."""
    words = re.findall(r'\b[A-Za-z0-9_-]{3,}\b', chunk_text)
    filtered = [w for w in words if w.lower() not in STOPWORDS]
    sorted_words = sorted(filtered, key=lambda w: (w[0].isupper(), len(w)), reverse=True)
    seen = []
    for w in sorted_words:
        if w.lower() not in [x.lower() for x in seen]:
            seen.append(w)
        if len(seen) >= limit:
            break
    return " ".join(seen)

def resolve_gemini_api_key() -> str:
    """Retrieve Gemini API key from env or apikeys.json."""
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        keys_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apikeys.json"))
        if os.path.exists(keys_file):
            try:
                with open(keys_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    keys = data.get("api_keys", [])
                    if keys:
                        api_key = random.choice(keys)
            except Exception as e:
                print(f"Warning loading apikeys.json: {e}")
    return api_key

def generate_fallback_slide_spec(topic_name: str, idx: int, total_chunks: int, chunk_text: str) -> Dict[str, Any]:
    """Deterministic fallback generator for slide specs if LLM call is unavailable."""
    cat_idx = 0 if total_chunks == 1 else min(int((idx / (total_chunks - 1)) * (len(CATEGORY_TAXONOMY) - 1)), len(CATEGORY_TAXONOMY) - 1)
    cat_name, cat_label = CATEGORY_TAXONOMY[cat_idx]
    
    keywords = extract_key_nouns(chunk_text, limit=3)
    title = f"{topic_name}: {keywords.title()}" if keywords else f"{topic_name}: {cat_label}"
    
    # Split text into bullet sentences
    raw_sentences = re.split(r'(?<=[.!?])\s+', chunk_text.strip())
    bullets = [s.strip() for s in raw_sentences if s.strip()][:4]
    if not bullets:
        bullets = [chunk_text[:100]]

    return {
        "chunk_id": f"seg_{idx}",
        "category": cat_name,
        "title": title,
        "bullets": bullets,
        "code_snippet": None,
        "chunk_text": chunk_text
    }

def generate_image_queries(topic_name: str, chunks: List[str]) -> List[Dict[str, Any]]:
    """
    Generate structured, context-aware slide specifications for each chunk.
    Uses Gemini 2.5-Flash to produce punchy slide titles, bullet points, and code snippets,
    with an automatic deterministic fallback if LLM is unavailable.
    """
    api_key = resolve_gemini_api_key()
    num_chunks = len(chunks)

    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = (
                f"You are a professional educational slide designer for a video tutorial about '{topic_name}'.\n"
                f"Below are {num_chunks} sequential narration script chunks. For each chunk, generate structured slide JSON data.\n\n"
                f"CRITICAL FORMATTING INSTRUCTIONS:\n"
                f"Output MUST be a valid JSON array containing exactly {num_chunks} objects (one per chunk in exact order).\n"
                f"Each object must have these fields:\n"
                f"- 'title': String (short, clear, punchy 3-7 word slide title summarizing the chunk)\n"
                f"- 'category': String (one of: 'INTRO_OVERVIEW', 'KEY_CONCEPTS', 'ARCHITECTURE_STRUCTURE', 'WORKFLOW_PROCESS', 'PRACTICAL_EXAMPLE', 'BENEFITS_COMPARISON', 'SUMMARY_CONCLUSION')\n"
                f"- 'bullets': List of 2 to 4 concise strings summarizing key facts from the chunk\n"
                f"- 'code_snippet': String or null (provide a short code snippet or example if applicable, else null)\n\n"
                f"SCRIPT CHUNKS:\n"
            )
            for idx, c_text in enumerate(chunks):
                prompt += f"--- Chunk seg_{idx} ---\n{c_text}\n"

            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json"
                )
            )

            if response.text:
                items = json.loads(response.text)
                if isinstance(items, list) and len(items) == num_chunks:
                    specs = []
                    for idx, item in enumerate(items):
                        specs.append({
                            "chunk_id": f"seg_{idx}",
                            "category": item.get("category", CATEGORY_TAXONOMY[min(idx, len(CATEGORY_TAXONOMY)-1)][0]),
                            "title": item.get("title", f"{topic_name} - Segment {idx+1}"),
                            "bullets": item.get("bullets", [chunks[idx][:80]]),
                            "code_snippet": item.get("code_snippet"),
                            "chunk_text": chunks[idx]
                        })
                    return specs
        except Exception as e:
            print(f"⚠️ Gemini slide spec generation warning: {e}. Falling back to rule engine.")

    # Fallback to rule engine if LLM fails or API key is absent
    return [generate_fallback_slide_spec(topic_name, idx, num_chunks, chunk_text) for idx, chunk_text in enumerate(chunks)]

