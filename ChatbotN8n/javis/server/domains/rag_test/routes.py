"""
domains.rag_test.routes — FastAPI Router cho Kiểm Thử Semantic Search RAG.
"""

from fastapi import APIRouter, Query

router = APIRouter(prefix="/test", tags=["RAG Testing & Evaluation"])


@router.post("/query")
async def test_query_endpoint(query: str = Query(...), brand: str = Query("zeo")):
    """Test 1 câu hỏi qua Semantic Search — xem bot sẽ trả lời gì."""
    from rag_search import semantic_search
    result = await semantic_search(query=query, brand=brand, top_k=5)
    return result
