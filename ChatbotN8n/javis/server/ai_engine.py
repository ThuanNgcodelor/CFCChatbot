"""
ai_engine.py — Unified Multi-Provider AI Engine for CFC AI
Hỗ trợ đa nhà cung cấp:
  1. Google Gemini (Gemini 2.0 Flash / 1.5 Flash - Miễn phí)
  2. OpenRouter (Mô hình miễn phí: deepseek-r1, llama-3.3-70b, gemini-2.0-flash)
  3. Groq (Miễn phí, tốc độ 500 token/s)
  4. Ollama Local (Chạy cục bộ offline khi không có mạng)

Tự động chuyển đổi dự phòng (Fallback Chain) khi gặp lỗi.
"""

import json
import logging
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_settings: dict = {}


def _load_settings() -> dict:
    global _settings
    cfg_path = Path(__file__).parent / "settings.json"
    if cfg_path.exists():
        _settings = json.loads(cfg_path.read_text(encoding="utf-8"))
    return _settings


async def call_gemini(
    prompt: str,
    system_prompt: str = "",
    api_key: Optional[str] = None,
    model: str = "gemini-2.0-flash",
    temperature: float = 0.3,
) -> Optional[str]:
    """Gọi Google Gemini API (Miễn phí 15 requests/phút)."""
    cfg = _load_settings().get("ai_providers", {}).get("gemini", {})
    key = api_key or cfg.get("api_key", "")
    if not key:
        return None

    model_name = model or cfg.get("model", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"

    contents = []
    if system_prompt:
        contents.append({"role": "user", "parts": [{"text": f"[Hướng dẫn hệ thống]: {system_prompt}"}]})
        contents.append({"role": "model", "parts": [{"text": "Tôi đã hiểu hướng dẫn."}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 2048,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
    except Exception as e:
        logger.warning("Lỗi khi gọi Google Gemini API: %s", e)
    return None


async def call_openrouter(
    prompt: str,
    system_prompt: str = "",
    api_key: Optional[str] = None,
    model: str = "google/gemini-2.0-flash-exp:free",
    temperature: float = 0.3,
) -> Optional[str]:
    """Gọi OpenRouter API (Hỗ trợ các model miễn phí)."""
    cfg = _load_settings().get("ai_providers", {}).get("openrouter", {})
    key = api_key or cfg.get("api_key", "")
    if not key:
        return None

    model_name = model or cfg.get("model", "google/gemini-2.0-flash-exp:free")
    url = "https://openrouter.ai/api/v1/chat/completions"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "https://cfc.vn",
        "X-Title": "CFC AI Assistant",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.warning("Lỗi khi gọi OpenRouter API: %s", e)
    return None


async def call_groq(
    prompt: str,
    system_prompt: str = "",
    api_key: Optional[str] = None,
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.3,
) -> Optional[str]:
    """Gọi Groq Cloud API (Miễn phí, siêu nhanh)."""
    cfg = _load_settings().get("ai_providers", {}).get("groq", {})
    key = api_key or cfg.get("api_key", "")
    if not key:
        return None

    model_name = model or cfg.get("model", "llama-3.3-70b-versatile")
    url = "https://api.groq.com/openai/v1/chat/completions"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.warning("Lỗi khi gọi Groq API: %s", e)
    return None


async def call_ollama(
    prompt: str,
    system_prompt: str = "",
    model: str = "qwen2.5:7b-instruct",
    temperature: float = 0.3,
) -> Optional[str]:
    """Gọi Ollama Local (Mặc định chạy offline)."""
    cfg = _load_settings().get("ollama", {})
    base_url = cfg.get("base_url", "http://127.0.0.1:11434")
    model_name = model or cfg.get("fallback_embed_model", "qwen2.5:7b-instruct")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    url = f"{base_url}/api/chat"
    payload = {
        "model": model_name,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": 1024},
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.warning("Lỗi khi gọi Ollama Local: %s", e)
    return None


async def generate_ai_text(
    prompt: str,
    system_prompt: str = "",
    preferred_provider: Optional[str] = None,
    temperature: float = 0.3,
) -> dict:
    """
    Sinh phản hồi AI với cơ chế Fallback thông minh:
    Thử lần lượt: Gemini -> OpenRouter -> Groq -> Ollama Local.
    """
    providers_order = ["gemini", "openrouter", "groq", "ollama"]
    if preferred_provider and preferred_provider in providers_order:
        providers_order.remove(preferred_provider)
        providers_order.insert(0, preferred_provider)

    for provider in providers_order:
        res = None
        if provider == "gemini":
            res = await call_gemini(prompt, system_prompt, temperature=temperature)
        elif provider == "openrouter":
            res = await call_openrouter(prompt, system_prompt, temperature=temperature)
        elif provider == "groq":
            res = await call_groq(prompt, system_prompt, temperature=temperature)
        elif provider == "ollama":
            res = await call_ollama(prompt, system_prompt, temperature=temperature)

        if res:
            return {
                "success": True,
                "provider": provider,
                "text": res,
            }

    return {
        "success": False,
        "provider": "none",
        "text": "Không thể kết nối tới bất kỳ nhà cung cấp AI nào. Vui lòng kiểm tra API key hoặc Ollama.",
    }
