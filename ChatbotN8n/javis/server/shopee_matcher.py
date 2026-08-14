"""
shopee_matcher.py — Module Khớp & Gửi Link Sản Phẩm Shopee Thông Minh cho CFC AI
Chức năng:
  1. Quản lý danh mục sản phẩm Shopee (SKU, giá bán, link Shopee Mall, ưu đãi).
  2. Tự động nhận diện nhu cầu mua hàng sàn TMĐT qua tin nhắn khách.
  3. Khớp chính xác sản phẩm (kể cả viết tắt, không dấu, màu sắc).
  4. Tạo câu trả lời kèm link Shopee chính xác & lời kêu gọi mua hàng (Call to Action).
"""

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_catalog_cache: Optional[list[dict]] = None


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d").replace("Đ", "d").lower()


def load_shopee_catalog() -> list[dict]:
    """Đọc danh mục sản phẩm Shopee từ file knowledge/shopee_catalog.json."""
    global _catalog_cache
    catalog_path = Path(__file__).resolve().parents[2] / "knowledge" / "shopee_catalog.json"
    if catalog_path.exists():
        try:
            _catalog_cache = json.loads(catalog_path.read_text(encoding="utf-8"))
            return _catalog_cache
        except Exception as e:
            logger.warning("Lỗi đọc shopee_catalog.json: %s", e)
    return _catalog_cache or []


def is_shopee_inquiry(text: str) -> bool:
    """Kiểm tra xem câu hỏi có chứa ý định mua qua Shopee / xin link mua hàng không."""
    folded = _fold(text)
    triggers = [
        "shopee", "shoppe", "sopi", "sope", "shopi", "san tmdt",
        "link mua", "link san pham", "gui link", "cho link", "cho xin link",
        "mua o dau", "dat online", "dat hang tren mang", "link shop", "link gian hang"
    ]
    return any(t in folded for t in triggers)


def match_shopee_product(query: str, brand: str = "zeo") -> Optional[dict]:
    """
    Khớp câu hỏi của khách với sản phẩm Shopee phù hợp nhất.
    Trả về thông tin sản phẩm và mẫu câu trả lời kèm link trực tiếp.
    """
    catalog = load_shopee_catalog()
    if not catalog:
        return None

    query_folded = _fold(query)
    brand_upper = brand.upper()

    # Lọc theo thương hiệu
    brand_products = [
        p for p in catalog
        if p.get("brand", "").upper() == brand_upper or (brand_upper == "ZEO" and p.get("brand") in ["ZEO", "PANO", "OPLUS"])
    ]
    if not brand_products:
        brand_products = catalog

    best_match = None
    highest_score = 0

    for prod in brand_products:
        prod_name_folded = _fold(prod.get("name", ""))
        keywords = prod.get("keywords", [])
        score = 0

        # Khớp từ khóa cụ thể
        for kw in keywords:
            kw_folded = _fold(kw)
            if kw_folded in query_folded:
                score += 3

        # Khớp từng từ trong tên sản phẩm
        words = prod_name_folded.split()
        for w in words:
            if len(w) >= 3 and w in query_folded:
                score += 1

        # Ưu tiên nếu khớp biến thể (màu sắc, dung tích)
        variant = _fold(prod.get("variant", ""))
        for v in variant.split():
            if len(v) >= 3 and v in query_folded:
                score += 2

        if score > highest_score:
            highest_score = score
            best_match = prod

    if not best_match or highest_score < 2:
        # Nếu khách chỉ hỏi link Shopee chung chung
        if is_shopee_inquiry(query):
            general_link = "https://shopee.vn/zeovietnam" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"
            brand_display = "ZeO Vietnam" if brand.lower() == "zeo" else "Cò Bay"
            return {
                "matched": True,
                "is_general_store": True,
                "product_name": f"Gian hàng Shopee chính thức {brand_display}",
                "shopee_url": general_link,
                "suggested_reply": (
                    f"Dạ, bạn có thể ghé gian hàng Shopee chính thức của {brand_display} tại link này nha:\n"
                    f"👉 {general_link}\n\n"
                    f"Gian hàng đang có đầy đủ các dòng sản phẩm cùng nhiều mã Freeship Extra và Voucher ưu đãi độc quyền ạ! 💙"
                ),
            }
        return None

    # Tạo câu trả lời cụ thể cho sản phẩm
    reply = (
        f"Dạ, link mua **{best_match['name']}** chính hãng trên Shopee Mall đây nha bạn:\n\n"
        f"👉 {best_match['shopee_url']}\n\n"
        f"• **Giá niêm yết:** {best_match.get('price', 'Ưu đãi')}\n"
        f"• **Ưu đãi:** {best_match.get('promotion', 'Freeship Extra toàn quốc')}\n\n"
        f"Bạn bấm vào link để đặt hàng giao tận nơi nhé! Cần hỗ trợ thêm bạn cứ nhắn mình nha. 💙"
    )

    return {
        "matched": True,
        "is_general_store": False,
        "product_id": best_match.get("id"),
        "product_name": best_match.get("name"),
        "price": best_match.get("price"),
        "shopee_url": best_match.get("shopee_url"),
        "promotion": best_match.get("promotion"),
        "suggested_reply": reply,
    }
