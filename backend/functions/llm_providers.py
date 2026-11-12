"""
Unified LLM Provider Abstraction for LangGraph Pipeline.

Wraps Cerebras (primary, lowest cost) and Gemini (fallback) behind
LangChain ChatModel interfaces so LangGraph nodes can swap providers
transparently.

Provider Priority:
  1. Cerebras ChatModel  (gpt-oss-120b — ~$0.10/M tokens)
  2. Gemini ChatModel    (gemini-2.5-flash-lite — free-tier / low cost)
"""

import os
import json
import random
from typing import Optional, Literal
from dotenv import load_dotenv


def _resolve_cerebras_key() -> Optional[str]:
    """Resolve Cerebras API key from env, .env file, or apikeys.json."""
    load_dotenv()
    key = os.environ.get("CEREBRAS_API_KEY", "").strip()
    if key:
        return key

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


def _resolve_gemini_key() -> Optional[str]:
    """Resolve Gemini API key from env or apikeys.json."""
    load_dotenv()
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key and key.strip():
        return key.strip()

    keys_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apikeys.json"))
    if os.path.exists(keys_file):
        try:
            with open(keys_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                keys = data.get("api_keys", [])
                if keys:
                    return random.choice(keys)
        except Exception:
            pass
    return None


class CerebrasDirectChatModel:
    """
    Zero-wrapper fallback adapter using standard openai.OpenAI client
    targeting Cerebras Inference endpoint. Implements .invoke(messages).
    """
    def __init__(self, model: str, api_key: str, temperature: float = 0.3, max_tokens: int = 1500, json_mode: bool = False):
        import openai
        self.model = model
        self.client = openai.OpenAI(base_url="https://api.cerebras.ai/v1", api_key=api_key)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.json_mode = json_mode

    def invoke(self, messages):
        formatted = []
        for msg in messages:
            role = "user"
            content = getattr(msg, "content", str(msg))
            type_name = getattr(msg, "type", "")
            cls_name = type(msg).__name__
            if type_name == "system" or "System" in cls_name:
                role = "system"
            elif type_name == "human" or "Human" in cls_name:
                role = "user"
            elif type_name == "ai" or "AI" in cls_name:
                role = "assistant"
            formatted.append({"role": role, "content": content})

        kwargs = {
            "model": self.model,
            "messages": formatted,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = self.client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""

        try:
            from langchain_core.messages import AIMessage
            return AIMessage(content=content)
        except Exception:
            class _SimpleAIMessage:
                def __init__(self, c):
                    self.content = c
            return _SimpleAIMessage(content)


def get_chat_model(
    provider: Literal["cerebras", "gemini", "auto"] = "auto",
    temperature: float = 0.3,
    max_tokens: int = 4000,
    json_mode: bool = False,
):
    """
    Return a LangChain ChatModel instance.

    Provider resolution:
      - "auto": Try Cerebras first, fall back to Gemini.
      - "cerebras": Force Cerebras (raises if no key).
      - "gemini": Force Gemini (raises if no key).

    Args:
        provider: Which LLM backend to use.
        temperature: Sampling temperature.
        max_tokens: Max output tokens.
        json_mode: If True, request JSON-structured output.

    Returns:
        A LangChain BaseChatModel instance.
    """
    cerebras_key = _resolve_cerebras_key()
    gemini_key = _resolve_gemini_key()

    model_kwargs = {}

    # ── Cerebras ──
    if provider in ("cerebras", "auto") and cerebras_key:
        cerebras_model = os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b").strip()
        effective_tokens = max(max_tokens, 1500) if "gpt-oss" in cerebras_model.lower() else max_tokens

        # Strategy 1: langchain_cerebras
        try:
            from langchain_cerebras import ChatCerebras
            kwargs = {
                "model": cerebras_model,
                "api_key": cerebras_key,
                "temperature": temperature,
                "max_tokens": effective_tokens,
            }
            if json_mode:
                kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
            chat = ChatCerebras(**kwargs)
            print(f"[LLM Provider] Using Cerebras ({cerebras_model}) via langchain_cerebras")
            return chat
        except Exception as e_cerebras:
            print(f"[LLM Provider] ChatCerebras unavailable ({e_cerebras}), trying ChatOpenAI adapter...")

        # Strategy 2: langchain_openai with Cerebras base_url
        try:
            from langchain_openai import ChatOpenAI
            kwargs = {
                "model": cerebras_model,
                "api_key": cerebras_key,
                "base_url": "https://api.cerebras.ai/v1",
                "temperature": temperature,
                "max_tokens": effective_tokens,
            }
            if json_mode:
                kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
            chat = ChatOpenAI(**kwargs)
            print(f"[LLM Provider] Using Cerebras ({cerebras_model}) via langchain_openai")
            return chat
        except Exception as e_openai:
            print(f"[LLM Provider] ChatOpenAI adapter unavailable ({e_openai}), trying direct OpenAI client...")

        # Strategy 3: Direct CerebrasOpenAIAdapter (zero-dependency on LangChain wrapper)
        try:
            chat = CerebrasDirectChatModel(
                model=cerebras_model,
                api_key=cerebras_key,
                temperature=temperature,
                max_tokens=effective_tokens,
                json_mode=json_mode,
            )
            print(f"[LLM Provider] Using Cerebras ({cerebras_model}) via direct OpenAI client")
            return chat
        except Exception as e_direct:
            print(f"[LLM Provider] Direct Cerebras client failed: {e_direct}, trying Gemini fallback...")
            if provider == "cerebras":
                raise e_direct

    # ── Gemini ──
    if provider in ("gemini", "auto") and gemini_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            kwargs = {
                "model": "gemini-2.5-flash-lite",
                "google_api_key": gemini_key,
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }

            chat = ChatGoogleGenerativeAI(**kwargs)
            print("[LLM Provider] Using Gemini (gemini-2.5-flash-lite)")
            return chat
        except Exception as e:
            if provider == "gemini":
                raise
            print(f"[LLM Provider] Gemini init failed: {e}")

    raise ValueError(
        "No LLM provider available. Set CEREBRAS_API_KEY or GEMINI_API_KEY in backend/.env. "
        f"Requested provider: {provider}"
    )


def invoke_with_fallback(messages, temperature=0.3, max_tokens=4000, json_mode=False) -> str:
    """
    Invoke LLM with automatic Cerebras → Gemini fallback.

    Args:
        messages: List of LangChain message objects (SystemMessage, HumanMessage).
        temperature: Sampling temperature.
        max_tokens: Max output tokens.
        json_mode: If True, request JSON output.

    Returns:
        The LLM response content as a string.
    """
    providers = []
    if _resolve_cerebras_key():
        providers.append("cerebras")
    if _resolve_gemini_key():
        providers.append("gemini")

    if not providers:
        raise ValueError("No LLM API keys found. Set CEREBRAS_API_KEY or GEMINI_API_KEY.")

    import time
    last_error = None
    for provider in providers:
        max_attempts = 2 if provider == "cerebras" else 1
        for attempt in range(1, max_attempts + 1):
            try:
                chat = get_chat_model(
                    provider=provider,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
                response = chat.invoke(messages)
                content = response.content if hasattr(response, "content") else str(response)
                if content and content.strip():
                    return content.strip()
                else:
                    if attempt < max_attempts:
                        time.sleep(1.0)
                        continue
                    raise ValueError(f"{provider} returned empty content")
            except Exception as e:
                last_error = e
                if attempt < max_attempts:
                    time.sleep(1.0)
                    continue
                print(f"[LLM Fallback] {provider} failed after {attempt} attempt(s): {e}")
                break

    raise ValueError(f"All LLM providers failed. Last error: {last_error}")
