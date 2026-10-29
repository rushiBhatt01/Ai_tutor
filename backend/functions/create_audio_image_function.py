import os
import re
from typing import List, Optional
from functions.create_speech_function import create_speech
from functions.get_image_function import get_image
from functions.generate_queries_function import generate_image_queries, generate_storyboard_slide_specs


def split_script_into_smart_chunks(script: str, min_chars: int = 200, max_chars: int = 450) -> List[str]:
    """
    Splits spoken script into coherent sentence-boundary chunks.
    Guarantees zero mid-sentence cuts so TTS audio clips start and end on full sentences.
    Groups 2-3 sentences per chunk aiming for ~300-450 characters.

    Kept for backward compatibility when no Storyboard is available.
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


CATEGORY_CYCLE = [
    "INTRO_OVERVIEW",
    "KEY_CONCEPTS",
    "ARCHITECTURE_STRUCTURE",
    "WORKFLOW_PROCESS",
    "PRACTICAL_EXAMPLE",
    "BENEFITS_COMPARISON",
    "SUMMARY_CONCLUSION"
]


def create_audio_image(topic_name, script_or_storyboard, character_name, timestamp, storyboard=None):
    """
    Synthesize TTS audio and generate slide images for a video tutorial.

    Polymorphic signature: supports both
      create_audio_image(topic, storyboard, character, timestamp)
      create_audio_image(topic, script, character, timestamp, storyboard=storyboard)

    When a validated Storyboard object is provided, iterates over its scenes
    for narration and visual queries. Otherwise falls back to the legacy
    character-count chunking path for backward compatibility.
    """
    # Detect whether second arg is a Storyboard instance
    if hasattr(script_or_storyboard, "scenes"):
        storyboard = script_or_storyboard
        script = " ".join(s.narration for s in storyboard.scenes)
    else:
        script = script_or_storyboard or ""

    character_dict = {
        'Benjamin': "en-IE-ConnorNeural",
        'Sophia': 'ar-SA-ZariyahNeural',
    }

    voice = character_dict.get(character_name, "en-IE-ConnorNeural")

    # Ensure output directories exist
    os.makedirs(os.path.join(timestamp, "audio"), exist_ok=True)
    os.makedirs(os.path.join(timestamp, "images"), exist_ok=True)

    if storyboard is not None:
        # ──────────────────────────────────────────────────────────
        # Storyboard-driven path (Story 2.2)
        # ──────────────────────────────────────────────────────────
        print(f"🎬 Using storyboard with {len(storyboard.scenes)} scene(s)")
        total_scenes = len(storyboard.scenes)
        scene_categories = []
        for idx in range(total_scenes):
            if idx == 0:
                scene_categories.append("INTRO_OVERVIEW")
            elif idx == total_scenes - 1:
                scene_categories.append("SUMMARY_CONCLUSION")
            else:
                scene_categories.append(CATEGORY_CYCLE[min(idx, len(CATEGORY_CYCLE) - 2)])
        slide_specs = generate_storyboard_slide_specs(topic_name, storyboard.scenes, scene_categories)

        # ── 1. Audio synthesis per scene ──
        for scene in storyboard.scenes:
            chunk_id = f"seg_{scene.scene_id}"
            audio_path = os.path.join(timestamp, "audio", f"{chunk_id}.wav")
            print(f"  🔊 [{chunk_id}] Synthesizing narration ({len(scene.narration.split())} words)")
            create_speech(scene.narration, audio_path, voice)

        # ── 2. Build slide specs from storyboard scenes ──
        chunk_queries = []
        for idx, scene in enumerate(storyboard.scenes):
            cat = scene_categories[idx]
            slide_spec = slide_specs.get(scene.scene_id, {})

            chunk_queries.append({
                "chunk_id": f"seg_{scene.scene_id}",
                "scene_id": scene.scene_id,
                "category": cat,
                "title": slide_spec.get("title") or scene.on_screen_text or scene.key_concept,
                "bullets": slide_spec.get("bullets", [scene.key_concept]),
                "code_snippet": None,
                "chunk_text": scene.narration,
                "visual_query": scene.visual_query,
                "layout_type": slide_spec.get("layout_type", "concept_map"),
                "diagram_nodes": slide_spec.get("diagram_nodes", []),
                "content_source": slide_spec.get("content_source", "deterministic_fallback"),
            })

        # ── 3. HD Slide Canvas generation ──
        get_image(chunk_queries, timestamp, topic_name=topic_name)

    else:
        # ──────────────────────────────────────────────────────────
        # Legacy chunking path (backward compatibility)
        # ──────────────────────────────────────────────────────────
        chunks = split_script_into_smart_chunks(script)
        print(f"Split script into {len(chunks)} sentence-aligned chunk(s)")

        # ── 1. Audio synthesis (chunk-id naming) ──
        for idx, chunk_text in enumerate(chunks):
            chunk_id = f"seg_{idx}"
            audio_path = os.path.join(timestamp, "audio", f"{chunk_id}.wav")
            create_speech(chunk_text, audio_path, voice)

        # ── 2. LLM-powered slide spec generation (returns chunk-indexed dicts) ──
        print("Generating structured slide specs with LLM...")
        chunk_queries = generate_image_queries(topic_name, chunks)

        # ── 3. HD Slide Canvas generation (chunk-id naming) ──
        get_image(chunk_queries, timestamp, topic_name=topic_name)
