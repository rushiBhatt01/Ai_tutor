"""
Cerebras AI client integration for video tutorial generation.

Configured with 'llama3.1-8b' (Meta Llama 3.1 8B), the lowest credit cost model
available on Cerebras Inference (~$0.10 per million tokens input/output).
Provides text generation, structured JSON generation, and automatic sanitization.
"""

import os
import json
import random
import re
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()
# Default model: dynamically read from CEREBRAS_MODEL in .env, defaulting to gpt-oss-120b
CEREBRAS_DEFAULT_MODEL = os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b").strip()


def resolve_cerebras_api_key() -> Optional[str]:
    """
    Resolve Cerebras API key checking:
    1. CEREBRAS_API_KEY in os.environ
    2. backend/.env file
    3. backend/apikeys.json under 'cerebras_api_key' or 'cerebras_api_keys'
    """
    load_dotenv()
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if api_key and api_key.strip():
        return api_key.strip()

    # Fallback to backend/.env if not yet loaded in environ
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("CEREBRAS_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass

    # Fallback to apikeys.json
    keys_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apikeys.json"))
    if os.path.exists(keys_file):
        try:
            with open(keys_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                single = data.get("cerebras_api_key")
                if single:
                    return single.strip()
                multiple = data.get("cerebras_api_keys", [])
                if multiple:
                    return random.choice(multiple).strip()
        except Exception:
            pass

    return None


def get_cerebras_client(api_key: Optional[str] = None):
    """
    Initialize and return a Cerebras SDK client.
    Raises ValueError if no API key is available.
    """
    resolved_key = api_key or resolve_cerebras_api_key()
    if not resolved_key:
        raise ValueError(
            "Cerebras API key not found. Please set CEREBRAS_API_KEY in your "
            "backend/.env file or environment variables."
        )

    from cerebras.cloud.sdk import Cerebras
    return Cerebras(api_key=resolved_key)


def generate_cerebras_completion(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    json_mode: bool = False,
    api_key: Optional[str] = None,
) -> str:
    """
    Generate completion using Cerebras inference (defaults to gpt-oss-120b).
    """
    chosen_model = (model or os.environ.get("CEREBRAS_MODEL") or CEREBRAS_DEFAULT_MODEL).strip()
    client = get_cerebras_client(api_key)

    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    elif json_mode:
        messages.append({
            "role": "system",
            "content": "You are a helpful assistant designed to output valid JSON."
        })

    messages.append({"role": "user", "content": prompt})

    kwargs: Dict[str, Any] = {
        "model": chosen_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    choice = response.choices[0]
    content = choice.message.content or ""

    if json_mode:
        content = strip_markdown_code_fences(content)

    return content.strip()


def strip_markdown_code_fences(text: str) -> str:
    """
    Strip ```json ... ``` code fences from LLM responses to ensure clean JSON parsing.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()
