"""
ai_engine.py — Unified Multi-Provider AI Engine for CFC AI
Hỗ trợ đa nhà cung cấp:
  1. Google Gemini (Gemini 2.0 Flash / 1.5 Flash - Miễn phí)
  2. OpenRouter (Mô hình miễn phí: deepseek-r1, llama-3.3-70b, gemini-2.0-flash)
  3. Groq (Miễn phí, tốc độ 500 token/s)
  4. Ollama Local (Chạy cục bộ offline khi không có mạng)

Tự động chuyển đổi dự phòng (Fallback Chain) khi gặp lỗi.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional, List

import httpx
from shopee_matcher import _fold

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

    primary_model = model or cfg.get("model", "openai/gpt-oss-120b")
    candidate_models = [primary_model]
    for fallback_m in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b", "groq/compound"]:
        if fallback_m not in candidate_models:
            candidate_models.append(fallback_m)

    url = "https://api.groq.com/openai/v1/chat/completions"
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    for model_name in candidate_models:
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
        }
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                elif resp.status_code == 404:
                    continue  # thử model tiếp theo
                else:
                    logger.warning("Groq API error (%s): %s", resp.status_code, resp.text[:150])
        except Exception as e:
            logger.warning("Lỗi khi gọi Groq API (%s): %s", model_name, e)
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


def _extract_json_object(text: str) -> Optional[dict[str, Any]]:
    """Parse object JSON từ phản hồi LLM, chịu được ```json fence hoặc text bao quanh."""
    if not text:
        return None
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.S | re.I)
    if fenced:
        cleaned = fenced.group(1).strip()
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start:end + 1]
    try:
        obj = json.loads(cleaned)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


async def plan_chat_intent_with_ollama(
    user_query: str,
    brand: str,
    conversation_summary: str = "",
    timeout: float = 1.6,
) -> Optional[dict[str, Any]]:
    """
    Dùng Ollama local như NLU planner: chỉ trả JSON intent/tool, không sinh câu trả lời khách.
    Tool deterministic/catalog vẫn là source of truth cho giá, link và sản phẩm.
    """
    cfg = _load_settings()
    nlu_cfg = cfg.get("llm_nlu", {}) if isinstance(cfg.get("llm_nlu", {}), dict) else {}
    ollama_cfg = cfg.get("ollama", {}) if isinstance(cfg.get("ollama", {}), dict) else {}
    model = (
        nlu_cfg.get("model")
        or ollama_cfg.get("chat_model")
        or ollama_cfg.get("fallback_embed_model")
        or "qwen2.5:7b-instruct"
    )

    system_prompt = """Bạn là bộ phân loại ý định NLU cho chatbot bán hàng ZeO.
NHIỆM VỤ: đọc tin nhắn khách và xuất đúng 1 JSON object. Không trả lời khách, không giải thích, không markdown.
Các intent hợp lệ:
- price_extreme: khách hỏi sản phẩm mắc nhất/đắt nhất/cao nhất hoặc rẻ nhất/thấp nhất.
- budget_filter: khách hỏi sản phẩm theo ngân sách/khoảng giá.
- product_link: khách xin link/mua sản phẩm cụ thể hoặc sản phẩm đã nhắc trước đó.
- product_search: khách hỏi có/bán/mua một loại sản phẩm cụ thể.
- product_availability: khách hỏi còn hàng, hết hàng hoặc tồn kho.
- catalog_group_select: khách chọn nhóm/số thứ tự từ danh mục vừa được giới thiệu.
- need_consultation: khách cần gợi ý theo nhu cầu như thơm lâu, tiết kiệm, sạch sâu, dịu nhẹ.
- specific_price: khách hỏi giá của sản phẩm hoặc nhóm sản phẩm cụ thể.
- return_process: khách hỏi cách liên hệ, các bước hoặc hồ sơ đổi trả.
- return_fee: khách hỏi đổi/trả có tốn phí không.
- customer_privacy: khách yêu cầu thông tin của một khách hàng/người khác.
- clarification: câu bị typo hoặc thiếu dữ kiện cần hỏi lại.
- unknown: không đủ chắc.
Schema bắt buộc:
{"intent":"unknown","confidence":0.0,"sort":"","need_type":"","category":"","product":"","reference":false,"reason":""}
Quy tắc:
- confidence từ 0 đến 1.
- sort chỉ dùng "highest" hoặc "lowest" cho price_extreme.
- need_type chỉ dùng "thom_lau", "tiet_kiem", "sach_sau", "diu_nhe".
- reference=true nếu có đại từ như "sản phẩm đó", "cái đó", "loại hồi nãy", "số 1".
- Không tự tạo giá, link, tên sản phẩm mới."""

    prompt = f"""Brand: {brand}
Lịch sử ngắn: {conversation_summary or "(không có)"}
Tin nhắn khách: {user_query}

Chỉ xuất JSON object đúng schema."""

    try:
        raw = await asyncio.wait_for(
            call_ollama(prompt, system_prompt=system_prompt, model=model, temperature=0.0),
            timeout=timeout,
        )
    except Exception as exc:
        logger.debug("Ollama NLU planner timeout/error: %s", exc)
        return None

    obj = _extract_json_object(raw or "")
    if not obj:
        return None

    allowed_intents = {
        "price_extreme", "budget_filter", "product_link",
        "product_search", "product_availability", "catalog_group_select",
        "need_consultation", "specific_price", "return_process", "return_fee",
        "customer_privacy", "clarification", "unknown",
    }
    intent = str(obj.get("intent", "unknown")).strip().lower()
    if intent not in allowed_intents:
        intent = "unknown"

    try:
        confidence = float(obj.get("confidence", 0.0))
    except Exception:
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    sort = str(obj.get("sort", "")).strip().lower()
    if sort not in {"highest", "lowest"}:
        sort = ""

    need_type = str(obj.get("need_type", "")).strip().lower()
    if need_type not in {"thom_lau", "tiet_kiem", "sach_sau", "diu_nhe"}:
        need_type = ""

    return {
        "intent": intent,
        "confidence": confidence,
        "sort": sort,
        "need_type": need_type,
        "category": str(obj.get("category", "")).strip()[:80],
        "product": str(obj.get("product", "")).strip()[:160],
        "reference": bool(obj.get("reference", False)),
        "reason": str(obj.get("reason", "")).strip()[:160],
        "provider": "ollama",
        "model": model,
    }


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


def _match_autonomous_tool(user_message: str, brand: str = "all") -> Optional[tuple]:
    """Tự động nhận diện công cụ cần thực thi ngay lập tức dựa trên ngữ cảnh câu hỏi."""
    folded = _fold(user_message)
    
    # 1. Báo cáo kinh doanh, Leads, Khách hàng CRM
    if any(k in folded for k in ["khach hang", "leads", "lead", "tong hop tinh hinh", "bao cao kinh doanh", "tinh hinh kinh doanh", "hom nay", "doanh so", "so lieu", "sdt"]):
        target_brand = "zeo" if "zeo" in folded and "cfc" not in folded else ("cfc" if "cfc" in folded and "zeo" not in folded else brand)
        return ("get_business_stats", {"brand": target_brand})
    
    # 2. n8n Workflows & Lỗi
    if any(k in folded for k in ["n8n", "workflow"]):
        if any(k in folded for k in ["loi", "error", "that bai", "kiem tra loi", "su co"]):
            return ("get_n8n_executions", {"status": "error", "limit": 10})
        return ("list_n8n_workflows", {})
        
    # 3. Shopee Catalog
    if any(k in folded for k in ["shopee", "danh muc shopee", "san pham shopee", "gia san pham", "catalogue", "gia ban"]):
        kw = ""
        for p in ["nuoc giat", "rua chen", "lau san", "toilet", "canxi", "phan bon", "javen", "vien sui", "ngu coc"]:
            if p in folded:
                kw = p
                break
        return ("get_shopee_catalog_summary", {"search_keyword": kw} if kw else {})
        
    # 4. Learning Queue
    if any(k in folded for k in ["learning queue", "hang doi", "cho duyet", "cau hoi cho duyet"]):
        return ("get_learning_queue_summary", {"limit": 5})
        
    # 5. Sức khỏe hệ thống
    if any(k in folded for k in ["he thong", "ram", "cpu", "redis", "suc khoe", "trang thai server", "o dia", "disk"]):
        return ("get_system_status", {"component": "all"})
        
    return None


async def run_assistant_agent_chat(
    user_message: str,
    history: Optional[List[dict]] = None,
    brand: str = "all",
    temperature: float = 0.4,
) -> dict:
    """
    Chạy Agent Loop thông minh: Tự động thực thi Tool lấy dữ liệu thật và tổng hợp báo cáo trực quan.
    """
    from ai_agent_tools import AGENT_TOOLS_SCHEMA, dispatch_tool_call

    cfg = _load_settings().get("ai_providers", {})
    groq_key = cfg.get("groq", {}).get("api_key", "")
    groq_model = cfg.get("groq", {}).get("model", "llama-3.3-70b-versatile")

    # 1. Kiểm tra nhận diện công cụ tự động (Autonomous Tool Dispatcher)
    auto_tool = _match_autonomous_tool(user_message, brand)
    if auto_tool:
        fn_name, fn_args = auto_tool
        try:
            logger.info("Autonomous Tool Execution: %s with args %s", fn_name, fn_args)
            tool_result = await dispatch_tool_call(fn_name, fn_args)
            action_cards = [{
                "tool": fn_name,
                "args": fn_args,
                "result": tool_result,
            }]
            
            # Yêu cầu LLM tổng hợp báo cáo từ dữ liệu thật
            synth_prompt = (
                f"Người dùng hỏi: \"{user_message}\"\n\n"
                f"Dữ liệu thực tế vừa được hệ thống truy xuất tự động từ công cụ '{fn_name}':\n"
                f"{json.dumps(tool_result, ensure_ascii=False, indent=2)}\n\n"
                "Hãy đóng vai Trợ lý Điều Hành AI, tổng hợp dữ liệu trên thành một báo cáo súc tích, chuyên nghiệp cho Quản trị viên. "
                "Làm nổi bật các chỉ số quan trọng (Leads, SĐT, Tình trạng), sử dụng định dạng Markdown đẹp mắt, có gạch đầu dòng rõ ràng. "
                "Tuyệt đối không giải thích lý thuyết về cách gọi công cụ, mà hãy trình bày trực tiếp các con số thực tế."
            )
            
            summary_res = await generate_ai_text(synth_prompt)
            final_text = summary_res.get("text", "")
            if not final_text:
                final_text = f"Đã thực thi thành công công cụ **{fn_name}** và truy xuất dữ liệu từ hệ thống."

            return {
                "success": True,
                "provider": summary_res.get("provider", "local"),
                "model": summary_res.get("model", "qwen2.5"),
                "text": final_text,
                "tools_used": [fn_name],
                "action_cards": action_cards,
            }
        except Exception as e:
            logger.warning("Auto tool execution error: %s", e)

    # 2. Thử gọi qua Groq với Tool Calling Schema nếu có API Key
    if groq_key:
        try:
            system_prompt = (
                f"Bạn là CFC AI Assistant — Trợ lý điều hành AI Vạn Năng cho ZeO Vietnam và CFC Cò Bay.\n"
                "Khi người dùng yêu cầu số liệu kinh doanh, danh mục Shopee, n8n, hoặc sức khỏe hệ thống, hãy gọi tool tương ứng để lấy dữ liệu thực tế.\n"
                "Với câu hỏi trò chuyện, đố vui, kỹ thuật: Trả lời cuốn hút, hóm hỉnh, sâu sắc."
            )
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                for h in history[-8:]:
                    r = h.get("role", "user")
                    c = h.get("content", "")
                    if r in ("user", "assistant") and c:
                        messages.append({"role": r, "content": c})
            messages.append({"role": "user", "content": user_message})

            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": groq_model,
                "messages": messages,
                "temperature": temperature,
                "tools": AGENT_TOOLS_SCHEMA,
                "tool_choice": "auto",
            }

            async with httpx.AsyncClient(timeout=35.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choice = data.get("choices", [{}])[0]
                    msg = choice.get("message", {})
                    tool_calls = msg.get("tool_calls", [])

                    if tool_calls:
                        action_cards = []
                        tools_used = []
                        messages.append(msg)

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
                            action_cards.append({
                                "tool": fn_name,
                                "args": fn_args,
                                "result": tool_result,
                            })
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "name": fn_name,
                                "content": json.dumps(tool_result, ensure_ascii=False),
                            })

                        # Gọi lần 2 để AI tổng hợp kết quả
                        resp2 = await client.post(url, headers=headers, json={
                            "model": groq_model,
                            "messages": messages,
                            "temperature": temperature,
                        })
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
                        return {
                            "success": True,
                            "provider": "groq",
                            "model": groq_model,
                            "text": msg.get("content", ""),
                            "tools_used": [],
                            "action_cards": [],
                        }
        except Exception as e:
            logger.warning("Groq agent chat error: %s", e)

    # 3. Trả lời thông thường (Chit-chat / Q&A)
    system_prompt = "Bạn là CFC AI Assistant — Trợ lý điều hành AI cho ZeO Vietnam và CFC Cò Bay. Trả lời tự nhiên, chuyên nghiệp và thân thiện."
    fallback_res = await generate_ai_text(user_message, system_prompt)
    return {
        "success": fallback_res.get("success", False),
        "provider": fallback_res.get("provider", "none"),
        "model": fallback_res.get("model", "qwen2.5"),
        "text": fallback_res.get("text", "Không thể sinh phản hồi từ AI."),
        "tools_used": [],
        "action_cards": [],
    }


async def synthesize_cskh_answer(
    user_query: str,
    brand: str,
    retrieved_facts: str,
    conversation_summary: str = "",
    timeout: float = 2.5,
) -> Optional[str]:
    """
    Dùng LLM (Ollama local / Groq / Gemini) để biến Fact từ Sheet thành câu trả lời CSKH 5 sao.
    TUYỆT ĐỐI không bịa đặt, giọng điệu tự nhiên, lịch sự, KHÔNG dùng icon sến súa/phản cảm như 🔥.
    """
    return await reason_and_answer_cskh(
        user_query=user_query,
        brand=brand,
        retrieved_facts=retrieved_facts,
        conversation_summary=conversation_summary,
        timeout=timeout,
    )


async def reason_and_answer_cskh(
    user_query: str,
    brand: str,
    retrieved_facts: str = "",
    chat_history: Optional[List[dict]] = None,
    catalog_products: Optional[List[dict]] = None,
    conversation_summary: str = "",
    timeout: float = 3.0,
) -> Optional[str]:
    """
    Trợ lý CSKH Thông Minh (Single Brain):
    Nhận diện câu hỏi tự nhiên, đối chiếu với Dữ liệu thực tế (Facts & Products từ Google Sheet/Redis)
    và Lịch sử trò chuyện để trả lời trọn vẹn, thuyết phục, chuẩn văn phong 5 sao và TUYỆT ĐỐI không bịa đặt.
    """
    if not (retrieved_facts or "").strip() and not catalog_products:
        logger.info("Skip CSKH reasoning: empty retrieved_facts and catalog_products")
        return None

    brand_upper = brand.upper()
    brand_display = "ZeO Vietnam (Chăm sóc gia đình sinh học: ZeO, PANO, Oplus)" if brand_upper == "ZEO" else "CFC Cò Bay (Phân bón & Dinh dưỡng cây trồng nông nghiệp Cần Thơ)"
    website_url = "https://zeo.vn/" if brand_upper == "ZEO" else "https://cfccobay.vn/"
    shopee_url = "https://shopee.vn/zeovietnamofficial" if brand_upper == "ZEO" else "https://shopee.vn/cfccobay"
    hotline = "1900 5307" if brand_upper == "ZEO" else "0292 3841 818"

    system_prompt = f"""Bạn là Chuyên viên CSKH và Tư vấn bán hàng cao cấp của thương hiệu {brand_display}.
Mục tiêu: Đọc hiểu sâu sắc câu hỏi của khách hàng, đối chiếu với LỊCH SỬ CHAT và DỮ LIỆU THỰC TẾ (FACTS) để đưa ra câu trả lời xuất sắc nhất.

QUY TẮC CỐT LÕI (BẮT BUỘC):
1. Giọng điệu & Xưng hô:
   - Thân thiện, ngọt ngào, lịch sự, chuyên nghiệp.
   - Xưng: 'mình' hoặc 'dạ em'; Gọi khách: 'bạn' hoặc 'anh/chị'.
2. Hiểu ngữ cảnh & Đa ý định (Context & Multi-Intent):
   - Đọc kỹ lịch sử trò chuyện để hiểu rõ các đại từ thay thế như 'cái số 2', 'loại đó', 'cái này', 'sản phẩm hồi nãy'.
   - Nếu khách hỏi gộp nhiều ý (ví dụ: vừa hỏi giá/sản phẩm vừa hỏi giao hàng/freeship về tỉnh), hãy giải đáp ĐẦY ĐỦ VÀ MẠCH LẠC tất cả các ý trong một câu trả lời duy nhất.
3. Nguyên tắc Zero-Hallucination (Không bịa đặt):
   - Chỉ sử dụng các dữ liệu về giá cả, thành phần, công nghệ, công dụng và chính sách có trong 'DỮ LIỆU THỰC TẾ & SẢN PHẨM' dưới đây.
   - Đối với giá phân bón hoặc liều lượng nông nghiệp chưa có số liệu cố định: Không tự bịa giá tĩnh/liều lượng, hãy giải thích giá phụ thuộc vào đại lý từng vùng và hướng dẫn khách để lại SĐT để kỹ sư/đại lý hỗ trợ.
   - Khi khách hỏi Mua sỉ / Nhập hàng / Đại lý (như 'cần nhập', 'muốn nhập', 'lấy sỉ', 'nhập số lượng lớn'): Hãy xác nhận công ty có chính sách chiết khấu sỉ rất tốt, xin Số điện thoại + Khu vực (Tỉnh/Thành) để chuyên viên gửi bảng giá sỉ, đồng thời cung cấp link Shopee Mall nếu khách có nhu cầu mua lẻ trải nghiệm.
4. Văn phong sạch & Tinh tế (Clean Styling):
   - TUYỆT ĐỐI KHÔNG dùng các icon phản cảm, sến súa, spam như: 🔥, 💥, ⚡, 💣, 😈, 💯.
   - Chỉ sử dụng các emoji thanh lịch, nhã nhặn như: 🌿, ⭐️, 💙, 👉, 💡 khi cần thiết.
5. Thông tin kênh mua hàng chính thức:
   - Gian hàng Shopee Mall chính hãng: {shopee_url} (Hỗ trợ mã Freeship Extra toàn quốc).
   - Website chính thức: {website_url}
   - Hotline hỗ trợ: {hotline}
6. Định dạng câu trả lời:
   - Ngắn gọn, súc tích, dễ đọc trên điện thoại di động (có thể gạch đầu dòng 1-3 ý chính).
   - Kết thúc bằng một lời gợi mở nhẹ nhàng (ví dụ hỏi thăm thêm nhu cầu, gửi link đặt hàng hoặc hỗ trợ tiếp).
   - Chỉ xuất ra nội dung tin nhắn gửi khách hàng, không viết thêm bất kỳ lời bình luận nào của AI."""

    # Chuẩn bị context. Không cho model tự trả lời khi không có fact:
    # caller phải fallback/hỏi rõ/chuyển admin ở lớp deterministic.
    facts_block = retrieved_facts.strip()

    products_str = ""
    if catalog_products and isinstance(catalog_products, list):
        prod_lines = []
        for p in catalog_products[:5]:
            p_name = p.get("name", "")
            p_price = p.get("price", "")
            p_link = p.get("shopee_url") or p.get("link_shopee") or shopee_url
            p_discount = p.get("discount_percent") or p.get("discount", "")
            p_disc_str = f" (Giảm {p_discount})" if p_discount else ""
            prod_lines.append(f"• {p_name} — Giá: {p_price}{p_disc_str} — Link: {p_link}")
        if prod_lines:
            products_str = "\nDANH MỤC SẢN PHẨM PHÙ HỢP TỪ SHOPEE:\n" + "\n".join(prod_lines)

    history_str = ""
    if chat_history and isinstance(chat_history, list):
        h_lines = []
        for h in chat_history[-6:]:
            role = "Khách" if h.get("role") == "user" else "CSKH"
            content = h.get("content", "").strip()
            if content:
                h_lines.append(f"{role}: {content}")
        if h_lines:
            history_str = "\nLỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY:\n" + "\n".join(h_lines)
    elif conversation_summary:
        history_str = f"\nTÓM TẮT LỊCH SỬ CHAT: {conversation_summary}"

    user_prompt = f"""{history_str}

DỮ LIỆU THỰC TẾ (FACTS TỪ GOOGLE SHEET & HỆ THỐNG):
{facts_block}
{products_str}

Khách hàng vừa nhắn: "{user_query}"
Hãy soạn câu trả lời CSKH 5 sao hoàn chỉnh gửi cho khách:"""

    try:
        res = await asyncio.wait_for(
            generate_ai_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                preferred_provider="ollama",
                temperature=0.25,
            ),
            timeout=timeout,
        )
        if res.get("success") and res.get("text"):
            ans = res.get("text", "").strip()
            # Lọc icon xấu
            ans = re.sub(r"[🔥💥💣⚡😈💯]", "", ans)
            if len(ans) >= 20:
                return ans
    except Exception as e:
        logger.warning("CSKH Agent synthesis error or timeout (%s): %s", brand, e)

    return None
