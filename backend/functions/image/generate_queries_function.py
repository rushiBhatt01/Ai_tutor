import os
import json
import random
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from functions.script.cerebras_client import (
    resolve_cerebras_api_key,
    generate_cerebras_completion,
    strip_markdown_code_fences,
    CEREBRAS_DEFAULT_MODEL,
)


def resolve_gemini_api_key() -> Optional[str]:
    """Retrieve Gemini API key from env or apikeys.json."""
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        keys_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "apikeys.json"))
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


def generate_storyboard_slide_specs(
    topic_name: str,
    scenes: list,
    categories: List[str] | None = None,
) -> Dict[int, Dict[str, Any]]:
    """Generate concise slide copy and diagram plans for all scenes in one API call."""
    if not scenes:
        return {}

    categories = categories or ["KEY_CONCEPTS"] * len(scenes)
    scene_payload = [
        {
            "scene_id": scene.scene_id,
            "category": categories[idx],
            "key_concept": scene.key_concept,
            "visual_intent": scene.visual_query,
            "narration": scene.narration,
        }
        for idx, scene in enumerate(scenes)
    ]
    prompt = (
        f"Create one PowerPoint-style slide specification for each scene in a tutorial about '{topic_name}'.\n"
        "The spoken narration is for audio only. Do not copy sentences from it onto slides.\n"
        "Write for scanning: each title is at most 6 words. Use short, informative phrases, not narration sentences.\n"
        "For INTRO_OVERVIEW, KEY_CONCEPTS, and SUMMARY_CONCLUSION slides, provide 3 or 4 informative bullets, each at most 10 words.\n"
        "For other slides, provide 2 or 3 bullets, each at most 8 words.\n"
        "Choose layout_type from flowchart, cycle, concept_map, or semantic_triple. Use semantic_triple for entity relationships or subject-predicate-object triples, flowchart for ordered steps, cycle for a repeating loop, "
        "and concept_map for related ideas. Do not use flowcharts on every slide; reserve them for real sequences.\n"
        "ARCHITECTURE_STRUCTURE slides must use flowchart.\n"
        "Give 3 or 4 diagram_nodes in meaningful order. Each node is a concrete label of at most 4 words. "
        "For flowcharts, nodes are process steps; for cycles, nodes are loop stages; for concept maps, the first node is central.\n"
        "Use plain text only. Do not include emoji, arrows, bullets, decorative glyphs, or unusual symbols.\n"
        "Use only facts supported by each scene. Keep each slide distinct from its neighbors.\n"
        "Return strict JSON with this shape: {\"slides\":[{\"scene_id\":0,\"title\":\"...\","
        "\"bullets\":[\"...\"],\"layout_type\":\"flowchart\",\"diagram_nodes\":[\"...\"]}]}\n"
        f"Create exactly {len(scenes)} slides, preserving scene IDs and order.\n\n"
        f"SCENES:\n{json.dumps(scene_payload, ensure_ascii=False)}"
    )

    def normalize(raw_text: str) -> Dict[int, Dict[str, Any]]:
        payload = json.loads(strip_markdown_code_fences(raw_text))
        items = payload.get("slides") if isinstance(payload, dict) else None
        if not isinstance(items, list) or len(items) != len(scenes):
            raise ValueError("Slide planner must return exactly one slide per scene")

        expected_ids = {scene.scene_id for scene in scenes}
        category_by_id = {item["scene_id"]: item["category"] for item in scene_payload}
        normalized = {}
        for item in items:
            scene_id = item.get("scene_id")
            if scene_id not in expected_ids or scene_id in normalized:
                raise ValueError("Slide planner returned missing, duplicate, or unknown scene IDs")

            def concise(value: Any, words: int) -> str:
                return " ".join(str(value or "").replace("\n", " ").split()[:words]).strip()

            layout = item.get("layout_type", "concept_map")
            if layout not in {"flowchart", "cycle", "concept_map", "semantic_triple", "triple"}:
                layout = "concept_map"
            category = category_by_id[scene_id]
            if category == "ARCHITECTURE_STRUCTURE":
                layout = "flowchart"
            raw_bullets = item.get("bullets", [])
            raw_nodes = item.get("diagram_nodes", [])
            if not isinstance(raw_bullets, list) or not isinstance(raw_nodes, list):
                raise ValueError(f"Slide {scene_id} bullets and diagram_nodes must be arrays")
            detailed_categories = {"INTRO_OVERVIEW", "KEY_CONCEPTS", "SUMMARY_CONCLUSION"}
            bullet_limit = 4 if category in detailed_categories else 3
            bullet_words = 10 if category in detailed_categories else 8
            minimum_bullets = 3 if category in detailed_categories else 2
            bullets = [concise(value, bullet_words).rstrip(".,;:") for value in raw_bullets if concise(value, bullet_words)][:bullet_limit]
            nodes = [concise(value, 4) for value in raw_nodes if concise(value, 4)][:4]
            if len(bullets) < minimum_bullets or len(nodes) < 3:
                raise ValueError(f"Slide {scene_id} is missing concise bullets or diagram nodes")
            normalized[scene_id] = {
                "title": concise(item.get("title"), 6) or f"{topic_name} key idea",
                "bullets": bullets,
                "category": category,
                "layout_type": layout,
                "diagram_nodes": nodes,
                "content_source": "llm_slide_planner",
            }
        return normalized

    cerebras_key = resolve_cerebras_api_key()
    if cerebras_key:
        try:
            raw_text = generate_cerebras_completion(
                prompt=prompt,
                system_prompt="You design concise visual teaching slides and return valid JSON only.",
                model=CEREBRAS_DEFAULT_MODEL,
                temperature=0.2,
                max_tokens=2400,
                json_mode=True,
                api_key=cerebras_key,
            )
            if raw_text:
                return normalize(raw_text)
        except Exception as error:
            print(f"⚠️ Cerebras slide planning failed: {error}. Trying Gemini fallback.")

    gemini_key = resolve_gemini_api_key()
    if gemini_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=2400,
                    response_mime_type="application/json",
                ),
            )
            if response.text:
                return normalize(response.text)
        except Exception as error:
            print(f"⚠️ Gemini slide planning failed: {error}. Using concise deterministic slides.")

    ignored = {"the", "and", "for", "with", "from", "that", "this", "into", "then", "when", "where", "what"}
    fallback_specs = {}
    detailed_categories = {"INTRO_OVERVIEW", "KEY_CONCEPTS", "SUMMARY_CONCLUSION"}
    for idx, scene in enumerate(scenes):
        category = categories[idx]
        concept_words = scene.key_concept.split()
        words = re.findall(r"[A-Za-z0-9+#.-]+", f"{scene.key_concept} {scene.visual_query}")
        nodes = []
        for word in words:
            label = word.strip(".,:;!?()[]")
            if len(label) > 2 and label.lower() not in ignored and label.lower() not in {node.lower() for node in nodes}:
                nodes.append(" ".join(label.split()[:4]))
            if len(nodes) == 4:
                break
        if len(nodes) < 3:
            nodes.extend(label for label in ["Key idea", "Outcome", "Result"] if label.lower() not in {node.lower() for node in nodes})
        nodes = nodes[:4]
        link_summary = " ".join((" → ".join(nodes[:2])).split()[:5])
        bullets = ["Focus: " + " ".join(concept_words[:7]), "Link: " + link_summary]
        if category in detailed_categories:
            bullets.append("Takeaway: " + " ".join(nodes[2:4]))
        fallback_specs[scene.scene_id] = {
            "title": " ".join(concept_words[:6]) or f"{topic_name} key idea",
            "bullets": bullets,
            "layout_type": "semantic_triple" if any(k in f"{scene.narration} {scene.key_concept}".lower() for k in ("triple", "rdf", "sparql", "knowledge graph", "predicate")) else ("flowchart" if category == "ARCHITECTURE_STRUCTURE" else "concept_map"),
            "category": category,
            "diagram_nodes": nodes[:4],
            "content_source": "deterministic_fallback",
        }
    return fallback_specs
