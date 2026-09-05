import os
import json
import random
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

def create_script(topic_name, level_of_explanation, age, creativity_level, humour_level, character_name="Tutor"):
    """
    Generates a structured, comprehensive educational video tutorial script
    using the Gemini 2.5-Flash model with audio TTS and Wav2Lip animation formatting.
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

    # Resolve API Key (checking GEMINI_API_KEY -> GOOGLE_API_KEY -> apikeys.json)
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

    if not api_key:
        raise ValueError(
            "Gemini API key not found. Please set GEMINI_API_KEY or GOOGLE_API_KEY "
            "in your environment or backend/.env file."
        )

    # Initialize Google GenAI client
    client = genai.Client(api_key=api_key)

    # Redefined prompt for Gemini 2.5-Flash
    prompt_content = (
        f"You are {character_name}, an expert educator and captivating video tutorial narrator.\n"
        f"Write a structured, comprehensive, and engaging video tutorial script explaining '{topic_name}' "
        f"tailored for a {age}-year-old audience.\n\n"
        f"NARRATIVE STRUCTURE:\n"
        f"The script must flow naturally as a spoken monologue across these 7 sequential sections:\n"
        f"1. INTRODUCTION: High-level overview, hook, and clear definition of {topic_name}.\n"
        f"2. KEY CONCEPTS: Core terminology, principles, and fundamental building blocks.\n"
        f"3. ARCHITECTURE & STRUCTURE: System layout, key components, and internal design.\n"
        f"4. WORKFLOW & PROCESS: Step-by-step execution flow and how components interact.\n"
        f"5. PRACTICAL EXAMPLE: A realistic use case, practical scenario, or concrete demonstration.\n"
        f"6. BENEFITS & ADVANTAGES: Major pros, trade-offs, and why this concept matters.\n"
        f"7. SUMMARY & CONCLUSION: Key takeaways and a memorable wrap-up.\n\n"
        f"STYLE & TONAL GUIDELINES:\n"
        f"- {level_string}\n"
        f"- {creativity_string}\n"
        f"- {humour_string}\n"
        f"- Speak in first-person as {character_name} with an enthusiastic, encouraging, and clear voice.\n\n"
        f"CRITICAL FORMATTING RULES FOR AUDIO TTS & LIP-SYNC (Wav2Lip):\n"
        f"1. Output ONLY the raw spoken text narration meant to be read aloud by Text-to-Speech.\n"
        f"2. Absolutely NO markdown formatting (no asterisks '*', hashtags '#', bullet points, or underline).\n"
        f"3. Absolutely NO stage directions, camera instructions, or brackets (e.g. do NOT include '[Pause]', '(Smiles)', '[Screen shows...]').\n"
        f"4. Do NOT include section headers or labels like 'Introduction:' or 'Key Concepts:'. Transition smoothly using natural spoken transition phrases.\n"
        f"5. Conclude with a warm, formal sign-off: 'Sincerely, {character_name}.'\n"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt_content,
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=1200,
            )
        )
        script_text = response.text.strip() if response.text else ""

        # Clean-up to strip any markdown symbols or stage directions for TTS safety
        script_text = re.sub(r'[*#_~`]', '', script_text)
        script_text = re.sub(r'\[.*?\]|\(.*?\)', '', script_text)
        script_text = re.sub(r' +', ' ', script_text).strip()

        return script_text

    except Exception as e:
        print(f"❌ Error invoking Gemini 2.5-Flash model for script generation: {e}")
        raise e
