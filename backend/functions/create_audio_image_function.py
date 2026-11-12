import os
import sys
import re

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
from typing import List, Optional
from functions.create_speech_function import create_speech
from functions.get_image_function import get_image
from functions.generate_queries_function import generate_storyboard_slide_specs
from functions.visual_artifacts import visual_scene_fingerprint


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

    if storyboard is None:
        from functions.create_storyboard_function import generate_fallback_storyboard
        storyboard = generate_fallback_storyboard(topic_name, script)

    from functions.visual_routing import route_storyboard
    route_storyboard(storyboard)

    character_dict = {
        'Benjamin': "en-IE-ConnorNeural",
        'Sophia': 'ar-SA-ZariyahNeural',
    }

    voice = character_dict.get(character_name, "en-IE-ConnorNeural")

    # Ensure output directories exist
    os.makedirs(os.path.join(timestamp, "audio"), exist_ok=True)
    os.makedirs(os.path.join(timestamp, "images"), exist_ok=True)

    # ──────────────────────────────────────────────────────────
    # Storyboard-driven path
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
            "scene_fingerprint": visual_scene_fingerprint(scene),
            "category": cat,
            "title": slide_spec.get("title") or scene.on_screen_text or scene.key_concept,
            "bullets": slide_spec.get("bullets", [scene.key_concept]),
            "code_snippet": None,
            "chunk_text": scene.narration,
            "visual_query": scene.visual_query,
            "must_show": scene.must_show or [scene.key_concept],
            "must_not_show": scene.must_not_show,
            "image_search_enabled": scene.visual_type in {"web_image", "hybrid_image", "hybrid_gif"},
            "visual_type": scene.visual_type,
            "layout_type": slide_spec.get("layout_type", "concept_map"),
            "diagram_nodes": slide_spec.get("diagram_nodes", []),
            "content_source": slide_spec.get("content_source", "deterministic_fallback"),
        })

    # ── 3. HD Slide Canvas generation ──
    get_image(chunk_queries, timestamp, topic_name=topic_name)
