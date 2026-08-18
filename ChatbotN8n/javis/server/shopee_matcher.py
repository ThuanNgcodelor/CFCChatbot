"""
shopee_matcher.py — Module Khớp, Tư Vấn & Gửi Link Shopee Động cho ZeO & CFC
Hỗ trợ AI Customer Service Specialist:
  1. Đọc danh mục sản phẩm Shopee động từ Redis (zeo:shopee:catalog:active / cfc:shopee:catalog:active)
  2. Tự động dự phòng đọc từ Google Sheet CSV nếu Redis chưa có snapshot
  3. Lọc & gợi ý sản phẩm theo Tầm Giá / Ngân Sách (dưới 100k, 50k-100k...)
  4. Lọc Bán Chạy & Mới Nhất theo từng Danh Mục (nước rửa chén, bột giặt, nước giặt...)
  5. Báo giá & gửi link trực tiếp Shopee Mall cho sản phẩm đích danh
  6. Tư vấn theo nhu cầu khách hàng (tiết kiệm, thơm lâu, sạch sâu, dịu nhẹ da tay)
  7. Làm mới cache tức thì qua refresh_shopee_cache()
"""

import csv
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)

# In-memory Hot Cache phân theo brand
_catalog_cache: dict[str, list[dict]] = {}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d").replace("Đ", "d").lower()


def _format_price(price: Any) -> str:
    try:
        num = int(str(price).replace(".", "").replace(",", "").replace("đ", "").strip())
        return f"{num:,.0f}đ".replace(",", ".")
    except Exception:
        return str(price or "Ưu đãi")


def _format_discount(disc: Any) -> str:
    s = str(disc or "").strip()
    if not s or s in ("0", "0%", "0.0"):
        return ""
    try:
        if "." in s and not s.endswith("%"):
            val = float(s)
            if 0 < val < 1:
                return f"{int(round(val * 100))}%"
        if s.endswith("%"):
            return s
        num = float(s)
        return f"{int(num)}%"
    except Exception:
        return s if s.endswith("%") else f"{s}%"


def _get_redis_sync_client() -> Optional[redis.Redis]:
    settings_path = Path(__file__).parent / "settings.json"
    if not settings_path.exists():
        settings_path = Path(__file__).parent / "settings.example.json"
    try:
        cfg = json.loads(settings_path.read_text(encoding="utf-8"))
        rcfg = cfg.get("redis", {})
        return redis.Redis(
            host=rcfg.get("host", "127.0.0.1"),
            port=int(rcfg.get("port", 6379)),
            password=rcfg.get("password"),
            db=int(rcfg.get("db", 0)),
            decode_responses=True,
        )
    except Exception as e:
        logger.warning("Không kết nối được Redis sync client: %s", e)
        return None


def _load_catalog_from_csv(brand: str) -> list[dict]:
    """Fallback đọc catalog từ file CSV template nếu Redis chưa có."""
    csv_candidates = [
        Path(__file__).resolve().parents[2] / "google_upload" / "zeo_shopee_catalog_template.csv",
        Path(__file__).resolve().parents[2] / "google_upload" / "zeovietnamofficial_shopee_catalog_crawled.csv",
    ]
    for p in csv_candidates:
        if p.exists():
            try:
                products = []
                with open(p, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        active = str(row.get("active", "true")).lower() in ("true", "1", "yes")
                        if not active:
                            continue
                        row_brand = row.get("brand", "").upper()
                        if brand.upper() == "ZEO" and row_brand in ["ZEO", "PANO", "OPLUS"]:
                            pass
                        elif brand.upper() == "CFC" and row_brand == "CFC":
                            pass
                        elif brand.upper() != row_brand:
                            continue

                        raw_kw = row.get("keywords", "")
                        kw_list = [k.strip() for k in raw_kw.split(";") if k.strip()] if isinstance(raw_kw, str) else list(raw_kw)
                        products.append({
                            "item_id": row.get("item_id", ""),
                            "name": row.get("name", ""),
                            "brand": row.get("brand", "ZeO"),
                            "category": row.get("category", ""),
                            "price": row.get("price", ""),
                            "original_price": row.get("original_price", ""),
                            "discount": row.get("discount", ""),
                            "badge": row.get("badge", "STANDARD"),
                            "specs": row.get("specs", ""),
                            "keywords": kw_list,
                            "variants": [v.strip() for v in str(row.get("variants", "")).split(";") if v.strip()],
                            "link_shopee": row.get("link_shopee") or row.get("shopee_url", ""),
                            "in_stock": str(row.get("in_stock", "true")).lower() in ("true", "1", "yes"),
                        })
                if products:
                    logger.info("Loaded %d Shopee products from CSV fallback (%s)", len(products), p.name)
                    return products
            except Exception as e:
                logger.warning("Error reading Shopee CSV fallback: %s", e)
    return []


def load_shopee_catalog(brand: str = "zeo") -> list[dict]:
    """Đọc danh mục sản phẩm Shopee động từ Redis hoặc fallback CSV."""
    global _catalog_cache
    b = brand.lower()
    if b in _catalog_cache and _catalog_cache[b]:
        return _catalog_cache[b]

    # 1. Thử đọc từ Redis key: {brand}:shopee:catalog:active
    r = _get_redis_sync_client()
    if r:
        try:
            redis_key = f"{b}:shopee:catalog:active"
            raw_data = r.get(redis_key)
            if not raw_data and b == "zeo":
                raw_data = r.get("zeo:shopee:catalog:active")

            if raw_data:
                parsed = json.loads(raw_data)
                items = parsed if isinstance(parsed, list) else parsed.get("products", [])
                if items:
                    _catalog_cache[b] = items
                    logger.info("Loaded %d Shopee products from Redis [%s]", len(items), redis_key)
                    return items
        except Exception as e:
            logger.warning("Lỗi đọc Shopee catalog từ Redis: %s", e)
        finally:
            try:
                r.close()
            except Exception:
                pass

    # 2. Fallback đọc từ file CSV template
    csv_products = _load_catalog_from_csv(b)
    if csv_products:
        _catalog_cache[b] = csv_products
        return csv_products

    return []


def refresh_shopee_cache(brand: str = "all"):
    """Làm mới lại in-memory cache cho Shopee catalog."""
    global _catalog_cache
    if brand == "all":
        _catalog_cache.clear()
        load_shopee_catalog("zeo")
        load_shopee_catalog("cfc")
    else:
        _catalog_cache.pop(brand.lower(), None)
        load_shopee_catalog(brand.lower())
    logger.info("✓ Shopee hot in-memory cache refreshed for brand=%s", brand)


def _detect_category_from_text(text: str) -> Optional[str]:
    folded = _fold(text)
    if any(k in folded for k in ["rua chen", "rua bat", "chen bat"]):
        return "Nước rửa chén"
    if any(k in folded for k in ["bot giat"]):
        return "Bột giặt"
    if any(k in folded for k in ["nuoc giat", "giat xa", "giat quan ao"]):
        return "Nước giặt"
    if any(k in folded for k in ["lau san", "lau nha"]):
        return "Nước lau sàn"
    if any(k in folded for k in ["toilet", "bon cau", "tay toilet"]):
        return "Tẩy Toilet"
    if any(k in folded for k in ["javel", "javen", "tay trang"]):
        return "Nước tẩy trắng Javen"
    if any(k in folded for k in ["tay mau", "oxy active"]):
        return "Nước tẩy quần áo màu"
    if any(k in folded for k in ["xa vai", "nuoc xa"]):
        return "Nước xả vải"
    if any(k in folded for k in ["lau kinh"]):
        return "Nước lau kính"
    if any(k in folded for k in ["tinh dau", "treo xe", "nuoc hoa xe"]):
        return "Tinh dầu & Nước hoa"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. PARSE BUDGET & GỢI Ý THEO TẦM GIÁ / NGÂN SÁCH
# ─────────────────────────────────────────────────────────────────────────────
def parse_budget_range(text: str) -> tuple[Optional[int], Optional[int]]:
    """Trích xuất khoảng giá min, max từ câu hỏi của khách hàng (vd: dưới 100k, 50k-100k...)."""
    folded = _fold(text).replace(",", "").replace(".", "")

    # Mẫu "từ X đến Y" hoặc "X - Y" hoặc "X den Y"
    range_match = re.search(r"(?:tu\s+)?(\d+)\s*(?:k|ngan|nghin|000)?\s*(?:-|den|toi|den muc)\s*(\d+)\s*(?:k|ngan|nghin|000|d|dong)?", folded)
    if range_match:
        try:
            v1 = int(range_match.group(1))
            v2 = int(range_match.group(2))
            min_p = v1 * 1000 if v1 < 1000 else v1
            max_p = v2 * 1000 if v2 < 1000 else v2
            if min_p > max_p:
                min_p, max_p = max_p, min_p
            return (min_p, max_p)
        except Exception:
            pass

    # Mẫu "dưới X", "tầm X đổ lại", "X quay đầu", "< X", "khoảng dưới X", "tầm dưới X"
    under_match = re.search(r"(?:duoi|tam duoi|khoang duoi|do lai|quay dau|<\s*|re hon|it hon|khong qua|tam khoang|tam)\s*(\d+)\s*(?:k|ngan|nghin|000|d|dong)?", folded)
    if under_match:
        try:
            val = int(under_match.group(1))
            max_p = val * 1000 if val < 1000 else val
            return (0, max_p)
        except Exception:
            pass

    # Mẫu "trên X", "> X"
    above_match = re.search(r"(?:tren|hon|>\s*)\s*(\d+)\s*(?:k|ngan|nghin|000|d|dong)?", folded)
    if above_match:
        try:
            val = int(above_match.group(1))
            min_p = val * 1000 if val < 1000 else val
            return (min_p, None)
        except Exception:
            pass

    return (None, None)


def is_budget_inquiry(text: str) -> bool:
    """Kiểm tra câu hỏi có chứa ý định hỏi về tầm giá, ngân sách không."""
    folded = _fold(text)
    if not any(k in folded for k in ["gia", "tam", "duoi", "khoang", "do lai", "quay dau", "muc gia", "ngan sach", "re"]):
        return False
    min_p, max_p = parse_budget_range(text)
    return max_p is not None or min_p is not None


def match_products_by_budget(query: str, brand: str = "zeo") -> Optional[dict]:
    """Lọc và gợi ý các sản phẩm phù hợp nhất trong khoảng giá người dùng yêu cầu."""
    min_p, max_p = parse_budget_range(query)
    if min_p is None and max_p is None:
        return None

    min_p = min_p or 0
    max_p = max_p or 999999999

    catalog = load_shopee_catalog(brand=brand)
    if not catalog:
        return None

    # Lọc sản phẩm còn hàng trong khoảng giá
    matched = []
    for p in catalog:
        if not p.get("in_stock", True):
            continue
        try:
            price = int(str(p.get("price", 0)).replace(".", "").replace(",", ""))
            if min_p <= price <= max_p:
                matched.append(p)
        except Exception:
            continue

    if not matched:
        return None

    # Kiểm tra xem khách có chỉ định danh mục không
    target_category = _detect_category_from_text(query)
    if target_category:
        cat_matched = [p for p in matched if p.get("category") == target_category]
        if cat_matched:
            matched = cat_matched

    # Ưu tiên Best Seller, New Arrival, sau đó chọn đa dạng danh mục
    def sort_p(p):
        badge = str(p.get("badge", ""))
        if "BEST_SELLER" in badge:
            return 1
        if "NEW_ARRIVAL" in badge:
            return 2
        return 3

    matched.sort(key=sort_p)

    # Chọn 3-4 sản phẩm tiêu biểu đa dạng nhóm
    selected = []
    seen_cats = set()
    for p in matched:
        c = p.get("category", "")
        if c not in seen_cats or len(selected) < 2:
            selected.append(p)
            seen_cats.add(c)
        if len(selected) >= 4:
            break

    if len(selected) < 3 and matched:
        selected = matched[:4]

    budget_label = ""
    if min_p > 0 and max_p < 999999999:
        budget_label = f"từ {_format_price(min_p)} đến {_format_price(max_p)}"
    elif max_p < 999999999:
        budget_label = f"dưới {_format_price(max_p)}"
    else:
        budget_label = f"từ {_format_price(min_p)} trở lên"

    lines = []
    medals = ["1.", "2.", "3.", "4."]
    for idx, p in enumerate(selected, start=1):
        num = medals[idx - 1] if idx <= len(medals) else f"{idx}."
        price_str = _format_price(p.get("price"))
        d_str = _format_discount(p.get("discount"))
        disc = f" (Giảm {d_str})" if d_str else ""
        lines.append(f"{num} **{p['name']}** — Giá ưu đãi: **{price_str}**{disc}")

    products_text = "\n".join(lines)
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"
    brand_display = "ZeO Vietnam" if brand.lower() == "zeo" else "CFC Cò Bay"

    reply = (
        f"Dạ trong phân khúc giá **{budget_label}**, các dòng sản phẩm bán chạy và được ưa chuộng nhất của {brand_display} gồm có:\n\n"
        f"{products_text}\n\n"
        f"👉 Bạn có thể xem trọn bộ ưu đãi và áp mã Freeship Extra tại gian hàng Shopee: {general_link}\n"
        f"Bạn đang quan tâm dòng giặt xả, rửa chén hay tẩy rửa gia đình để mình tư vấn chi tiết hơn nha! 💙"
    )

    return {
        "matched": True,
        "intent": "shopee_budget_filter",
        "confidence": "high",
        "score": 0.98,
        "suggested_reply": reply,
        "shopee_url": general_link,
        "selected_products": selected,
    }


def is_bestseller_inquiry(text: str) -> bool:
    """Kiểm tra xem khách có hỏi về sản phẩm bán chạy / hot nhất không."""
    folded = _fold(text)
    return bool(re.search(r"\b(ban chay|hot nhat|top ban chay|mat hang ban chay|san pham hot|loai nao ban chay|dong nao ban chay|nhieu nguoi mua|mua nhieu nhat|top seller|best seller|top san pham)\b", folded))


def is_new_arrival_inquiry(text: str) -> bool:
    """Kiểm tra xem khách có hỏi về sản phẩm mới nhất / mới ra mắt không."""
    folded = _fold(text)
    return bool(re.search(r"\b(moi ra|moi nhat|hang moi|san pham moi|dong moi|moi ve|moi ra mat|hang moi ve|new arrival|vua ra)\b", folded))


def match_best_sellers(query: str, brand: str = "zeo") -> dict:
    """Trả lời danh sách Top sản phẩm Bán Chạy Nhất (hỗ trợ lọc theo danh mục)."""
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"
    brand_display = "ZeO & PANO" if brand.lower() == "zeo" else "CFC Cò Bay"

    catalog = load_shopee_catalog(brand=brand)
    target_category = _detect_category_from_text(query)

    if target_category:
        cat_items = [p for p in catalog if p.get("category") == target_category and p.get("in_stock", True)]
        cat_items.sort(key=lambda p: 1 if "BEST_SELLER" in str(p.get("badge", "")) else 2)
        top_items = cat_items[:3]
        if top_items:
            best_one = top_items[0]
            price_str = _format_price(best_one.get("price"))
            d_str = _format_discount(best_one.get("discount"))
            disc = f" (Giảm {d_str})" if d_str else ""
            url = best_one.get("link_shopee") or general_link

            reply = (
                f"Dạ trong nhóm **{target_category}**, dòng sản phẩm **BÁN CHẠY NHẤT** hiện nay là:\n\n"
                f"🥇 **{best_one['name']}**\n"
                f"• **Giá ưu đãi:** **{price_str}**{disc}\n"
                f"• **Ưu đãi:** Freeship Extra toàn quốc\n\n"
                f"👉 Link đặt mua chính hãng trên Shopee Mall: {url}\n\n"
                f"Bạn cần tư vấn thêm về dung tích hay mùi hương nào cứ nhắn mình hỗ trợ nhé! 💙"
            )
            return {
                "matched": True,
                "intent": "bestsellers",
                "confidence": "high",
                "score": 0.99,
                "suggested_reply": reply,
                "shopee_url": url,
            }

    bestsellers = [p for p in catalog if "BEST_SELLER" in str(p.get("badge", ""))]
    if not bestsellers:
        bestsellers = [p for p in catalog if p.get("in_stock", True)][:7]

    lines = []
    medals = ["🥇", "🥈", "🥉", "⭐️", "⭐️", "⭐️", "⭐️", "⭐️", "⭐️", "⭐️"]
    for idx, p in enumerate(bestsellers[:10], start=1):
        medal = medals[idx - 1] if idx <= len(medals) else "⭐️"
        price_str = _format_price(p.get("price"))
        d_str = _format_discount(p.get("discount"))
        disc = f" ({d_str})" if d_str else ""
        lines.append(f"{idx}. {medal} **{p['name']}** - Giá: **{price_str}**{disc}")

    products_text = "\n".join(lines)
    reply = (
        f"Dạ các dòng sản phẩm **BÁN CHẠY NHẤT** hiện nay của {brand_display} trên Shopee Mall gồm có:\n\n"
        f"{products_text}\n\n"
        f"👉 Xem toàn bộ gian hàng và nhận mã Freeship Extra tại: {general_link}\n"
        f"Bạn quan tâm dòng sản phẩm nào cứ nhắn mình tư vấn kỹ hơn nhé! 💙"
    )

    return {
        "matched": True,
        "intent": "bestsellers",
        "confidence": "high",
        "score": 0.98,
        "suggested_reply": reply,
        "shopee_url": general_link,
    }


def match_new_arrivals(query: str, brand: str = "zeo") -> dict:
    """Trả lời danh sách sản phẩm Mới Ra Mắt (hỗ trợ lọc theo danh mục)."""
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"
    brand_display = "ZeO & PANO" if brand.lower() == "zeo" else "CFC Cò Bay"

    catalog = load_shopee_catalog(brand=brand)
    target_category = _detect_category_from_text(query)

    if target_category:
        cat_items = [p for p in catalog if p.get("category") == target_category and p.get("in_stock", True)]
        cat_items.sort(key=lambda p: 1 if "NEW_ARRIVAL" in str(p.get("badge", "")) else 2)
        top_items = cat_items[:3]
        if top_items:
            best_one = top_items[0]
            price_str = _format_price(best_one.get("price"))
            d_str = _format_discount(best_one.get("discount"))
            disc = f" (Giảm {d_str})" if d_str else ""
            url = best_one.get("link_shopee") or general_link

            reply = (
                f"Dạ trong nhóm **{target_category}**, dòng sản phẩm **MỚI RA MẮT** nổi bật nhất là:\n\n"
                f"✨ **{best_one['name']}**\n"
                f"• **Giá ưu đãi:** **{price_str}**{disc}\n"
                f"• **Ưu đãi:** Freeship Extra toàn quốc\n\n"
                f"👉 Xem chi tiết và nhận quà tặng kèm tại: {url}\n\n"
                f"Bạn cần tư vấn chi tiết hơn cứ nhắn mình nhé! 💙"
            )
            return {
                "matched": True,
                "intent": "new_arrivals",
                "confidence": "high",
                "score": 0.99,
                "suggested_reply": reply,
                "shopee_url": url,
            }

    new_items = [p for p in catalog if "NEW_ARRIVAL" in str(p.get("badge", ""))]
    if not new_items:
        new_items = [p for p in catalog if p.get("in_stock", True)][:7]

    lines = []
    for idx, p in enumerate(new_items[:10], start=1):
        price_str = _format_price(p.get("price"))
        d_str = _format_discount(p.get("discount"))
        disc = f" ({d_str})" if d_str else ""
        lines.append(f"{idx}. ✨ **{p['name']}** - Giá ưu đãi: **{price_str}**{disc}")

    products_text = "\n".join(lines)
    reply = (
        f"Dạ các dòng sản phẩm **MỚI RA MẮT** cực hot của {brand_display} trên Shopee Mall gồm có:\n\n"
        f"{products_text}\n\n"
        f"👉 Xem chi tiết các sản phẩm mới và nhận quà tặng kèm tại: {general_link}\n"
        f"Bạn nhắn mình nhu cầu giặt giũ / tẩy rửa để mình gợi ý combo phù hợp nhất nha! 💙"
    )

    return {
        "matched": True,
        "intent": "new_arrivals",
        "confidence": "high",
        "score": 0.98,
        "suggested_reply": reply,
        "shopee_url": general_link,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. MATCH BÁO GIÁ & GỬI LINK CHO SẢN PHẨM ĐÍCH DANH
# ─────────────────────────────────────────────────────────────────────────────
def match_specific_product_price(query: str, brand: str = "zeo") -> Optional[dict]:
    """
    Nhận diện câu hỏi giá cho một sản phẩm cụ thể (vd: xin giá nước rửa chén vitamin e, bột giặt pano bao nhiêu...).
    Trả về giá niêm yết, giá khuyến mãi và link Shopee Mall trực tiếp.
    """
    query_folded = _fold(query)

    # Loại trừ câu hỏi về liều lượng / cách dùng (vd: 1kg cho 5 bộ đồ, bón bao nhiêu kg...)
    if re.search(r"\b(bao nhieu (?:bo|kg|lit|goi|can|gam|muong|nap)|cho \d+ bo|bon bao nhieu|bao nhieu do|lieu luong|cach dung)\b", query_folded):
        return None

    # Kiểm tra xem có từ khóa hỏi giá rõ ràng bằng word boundary không
    has_price_ask = bool(re.search(r"\b(gia|gia ban|gia ca|bao nhieu|nhieu tien|bao gia|bang gia|xin gia|ton bao nhieu|mua het bao|gia sao|gia the nao)\b", query_folded))
    if not has_price_ask:
        return None

    # Phải có từ khóa định danh sản phẩm
    has_product_mention = any(k in query_folded for k in [
        "rua chen", "rua bat", "bot giat", "nuoc giat", "lau san", "toilet", "bon cau",
        "javel", "javen", "tay mau", "xa vai", "lau kinh", "treo xe", "tinh dau",
        "vitamin e", "nha dam", "cam chanh", "oai huong", "tao dua", "bio enzyme", "2in1",
        "nano clean", "pano", "oplus", "zif"
    ])
    if not has_product_mention:
        return None

    # Phải có tên thương hiệu con hoặc biến thể hoặc mùi hương / quy cách cụ thể để báo giá chính xác
    has_specific_subbrand_or_variant = any(k in query_folded for k in [
        "pano", "oplus", "zif", "javen", "javel", "bio enzyme", "nano clean", "2in1", "4in1",
        "vitamin e", "nha dam", "cam chanh", "oai huong", "tao dua", "trai cay", "chanh",
        "300g", "400g", "720g", "2.4kg", "3.5kg", "3.8kg", "5.5kg", "9kg", "650ml", "1000ml"
    ])
    if not has_specific_subbrand_or_variant:
        return None

    catalog = load_shopee_catalog(brand=brand)
    if not catalog:
        return None

    brand_products = [
        p for p in catalog
        if p.get("brand", "").upper() == brand.upper() or (brand.upper() == "ZEO" and p.get("brand", "").upper() in ["ZEO", "PANO", "OPLUS"])
    ]
    if not brand_products:
        brand_products = catalog

    best_match = None
    highest_score = 0

    for prod in brand_products:
        prod_name_folded = _fold(prod.get("name", ""))
        keywords = prod.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(";") if k.strip()]

        score = 0
        cat_folded = _fold(prod.get("category", ""))
        if cat_folded and cat_folded in query_folded:
            score += 5

        for kw in keywords:
            kw_folded = _fold(kw)
            if kw_folded and kw_folded in query_folded:
                score += 4

        words = prod_name_folded.split()
        for w in words:
            if len(w) >= 3 and w in query_folded:
                score += 1

        variants = prod.get("variants", [])
        if isinstance(variants, str):
            variants = [v.strip() for v in variants.split(";") if v.strip()]
        for v in variants:
            v_folded = _fold(v)
            if v_folded and v_folded in query_folded:
                score += 3

        if score > highest_score:
            highest_score = score
            best_match = prod

    # Ngưỡng tin cậy cao: ít nhất 7 điểm (đảm bảo khớp đúng sản phẩm chứ không bắt nhầm)
    if not best_match or highest_score < 7:
        return None

    price_str = _format_price(best_match.get("price"))
    orig_str = _format_price(best_match.get("original_price"))
    d_str = _format_discount(best_match.get("discount", ""))
    disc_text = f" (Đang giảm {d_str} từ giá gốc {orig_str})" if d_str else ""
    url = best_match.get("link_shopee") or best_match.get("shopee_url") or "https://shopee.vn/zeovietnamofficial"

    reply = (
        f"Dạ giá của **{best_match['name']}** chính hãng hiện tại là:\n\n"
        f"• **Giá ưu đãi:** **{price_str}**{disc_text}\n"
        f"• **Ưu đãi sàn:** Hỗ trợ mã Freeship Extra toàn quốc\n\n"
        f"👉 Bạn có thể bấm vào link Shopee Mall sau để đặt hàng giao tận nơi nha:\n"
        f"{url}\n\n"
        f"Cần tư vấn thêm quy cách hay mùi hương nào bạn cứ nhắn mình hỗ trợ nhé! 💙"
    )

    return {
        "matched": True,
        "intent": "specific_product_pricing",
        "confidence": "high",
        "score": 0.99,
        "product_name": best_match.get("name"),
        "shopee_url": url,
        "suggested_reply": reply,
        "matched_product": best_match,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. TƯ VẤN THEO NHU CẦU NỐI TIẾP (NEED-BASED MULTI-TURN)
# ─────────────────────────────────────────────────────────────────────────────
def match_need_preference(need_type: str, brand: str = "zeo") -> Optional[dict]:
    """Tư vấn thông minh khi khách chọn nhu cầu: tiết kiệm, thơm lâu, sạch sâu, dịu nhẹ."""
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"

    if need_type == "tiet_kiem":
        reply = (
            "Dạ nếu bạn đang ưu tiên **tiết kiệm chi phí**, bên mình gợi ý 2 lựa chọn kinh tế nhất:\n\n"
            "1. ⭐️ **Bột giặt Oplus 4in1 (Túi 720g / 5.5kg)** — Công nghệ ION hòa tan cực nhanh, tiết kiệm nước và bột giặt (Giá từ **66.000đ**).\n"
            "2. ⭐️ **Bột giặt Pano Hương Cam Chanh (Túi 2.4kg / 5.5kg)** — Sạch quần áo, ít cặn, giá siêu tiết kiệm (Chỉ từ **46.350đ**).\n"
            "3. ⭐️ **Nước giặt Pano Can to 3.8kg** — Can lớn dùng lâu dài cho cả gia đình (Giá **123.291đ**).\n\n"
            f"👉 Xem chi tiết trên Shopee Mall: {general_link}\n"
            "Bạn muốn chọn túi nhỏ dùng thử hay can lớn để tiết kiệm tối đa ạ? 💙"
        )
    elif need_type == "thom_lau":
        reply = (
            "Dạ với nhu cầu **lưu hương thơm lâu quyến rũ**, bạn không nên bỏ qua:\n\n"
            "1. 🌸 **Nước giặt & Bột giặt PANO Hương Nước Hoa Pháp** — Ứng dụng công nghệ VEILEX khử triệt để mùi ẩm mốc, tỏa hương sang trọng cả ngày.\n"
            "2. 🌸 **Nước giặt 2in1 Oplus Hương Nước Hoa Pháp** — Vừa giặt sạch vừa xả mềm vải thơm ngát (Giá từ **62.100đ**).\n"
            "3. 🌸 **Combo Nước xả vải Nano Clean ZeO (Hương hoa trắng & Xạ hương)** — Giữ hương sâu trong từng sợi vải.\n\n"
            f"👉 Bạn có thể đặt mua ngay tại: {general_link}\n"
            "Bạn thích phong cách hương nước hoa nồng nàn hay hương hoa dịu nhẹ thanh mát hơn ạ? 💙"
        )
    elif need_type == "sach_sau":
        reply = (
            "Dạ với nhu cầu **sạch sâu đánh bay vết bẩn cứng đầu**, dòng sản phẩm tối ưu nhất là:\n\n"
            "1. ⚡️ **Bột giặt ZeO Sinh Học (Công nghệ Enzyme Thụy Điển)** — Bẻ gãy các vết bẩn protein, dầu mỡ khó giặt mà không hại sợi vải, được Viện Pasteur chứng nhận diệt khuẩn.\n"
            "2. ⚡️ **Nước giặt Pano Active** — Đậm đặc làm sạch sâu vết ố cổ áo, tay áo hiệu quả.\n"
            "3. ⚡️ **Nước tẩy quần áo màu Oxy Active ZeO** — Tẩy sạch vết ố màu mà không làm phai màu vải.\n\n"
            f"👉 Tham khảo gian hàng chính hãng tại: {general_link}\n"
            "Bạn đang cần xử lý loại vết bẩn nào cứ nhắn mình tư vấn giải pháp phù hợp nha! 💙"
        )
    elif need_type == "diu_nhe":
        reply = (
            "Dạ nếu bạn cần sản phẩm **dịu nhẹ, bảo vệ da tay và an toàn cho quần áo em bé / da nhạy cảm**:\n\n"
            "1. 🌿 **Bột giặt ZeO Nha Đam (Aloe Vera)** — Tinh chất nha đam the mát, độ pH trung tính, dịu nhẹ tối đa cho da tay khi giặt tay.\n"
            "2. 🌿 **Nước rửa chén PANO Vitamin E** — Bổ sung Vitamin E dưỡng ẩm, rửa sạch dầu mỡ mà không gây khô ráp da tay.\n"
            "3. 🌿 **Nước rửa chén ZeO / ZIF 100% Cốt Chanh Tự Nhiên** — Diệt khuẩn an toàn cho chén đĩa cả gia đình.\n\n"
            f"👉 Xem chi tiết tại: {general_link}\n"
            "Bạn cần mua nước rửa chén hay bột giặt dịu da tay ạ? 💙"
        )
    else:
        return None

    return {
        "matched": True,
        "intent": f"need_consultation_{need_type}",
        "confidence": "high",
        "score": 0.98,
        "suggested_reply": reply,
        "shopee_url": general_link,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. GENERAL MATCHING & FALLBACK
# ─────────────────────────────────────────────────────────────────────────────
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
    """Kiểm tra xem câu hỏi có chứa ý định mua qua Shopee / xin link mua sàn Shopee không."""
    folded = _fold(text)
    # Loại trừ hỏi website công ty
    if any(w in folded for w in ["website", "trang web", "link web", "zeo vn", "zeo.vn", "cfccobay"]):
        return False
    # Loại trừ mua offline / đại lý
    if any(w in folded for w in ["dai ly", "tap hoa", "sieu thi", "cua hang", "offline"]):
        return False
    triggers = [
        "shopee", "shoppe", "sopi", "sope", "shopi", "san tmdt",
        "link shopee", "gian hang shopee", "shopee mall", "shopee cua shop",
        "link nuoc", "link bot", "link san pham", "cho xin link", "cho link", "gui link",
        "mua o dau", "mua o cho nao", "mua tai dau", "dat online o dau", "dat tren mang o dau"
    ]
    return any(t in folded for t in triggers)


def match_promotions_and_deals(query: str, brand: str = "zeo") -> dict:
    """Trả lời trung thực về các chương trình Sale & Khuyến mãi hiện có của ZeO / CFC."""
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
        "shopee_url": general_link,
    }


def match_shopee_product(query: str, brand: str = "zeo") -> Optional[dict]:
    """Khớp câu hỏi của khách với sản phẩm Shopee phù hợp nhất."""
    query_folded = _fold(query)
    brand_upper = brand.upper()

    # 1. Kiểm tra hỏi tầm giá / ngân sách
    if is_budget_inquiry(query):
        budget_res = match_products_by_budget(query, brand=brand)
        if budget_res:
            return budget_res

    # 2. Kiểm tra hỏi giá cụ thể cho một sản phẩm
    price_res = match_specific_product_price(query, brand=brand)
    if price_res:
        return price_res

    # 3. Kiểm tra hỏi Bán chạy / Mới nhất
    if is_bestseller_inquiry(query):
        return match_best_sellers(query, brand=brand)
    if is_new_arrival_inquiry(query):
        return match_new_arrivals(query, brand=brand)

    # 4. Kiểm tra hỏi khuyến mãi / flash sale
    if is_promotion_inquiry(query):
        return match_promotions_and_deals(query, brand=brand)

    catalog = load_shopee_catalog(brand=brand)
    if not catalog:
        return None

    brand_products = [
        p for p in catalog
        if p.get("brand", "").upper() == brand_upper or (brand_upper == "ZEO" and p.get("brand", "").upper() in ["ZEO", "PANO", "OPLUS"])
    ]
    if not brand_products:
        brand_products = catalog

    best_match = None
    highest_score = 0

    for prod in brand_products:
        prod_name_folded = _fold(prod.get("name", ""))
        keywords = prod.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(";") if k.strip()]

        score = 0
        cat_folded = _fold(prod.get("category", ""))
        if cat_folded and cat_folded in query_folded:
            score += 5

        for kw in keywords:
            kw_folded = _fold(kw)
            if kw_folded and kw_folded in query_folded:
                score += 4

        words = prod_name_folded.split()
        for w in words:
            if len(w) >= 3 and w in query_folded:
                score += 1

        variants = prod.get("variants", [])
        if isinstance(variants, str):
            variants = [v.strip() for v in variants.split(";") if v.strip()]
        for v in variants:
            v_folded = _fold(v)
            if v_folded and v_folded in query_folded:
                score += 3

        if score > highest_score:
            highest_score = score
            best_match = prod

    if not best_match or highest_score < 4:
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

    price_str = _format_price(best_match.get("price"))
    url = best_match.get("link_shopee") or best_match.get("shopee_url") or "https://shopee.vn/zeovietnamofficial"

    reply = (
        f"Dạ, link mua **{best_match['name']}** chính hãng trên Shopee Mall đây nha bạn:\n\n"
        f"👉 {url}\n\n"
        f"• **Giá niêm yết:** {price_str}\n"
        f"• **Ưu đãi:** Freeship Extra toàn quốc\n\n"
        f"Bạn bấm vào link để đặt hàng giao tận nơi nhé! Cần hỗ trợ thêm bạn cứ nhắn mình nha. 💙"
    )

    return {
        "matched": True,
        "is_general_store": False,
        "product_id": best_match.get("item_id") or best_match.get("id"),
        "product_name": best_match.get("name"),
        "shopee_url": url,
        "matched_product": best_match,
        "suggested_reply": reply,
    }
