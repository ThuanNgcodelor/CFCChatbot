"""
rag_search.py — Tìm kiếm ngữ nghĩa (Semantic Search) qua RediSearch Vector.

Nhận câu hỏi của khách → embed → KNN search trong Redis → trả top-k kết quả.
"""

import json
import logging
import struct
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import redis.asyncio as aioredis

from embedder import embed_text, vec_to_bytes, get_embed_dim

logger = logging.getLogger(__name__)

_redis_pool: Optional[aioredis.Redis] = None


def _load_settings() -> dict:
    settings_path = Path(__file__).parent / "settings.json"
    return json.loads(settings_path.read_text(encoding="utf-8"))


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        cfg = _load_settings()["redis"]
        # Dùng kwargs riêng lᮧ để tránh lỗi URL-encoding khi password có ký tự đặc biệt
        _redis_pool = aioredis.Redis(
            host=cfg["host"],
            port=int(cfg["port"]),
            password=cfg["password"],
            db=int(cfg.get("db", 0)),
            decode_responses=False,
        )
    return _redis_pool


def get_index_name(brand: str, cfg: dict) -> str:
    if brand.lower() == "cfc":
        return cfg["rag"]["cfc_index_name"]
    return cfg["rag"]["zeo_index_name"]


def _cosine_to_confidence(distance: float) -> float:
    """
    RediSearch COSINE trả về DISTANCE (0=giống nhau, 2=hoàn toàn khác).
    Chuyển thành score 0..1 (1=hoàn toàn giống).
    """
    similarity = 1.0 - (distance / 2.0)
    return round(max(0.0, min(1.0, similarity)), 4)


def _normalize_vi_query(text: str) -> str:
    import unicodedata
    import re
    t = unicodedata.normalize("NFD", str(text or ""))
    t = re.sub(r"[\u0300-\u036f]", "", t)
    t = t.replace("đ", "d").replace("Đ", "d")
    return t.lower().strip()


async def semantic_search(
    query: str,
    brand: str = "zeo",
    top_k: int = 5,
    category_filter: Optional[str] = None,
) -> dict:
    """
    Tìm FAQ gần nhất với câu hỏi `query` trong vector index của brand tương ứng.
    """
    cfg = _load_settings()
    rag_cfg = cfg["rag"]
    index_name = get_index_name(brand, cfg)

    # 1. Tạo embedding cho câu hỏi (kết hợp cả có dấu và không dấu để tối ưu tiếng Việt)
    norm_q = _normalize_vi_query(query)
    embed_query = f"{query} | {norm_q}" if query.strip().lower() != norm_q else query
    vec = await embed_text(embed_query)
    if vec is None:
        return {
            "error": "Không thể tạo embedding cho query — Ollama có thể đang không chạy",
            "query": query,
            "confidence": "low",
            "score": 0.0,
        }

    query_bytes = vec_to_bytes(vec)

    # 2. Chạy KNN search trên RediSearch
    r = await get_redis()
    try:
        # Build filter
        if category_filter:
            filter_str = f"@category:{{{category_filter}}}"
        else:
            filter_str = "*"

        results = await r.execute_command(
            "FT.SEARCH", index_name,
            f"({filter_str})=>[KNN {top_k} @embedding $vec AS __score]",
            "PARAMS", "2", "vec", query_bytes,
            "RETURN", "6", "intent", "answer", "answer_mode", "risk_level", "category", "__score",
            "SORTBY", "__score", "ASC",
            "DIALECT", "2",
        )
    except Exception as e:
        err_msg = str(e)
        if "no such index" in err_msg.lower() or "unknown index" in err_msg.lower():
            return {
                "error": f"Index '{index_name}' chưa tồn tại. Hãy chạy POST /sync?brand={brand} trước.",
                "query": query,
                "confidence": "low",
                "score": 0.0,
            }
        logger.error("RediSearch error: %s", e)
        return {"error": str(e), "query": query, "confidence": "low", "score": 0.0}

    # 3. Parse kết quả
    if not results or results[0] == 0:
        return {
            "query": query,
            "brand": brand,
            "confidence": "low",
            "score": 0.0,
            "intent": "",
            "answer": "",
            "answer_mode": "direct",
            "risk_level": "low",
            "results": [],
        }

    total = results[0]
    parsed_results = []

    # RediSearch trả về: [count, key1, [field1, val1, ...], key2, ...]
    i = 1
    while i < len(results):
        doc_key = results[i].decode() if isinstance(results[i], bytes) else results[i]
        fields_raw = results[i + 1] if i + 1 < len(results) else []
        i += 2

        fields = {}
        j = 0
        while j < len(fields_raw) - 1:
            k = fields_raw[j]
            v = fields_raw[j + 1]
            key = k.decode() if isinstance(k, bytes) else k
            val = v.decode() if isinstance(v, bytes) else v
            fields[key] = val
            j += 2

        distance = float(fields.get("__score", 2.0))
        score = _cosine_to_confidence(distance)

        parsed_results.append({
            "intent": fields.get("intent", ""),
            "answer": fields.get("answer", ""),
            "answer_mode": fields.get("answer_mode", "direct"),
            "risk_level": fields.get("risk_level", "low"),
            "category": fields.get("category", "faq"),
            "score": score,
        })

    if not parsed_results:
        return {
            "query": query,
            "brand": brand,
            "confidence": "low",
            "score": 0.0,
            "intent": "",
            "answer": "",
            "results": [],
        }

    best = parsed_results[0]
    best_score = best["score"]
    second_score = parsed_results[1]["score"] if len(parsed_results) > 1 else 0.0
    margin = best_score - second_score

    high_thresh = rag_cfg["high_confidence_threshold"]
    med_thresh = rag_cfg["medium_confidence_threshold"]

    if best_score >= high_thresh and margin >= 0.05:
        confidence = "high"
    elif best_score >= med_thresh:
        confidence = "medium"
    # 3-Layer Fallback:
    # 1. Score >= High (0.78): Direct / confident reply
    # 2. Score >= Med (0.55): Medium confidence / Rewrite
    # 3. Score < Med (0.55): Auto-escalate to Admin via Telegram + push to Learning Queue
    if confidence == "low":
        fallback_msg = (
            f"Dạ câu hỏi này em xin phép chuyển cho chuyên viên tư vấn của {brand.upper()} hỗ trợ mình kỹ hơn ngay nhé ạ! "
            "Anh/chị có thể để lại số điện thoại hoặc tin nhắn chi tiết giúp em nha."
        )
        if not best["answer"] or best_score < 0.35:
            best["answer"] = fallback_msg

        # Auto-push to Learning Queue in Redis
        try:
            r = await get_redis()
            lq_item = json.dumps({
                "query": query,
                "user_message": query,
                "confidence": best_score,
                "brand": brand.upper(),
                "bot_reply": best["answer"],
                "timestamp": datetime.now().isoformat() if "datetime" in globals() else "",
            }, ensure_ascii=False)
            await r.rpush(f"{brand.lower()}:learning:queue", lq_item)
        except Exception:
            pass

        # Auto-notify admin via Telegram
        try:
            from telegram_notifier import notify_admin_unanswered
            import asyncio
            asyncio.create_task(notify_admin_unanswered(brand=brand, query=query, score=best_score))
        except Exception:
            pass

    return {
        "query": query,
        "brand": brand,
        "confidence": confidence,
        "score": best_score,
        "score_margin": round(margin, 4),
        "intent": best["intent"],
        "answer": best["answer"],
        "answer_mode": best["answer_mode"],
        "risk_level": best["risk_level"],
        "category": best["category"],
        "results": parsed_results,
    }
