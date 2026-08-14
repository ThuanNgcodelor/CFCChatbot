"""
admin_routes.py — FastAPI Router cho CFC AI Admin Dashboard
Modules 1-4: Status, n8n Control, Customers, Learning Queue, Settings
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_settings: dict = {}


def _auto_get_redis_env_pass() -> str:
    """Tự động đọc mật khẩu Redis từ file .env nếu có."""
    for p in [
        Path(__file__).resolve().parents[2] / "infra" / "redis" / ".env",
        Path(__file__).parent / ".env",
    ]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("REDIS_PASSWORD="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _cfg() -> dict:
    global _settings
    cfg_path = Path(__file__).parent / "settings.json"
    if cfg_path.exists():
        _settings = json.loads(cfg_path.read_text(encoding="utf-8"))
    else:
        _settings = {}
    
    # Tự động điền redis password nếu đang trống
    if not _settings.get("redis", {}).get("password"):
        env_pass = _auto_get_redis_env_pass()
        if env_pass:
            _settings.setdefault("redis", {})["password"] = env_pass

    return _settings


def _get_redis(decode: bool = True) -> aioredis.Redis:
    c = _cfg()["redis"]
    return aioredis.Redis(
        host=c.get("host", "127.0.0.1"),
        port=int(c.get("port", 6379)),
        password=c.get("password", "") or None,
        db=int(c.get("db", 0)),
        decode_responses=decode,
    )


def _n8n_cfg() -> dict:
    return _cfg().get("n8n", {"url": "https://n8n.dinhduongcantho.io.vn", "api_key": ""})


class SettingsUpdateRequest(BaseModel):
    redis: Optional[dict] = None
    ollama: Optional[dict] = None
    n8n: Optional[dict] = None
    rag: Optional[dict] = None


@router.get("/settings")
async def get_settings():
    """Lấy cấu hình hiện tại để hiển thị trên giao diện Cài đặt."""
    return _cfg()


@router.post("/settings")
async def update_settings(req: SettingsUpdateRequest):
    """Lưu cấu hình API keys và kết nối trực tiếp từ giao diện Admin."""
    global _settings
    cfg_path = Path(__file__).parent / "settings.json"
    current_cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}

    if req.redis:
        current_cfg.setdefault("redis", {}).update(req.redis)
    if req.ollama:
        current_cfg.setdefault("ollama", {}).update(req.ollama)
    if req.n8n:
        current_cfg.setdefault("n8n", {}).update(req.n8n)
    if req.rag:
        current_cfg.setdefault("rag", {}).update(req.rag)

    cfg_path.write_text(json.dumps(current_cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    _settings = current_cfg

    # Refresh module caches
    try:
        import rag_search, embedder
        rag_search._redis_pool = None
        rag_search._settings = {}
        embedder._settings = {}
    except Exception:
        pass

    return {
        "success": True,
        "message": "Đã lưu cài đặt và API keys thành công!",
        "settings": current_cfg,
    }


# ─────────────────────────────────────────────────────
# MODULE 1: STATUS & DASHBOARD STATS
# ─────────────────────────────────────────────────────

@router.get("/status")
async def system_status():
    """Trạng thái tất cả dịch vụ: Redis, Ollama, n8n, Python API."""
    cfg = _cfg()
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {}
    }

    # Redis
    try:
        r = _get_redis()
        await r.ping()
        info = await r.info("server")
        result["services"]["redis"] = {
            "status": "ok",
            "version": info.get("redis_version", "?"),
            "uptime_seconds": info.get("uptime_in_seconds", 0),
        }
        await r.aclose()
    except Exception as e:
        result["services"]["redis"] = {"status": "error", "detail": str(e)}

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{cfg['ollama']['base_url']}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            result["services"]["ollama"] = {
                "status": "ok",
                "models": models,
                "embed_model": cfg["ollama"]["embed_model"],
                "embed_ready": any(cfg["ollama"]["embed_model"].split(":")[0] in m for m in models),
            }
    except Exception as e:
        result["services"]["ollama"] = {"status": "error", "detail": str(e)}

    # n8n
    n8n = _n8n_cfg()
    try:
        headers = {"X-N8N-API-KEY": n8n["api_key"]} if n8n.get("api_key") else {}
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{n8n['url']}/api/v1/workflows", headers=headers)
            if resp.status_code == 200:
                wf_data = resp.json()
                workflows = wf_data.get("data", [])
                active_count = sum(1 for w in workflows if w.get("active"))
                result["services"]["n8n"] = {
                    "status": "ok",
                    "url": n8n["url"],
                    "total_workflows": len(workflows),
                    "active_workflows": active_count,
                }
            else:
                result["services"]["n8n"] = {"status": "no_api_key", "url": n8n["url"]}
    except Exception as e:
        result["services"]["n8n"] = {"status": "error", "detail": str(e)}

    # Python API itself
    result["services"]["python_api"] = {"status": "ok", "version": "1.0.0"}

    return result


@router.get("/stats/today")
async def stats_today():
    """Thống kê hôm nay: số khách, brand, lead stage, intent phổ biến."""
    r = _get_redis()
    try:
        stats = {
            "zeo": {"customers": 0, "lead_stages": {}, "top_intents": {}},
            "cfc": {"customers": 0, "lead_stages": {}, "top_intents": {}},
            "total_customers": 0,
        }

        for brand in ["zeo", "cfc"]:
            pattern = f"{brand}:customer:messenger:*"
            cursor = 0
            keys = []
            while True:
                cursor, batch = await r.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

            stats[brand]["customers"] = len(keys)
            stats["total_customers"] += len(keys)

            for key in keys:
                raw = await r.get(key)
                if not raw:
                    continue
                try:
                    profile = json.loads(raw)
                except Exception:
                    continue
                stage = profile.get("lead_stage", "new")
                stats[brand]["lead_stages"][stage] = stats[brand]["lead_stages"].get(stage, 0) + 1
                intent = profile.get("last_intent", "")
                if intent:
                    stats[brand]["top_intents"][intent] = stats[brand]["top_intents"].get(intent, 0) + 1

            # Sort top intents
            stats[brand]["top_intents"] = dict(
                sorted(stats[brand]["top_intents"].items(), key=lambda x: -x[1])[:8]
            )

        # Learning queue counts
        for brand in ["zeo", "cfc"]:
            lq_key = f"{brand}:learning:queue"
            lq_len = await r.llen(lq_key) if await r.exists(lq_key) else 0
            stats[brand]["learning_queue_count"] = lq_len

        return stats
    finally:
        await r.aclose()


# ─────────────────────────────────────────────────────
# MODULE 2: N8N CONTROL
# ─────────────────────────────────────────────────────

async def _n8n_request(method: str, path: str, body: dict = None):
    n8n = _n8n_cfg()
    headers = {
        "Content-Type": "application/json",
        "X-N8N-API-KEY": n8n.get("api_key", ""),
    }
    url = f"{n8n['url']}/api/v1{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers)
        elif method == "POST":
            resp = await client.post(url, headers=headers, json=body or {})
        elif method == "PATCH":
            resp = await client.patch(url, headers=headers, json=body or {})
        else:
            raise ValueError(f"Unknown method: {method}")
    return resp


@router.get("/n8n/workflows")
async def list_n8n_workflows():
    """Danh sách workflow n8n và trạng thái active."""
    try:
        resp = await _n8n_request("GET", "/workflows?limit=50")
        if resp.status_code != 200:
            return {"error": f"n8n trả về {resp.status_code}", "data": []}
        data = resp.json().get("data", [])
        workflows = [
            {
                "id": w["id"],
                "name": w["name"],
                "active": w.get("active", False),
                "updatedAt": w.get("updatedAt", ""),
                "tags": [t["name"] for t in w.get("tags", [])],
            }
            for w in data
        ]
        return {"workflows": workflows, "total": len(workflows)}
    except Exception as e:
        return {"error": str(e), "workflows": []}


@router.post("/n8n/workflows/{workflow_id}/toggle")
async def toggle_workflow(workflow_id: str):
    """Bật hoặc tắt một workflow."""
    try:
        # Lấy trạng thái hiện tại
        resp = await _n8n_request("GET", f"/workflows/{workflow_id}")
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Workflow không tìm thấy")
        wf = resp.json()
        is_active = wf.get("active", False)

        if is_active:
            resp2 = await _n8n_request("POST", f"/workflows/{workflow_id}/deactivate")
        else:
            resp2 = await _n8n_request("POST", f"/workflows/{workflow_id}/activate")

        return {"id": workflow_id, "name": wf.get("name"), "active": not is_active, "changed": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/n8n/executions")
async def list_executions(limit: int = Query(20, le=50)):
    """Lịch sử chạy workflow gần nhất."""
    try:
        resp = await _n8n_request("GET", f"/executions?limit={limit}&status=all")
        if resp.status_code != 200:
            return {"error": f"n8n {resp.status_code}", "data": []}
        data = resp.json().get("data", [])
        executions = [
            {
                "id": e["id"],
                "workflowId": e.get("workflowId"),
                "workflowName": e.get("workflowData", {}).get("name", "?"),
                "status": e.get("status", "?"),
                "startedAt": e.get("startedAt", ""),
                "stoppedAt": e.get("stoppedAt", ""),
            }
            for e in data
        ]
        return {"executions": executions}
    except Exception as e:
        return {"error": str(e), "executions": []}


@router.post("/n8n/sync-knowledge")
async def trigger_knowledge_sync(brand: str = Query("all")):
    """Trigger đồng bộ Knowledge từ Google Sheets lên Redis + Vector Index."""
    from knowledge_sync import sync_brand
    if brand == "all":
        zeo = await sync_brand("zeo")
        cfc = await sync_brand("cfc")
        return {"zeo": zeo, "cfc": cfc}
    result = await sync_brand(brand)
    return result


# ─────────────────────────────────────────────────────
# MODULE 3: CUSTOMER CONVERSATIONS
# ─────────────────────────────────────────────────────

@router.get("/customers")
async def list_customers(brand: str = Query("all"), page: int = 1, page_size: int = 20):
    """Danh sách khách hàng và thông tin profile."""
    r = _get_redis()
    try:
        brands = ["zeo", "cfc"] if brand == "all" else [brand]
        all_customers = []

        for b in brands:
            pattern = f"{b}:customer:messenger:*"
            cursor = 0
            keys = []
            while True:
                cursor, batch = await r.scan(cursor, match=pattern, count=200)
                keys.extend(batch)
                if cursor == 0:
                    break

            for key in keys:
                raw = await r.get(key)
                if not raw:
                    continue
                try:
                    profile = json.loads(raw)
                except Exception:
                    continue
                sender_id = key.split(":")[-1]
                all_customers.append({
                    "sender_id": sender_id,
                    "brand": b.upper(),
                    "fb_name": profile.get("fb_name", ""),
                    "phone": profile.get("phone", "") or profile.get("customer_phone", ""),
                    "area": profile.get("area", "") or profile.get("customer_location", ""),
                    "lead_stage": profile.get("lead_stage", "new"),
                    "last_intent": profile.get("last_intent", ""),
                    "last_need": profile.get("last_need", ""),
                    "last_seen_at": profile.get("last_seen_at", ""),
                    "first_seen_at": profile.get("first_seen_at", ""),
                })

        # Sort by last_seen_at desc
        all_customers.sort(key=lambda x: x.get("last_seen_at", ""), reverse=True)
        total = len(all_customers)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "customers": all_customers[start:end],
        }
    finally:
        await r.aclose()


@router.get("/customers/{brand}/{sender_id}/session")
async def get_customer_session(brand: str, sender_id: str):
    """Xem session chat của 1 khách."""
    r = _get_redis()
    b = brand.lower()
    try:
        profile_raw = await r.get(f"{b}:customer:messenger:{sender_id}")
        session_raw = await r.get(f"{b}:session:messenger:{sender_id}")

        profile = json.loads(profile_raw) if profile_raw else {}
        session = json.loads(session_raw) if session_raw else {}

        return {
            "sender_id": sender_id,
            "brand": brand.upper(),
            "profile": profile,
            "session": session,
        }
    finally:
        await r.aclose()


class CustomerUpdateRequest(BaseModel):
    fb_name: Optional[str] = None
    phone: Optional[str] = None
    area: Optional[str] = None
    lead_stage: Optional[str] = None
    last_intent: Optional[str] = None


@router.put("/customers/{brand}/{sender_id}")
async def update_customer(brand: str, sender_id: str, req: CustomerUpdateRequest):
    """Chỉnh sửa thông tin khách hàng (SĐT, Khu vực, Tên, Lead stage) trong Redis."""
    r = _get_redis()
    b = brand.lower()
    customer_key = f"{b}:customer:messenger:{sender_id}"
    session_key = f"{b}:session:messenger:{sender_id}"
    try:
        raw_cust = await r.get(customer_key)
        profile = json.loads(raw_cust) if raw_cust else {}

        if req.fb_name is not None:
            profile["fb_name"] = req.fb_name
        if req.phone is not None:
            profile["phone"] = req.phone
            profile["customer_phone"] = req.phone
        if req.area is not None:
            profile["area"] = req.area
            profile["customer_location"] = req.area
        if req.lead_stage is not None:
            profile["lead_stage"] = req.lead_stage
        if req.last_intent is not None:
            profile["last_intent"] = req.last_intent

        profile["updated_at"] = datetime.now(timezone.utc).isoformat()
        await r.set(customer_key, json.dumps(profile, ensure_ascii=False))

        # Cập nhật cả session tương ứng nếu có
        raw_sess = await r.get(session_key)
        if raw_sess:
            sess = json.loads(raw_sess)
            if req.phone is not None:
                sess["customer_phone"] = req.phone
            if req.area is not None:
                sess["customer_location"] = req.area
            if req.lead_stage is not None:
                sess["lead_stage"] = req.lead_stage
            await r.set(session_key, json.dumps(sess, ensure_ascii=False))

        return {"success": True, "message": "Đã cập nhật thông tin khách hàng thành công!", "profile": profile}
    finally:
        await r.aclose()


@router.delete("/customers/{brand}/{sender_id}")
async def delete_customer(brand: str, sender_id: str):
    """Xóa hoàn toàn hồ sơ và session của khách hàng khỏi Redis."""
    r = _get_redis()
    b = brand.lower()
    try:
        await r.delete(f"{b}:customer:messenger:{sender_id}")
        await r.delete(f"{b}:session:messenger:{sender_id}")
        return {"success": True, "message": f"Đã xóa hoàn toàn khách hàng {sender_id} khỏi Redis"}
    finally:
        await r.aclose()


@router.delete("/customers/{brand}/{sender_id}/session")
async def reset_customer_session(brand: str, sender_id: str):
    """Reset session chat (giúp bot bắt đầu lại hội thoại)."""
    r = _get_redis()
    b = brand.lower()
    try:
        await r.delete(f"{b}:session:messenger:{sender_id}")
        return {"success": True, "message": f"Đã reset session của {sender_id}"}
    finally:
        await r.aclose()


# ─────────────────────────────────────────────────────
# MODULE 4: LEARNING QUEUE
# ─────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    intent: str
    question_examples: str  # Phân cách bằng ";"
    answer: str
    category: str = "faq"
    answer_mode: str = "rewrite"
    risk_level: str = "low"


@router.get("/learning-queue")
async def get_learning_queue(brand: str = Query("all"), limit: int = 50):
    """Lấy danh sách câu hỏi bot chưa chắc / khách phàn nàn để review."""
    r = _get_redis()
    try:
        brands = ["zeo", "cfc"] if brand == "all" else [brand]
        items = []

        for b in brands:
            lq_key = f"{b}:learning:queue"
            # Thử cả 2 kiểu key
            lq_key_alt = f"{b}:kb:learning:queue"

            for key in [lq_key, lq_key_alt]:
                key_type = await r.type(key)
                if key_type == "none":
                    continue

                if key_type == "list":
                    raw_items = await r.lrange(key, 0, limit - 1)
                elif key_type == "set":
                    raw_items = list(await r.smembers(key))[:limit]
                else:
                    continue

                for raw in raw_items:
                    try:
                        item = json.loads(raw)
                        item["brand"] = b.upper()
                        item["queue_key"] = key
                        items.append(item)
                    except Exception:
                        items.append({"raw": raw, "brand": b.upper(), "queue_key": key})

        return {"total": len(items), "items": items}
    finally:
        await r.aclose()


@router.post("/learning-queue/dismiss")
async def dismiss_queue_item(brand: str, queue_key: str, raw_value: str):
    """Xóa 1 item khỏi learning queue (bỏ qua)."""
    r = _get_redis()
    try:
        removed = await r.lrem(queue_key, 1, raw_value)
        return {"success": removed > 0}
    finally:
        await r.aclose()


@router.post("/learning-queue/approve")
async def approve_and_add_to_faq(brand: str, req: ApproveRequest):
    """
    Duyệt 1 câu từ Learning Queue → thêm vào Redis KB snapshot + re-sync vector.
    NOTE: Cần tự thêm vào Google Sheets riêng nếu muốn persist lâu dài.
    """
    from knowledge_sync import sync_brand, ensure_index, build_embed_text
    from embedder import embed_text as get_embed, vec_to_bytes, get_embed_dim

    r = _get_redis(decode=False)
    r_text = _get_redis(decode=True)

    try:
        # Đọc snapshot hiện tại
        kb_key = f"{brand.lower()}:kb:basic:active"
        raw = await r_text.get(kb_key)
        if not raw:
            raise HTTPException(status_code=404, detail=f"KB key '{kb_key}' không tìm thấy")

        data = json.loads(raw)
        if isinstance(data, dict):
            items_raw = data.get("snapshot_json") or data.get("knowledgeItems") or "[]"
            items = json.loads(items_raw) if isinstance(items_raw, str) else items_raw
            wrapper = data
        else:
            items = data
            wrapper = None

        # Tạo item mới
        new_item = {
            "active": True,
            "brand": brand.upper(),
            "category": req.category,
            "intent": req.intent,
            "question_examples": req.question_examples,
            "answer": req.answer,
            "priority": 80,
            "source_id": f"learning_approved_{int(time.time())}",
            "updated_at": datetime.now().strftime("%Y-%m-%d"),
            "audience": "customer",
            "answer_mode": req.answer_mode,
            "risk_level": req.risk_level,
        }

        # Thêm vào list và lưu lại
        items.append(new_item)
        if wrapper:
            wrapper["snapshot_json"] = json.dumps(items, ensure_ascii=False)
            await r_text.set(kb_key, json.dumps(wrapper, ensure_ascii=False))
        else:
            await r_text.set(kb_key, json.dumps(items, ensure_ascii=False))

        # Re-sync vector index cho item mới
        cfg = _cfg()
        index_name = f"{brand.lower()}:vec:faq"
        embed_dim = get_embed_dim()
        await ensure_index(r, index_name, embed_dim)

        embed_text_str = build_embed_text(new_item)
        vec = await get_embed(embed_text_str)
        if vec:
            doc_key = f"{index_name}:doc:{new_item['source_id']}:{req.intent}"
            await r.hset(doc_key, mapping={
                "embedding": vec_to_bytes(vec),
                "intent": req.intent,
                "brand": brand.upper(),
                "category": req.category,
                "answer": req.answer,
                "answer_mode": req.answer_mode,
                "risk_level": req.risk_level,
                "source_id": new_item["source_id"],
                "priority": 80,
            })

        return {"success": True, "intent": req.intent, "message": "Đã thêm vào KB và cập nhật Vector Index"}
    finally:
        await r.aclose()
        await r_text.aclose()


@router.post("/test/query")
async def test_query(query: str, brand: str = "zeo"):
    """Test 1 câu hỏi qua Semantic Search — xem bot sẽ trả lời gì."""
    from rag_search import semantic_search
    result = await semantic_search(query=query, brand=brand, top_k=5)
    return result
