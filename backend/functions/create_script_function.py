import os
import json
import random
import re
from dotenv import load_dotenv

from functions.cerebras_client import (
    resolve_cerebras_api_key,
    generate_cerebras_completion,
    CEREBRAS_DEFAULT_MODEL,
)


def sanitize_script_for_tts(script_text: str) -> str:
    """
    Strips all markdown formatting symbols (##, **, *, #, _, ~, `, -, etc.)
    and bracketed stage directions so Text-to-Speech never dictates symbols aloud.
    """
    if not script_text:
        return ""
    # Remove markdown header tokens (e.g., ### 1. Introduction)
    script_text = re.sub(r'#{1,6}\s*', '', script_text)
    # Remove bold, italic, code backticks, symbols
    script_text = re.sub(r'[*#_~`>|\\]', '', script_text)
    # Remove bracketed directions like [Pause], (smiling), [Screen shows...]
    script_text = re.sub(r'\[.*?\]|\(.*?\)', '', script_text)
    # Remove horizontal rules and repeated dashes
    script_text = re.sub(r'-{2,}', ' ', script_text)
    # Clean up whitespace
    script_text = re.sub(r'\n{3,}', '\n\n', script_text)
    script_text = re.sub(r'[ \t]+', ' ', script_text).strip()
    return script_text


def create_script(topic_name, level_of_explanation, age, creativity_level, humour_level, character_name="Tutor"):
    """
    Generates a structured, comprehensive educational video tutorial script
    using Cerebras llama3.1-8b (lowest credit consumption model: ~$0.10/M tokens),
    with seamless fallback to Gemini if Cerebras key is absent.
    Formatted cleanly for TTS and Wav2Lip animation.
    """
    load_dotenv()
    age = str(age)

    # Define explanation level guidance
    if level_of_explanation == 'beginner':
        level_string = (
            "Explain this topic in simple, intuitive terms suitable for a beginner. "
            "Focus on foundational logic, intuitive concepts, and core importance without overly complex technical jargon."
        )
    elif level_of_explanation == 'intermediate':
        level_string = (
            "Explain the topic with moderate depth and technical clarity. "
            "Cover underlying mechanisms, practical functionality, and key architecture details clearly."
        )
    else:
        level_string = (
            "Provide an in-depth, comprehensive technical explanation. "
            "Delve into intricate architectural details, inner workings, optimization trade-offs, and practical implementations."
        )

    def _to_int(val, default=5):
        try:
            return int(val)
        except (ValueError, TypeError):
            mapping = {"low": 2, "medium": 5, "high": 8}
            return mapping.get(str(val).lower(), default)

    creativity_level = _to_int(creativity_level, 8)
    humour_level = _to_int(humour_level, 6)

    # Define creativity guidance
    if creativity_level < 4:
        creativity_string = "Maintain a straightforward, direct explanatory approach."
    elif creativity_level < 7:
        creativity_string = "Use creative analogies and relatable real-world examples to make abstract concepts accessible."
    else:
        creativity_string = "Use highly imaginative visual analogies, vibrant metaphors, and engaging mental pictures throughout."

    # Define humour guidance
    if humour_level < 4:
        humour_string = "Keep the tone professional, clear, and informative."
    elif humour_level < 7:
        humour_string = "Incorporate a lighthearted, friendly humor to keep the viewer entertained."
    else:
        humour_string = "Add funny observations, witty remarks, and playful banter to make the learning experience hilarious and engaging."

    # Concise prompt targeting 60-90 seconds of narration (150-225 words)
    system_prompt = (
        f"You are {character_name}, an expert educator and captivating video tutorial narrator.\n"
        f"Output ONLY plain, spoken prose narration for Text-to-Speech.\n"
        f"Do NOT include markdown headers, bolding, bullet points, stage directions, or brackets."
    )
    user_prompt = (
        f"Write a SHORT, punchy video tutorial script explaining '{topic_name}' "
        f"tailored for a {age}-year-old audience.\n\n"
        f"ABSOLUTE LENGTH CONSTRAINT:\n"
        f"The ENTIRE script MUST be between 150 and 225 words total (60 to 90 seconds of spoken narration). "
        f"Be concise, direct, and impactful. Every sentence must earn its place.\n\n"
        f"NARRATIVE STRUCTURE (4 brief sections, flowing naturally as speech):\n"
        f"1. HOOK & INTRO: One attention-grabbing sentence, then a crisp definition of {topic_name} (2-3 sentences max).\n"
        f"2. CORE EXPLANATION: The essential 'what' and 'how' — cover only the most important concepts (3-4 sentences max).\n"
        f"3. QUICK EXAMPLE OR ANALOGY: One vivid, relatable example or analogy that makes the concept click (2-3 sentences max).\n"
        f"4. WRAP-UP: One punchy takeaway and a brief sign-off (1-2 sentences max).\n\n"
        f"STYLE & TONAL GUIDELINES:\n"
        f"- {level_string}\n"
        f"- {creativity_string}\n"
        f"- {humour_string}\n"
        f"- Speak in first-person as {character_name} with an enthusiastic, encouraging, and clear voice.\n\n"
        f"CRITICAL FORMATTING RULES FOR TEXT-TO-SPEECH & WAV2LIP:\n"
        f"1. Output ONLY plain, raw spoken prose narration meant to be read aloud by Text-to-Speech.\n"
        f"2. NEVER use markdown symbols: NO asterisks, hashtags, underscores, backticks, or bullet points.\n"
        f"3. Do NOT include stage directions, camera instructions, or brackets.\n"
        f"4. Do NOT include section headers. Use natural spoken transition phrases instead.\n"
        f"5. Conclude with a warm sign-off: 'Sincerely, {character_name}.'\n"
        f"6. Remember: MAXIMUM 225 words. Count carefully.\n"
    )

    # 1. Primary path: Cerebras (lowest cost Llama 3.1 8B)
    cerebras_key = resolve_cerebras_api_key()
    if cerebras_key:
        try:
            print(f"🚀 Generating script using Cerebras ({CEREBRAS_DEFAULT_MODEL} - lowest credit consumption)...")
            script_text = generate_cerebras_completion(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=CEREBRAS_DEFAULT_MODEL,
                temperature=0.3,
                max_tokens=450,
                api_key=cerebras_key,
            )
            sanitized_script = sanitize_script_for_tts(script_text)
            words = sanitized_script.split()
            if len(words) > 240:
                sanitized_script = " ".join(words[:240])
                last_period = sanitized_script.rfind(".")
                if last_period > len(sanitized_script) * 0.6:
                    sanitized_script = sanitized_script[:last_period + 1]
            return sanitized_script
        except Exception as cerebras_err:
            print(f"⚠️ Cerebras generation error: {cerebras_err}. Trying Gemini fallback if available...")

    # 2. Fallback path: Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not gemini_key:
        keys_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apikeys.json"))
        if os.path.exists(keys_file):
            try:
                with open(keys_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    keys = data.get("api_keys", [])
                    if keys:
                        gemini_key = random.choice(keys)
            except Exception:
                pass

    if gemini_key:
        try:
            print("ℹ️ Invoking Gemini fallback for script generation...")
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=f"{system_prompt}\n\n{user_prompt}",
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=450,
                )
            )
            script_text = response.text.strip() if response.text else ""
            sanitized_script = sanitize_script_for_tts(script_text)
            words = sanitized_script.split()
            if len(words) > 240:
                sanitized_script = " ".join(words[:240])
                last_period = sanitized_script.rfind(".")
                if last_period > len(sanitized_script) * 0.6:
                    sanitized_script = sanitized_script[:last_period + 1]
            return sanitized_script
        except Exception as gemini_err:
            print(f"❌ Gemini fallback error: {gemini_err}")
            raise gemini_err

    raise ValueError(
        "No LLM API key found. Please set CEREBRAS_API_KEY (recommended for lowest cost) "
        "or GEMINI_API_KEY in backend/.env."
    )
