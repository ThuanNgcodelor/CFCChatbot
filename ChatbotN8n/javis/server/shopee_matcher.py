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
    for p in [
        Path(__file__).resolve().parent.parent / "knowledge" / "shopee_catalog.json",
        Path(__file__).resolve().parents[2] / "knowledge" / "shopee_catalog.json",
        Path(__file__).resolve().parent / "shopee_catalog.json",
    ]:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    _catalog_cache = data.get("products", [])
                elif isinstance(data, list):
                    _catalog_cache = data
                return _catalog_cache or []
            except Exception as e:
                logger.warning("Lỗi đọc shopee_catalog.json (%s): %s", p, e)
    return _catalog_cache or []


def is_promotion_inquiry(text: str) -> bool:
    """Kiểm tra xem câu hỏi có chứa ý định hỏi về Sale / Khuyến Mãi / Giảm Giá / Ưu Đãi / Voucher không."""
    folded = _fold(text)
    triggers = [
        "sale", "khuyen mai", "giam gia", "uu dai", "voucher", "ma giam",
        "co giam", "co sale", "co khuyen mai", "dang sale", "dang giam", "deal",
        "chiet khau", "tang kem", "qua tang", "combo", "gia re"
    ]
    return any(t in folded for t in triggers)


def is_shopee_inquiry(text: str) -> bool:
    """Kiểm tra xem câu hỏi có chứa ý định mua qua Shopee / xin link mua hàng không."""
    folded = _fold(text)
    triggers = [
        "shopee", "shoppe", "sopi", "sope", "shopi", "san tmdt",
        "link mua", "link san pham", "gui link", "cho link", "cho xin link",
        "mua o dau", "dat online", "dat hang tren mang", "link shop", "link gian hang"
    ]
    return any(t in folded for t in triggers)


def match_promotions_and_deals(query: str, brand: str = "zeo") -> dict:
    """
    Trả lời trung thực về các chương trình Sale & Khuyến mãi hiện có của ZeO / CFC.
    Không bịa giá — điều hướng xem trực tiếp tại Shopee Mall hoặc hỗ trợ qua nhân viên.
    """
    brand_display = "ZeO Vietnam" if brand.lower() == "zeo" else "CFC Cò Bay"
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"

    if brand.lower() == "zeo":
        reply = (
            f"Dạ các chương trình khuyến mãi, Flash Sale và Voucher giảm giá độc quyền được {brand_display} "
            f"cập nhật liên tục trực tiếp trên gian hàng chính hãng Shopee Mall:\n\n"
            f"👉 {general_link}\n\n"
            f"• Gian hàng đang hỗ trợ mã **Freeship Extra** toàn quốc cùng các mã giảm giá theo từng đợt khuyến mãi của sàn.\n"
            f"• Bạn có thể bấm vào link trên để xem giá ưu đãi mới nhất hoặc nhắn tên dòng sản phẩm bạn quan tâm để mình hỗ trợ nhé! 💙"
        )
    else:
        reply = (
            f"Dạ các chương trình ưu đãi và chiết khấu phân bón {brand_display} được áp dụng theo từng vụ mùa và số lượng đặt hàng. "
            f"Bạn vui lòng để lại Số Điện Thoại và Cây Trồng cần bón để kỹ sư Cò Bay liên hệ gửi chính sách ưu đãi tốt nhất cho mình nhé ạ!"
        )

    return {
        "matched": True,
        "intent": "promotion_deals",
        "confidence": "high",
        "score": 0.96,
        "suggested_reply": reply,
        "shopee_url": general_link
    }


def match_shopee_product(query: str, brand: str = "zeo") -> Optional[dict]:
    """
    Khớp câu hỏi của khách với sản phẩm Shopee phù hợp nhất.
    Trả về thông tin sản phẩm và mẫu câu trả lời kèm link trực tiếp.
    """
    # Nếu hỏi về khuyến mãi / sale trên Shopee -> Trả về deal khuyến mãi
    if is_promotion_inquiry(query):
        return match_promotions_and_deals(query, brand=brand)

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
            general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"
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
        f"👉 {best_match.get('link_shopee') or best_match.get('shopee_url', '')}\n\n"
        f"• **Giá niêm yết:** {best_match.get('price', 'Ưu đãi')}\n"
        f"• **Ưu đãi:** {best_match.get('promotion', 'Freeship Extra toàn quốc')}\n\n"
        f"Bạn bấm vào link để đặt hàng giao tận nơi nhé! Cần hỗ trợ thêm bạn cứ nhắn mình nha. 💙"
    )

    return {
        "matched": True,
        "is_general_store": False,
        "product_id": best_match.get("id"),
        "product_name": best_match.get("name"),
        "shopee_url": best_match.get("link_shopee") or best_match.get("shopee_url", ""),
        "matched_product": best_match,
        "suggested_reply": reply,
    }
