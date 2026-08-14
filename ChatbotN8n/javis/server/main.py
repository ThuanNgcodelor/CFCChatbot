"""
main.py — FastAPI app chính cho Semantic RAG Service.

Endpoints:
  GET  /health          → kiểm tra service + Ollama + Redis
  POST /sync?brand=zeo  → đồng bộ FAQ từ Redis snapshot → Vector Index
  POST /search          → tìm kiếm ngữ nghĩa
  POST /rewrite         → gọi Ollama để viết lại câu trả lời tự nhiên hơn (tuỳ chọn)
"""

import json
import logging
from pathlib import Path
from typing import Optional

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from embedder import embed_text, get_embed_dim
from knowledge_sync import sync_brand
from rag_search import get_redis, semantic_search

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ZeO/CFC Semantic RAG Service",
    description="Tìm kiếm ngữ nghĩa tiếng Việt cho Chatbot ZeO và CFC Cò Bay",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_settings() -> dict:
    settings_path = Path(__file__).parent / "settings.json"
    return json.loads(settings_path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────
# Models
# ─────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    brand: str = "zeo"   # "zeo" hoặc "cfc"
    top_k: int = 5
    category_filter: Optional[str] = None


class RewriteRequest(BaseModel):
    query: str            # Câu hỏi gốc của khách
    answer: str           # Câu trả lời thô từ RAG
    brand: str = "zeo"
    tone: str = "friendly"  # "friendly" | "formal"


# ─────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────

@app.get("/health")
async def health():
    """Kiểm tra trạng thái của service, Ollama và Redis."""
    cfg = _load_settings()
    status = {"service": "ok", "ollama": "unknown", "redis": "unknown", "embed_model": cfg["ollama"]["embed_model"]}

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{cfg['ollama']['base_url']}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            has_embed = any(cfg["ollama"]["embed_model"].split(":")[0] in m for m in models)
            status["ollama"] = "ok"
            status["embed_model_available"] = has_embed
            status["available_models"] = models
    except Exception as e:
        status["ollama"] = f"error: {e}"

    # Check Redis
    try:
        r = await get_redis()
        await r.ping()
        status["redis"] = "ok"
        # Kiểm tra index đã tồn tại chưa
        try:
            result = await r.execute_command("FT._LIST")
            status["vector_indexes"] = [idx.decode() if isinstance(idx, bytes) else idx for idx in result]
        except Exception:
            status["vector_indexes"] = []
    except Exception as e:
        status["redis"] = f"error: {e}"

    return status


@app.post("/sync")
async def sync_knowledge(brand: str = Query("zeo", description="'zeo' hoặc 'cfc' hoặc 'all'")):
    """
    Đọc FAQ từ Redis snapshot, tạo embeddings, upsert vào Vector Index.
    Chạy khi cập nhật dữ liệu FAQ mới từ Google Sheets.
    """
    if brand.lower() == "all":
        zeo_result = await sync_brand("zeo")
        cfc_result = await sync_brand("cfc")
        return {"zeo": zeo_result, "cfc": cfc_result}
    
    if brand.lower() not in ("zeo", "cfc"):
        raise HTTPException(status_code=400, detail="brand phải là 'zeo', 'cfc', hoặc 'all'")
    
    result = await sync_brand(brand.lower())
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.post("/search")
async def search(req: SearchRequest):
    """
    Tìm kiếm ngữ nghĩa: nhận câu hỏi → embed → KNN trên Redis → trả top kết quả.
    
    n8n gọi endpoint này thay cho Node JS 'RAG Tim Kiem'.
    """
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query không được để trống")
    
    result = await semantic_search(
        query=req.query.strip(),
        brand=req.brand.lower(),
        top_k=min(req.top_k, 10),
        category_filter=req.category_filter,
    )
    
    if "error" in result:
        # Trả 200 thay vì 500 để n8n không crash — chỉ confidence=low
        return result
    
    return result


@app.post("/rewrite")
async def rewrite_answer(req: RewriteRequest):
    """
    Dùng Ollama (qwen2.5:7b-instruct) để viết lại câu trả lời thô RAG
    thành ngôn ngữ tự nhiên, thân thiện.
    
    n8n có thể gọi endpoint này sau /search nếu answer_mode='rewrite'.
    """
    cfg = _load_settings()
    
    brand_name = "ZeO" if req.brand.lower() == "zeo" else "Cò Bay"
    tone_instruction = (
        "thân thiện, gần gũi, dùng 'bạn' và 'mình'"
        if req.tone == "friendly"
        else "lịch sự, chuyên nghiệp"
    )
    
    system_prompt = (
        f"Bạn là nhân viên CSKH của {brand_name}. "
        f"Viết lại câu trả lời sau theo giọng {tone_instruction}. "
        f"Giữ nguyên tất cả thông tin thực tế (giá, địa chỉ, số điện thoại, chính sách). "
        f"KHÔNG thêm thông tin mới hoặc bịa đặt. Chỉ trả về câu trả lời, không giải thích."
    )
    
    user_prompt = (
        f"Khách hỏi: {req.query}\n"
        f"Câu trả lời thô: {req.answer}\n"
        f"Hãy viết lại câu trả lời cho tự nhiên hơn:"
    )
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{cfg['ollama']['base_url']}/api/chat",
                json={
                    "model": "qwen2.5:7b-instruct",
                    "stream": False,
                    "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 300},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            rewritten = data.get("message", {}).get("content", req.answer).strip()
    except Exception as e:
        logger.warning("Rewrite lỗi, trả về answer gốc: %s", e)
        rewritten = req.answer

    return {
        "original_answer": req.answer,
        "rewritten_answer": rewritten,
        "brand": req.brand,
    }


# ─────────────────────────────────────────
# Dev entrypoint
# ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    cfg = _load_settings()
    srv = cfg.get("server", {})
    uvicorn.run(
        "main:app",
        host=srv.get("host", "0.0.0.0"),
        port=srv.get("port", 8000),
        reload=srv.get("reload", True),
    )
