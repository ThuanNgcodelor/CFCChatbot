"""
knowledge_sync.py — Đọc dữ liệu FAQ từ Redis (JSON snapshot của n8n),
tạo vector embeddings cho mỗi item, và upsert vào Redis Vector Index (RediSearch).

Chạy thủ công: python knowledge_sync.py
Hoặc gọi qua API: POST /sync?brand=zeo
"""

import asyncio
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional

import redis.asyncio as aioredis

from embedder import embed_text, get_embed_dim, vec_to_bytes

logger = logging.getLogger(__name__)


def _load_settings() -> dict:
    settings_path = Path(__file__).parent / "settings.json"
    return json.loads(settings_path.read_text(encoding="utf-8"))


def normalize_vi(text: str) -> str:
    """Chuẩn hóa tiếng Việt về dạng không dấu, lowercase để ghép vào embedding text."""
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[\u0300-\u036f]", "", text)
    text = text.replace("đ", "d").replace("Đ", "D")
    return text.lower()


def build_embed_text(item: dict) -> str:
    """
    Gom intent + question_examples + answer thành một đoạn text cho embedding.
    Ghép cả dạng gốc (có dấu) + dạng không dấu để model học cả 2 biến thể.
    """
    intent = str(item.get("intent", "")).replace("_", " ")
    answer = str(item.get("answer", ""))
    
    # question_examples có thể là string phân cách bởi ";" hoặc list
    raw_examples = item.get("question_examples", "")
    if isinstance(raw_examples, list):
        examples = [e.strip() for e in raw_examples if e.strip()]
    else:
        examples = [e.strip() for e in str(raw_examples).split(";") if e.strip()]

    parts = [intent] + examples + [answer]
    original_text = " | ".join(parts)
    no_accent_text = normalize_vi(original_text)
    
    # Kết hợp cả 2 để model nắm được cả 2 cách viết
    return f"{original_text} | {no_accent_text}"


def parse_snapshot(raw: str) -> list[dict]:
    """Parse JSON snapshot từ Redis (có thể là array hoặc có wrapper envelope)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Không parse được snapshot JSON")
        return []
    
    if isinstance(data, list):
        return data
    
    # Dạng envelope: {"snapshot_json": "[...]", "updated_at": "..."}
    items_raw = data.get("snapshot_json") or data.get("knowledgeItems") or data.get("snapshot")
    if isinstance(items_raw, str):
        try:
            items = json.loads(items_raw)
        except json.JSONDecodeError:
            return []
    elif isinstance(items_raw, list):
        items = items_raw
    else:
        return []
    
    return items if isinstance(items, list) else []


def get_index_name(brand: str, cfg: dict) -> str:
    if brand.lower() == "cfc":
        return cfg["rag"]["cfc_index_name"]
    return cfg["rag"]["zeo_index_name"]


def get_kb_key(brand: str, cfg: dict) -> str:
    if brand.lower() == "cfc":
        return cfg["rag"]["cfc_kb_key"]
    return cfg["rag"]["zeo_kb_key"]


async def ensure_index(r: aioredis.Redis, index_name: str, embed_dim: int) -> None:
    """Tạo RediSearch Vector Index nếu chưa có."""
    try:
        await r.execute_command("FT.INFO", index_name)
        logger.info("Index '%s' đã tồn tại.", index_name)
    except Exception:
        logger.info("Tạo mới index '%s' (dim=%d)...", index_name, embed_dim)
        # Schema: lưu doc dạng HASH
        # Field: embedding (VECTOR), intent (TEXT), brand (TAG), answer (TEXT), source_id (TAG), category (TAG)
        await r.execute_command(
            "FT.CREATE", index_name,
            "ON", "HASH",
            "PREFIX", "1", f"{index_name}:doc:",
            "SCHEMA",
            "embedding", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(embed_dim),
                "DISTANCE_METRIC", "COSINE",
            "intent", "TEXT", "WEIGHT", "2.0",
            "brand", "TAG",
            "category", "TAG",
            "answer_mode", "TAG",
            "risk_level", "TAG",
            "source_id", "TAG",
            "priority", "NUMERIC",
            "answer", "TEXT",
        )
        logger.info("Tạo index '%s' thành công.", index_name)


async def sync_brand(brand: str = "zeo") -> dict:
    """
    Đồng bộ dữ liệu FAQ từ Redis snapshot → Vector Index.
    """
    cfg = _load_settings()
    redis_cfg = cfg["redis"]
    
    # Dùng kwargs riêng lẻ để tránh lỗi URL-encoding khi password có ký tự đặc biệt
    r = aioredis.Redis(
        host=redis_cfg["host"],
        port=int(redis_cfg["port"]),
        password=redis_cfg["password"],
        db=int(redis_cfg.get("db", 0)),
        decode_responses=False,
    )

    try:
        kb_key = get_kb_key(brand, cfg)
        index_name = get_index_name(brand, cfg)
        embed_dim = get_embed_dim()

        # Đọc snapshot từ Redis
        raw = await r.get(kb_key)
        if not raw:
            return {"error": f"Key '{kb_key}' không tìm thấy trong Redis", "synced": 0}
        
        items = parse_snapshot(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        if not items:
            return {"error": "Snapshot rỗng hoặc không parse được", "synced": 0}

        # Tạo index nếu chưa có
        await ensure_index(r, index_name, embed_dim)

        # Upsert từng item
        synced = 0
        skipped = 0
        errors = 0
        
        for item in items:
            # Lọc bỏ item không active, không có answer, audience=internal
            active = str(item.get("active", "true")).lower() in ("true", "1", "yes")
            if not active:
                skipped += 1
                continue
            if not item.get("answer") or not item.get("intent"):
                skipped += 1
                continue
            if str(item.get("audience", "customer")).lower() == "internal":
                skipped += 1
                continue

            embed_text_str = build_embed_text(item)
            vec = await embed_text(embed_text_str)
            
            if vec is None:
                logger.warning("Không lấy được embedding cho intent: %s", item.get("intent"))
                errors += 1
                continue

            doc_key = f"{index_name}:doc:{item.get('source_id', 'faq')}:{item.get('intent', 'unknown')}"
            
            mapping = {
                "embedding": vec_to_bytes(vec),
                "intent": str(item.get("intent", "")),
                "brand": str(item.get("brand", brand)).split("/")[0].strip(),
                "category": str(item.get("category", "faq")),
                "answer": str(item.get("answer", "")),
                "answer_mode": str(item.get("answer_mode", "direct")),
                "risk_level": str(item.get("risk_level", "low")),
                "source_id": str(item.get("source_id", "")),
                "priority": int(item.get("priority", 0)),
            }
            
            await r.hset(doc_key, mapping=mapping)
            synced += 1
            logger.info("✓ [%s] %s", brand.upper(), item.get("intent"))

        return {
            "brand": brand,
            "index": index_name,
            "synced": synced,
            "skipped": skipped,
            "errors": errors,
            "total": len(items),
        }
    finally:
        await r.aclose()


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    
    print("=== Đồng bộ ZeO KB → Redis Vector ===")
    result = await sync_brand("zeo")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print("\n=== Đồng bộ CFC KB → Redis Vector ===")
    result = await sync_brand("cfc")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
