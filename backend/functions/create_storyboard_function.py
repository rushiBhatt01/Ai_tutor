"""
AI Lesson Storyboard Planner.

Transforms a plain-text tutorial script into a validated Storyboard
of 3–8 pedagogical scenes using Cerebras AI (llama3.1-8b - lowest credit cost model),
with automatic 1-shot repair and fallback hierarchy:
  1. Primary: Cerebras Llama 3.1 8B structured JSON (~$0.10/M tokens).
  2. Fallback LLM: Gemini 2.5-Flash-Lite structured JSON.
  3. Deterministic: Sentence-based chunker that guarantees valid Storyboard output.
"""

import os
import json
import random
import re
from typing import Optional

from dotenv import load_dotenv
from pydantic import ValidationError

from functions.storyboard_schema import Scene, Storyboard
from functions.cerebras_client import (
    resolve_cerebras_api_key,
    generate_cerebras_completion,
    strip_markdown_code_fences,
    CEREBRAS_DEFAULT_MODEL,
)


# ---------------------------------------------------------------------------
# API Key Resolution
# ---------------------------------------------------------------------------

def _resolve_gemini_api_key() -> Optional[str]:
    """Retrieve Gemini API key from env or apikeys.json."""
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        keys_file = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "apikeys.json")
        )
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


# ---------------------------------------------------------------------------
# Deterministic Fallback Chunker
# ---------------------------------------------------------------------------

def generate_fallback_storyboard(topic_name: str, script: str) -> Storyboard:
    """
    Deterministically partition script into 3–5 scenes using sentence boundaries.
    Guarantees a valid Storyboard instance even if LLM is completely unavailable.
    """
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script.strip()) if s.strip()]
    if not sentences:
        sentences = [script.strip() or "Introduction to the topic."]

    # Target 3–5 scenes
    target_scenes = max(3, min(5, len(sentences)))
    chunk_size = max(1, len(sentences) // target_scenes)

    scenes = []
    for idx in range(target_scenes):
        start = idx * chunk_size
        end = start + chunk_size if idx < target_scenes - 1 else len(sentences)
        narration = " ".join(sentences[start:end]).strip()

        # Ensure narration meets minimum length constraint (20 chars)
        if len(narration) < 20:
            narration = narration + " " + topic_name + " explained clearly."

        # Extract a short title from the first sentence
        first_sentence = sentences[start] if start < len(sentences) else topic_name
        title_words = first_sentence.split()[:7]
        title = " ".join(title_words).rstrip(".,!?")
        if len(title) < 2:
            title = f"{topic_name} Part {idx + 1}"

        # Estimate duration from word count (~2.5 words/sec for TTS)
        word_count = len(narration.split())
        estimated_secs = max(3, min(90, int(word_count / 2.5)))

        scenes.append(Scene(
            scene_id=idx,
            key_concept=title[:160],
            narration=narration[:1200],
            visual_query=f"{topic_name} {title[:60]} educational diagram"[:180],
            on_screen_text=title[:120],
            estimated_seconds=estimated_secs,
        ))

    return Storyboard(title=topic_name[:120], scenes=scenes)


# ---------------------------------------------------------------------------
# LLM-Powered Storyboard Planner Prompts
# ---------------------------------------------------------------------------

_PLANNER_PROMPT_TEMPLATE = """You are a professional educational video storyboard planner.
Given the topic "{topic_name}" and the script below, create a teaching storyboard.

RULES:
- Split the script into 3 to 8 scenes. Preserve the script's teaching order.
- Use ONLY facts from the script. Do NOT add unsupported claims.
- Each scene's narration must be self-contained, speakable prose (no markdown).
- visual_query must describe a concrete educational image or diagram, not an abstract phrase.
- estimated_seconds should reflect spoken word count (~2.5 words/second).

OUTPUT FORMAT (strict JSON object):
{{
  "title": "...",
  "scenes": [
    {{
      "scene_id": 0,
      "key_concept": "...",
      "narration": "...",
      "visual_query": "...",
      "on_screen_text": "...",
      "estimated_seconds": 20
    }}
  ]
}}

SCRIPT:
{script}
"""

_REPAIR_PROMPT_TEMPLATE = """The previous JSON output failed validation with this error:
{error}

Please fix the JSON and return ONLY a corrected JSON object matching the exact schema.
Remember: scene_id values must start at 0 and be contiguous (0, 1, 2, ...).
All string fields must be non-empty. estimated_seconds must be between 3 and 90.
"""


def _parse_and_validate(raw_json: str) -> Storyboard:
    """Parse raw JSON string into a validated Storyboard model, stripping any code fences."""
    cleaned = strip_markdown_code_fences(raw_json)
    return Storyboard.model_validate_json(cleaned)


def create_storyboard(topic_name: str, script: str) -> Storyboard:
    """
    Generate a validated Storyboard from a tutorial script.

    Strategy:
      1. Primary: Call Cerebras (llama3.1-8b) with structured JSON output (lowest credits).
      2. If validation fails, attempt 1-shot repair.
      3. Fall back to Gemini if Cerebras is unavailable.
      4. Fall back to deterministic chunker if all LLM attempts fail.
    """
    prompt = _PLANNER_PROMPT_TEMPLATE.format(topic_name=topic_name, script=script)

    # ── Attempt 1: Cerebras llama3.1-8b (Lowest credit consumption) ──
    cerebras_key = resolve_cerebras_api_key()
    if cerebras_key:
        try:
            print(f"🎬 Generating storyboard with Cerebras ({CEREBRAS_DEFAULT_MODEL})...")
            raw_json = generate_cerebras_completion(
                prompt=prompt,
                system_prompt="You are an expert storyboard planner that outputs valid JSON matching the exact schema.",
                model=CEREBRAS_DEFAULT_MODEL,
                temperature=0.2,
                max_tokens=2000,
                json_mode=True,
                api_key=cerebras_key,
            )
            if raw_json:
                try:
                    storyboard = _parse_and_validate(raw_json)
                    print(f"✅ Storyboard generated: {len(storyboard.scenes)} scenes for '{topic_name}' via Cerebras")
                    return storyboard
                except (ValidationError, ValueError, json.JSONDecodeError) as first_error:
                    print(f"⚠️ Cerebras attempt 1 validation failed: {first_error}. Attempting 1-shot repair...")
                    repair_prompt = f"{prompt}\n\n" + _REPAIR_PROMPT_TEMPLATE.format(error=str(first_error))
                    repair_json = generate_cerebras_completion(
                        prompt=repair_prompt,
                        system_prompt="You are an expert storyboard planner that outputs valid JSON matching the exact schema.",
                        model=CEREBRAS_DEFAULT_MODEL,
                        temperature=0.1,
                        max_tokens=2000,
                        json_mode=True,
                        api_key=cerebras_key,
                    )
                    if repair_json:
                        storyboard = _parse_and_validate(repair_json)
                        print(f"✅ Storyboard repaired successfully via Cerebras: {len(storyboard.scenes)} scenes")
                        return storyboard
        except Exception as cerebras_error:
            print(f"⚠️ Cerebras storyboard generation failed: {cerebras_error}. Falling back to secondary provider...")

    # ── Attempt 2: Gemini Fallback ──
    gemini_key = _resolve_gemini_api_key()
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
                    max_output_tokens=2000,
                    response_mime_type="application/json",
                ),
            )
            raw_json = response.text.strip() if response.text else ""
            if raw_json:
                try:
                    storyboard = _parse_and_validate(raw_json)
                    print(f"✅ Storyboard generated: {len(storyboard.scenes)} scenes for '{topic_name}' via Gemini fallback")
                    return storyboard
                except (ValidationError, ValueError, json.JSONDecodeError) as first_error:
                    print(f"⚠️ Gemini attempt 1 validation failed: {first_error}. Trying repair...")
                    repair_prompt = _REPAIR_PROMPT_TEMPLATE.format(error=str(first_error))
                    repair_response = client.models.generate_content(
                        model="gemini-2.5-flash-lite",
                        contents=f"{prompt}\n\n{repair_prompt}",
                        config=types.GenerateContentConfig(
                            temperature=0.1,
                            max_output_tokens=2000,
                            response_mime_type="application/json",
                        ),
                    )
                    repair_json = repair_response.text.strip() if repair_response.text else ""
                    if repair_json:
                        storyboard = _parse_and_validate(repair_json)
                        print(f"✅ Storyboard repaired successfully via Gemini: {len(storyboard.scenes)} scenes")
                        return storyboard
        except Exception as gemini_error:
            print(f"⚠️ Gemini fallback storyboard generation failed: {gemini_error}")

    # ── Attempt 3: Deterministic Fallback ──
    print("🔄 Falling back to deterministic storyboard generation.")
    return generate_fallback_storyboard(topic_name, script)
