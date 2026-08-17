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
from typing import Optional, List

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


def _should_enable_tools(message: str) -> bool:
    """Kiểm tra xem câu hỏi của user có cần gọi công cụ hệ thống/CRM/n8n hay không."""
    from shopee_matcher import _fold
    folded = _fold(message).lower()
    triggers = [
        "n8n", "workflow", "flow", "bat", "tat", "activate", "deactivate", "toggle", "chay", "sync",
        "lead", "khach", "sdt", "so dien thoai", "doanh thu", "ban hang", "thong ke", "bao cao",
        "shopee", "san pham", "gia", "mua", "nuoc giat", "rua chen", "lau san", "phan bon", "co bay", "zeo",
        "faq", "kich ban", "tra loi", "learning", "hang doi", "duyet",
        "redis", "dung luong", "ram", "bo nho", "cpu", "server", "ollama", "token", "tai nguyen",
        "kiem tra", "trang thai", "loi", "error", "execution", "status",
        "lenh", "terminal", "bash", "shell", "o cung", "disk", "file", "doc file", "log", "curl",
        "ping", "tien trinh", "process", "lich", "calendar", "mail", "email", "gui mail", "telegram", "webhook"
    ]
    return any(t in folded for t in triggers)


async def run_assistant_agent_chat(
    user_message: str,
    history: Optional[List[dict]] = None,
    brand: str = "all",
    temperature: float = 0.4,
) -> dict:
    """
    Chạy Agent Loop thông minh: Tán gẫu tự nhiên nếu là câu hỏi chung, chỉ gọi Tool khi cần thiết.
    """
    from ai_agent_tools import AGENT_TOOLS_SCHEMA, dispatch_tool_call

    cfg = _load_settings().get("ai_providers", {})
    groq_key = cfg.get("groq", {}).get("api_key", "")
    groq_model = cfg.get("groq", {}).get("model", "llama-3.3-70b-versatile")
    openrouter_key = cfg.get("openrouter", {}).get("api_key", "")
    openrouter_model = cfg.get("openrouter", {}).get("model", "google/gemini-2.0-flash-exp:free")

    system_prompt = (
        f"Bạn là CFC AI Assistant — Trợ lý điều hành AI Vạn Năng (Universal Operations Assistant) cho hệ thống ZeO Vietnam và CFC Cò Bay.\n"
        f"Model: {groq_model} qua Groq Cloud API siêu tốc.\n\n"
        "BỘ VŨ KHÍ CỦA BẠN (UNIVERSAL TOOLS):\n"
        "1. execute_system_command: Siêu công cụ thực thi lệnh Shell / Bash / CLI (vd: 'df -h' kiểm tra ổ đĩa, 'ps aux' kiểm tra tiến trình, 'redis-cli info' đọc Redis, 'curl -s wttr.in/...' xem thời tiết, 'cat /path' đọc file, 'grep' tìm log...). Bạn có thể tự do viết bất kỳ câu lệnh nào để phục vụ người dùng!\n"
        "2. trigger_n8n_webhook: Kích hoạt các workflow n8n (Google Calendar, Gmail, Telegram, Zalo, Google Sheets).\n"
        "3. list_n8n_workflows & toggle_n8n_workflow: Quản trị và bật/tắt workflow tự động hoá n8n.\n"
        "4. get_business_stats & get_shopee_catalog_summary: Báo cáo CRM và tra cứu Shopee Mall.\n"
        "5. get_system_status: Báo cáo nhanh sức khỏe Redis, RAM, Ollama, n8n.\n\n"
        "TÍNH CÁCH & QUY TẮC:\n"
        "- ĐA NĂNG & THÔNG MINH: Tự động chạy lệnh hoặc kích hoạt tool khi người dùng cần bất kỳ dữ liệu thực tế nào.\n"
        "- Với câu hỏi đố vui, khoa học, triết học, lập trình, tán gẫu: Trả lời cuốn hút, hóm hỉnh, sâu sắc, KHÔNG gọi tool thừa.\n"
        "- Khi chạy lệnh hệ thống: Giải thích ngắn gọn kết quả một cách thân thiện, chuyên nghiệp."
    )

    # Chuẩn bị hội thoại
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for h in history[-8:]:  # Giữ tối đa 8 tin nhắn gần nhất
            r = h.get("role", "user")
            c = h.get("content", "")
            if r in ("user", "assistant") and c:
                messages.append({"role": r, "content": c})

    messages.append({"role": "user", "content": user_message})

    needs_tools = _should_enable_tools(user_message)

    # Thử gọi qua Groq trước nếu có key
    if groq_key:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": groq_model,
                "messages": messages,
                "temperature": temperature,
            }
            if needs_tools:
                payload["tools"] = AGENT_TOOLS_SCHEMA
                payload["tool_choice"] = "auto"

            async with httpx.AsyncClient(timeout=35.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choice = data.get("choices", [{}])[0]
                    msg = choice.get("message", {})

                    tool_calls = msg.get("tool_calls", [])
                    action_cards = []
                    tools_used = []

                    if tool_calls:
                        # Append assistant message chứa tool_calls
                        messages.append(msg)

                        # Thực thi từng tool
                        for tc in tool_calls:
                            tc_id = tc.get("id", "call_1")
                            fn_name = tc.get("function", {}).get("name", "")
                            raw_args = tc.get("function", {}).get("arguments", "{}")
                            try:
                                fn_args = json.loads(raw_args)
                            except Exception:
                                fn_args = {}

                            tools_used.append(fn_name)
                            tool_result = await dispatch_tool_call(fn_name, fn_args)

                            # Lưu action card cho giao diện
                            action_cards.append({
                                "tool": fn_name,
                                "args": fn_args,
                                "result": tool_result,
                            })

                            # Append tool response
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "name": fn_name,
                                "content": json.dumps(tool_result, ensure_ascii=False),
                            })

                        # Gọi lần 2 để AI tổng hợp kết quả
                        second_payload = {
                            "model": groq_model,
                            "messages": messages,
                            "temperature": temperature,
                        }
                        resp2 = await client.post(url, headers=headers, json=second_payload)
                        if resp2.status_code == 200:
                            data2 = resp2.json()
                            final_text = data2.get("choices", [{}])[0].get("message", {}).get("content", "")
                            return {
                                "success": True,
                                "provider": "groq",
                                "model": groq_model,
                                "text": final_text,
                                "tools_used": tools_used,
                                "action_cards": action_cards,
                            }
                    else:
                        # AI trả lời trực tiếp không cần tool
                        return {
                            "success": True,
                            "provider": "groq",
                            "model": groq_model,
                            "text": msg.get("content", ""),
                            "tools_used": [],
                            "action_cards": [],
                        }
        except Exception as e:
            logger.warning(f"Groq agent chat error: {e}")

    # Fallback sang trả lời văn bản thông thường
    fallback_res = await generate_ai_text(user_message, system_prompt)
    return {
        "success": fallback_res.get("success", False),
        "provider": fallback_res.get("provider", "none"),
        "model": "standard-fallback",
        "text": fallback_res.get("text", "Không thể sinh phản hồi từ AI."),
        "tools_used": [],
        "action_cards": [],
    }
