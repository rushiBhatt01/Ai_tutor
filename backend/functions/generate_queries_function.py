import re
from typing import List, Dict, Any

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
    ("INTRO_OVERVIEW", "introduction conceptual diagram overview HD"),
    ("KEY_CONCEPTS", "key concepts core principles infographic HD"),
    ("ARCHITECTURE_STRUCTURE", "system architecture component layout diagram HD"),
    ("WORKFLOW_PROCESS", "workflow process sequence flow chart diagram HD"),
    ("PRACTICAL_EXAMPLE", "real world practical code example demo HD"),
    ("BENEFITS_COMPARISON", "advantages comparison matrix chart HD"),
    ("SUMMARY_CONCLUSION", "summary key takeaways conclusion diagram HD")
]

def extract_key_nouns(chunk_text: str, limit: int = 3) -> str:
    """
    Extract top technical nouns/keywords from a chunk text without AI calls.
    Uses regex term extraction and stopword filtering.
    """
    words = re.findall(r'\b[A-Za-z0-9_-]{3,}\b', chunk_text)
    filtered = [w for w in words if w.lower() not in STOPWORDS]
    
    # Sort terms prioritizing capitalized proper nouns and longer technical words
    sorted_words = sorted(filtered, key=lambda w: (w[0].isupper(), len(w)), reverse=True)
    
    seen = []
    for w in sorted_words:
        if w.lower() not in [x.lower() for x in seen]:
            seen.append(w)
        if len(seen) >= limit:
            break
            
    return " ".join(seen)

def generate_image_queries(topic_name: str, chunks: List[str]) -> List[Dict[str, Any]]:
    """
    Build structured, context-aware image queries using a 100% deterministic,
    zero-AI rule engine. Maps chunks proportionally across a 7-category taxonomy.
    """
    num_chunks = len(chunks)
    queries: List[Dict[str, Any]] = []

    for idx, chunk_text in enumerate(chunks):
        chunk_id = f"seg_{idx}"

        # Proportional mapping to 7-category visual taxonomy
        if num_chunks == 1:
            cat_idx = 0
        else:
            cat_idx = min(
                int((idx / (num_chunks - 1)) * (len(CATEGORY_TAXONOMY) - 1)),
                len(CATEGORY_TAXONOMY) - 1
            )

        cat_name, cat_query_pattern = CATEGORY_TAXONOMY[cat_idx]
        keywords = extract_key_nouns(chunk_text, limit=3)

        # Primary search query combining topic, chunk keywords, and taxonomy pattern
        if keywords:
            query = f"{topic_name} {keywords} {cat_query_pattern}".strip()
        else:
            query = f"{topic_name} {cat_query_pattern}".strip()

        queries.append({
            "chunk_id": chunk_id,
            "category": cat_name,
            "query": query,
            "keywords": keywords,
            "chunk_text": chunk_text
        })

    return queries
