"""
chat_pipeline.py — High-Performance Fast-Path Chatbot Pipeline cho ZeO & CFC
Đạt tốc độ phản hồi < 50ms - 300ms (Nhanh gấp 20 - 50 lần flow n8n cũ)

Quy trình:
  1. Fast-Path Regex & Normalize: Chào hỏi, cảm ơn, nhận diện SĐT, khiếu nại (< 5ms)
  2. Shopee Catalog Matcher: Khớp link Shopee Mall chính hãng (< 10ms)
  3. RediSearch Vector Search (KNN BGE-M3): Tra cứu FAQ chuẩn xác (< 40ms)
  4. Tiered Response Execution: Trả lời trực tiếp nếu điểm cao, chỉ rewrite khi cần
  5. Async Redis Profile/Session Update & Telegram Alerts (Không block khách)
"""

import asyncio
import json
import logging
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

import redis.asyncio as aioredis
from pydantic import BaseModel

from rag_search import get_redis, get_faq_by_intent, semantic_search
from shopee_matcher import match_shopee_product, is_shopee_inquiry
from telegram_notifier import notify_new_lead, notify_admin_unanswered

logger = logging.getLogger(__name__)

# Cấu hình từ viết tắt tiếng Việt
VIETNAMESE_ALIASES = {
    "k": "khong", "ko": "khong", "kh": "khong", "hok": "khong", "hem": "khong", "hong": "khong",
    "dc": "duoc", "dk": "duoc", "sp": "san pham", "ib": "nhan tin", "nt": "nhan tin",
    "nhiu": "nhieu",
    "bn": "bao nhieu", "mn": "minh", "ship": "giao hang", "cty": "cong ty",
    "web": "website", "wed": "website", "wep": "website",
    "sdt": "so dien thoai", "ssdt": "so dien thoai", "dt": "dien thoai", "npp": "nha phan phoi",
}

PHONE_REGEX = re.compile(r"(?:\+84|84|0)(?:3[2-9]|5[2689]|7[06789]|8[0-9]|9[0-9])[0-9]{7}\b")
AREA_KEYWORDS = [
    "tinh", "thanh pho", "tp", "huyen", "quan", "q", "xa", "phuong", "thi xa", "khu vuc",
    "can tho", "thai binh", "kien giang", "rach gia", "tra noc", "tphcm", "ho chi minh",
    "binh duong", "dong nai", "long an", "vung tau", "da nang", "ha noi", "hai phong",
    "an giang", "dong thap", "soc trang", "bac lieu", "ca mau", "hau giang", "vinh long", "tien giang",
]

SENSITIVE_KEYWORDS = [
    "hoan tien", "doi tra", "khieu nai", "lua dao", "san pham loi", "hang gia", "tai khoan ngan hang", "chuyen khoan", "so tai khoan"
]

ZEO_COMPETITOR_PRODUCT_PATTERNS = [
    r"\bomo\b", r"\bariel\b", r"\btide\b", r"\bsurf\b", r"\baba\b", r"\blix\b", r"\bnet\b", r"\bdowny\b", r"\bcomfort\b",
]

PRODUCT_MEMORY_BY_INTENT = {
    "zeo_product_catalog_overview": [
        {"name": "Giặt giũ ZeO/PANO/Oplus", "category": "laundry", "intent": "zeo_laundry_product_overview"},
        {"name": "Rửa chén ZeO/ZIF/PANO/Oplus", "category": "dishwashing", "intent": "zeo_dishwashing_product_overview"},
        {"name": "Lau sàn ZeO/Oplus", "category": "floor_cleaner", "intent": "zeo_floor_cleaner_product_overview"},
        {"name": "Tẩy rửa vệ sinh ZeO/PANO", "category": "cleaning_hygiene", "intent": "zeo_cleaning_hygiene_product_overview"},
    ],
    "zeo_laundry_product_overview": [
        {"name": "Bột giặt ZeO", "category": "laundry", "intent": "zeo_detergent_technology"},
        {"name": "Bột giặt Oplus", "category": "laundry", "intent": "oplus_detergent_features"},
        {"name": "Bột giặt & Nước giặt PANO", "category": "laundry", "intent": "pano_product_type"},
    ],
    "zeo_dishwashing_product_overview": [
        {"name": "Nước rửa chén ZeO/ZIF", "category": "dishwashing", "intent": "zeo_zif_dishwashing_liquid"},
        {"name": "PANO Rửa Chén Chanh", "category": "dishwashing", "intent": "pano_dishwashing_lemon_and_vitamin_e"},
        {"name": "PANO Rửa Chén Vitamin E", "category": "dishwashing", "intent": "pano_dishwashing_lemon_and_vitamin_e"},
        {"name": "Oplus Rửa Chén", "category": "dishwashing", "intent": "oplus_dishwashing_liquid"},
    ],
    "zeo_floor_cleaner_product_overview": [
        {"name": "Nước lau sàn ZeO", "category": "floor_cleaner", "intent": "zeo_floor_cleaner_product_overview"},
        {"name": "Nước lau sàn Oplus", "category": "floor_cleaner", "intent": "zeo_floor_cleaner_product_overview"},
    ],
    "zeo_cleaning_hygiene_product_overview": [
        {"name": "Javen ZeO", "category": "cleaning_hygiene", "intent": "zeo_cleaning_hygiene_product_overview"},
        {"name": "Tẩy Toilet ZeO", "category": "cleaning_hygiene", "intent": "zeo_cleaning_hygiene_product_overview"},
        {"name": "Tẩy màu ZeO", "category": "cleaning_hygiene", "intent": "zeo_cleaning_hygiene_product_overview"},
        {"name": "Lau kính ZeO", "category": "cleaning_hygiene", "intent": "zeo_cleaning_hygiene_product_overview"},
        {"name": "Xịt tẩy đa năng PANO", "category": "cleaning_hygiene", "intent": "pano_multipurpose_cleaner"},
    ],
    "pano_product_type": [
        {"name": "Bột giặt & Nước giặt PANO", "category": "laundry", "intent": "pano_product_type"},
        {"name": "Nước rửa chén PANO", "category": "dishwashing", "intent": "pano_dishwashing_lemon_and_vitamin_e"},
        {"name": "Xịt tẩy đa năng PANO", "category": "cleaning_hygiene", "intent": "pano_multipurpose_cleaner"},
    ],
    "pano_dishwashing_lemon_and_vitamin_e": [
        {"name": "PANO Rửa Chén Chanh", "category": "dishwashing", "intent": "pano_dishwashing_lemon_and_vitamin_e"},
        {"name": "PANO Rửa Chén Vitamin E", "category": "dishwashing", "intent": "pano_dishwashing_lemon_and_vitamin_e"},
    ],
    "product_lines": [
        {"name": "Dinh dưỡng cây trồng cao cấp CFC Cò Bay", "category": "fertilizer", "intent": "product_lines"},
        {"name": "Phân bón hữu cơ sinh học CFC Cò Bay", "category": "fertilizer", "intent": "cfc_organic_fertilizer_info"},
        {"name": "Phân bón NPK CFC Cò Bay", "category": "fertilizer", "intent": "cfc_npk_product_info"},
    ],
}

PRODUCT_ENTITY_PATTERNS = [
    ("zeo_zif_dishwashing_liquid", "Nước rửa chén ZeO/ZIF", "dishwashing", r"\bzif\b|nuoc rua chen zeo|rua chen zeo"),
    ("pano_product_type", "PANO", "product_family", r"\bpano\b"),
    ("oplus_detergent_features", "Oplus", "product_family", r"\boplus\b"),
    ("zeo_laundry_product_overview", "Giặt giũ ZeO/PANO/Oplus", "laundry", r"giat giu|nuoc giat|bot giat|giat quan ao"),
    ("zeo_dishwashing_product_overview", "Rửa chén ZeO/ZIF/PANO/Oplus", "dishwashing", r"nuoc rua chen|rua chen|rua bat"),
    ("zeo_floor_cleaner_product_overview", "Lau sàn ZeO/Oplus", "floor_cleaner", r"nuoc lau san|lau san|lau nha"),
    ("zeo_cleaning_hygiene_product_overview", "Tẩy rửa vệ sinh ZeO/PANO", "cleaning_hygiene", r"javen|toilet|bon cau|tay rua|ve sinh|lau kinh|xit tay|tay mau"),
    ("cfc_npk_product_info", "Phân bón NPK CFC Cò Bay", "fertilizer", r"\bnpk\b"),
    ("cfc_organic_fertilizer_info", "Phân bón hữu cơ sinh học CFC Cò Bay", "fertilizer", r"huu co|sinh hoc"),
    ("product_lines", "Phân bón CFC Cò Bay", "fertilizer", r"phan bon|co bay|cfc"),
]


def _normalize_vn(text: str) -> str:
    """Loại bỏ dấu tiếng Việt và chuẩn hóa ký tự."""
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "d").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [VIETNAMESE_ALIASES.get(t, t) for t in text.split() if t]
    return " ".join(tokens)


def _extract_phone_and_area(text: str, norm: str) -> Tuple[str, str]:
    """Trích xuất SĐT và Khu vực địa chỉ."""
    phone_match = PHONE_REGEX.search(text)
    phone = phone_match.group(0).strip() if phone_match else ""
    if not phone:
        digits = re.sub(r"\D", "", text)
        if len(digits) in (10, 11) and ("so dien thoai" in norm or "sdt" in norm or "lien he" in norm):
            phone = digits

    # Tìm khu vực
    area = ""
    asks_area_question = (
        re.search(r"(dia chi|khu vuc|noi o|tinh thanh).*(cua )?(toi|minh|em|anh|chi)", norm)
        or re.search(r"(o dau|tai dau|cho nao|dia chi.*o dau|mua o dau|ban o dau)", norm)
    )
    if asks_area_question:
        return phone, area

    text_without_phone = text.replace(phone, "").strip() if phone else text
    norm_without_phone = _normalize_vn(text_without_phone)
    area_tokens = {"tinh", "tp", "huyen", "quan", "xa", "phuong", "thi", "mien", "tphcm"}
    norm_tokens = set(norm.split())
    has_named_area = any(k in norm for k in AREA_KEYWORDS if len(k) > 2)
    has_area_token = bool(norm_tokens & area_tokens)
    has_area_phrase = bool(re.search(r"(^|\s)(minh|em|toi|anh|chi|ben minh)\s+(o|tai)\s+[a-z0-9]", norm))
    has_prefixed_area = bool(re.search(r"(^|\s)(o|tai|khu vuc)\s+(tinh|tp|huyen|quan|xa|phuong|thanh pho)?\s*[a-z0-9]", norm))
    if has_named_area or has_area_token or has_area_phrase or has_prefixed_area:
        cleaned = re.sub(
            r"(?i)\b(sdt|ssdt|số điện thoại|so dien thoai|điện thoại|dien thoai|của tôi|cua toi|của mình|cua minh|của em|cua em|là|la|liên hệ|lien he|gọi tôi|goi toi|gọi mình|goi minh|nhé|nhe|nha)\b",
            " ",
            text_without_phone,
        )
        cleaned = re.sub(r"[\s,./:-]+", " ", cleaned).strip()
        cleaned_norm = _normalize_vn(cleaned)
        if cleaned and cleaned_norm not in {"", "toi", "minh", "em", "anh", "chi"}:
            area = cleaned

    return phone, area


def _default_conversation_state(brand: str) -> dict[str, Any]:
    return {
        "brand": brand.upper(),
        "conversation_topic": "",
        "current_intent": "",
        "active_entities": {
            "product": "",
            "product_intent": "",
            "category": "",
        },
        "last_products_shown": [],
        "customer_constraints": {},
        "recent_turns": [],
        "conversation_summary": "",
        "last_source_id": "",
        "updated_at": "",
    }


def _load_conversation_state(existing_session: dict, brand: str) -> dict[str, Any]:
    raw_state = existing_session.get("conversation_state") or {}
    if isinstance(raw_state, str):
        try:
            raw_state = json.loads(raw_state)
        except Exception:
            raw_state = {}
    if not isinstance(raw_state, dict):
        raw_state = {}

    state = _default_conversation_state(brand)
    state.update({k: v for k, v in raw_state.items() if v not in (None, "")})
    active_entities = state.get("active_entities") if isinstance(state.get("active_entities"), dict) else {}
    state["active_entities"] = {
        "product": active_entities.get("product") or existing_session.get("current_product", ""),
        "product_intent": active_entities.get("product_intent") or active_entities.get("intent", ""),
        "category": active_entities.get("category") or existing_session.get("current_category", ""),
    }
    if not isinstance(state.get("last_products_shown"), list):
        state["last_products_shown"] = []
    if not isinstance(state.get("customer_constraints"), dict):
        state["customer_constraints"] = {}
    if not isinstance(state.get("recent_turns"), list):
        state["recent_turns"] = []
    return state


def _copy_product_item(item: dict) -> dict[str, str]:
    return {
        "name": str(item.get("name", "")).strip(),
        "category": str(item.get("category", "")).strip(),
        "intent": str(item.get("intent", "")).strip(),
    }


def _extract_query_entities(norm_text: str, brand: str) -> dict[str, Any]:
    matched_entities = []
    brand_l = brand.lower()
    for intent, name, category, pattern in PRODUCT_ENTITY_PATTERNS:
        if brand_l == "zeo" and (intent.startswith("cfc_") or name.startswith("Phân bón CFC")):
            continue
        if brand_l == "cfc" and (
            intent.startswith("zeo_")
            or intent.startswith("pano_")
            or intent.startswith("oplus_")
            or name in {"PANO", "Oplus"}
        ):
            continue
        if re.search(pattern, norm_text):
            matched_entities.append({
                "product": name,
                "product_intent": intent,
                "category": category,
            })

    primary = matched_entities[0] if matched_entities else {}
    return {
        "product": primary.get("product", ""),
        "product_intent": primary.get("product_intent", ""),
        "category": primary.get("category", ""),
        "matched_entities": matched_entities,
    }


def _has_reference_signal(norm_text: str) -> bool:
    tokens = norm_text.split()
    if _has_any(norm_text, [
        r"\b(cai|loai|dong|san pham|phan|mon)\s+(nay|do|tren|hoi nay|vua roi|vua noi)\b",
        r"\b(no|do|nay|tren)\s+(gia|bao nhieu|nhieu tien|ship|giao hang|con hang|con khong|con)\b",
        r"\b(cai|loai|dong|san pham|phan)\s+(dau tien|thu nhat|thu hai|thu ba|thu tu|thu 1|thu 2|thu 3|thu 4|so 1|so 2|so 3|so 4|\d)\b",
        r"\b(dau tien|thu nhat|thu hai|thu ba|thu tu|thu 1|thu 2|thu 3|thu 4|so 1|so 2|so 3|so 4)\b",
        r"\b(vua hoi|vua noi|hoi nay|luc nay|o tren)\b",
    ]):
        return True
    return len(tokens) <= 5 and any(t in {"no", "do", "nay", "tren"} for t in tokens)


def _ordinal_reference_index(norm_text: str) -> Optional[int]:
    ordinal_patterns = [
        (0, r"\b(dau tien|thu nhat|thu 1|so 1|muc 1|loai 1|cai 1|1)\b"),
        (1, r"\b(thu hai|thu 2|so 2|muc 2|loai 2|cai 2|2)\b"),
        (2, r"\b(thu ba|thu 3|so 3|muc 3|loai 3|cai 3|3)\b"),
        (3, r"\b(thu tu|thu 4|so 4|muc 4|loai 4|cai 4|4)\b"),
    ]
    for idx, pattern in ordinal_patterns:
        if re.search(pattern, norm_text):
            return idx
    return None


def _resolve_reference(raw_text: str, norm_text: str, conversation_state: dict[str, Any]) -> dict[str, Any]:
    if not _has_reference_signal(norm_text):
        return {
            "references_previous_turn": False,
            "resolved": False,
            "product": "",
            "product_intent": "",
            "category": "",
            "resolved_query": raw_text,
            "reason": "no_reference",
        }

    products = [
        _copy_product_item(item)
        for item in (conversation_state.get("last_products_shown") or [])
        if isinstance(item, dict) and item.get("name")
    ]
    active = conversation_state.get("active_entities") or {}
    idx = _ordinal_reference_index(norm_text)
    chosen: dict[str, str] = {}
    reason = "unresolved"

    if idx is not None and 0 <= idx < len(products):
        chosen = products[idx]
        reason = "ordinal"
    elif active.get("product"):
        chosen = {
            "name": str(active.get("product", "")),
            "intent": str(active.get("product_intent", "")),
            "category": str(active.get("category", "")),
        }
        reason = "active_entity"
    elif len(products) == 1:
        chosen = products[0]
        reason = "single_last_product"

    if not chosen:
        return {
            "references_previous_turn": True,
            "resolved": False,
            "product": "",
            "product_intent": "",
            "category": "",
            "resolved_query": raw_text,
            "reason": reason,
        }

    product = chosen.get("name", "").strip()
    return {
        "references_previous_turn": True,
        "resolved": True,
        "product": product,
        "product_intent": chosen.get("intent", ""),
        "category": chosen.get("category", ""),
        "resolved_query": f"{raw_text} ({product})" if product else raw_text,
        "reason": reason,
    }


def _looks_like_shipping_request(norm_text: str) -> bool:
    return _has_any(norm_text, [
        r"(giao hang|van chuyen|gui hang|giao ve|ship|phi ship|cuoc|cod|thanh toan khi nhan)",
        r"(ve|toi|den).{0,30}(tinh|tp|thanh pho|huyen|quan|can tho|tphcm|ha noi|da nang|long an|dong nai|binh duong)",
    ])


def _looks_like_availability_request(norm_text: str) -> bool:
    return _has_any(norm_text, [
        r"(con hang|het hang|con khong|con hong|con ko|co san|ton kho|het chua|con nua khong|con nua hong)",
    ])


def _product_memory_for_intent(intent: str, answer: str, brand: str) -> list[dict[str, str]]:
    if intent in PRODUCT_MEMORY_BY_INTENT:
        return [_copy_product_item(item) for item in PRODUCT_MEMORY_BY_INTENT[intent]]

    norm_answer = _normalize_vn(answer)
    if not norm_answer:
        return []

    products = []
    for entity_intent, name, category, pattern in PRODUCT_ENTITY_PATTERNS:
        if brand.lower() == "zeo" and (entity_intent.startswith("cfc_") or name.startswith("Phân bón CFC")):
            continue
        if brand.lower() == "cfc" and (
            entity_intent.startswith("zeo_")
            or entity_intent.startswith("pano_")
            or entity_intent.startswith("oplus_")
            or name in {"PANO", "Oplus"}
        ):
            continue
        if entity_intent == intent or re.search(pattern, norm_answer):
            item = {"name": name, "category": category, "intent": entity_intent}
            if item not in products:
                products.append(item)
    return products[:8]


def _build_next_conversation_state(
    previous_state: dict[str, Any],
    *,
    brand: str,
    user_message: str,
    bot_reply: str,
    intent: str,
    lead_stage: str,
    query_entities: dict[str, Any],
    reference_resolution: dict[str, Any],
    source_id: str = "",
) -> dict[str, Any]:
    state = _load_conversation_state({"conversation_state": previous_state}, brand)
    now_str = datetime.now(timezone.utc).isoformat()
    products = _product_memory_for_intent(intent, bot_reply, brand)

    if products:
        state["last_products_shown"] = products
    elif query_entities.get("product"):
        state["last_products_shown"] = [{
            "name": query_entities.get("product", ""),
            "category": query_entities.get("category", ""),
            "intent": query_entities.get("product_intent", ""),
        }]

    active_product = query_entities.get("product") or reference_resolution.get("product") or ""
    active_intent = query_entities.get("product_intent") or reference_resolution.get("product_intent") or ""
    active_category = query_entities.get("category") or reference_resolution.get("category") or ""
    if active_product:
        state["active_entities"] = {
            "product": active_product,
            "product_intent": active_intent,
            "category": active_category,
        }
    elif len(state.get("last_products_shown", [])) == 1:
        only_product = state["last_products_shown"][0]
        state["active_entities"] = {
            "product": only_product.get("name", ""),
            "product_intent": only_product.get("intent", ""),
            "category": only_product.get("category", ""),
        }

    if area_match := re.search(r"\b(o|tai|ve|den)\s+(.{2,40})$", _normalize_vn(user_message)):
        state["customer_constraints"]["last_area_hint"] = area_match.group(2).strip()

    state["brand"] = brand.upper()
    state["current_intent"] = intent
    state["conversation_topic"] = active_category or state.get("conversation_topic", "")
    state["last_source_id"] = source_id or state.get("last_source_id", "")
    state["updated_at"] = now_str
    state["conversation_summary"] = (
        f"Intent gần nhất: {intent}; "
        f"sản phẩm/ngữ cảnh: {state.get('active_entities', {}).get('product') or 'chưa rõ'}; "
        f"lead_stage: {lead_stage}."
    )

    recent_turns = state.get("recent_turns") or []
    recent_turns.append({
        "user": user_message,
        "bot": bot_reply[:600],
        "intent": intent,
        "timestamp": now_str,
    })
    state["recent_turns"] = recent_turns[-6:]
    return state


def _format_inline_numbered_list(answer: str) -> str:
    """Chuyển danh sách đánh số viết liền trong Sheet thành từng dòng dễ đọc."""
    matches = list(re.finditer(r"(?<!\d)(\d{1,2})\.\s+", answer))
    if len(matches) < 2 or "\n" in answer:
        return answer

    prefix = answer[:matches[0].start()].strip()
    items = []
    tail = ""

    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(answer)
        item = answer[match.end():end].strip(" ;")

        if idx == len(matches) - 1:
            tail_match = re.search(
                r"(?<!\d)\.\s+(Bạn|Anh/chị|Anh chị|Nếu|Mình|Dạ bạn)\b",
                item,
            )
            if tail_match:
                tail = item[tail_match.start() + 2:].strip()
                item = item[:tail_match.start() + 1].strip()

        items.append(f"{match.group(1)}. {item}")

    parts = []
    if prefix:
        parts.append(prefix)
    parts.append("\n".join(items))
    if tail:
        parts.append(tail)
    return "\n\n".join(parts)


def _prettify_answer(answer: str) -> str:
    """Chuẩn hóa output Messenger: gọn khoảng trắng, xuống dòng danh sách rõ ràng."""
    text = str(answer or "").strip()
    if not text:
        return text
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = _format_inline_numbered_list(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _has_product_view_action(norm_text: str) -> bool:
    return bool(re.search(
        r"(muon xem|xem ve|xem dong|cho.*xem|tim hieu|hoi ve|thong tin ve|tu van|can xem|gui.*thong tin|co.*gi|co.*loai nao|co.*dong nao|co.*dong phan|gom nhung gi|dong san pham|san pham nao|san pham gi)",
        norm_text,
    ))


def _has_price_signal(norm_text: str) -> bool:
    return bool(
        re.search(r"(^|\s)(gia|bao gia|xin gia|bang gia|gia ban|gia ca)(\s|$)", norm_text)
        or re.search(r"(bao nhieu tien|nhieu tien|bao nhieu)$", norm_text)
        or re.search(r"(gia .{1,80} bao nhieu|bao nhieu tien)", norm_text)
    )


def _detect_product_group_intent(norm_text: str, brand: str) -> Optional[str]:
    """Nhận diện câu hỏi xem/tìm hiểu nhóm sản phẩm bằng tiếng Việt tự nhiên."""
    view_action = _has_product_view_action(norm_text)
    if not view_action:
        return None

    if brand.lower() == "cfc":
        if re.search(r"(npk)\b", norm_text):
            return "cfc_npk_product_info"
        if re.search(r"(huu co|sinh hoc)\b", norm_text):
            return "cfc_organic_fertilizer_info"
        if re.search(r"(phan bon|phan co bay|cac loai phan|dong phan|dong phan nao|san pham cfc|san pham co bay)", norm_text):
            return "product_lines"
        return None

    zeo_groups = [
        ("zeo_dishwashing_product_overview", r"(nuoc rua chen|nuoc rua bat|rua chen|rua bat|zif)"),
        ("zeo_laundry_product_overview", r"(giat giu|nuoc giat|bot giat|giat quan ao|do giat|giat xa)"),
        ("zeo_floor_cleaner_product_overview", r"(nuoc lau san|lau san|nuoc lau nha|lau nha)"),
        ("zeo_cleaning_hygiene_product_overview", r"(tay rua ve sinh|tay rua|ve sinh|javen|toilet|bon cau|lau kinh|xit tay|tay mau|nha tam)"),
        ("pano_product_type", r"\bpano\b"),
        ("zeo_product_catalog_overview", r"(san pham|mat hang|dong san pham|nhom san pham|zeo co gi|shop co gi)"),
    ]
    for intent, pattern in zeo_groups:
        if re.search(pattern, norm_text):
            return intent
    return None


def _has_any(norm_text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, norm_text) for pattern in patterns)


def _is_internal_content_request(norm_text: str) -> bool:
    return _has_any(norm_text, [
        r"\b(noi dung|bai dang|kich ban|script|mau|caption|video|reels|quang cao)\b",
        r"(viet.*(bai|noi dung|caption|kich ban))",
    ])


def _detect_company_overview_intent(norm_text: str, brand: str) -> Optional[str]:
    if _has_any(norm_text, [
        r"(gioi thieu|so luoc|thong tin).{0,30}(cong ty|cty|thuong hieu|zeo|pano|oplus|cfc|co bay)",
        r"(cong ty|cty|thuong hieu).{0,30}(la gi|lam gi|thuoc|cua ai|san xuat|thanh lap|bao nhieu nam)",
        r"(zeo|pano|oplus|cfc|co bay).{0,30}(thuoc cong ty|la cua cong ty|la thuong hieu gi)",
        r"(cfc homecare|homecare).{0,40}(cong ty|cty|thuoc|cua)",
    ]):
        return "company_overview"
    return None


def _detect_address_intent(norm_text: str, brand: str) -> Optional[str]:
    if _has_any(norm_text, [
        r"(dia chi|nha may|tru so|van phong).{0,40}(o dau|tai dau|cho nao|cong ty|cty|shop)?",
        r"(cong ty|cty|shop|nha may|tru so).{0,25}(o dau|tai dau|nam o dau|dia chi)",
        r"\b(cty|cong ty) o dau\b",
    ]):
        return "company_address" if brand.lower() == "zeo" else "address"
    return None


def _detect_contact_intent(norm_text: str, brand: str) -> Optional[str]:
    if _has_any(norm_text, [
        r"^(so dien thoai|dien thoai|hotline|tong dai|lien he)$",
        r"(so dien thoai|hotline|tong dai|so lien he|lien he).{0,30}(cong ty|cong tu|cty|shop|admin|ben minh)?",
        r"(cong ty|cong tu|cty|shop|admin|ben minh).{0,30}(so dien thoai|hotline|tong dai|so lien he|lien he)",
    ]):
        return "company_contact_information" if brand.lower() == "zeo" else "cfc_company_website"
    return None


def _detect_official_channel_request(norm_text: str) -> Optional[str]:
    if "shopee" in norm_text or "sopi" in norm_text or "shoppe" in norm_text:
        return None
    has_channel = re.search(r"(tiktok|tik tok|lazada|zalo|facebook|fb)", norm_text)
    if has_channel and (len(norm_text.split()) <= 4 or re.search(r"(zeo|pano|oplus|cfc|co bay|cong ty|cty)", norm_text)):
        return "official_channel_unverified"
    if _has_any(norm_text, [
        r"^(tiktok|tik tok|lazada|zalo|facebook|fb)$",
        r"(link|kenh|trang|shop|official|chinh thuc).{0,30}(tiktok|tik tok|lazada|zalo|facebook|fb)",
        r"(tiktok|tik tok|lazada|zalo|facebook|fb).{0,30}(link|kenh|trang|shop|official|chinh thuc|co khong|ko)",
    ]):
        return "official_channel_unverified"
    return None


def _detect_customer_correction(norm_text: str) -> bool:
    return _has_any(norm_text, [
        r"(sai|khong dung|chua dung|nham).{0,40}(dia chi|thong tin|tra loi|noi dung|so dien thoai|hotline)",
        r"(de toi|toi|minh).{0,20}(chinh|sua|cap nhat).{0,30}(lai|cho)",
        r"(dia chi|so dien thoai|hotline).{0,30}(moi|dung|phai la)",
    ])


def _detect_language_request(norm_text: str) -> bool:
    return _has_any(norm_text, [
        r"(noi|tra loi|tu van).{0,20}(tieng trung|tieng anh|english|chinese|mandarin)",
        r"^(tieng trung|tieng anh|english|chinese)$",
    ])


def _detect_out_of_scope_general_question(norm_text: str) -> bool:
    """Chặn câu hỏi đời sống/chung chung để RAG không kéo nhầm sang FAQ sản phẩm."""
    in_scope_words = [
        "shop", "admin", "zeo", "pano", "oplus", "cfc", "co bay", "san pham", "phan bon",
        "nuoc giat", "bot giat", "nuoc rua chen", "lau san", "javen", "toilet", "npk",
        "gia", "ship", "giao hang", "mua", "dat hang", "hotline", "dia chi", "mo cua", "lam viec",
    ]
    if any(word in norm_text for word in in_scope_words):
        return False

    return _has_any(norm_text, [
        r"^(hom nay )?(thu may|ngay may)$",
        r"\bhom nay\s+(la\s+)?(thu may|ngay may|ngay gi)\b",
        r"\b(bay gio|gio nay|luc nay)\s+(la\s+)?(may gio|gio nao)\b",
        r"^(may gio roi|ngay may roi|thu may roi)$",
        r"\b(thoi tiet|mua khong|nang khong|nhiet do)\b",
        r"\b(tin tuc|bong da|xo so|ket qua xo so|lich am|ngay le)\b",
        r"\b(ke chuyen|hat bai|lam tho|giai toan|dich cau nay)\b",
    ])


def _detect_new_product_request(norm_text: str) -> bool:
    return _has_any(norm_text, [
        r"(san pham|hang|dong).{0,20}(moi ra mat|moi nhat|moi ve|moi co)",
        r"(moi ra mat|moi nhat).{0,20}(san pham|hang|dong)",
    ])


def _detect_competitor_product(norm_text: str, brand: str) -> bool:
    if brand.lower() != "zeo":
        return False
    return any(re.search(pattern, norm_text) for pattern in ZEO_COMPETITOR_PRODUCT_PATTERNS)


def _detect_cfc_cross_brand(norm_text: str, brand: str) -> bool:
    if brand.lower() != "cfc":
        return False
    return _has_any(norm_text, [
        r"(nuoc giat|bot giat|nuoc rua chen|rua chen|lau san|nuoc lau san|tay toilet|javen|xit tay|nuoc tay|pano|oplus|zeo)",
    ])


def _detect_proof_or_certification_intent(norm_text: str, brand: str, previous_intent: str = "") -> Optional[str]:
    if brand.lower() != "zeo":
        return None
    asks_proof = _has_any(norm_text, [
        r"(giay to|chung minh|chung nhan|kiem dinh|kiem nghiem|bang chung|co so nao|tai lieu).{0,40}(cong nghe|diet khuan|san pham|bot giat|zeo|do)",
        r"(pasteur|singapore|chung nhan|kiem dinh|kiem nghiem)",
    ])
    follows_tech = previous_intent in {"zeo_detergent_technology", "zeo_detergent_certification"}
    if asks_proof or ("cong nghe do" in norm_text and follows_tech):
        return "zeo_detergent_certification"
    return None


def _detect_usage_safety_gap(norm_text: str, brand: str) -> bool:
    if brand.lower() == "cfc":
        return _has_any(norm_text, [
            r"(\bbon\b|\bpha\b|\btron\b|lieu luong|bao nhieu kg|cong lua|thuoc sau|tri benh|dao on)",
        ])
    return _has_any(norm_text, [
        r"(lieu luong|cach dung|dung bao nhieu|bao nhieu ml|bao nhieu kg|may bo do|\d+\s*(kg|lit|ml).{0,20}(bo do|quan ao))",
        r"(uong duoc|vao mat|dinh vao mat|nuot phai|an phai)",
    ])


def _detect_specific_product_intent(norm_text: str, brand: str) -> Optional[str]:
    if brand.lower() == "cfc":
        if re.search(r"\bnpk\b", norm_text):
            return "cfc_npk_product_info"
        if re.search(r"(huu co|sinh hoc)", norm_text):
            return "cfc_organic_fertilizer_info"
        return None

    if re.search(r"\bzif\b", norm_text):
        return "zeo_zif_dishwashing_liquid"
    if "pano" in norm_text:
        if re.search(r"(rua chen|rua bat)", norm_text):
            return "pano_dishwashing_lemon_and_vitamin_e"
        if re.search(r"(mui|huong|mau)", norm_text):
            return "pano_laundry_fragrance_options"
        if re.search(r"(quy cach|tui|can|dong goi)", norm_text):
            return "pano_laundry_packaging_and_segment"
        if re.search(r"(nuoc giat|bot giat|giat)", norm_text):
            return "pano_product_type"
        return "pano_product_type"
    if "oplus" in norm_text:
        if re.search(r"(rua chen|rua bat)", norm_text):
            return "oplus_dishwashing_liquid"
        if re.search(r"(cong nghe|ion)", norm_text):
            return "oplus_detergent_ion_technology"
        if re.search(r"(nuoc xa|xa vai)", norm_text):
            return "oplus_fabric_softener_unverified"
        if re.search(r"(bot giat|giat)", norm_text):
            return "oplus_detergent_features"
    if re.search(r"(bot giat|nuoc giat).{0,20}\bzeo\b|\bzeo\b.{0,20}(bot giat|nuoc giat)", norm_text):
        if re.search(r"(chung nhan|pasteur|kiem dinh|kiem nghiem|giay to|chung minh)", norm_text):
            return "zeo_detergent_certification"
        return "zeo_detergent_technology"
    return None


class ChatPipelineRequest(BaseModel):
    brand: str = "zeo"                  # "zeo" hoặc "cfc"
    sender_id: str                      # Messenger PSID
    text: str                           # Tin nhắn của khách
    fb_name: Optional[str] = ""         # Tên hiển thị Facebook
    message_id: Optional[str] = ""      # Message ID từ Facebook webhook


class ChatPipelineResponse(BaseModel):
    ok: bool = True
    answer: str
    intent: str
    confidence: str
    score: float
    brand: str
    has_phone: bool = False
    phone: str = ""
    area: str = ""
    lead_stage: str = "new"
    shopee_url: Optional[str] = None
    latency_ms: float = 0.0


async def _sheet_fast_response(
    brand: str,
    start_time: float,
    intent: str,
    *,
    lead_stage: str = "new",
    unavailable_intent: Optional[str] = None,
    unavailable_answer: Optional[str] = None,
) -> ChatPipelineResponse:
    item = await get_faq_by_intent(brand, intent)
    answer = item.get("answer", "").strip()
    if answer:
        return _fast_response(answer, intent, brand, start_time, lead_stage=lead_stage)

    fallback = unavailable_answer or (
        "Dạ hiện mục thông tin này chưa tải được từ hệ thống kiến thức. "
        "Admin sẽ kiểm tra lại dữ liệu và phản hồi bạn chính xác hơn nha."
    )
    return _fast_response(fallback, unavailable_intent or f"{intent}_unavailable", brand, start_time, lead_stage=lead_stage)


async def process_chat_pipeline(req: ChatPipelineRequest) -> ChatPipelineResponse:
    start_time = time.perf_counter()
    brand = req.brand.lower()
    raw_text = (req.text or "").strip()
    sender_id = req.sender_id.strip()
    fb_name = (req.fb_name or "").strip()
    
    if not raw_text:
        return ChatPipelineResponse(
            answer=_prettify_answer("Dạ bạn cần bên mình hỗ trợ thông tin gì ạ?"),
            intent="empty_input",
            confidence="high",
            score=1.0,
            brand=brand.upper(),
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
        )

    norm_text = _normalize_vn(raw_text)
    phone, area = _extract_phone_and_area(raw_text, norm_text)
    has_phone = bool(phone)

    # Đọc nhanh profile & session cũ từ Redis (Song song để tối ưu I/O)
    r = await get_redis()
    customer_key = f"{brand}:customer:messenger:{sender_id}"
    session_key = f"{brand}:session:messenger:{sender_id}"

    existing_profile = {}
    existing_session = {}
    try:
        raw_p, raw_s = await asyncio.gather(
            r.get(customer_key),
            r.get(session_key),
            return_exceptions=True,
        )
        if isinstance(raw_p, (str, bytes)) and raw_p:
            existing_profile = json.loads(raw_p)
        if isinstance(raw_s, (str, bytes)) and raw_s:
            existing_session = json.loads(raw_s)
    except Exception as e:
        logger.warning("Redis read error in pipeline: %s", e)

    # Merge phone & area nếu profile/session cũ đã có
    stored_phone = (
        existing_profile.get("phone")
        or existing_profile.get("customer_phone")
        or existing_session.get("customer_phone")
        or existing_session.get("phone")
        or ""
    )
    stored_area = (
        existing_profile.get("area")
        or existing_profile.get("customer_location")
        or existing_session.get("customer_location")
        or existing_session.get("area")
        or ""
    )
    if not phone and stored_phone:
        phone = stored_phone
    if not area and stored_area:
        area = stored_area

    lead_stage = existing_profile.get("lead_stage", "new")
    previous_intent = existing_session.get("last_intent", "")
    conversation_state = _load_conversation_state(existing_session, brand)
    query_entities = _extract_query_entities(norm_text, brand)
    reference_resolution = _resolve_reference(raw_text, norm_text, conversation_state)
    if reference_resolution.get("resolved") and not query_entities.get("product"):
        query_entities = {
            "product": reference_resolution.get("product", ""),
            "product_intent": reference_resolution.get("product_intent", ""),
            "category": reference_resolution.get("category", ""),
            "matched_entities": [{
                "product": reference_resolution.get("product", ""),
                "product_intent": reference_resolution.get("product_intent", ""),
                "category": reference_resolution.get("category", ""),
            }],
        }

    def _remember_response(
        answer: str,
        intent: str,
        stage: str,
        *,
        confidence: str = "high",
        score: float = 1.0,
        source_id: str = "",
        fallback_reason: str = "",
    ) -> None:
        next_state = _build_next_conversation_state(
            conversation_state,
            brand=brand,
            user_message=raw_text,
            bot_reply=answer,
            intent=intent,
            lead_stage=stage,
            query_entities=query_entities,
            reference_resolution=reference_resolution,
            source_id=source_id,
        )
        trace = {
            "normalized_text": norm_text,
            "resolved_query": reference_resolution.get("resolved_query", raw_text),
            "reference": {
                "used": bool(reference_resolution.get("references_previous_turn")),
                "resolved": bool(reference_resolution.get("resolved")),
                "reason": reference_resolution.get("reason", ""),
                "product": reference_resolution.get("product", ""),
            },
            "query_entities": query_entities,
            "source_id": source_id,
            "confidence": confidence,
            "score": score,
            "fallback_reason": fallback_reason,
        }
        asyncio.create_task(_async_save_session(
            brand=brand,
            sender_id=sender_id,
            user_message=raw_text,
            bot_reply=_prettify_answer(answer),
            intent=intent,
            lead_stage=stage,
            conversation_state=next_state,
            trace=trace,
        ))

    async def _sheet_response_remember(
        intent: str,
        *,
        stage: str = "new",
        unavailable_intent: Optional[str] = None,
        unavailable_answer: Optional[str] = None,
    ) -> ChatPipelineResponse:
        item = await get_faq_by_intent(brand, intent)
        answer = item.get("answer", "").strip()
        response_intent = intent
        source_id = item.get("source_id", "")
        if not answer:
            response_intent = unavailable_intent or f"{intent}_unavailable"
            answer = unavailable_answer or (
                "Dạ hiện mục thông tin này chưa tải được từ hệ thống kiến thức. "
                "Admin sẽ kiểm tra lại dữ liệu và phản hồi bạn chính xác hơn nha."
            )
        _remember_response(answer, response_intent, stage, source_id=source_id)
        return _fast_response(answer, response_intent, brand, start_time, lead_stage=stage)

    def _fast_response_remember(answer: str, intent: str, *, stage: str = "new") -> ChatPipelineResponse:
        _remember_response(answer, intent, stage)
        return _fast_response(answer, intent, brand, start_time, lead_stage=stage)

    # ─────────────────────────────────────────────────────────────
    # FAST-PATH 1: KHÁCH ĐỂ LẠI SỐ ĐIỆN THOẠI & ĐỊA CHỈ (< 20ms)
    # ─────────────────────────────────────────────────────────────
    if has_phone:
        lead_stage = "lead_ready"
        if brand == "zeo":
            final_reply = (
                f"Dạ ZeO Vietnam đã nhận được số điện thoại {phone}"
                f"{f' tại {area}' if area else ''} của bạn. "
                "Chuyên viên tư vấn ZeO sẽ liên hệ trực tiếp để hỗ trợ chốt đơn và gửi ưu đãi cho bạn ngay nha!"
            )
        else:
            final_reply = (
                f"Dạ Cò Bay đã nhận được số điện thoại {phone}"
                f"{f' tại khu vực {area}' if area else ''} của bạn. "
                "Kỹ sư nông nghiệp Cò Bay sẽ liên hệ tư vấn quy trình bón phân và giao hàng tận nơi cho mình sớm nhất nhé ạ!"
            )

        # Cập nhật profile & Bắn thông báo Telegram (Background Async)
        existing_profile.update({
            "brand": brand.upper(),
            "sender_id": sender_id,
            "fb_name": fb_name or existing_profile.get("fb_name", ""),
            "phone": phone,
            "customer_phone": phone,
            "area": area or existing_profile.get("area", ""),
            "customer_location": area or existing_profile.get("area", ""),
            "lead_stage": "lead_ready",
            "last_intent": "contact_phone_provided",
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        })

        asyncio.create_task(_async_save_profile_and_notify(
            brand=brand,
            sender_id=sender_id,
            profile=existing_profile,
            phone=phone,
            area=area,
            fb_name=fb_name,
            need="Khách để lại SĐT trên Messenger",
        ))

        return ChatPipelineResponse(
            answer=_prettify_answer(final_reply),
            intent="contact_phone_provided",
            confidence="high",
            score=1.0,
            brand=brand.upper(),
            has_phone=True,
            phone=phone,
            area=area,
            lead_stage="lead_ready",
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
        )

    # ─────────────────────────────────────────────────────────────
    # FAST-PATH 1.5: KHÁCH HỎI LẠI THÔNG TIN ĐÃ LƯU (< 20ms)
    # ─────────────────────────────────────────────────────────────
    asks_saved_phone = (
        re.search(r"(so dien thoai|dien thoai|sdt).*(cua )?(toi|minh|em|anh|chi)", norm_text)
        or re.search(r"(ban|shop|ad|admin).*(con nho|nho|co luu|da luu).*(so dien thoai|dien thoai|sdt)", norm_text)
        or re.search(r"(toi|minh|em|anh|chi).*(da gui|co gui|gui roi).*(so dien thoai|dien thoai|sdt)", norm_text)
    )
    asks_saved_area = (
        re.search(r"(dia chi|khu vuc|noi o|tinh thanh).*(cua )?(toi|minh|em|anh|chi)", norm_text)
        or re.search(r"(ban|shop|ad|admin).*(con nho|nho|co luu|da luu).*(dia chi|khu vuc|noi o|tinh thanh)", norm_text)
        or re.search(r"(toi|minh|em|anh|chi).*(o dau|khu vuc nao|dia chi nao)", norm_text)
    )
    asks_profile_recall = (
        re.search(r"(thong tin|ho so).*(cua )?(toi|minh|em|anh|chi)", norm_text)
        or re.search(r"(ban|shop|ad|admin).*(con nho|nho|co luu|da luu).*(toi|minh|em|anh|chi)", norm_text)
        or re.search(r"(nho|con nho).*(dia chi|khu vuc|so dien thoai|dien thoai|sdt)", norm_text)
    )
    if asks_saved_phone or asks_saved_area or asks_profile_recall:
        brand_display = "ZeO" if brand == "zeo" else "Cò Bay"
        if asks_saved_phone and asks_saved_area:
            if phone and area:
                final_reply = f"Dạ có, {brand_display} đang lưu số điện thoại của bạn là {phone} và khu vực/địa chỉ là {area}."
            elif phone:
                final_reply = f"Dạ {brand_display} đang lưu số điện thoại của bạn là {phone}. Mình chưa thấy khu vực/địa chỉ trong hồ sơ chat này, bạn gửi thêm giúp mình nha."
            elif area:
                final_reply = f"Dạ {brand_display} đang lưu khu vực/địa chỉ của bạn là {area}. Mình chưa thấy số điện thoại trong hồ sơ chat này, bạn gửi thêm giúp mình nha."
            else:
                final_reply = f"Dạ hiện {brand_display} chưa thấy lưu số điện thoại và khu vực/địa chỉ trong hồ sơ chat này. Bạn gửi lại giúp mình để bên mình lưu và hỗ trợ đúng hơn nha."
        elif asks_saved_phone:
            final_reply = (
                f"Dạ số điện thoại {brand_display} đang lưu của bạn là {phone}."
                if phone
                else f"Dạ hiện {brand_display} chưa thấy lưu số điện thoại trong hồ sơ chat này. Bạn gửi lại số điện thoại giúp mình nha."
            )
        elif asks_saved_area:
            final_reply = (
                f"Dạ khu vực/địa chỉ {brand_display} đang lưu của bạn là {area}."
                if area
                else f"Dạ hiện {brand_display} chưa thấy lưu khu vực/địa chỉ trong hồ sơ chat này. Bạn gửi lại khu vực/tỉnh thành giúp mình nha."
            )
        elif phone and area:
            final_reply = f"Dạ có, {brand_display} đang lưu số điện thoại {phone} và khu vực/địa chỉ {area} của bạn."
        elif phone:
            final_reply = f"Dạ có, {brand_display} đang lưu số điện thoại của bạn là {phone}. Bạn gửi thêm khu vực/tỉnh thành để bên mình hỗ trợ đúng hơn nha."
        elif area:
            final_reply = f"Dạ có, {brand_display} đang lưu khu vực/địa chỉ của bạn là {area}. Bạn gửi thêm số điện thoại để bên mình tiện liên hệ nha."
        else:
            final_reply = f"Dạ hiện {brand_display} chưa thấy có đủ thông tin của bạn trong hồ sơ chat này. Bạn gửi lại số điện thoại và khu vực/tỉnh thành giúp mình nha."

        return ChatPipelineResponse(
            answer=_prettify_answer(final_reply),
            intent="customer_profile_lookup",
            confidence="high",
            score=1.0,
            brand=brand.upper(),
            has_phone=bool(phone),
            phone=phone or "",
            area=area or "",
            lead_stage=lead_stage,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
        )

    # ─────────────────────────────────────────────────────────────
    # FAST-PATH 2: CHÀO HỎI, CẢM ƠN, XÁC NHẬN (< 10ms)
    # ─────────────────────────────────────────────────────────────
    token_count = len(norm_text.split())
    if token_count <= 4:
        if re.search(r"^(xin chao|chao|hello|hi|alo|shop oi|admin oi|ad oi|shop)\b", norm_text):
            greeting = "Dạ ZeO Vietnam chào bạn! Bạn đang cần tư vấn về nước giặt sinh học, nước rửa chén hay mua hàng ạ?" if brand == "zeo" else "Dạ phân bón Cò Bay (CFC) chào bạn! Bạn đang cần tư vấn phân bón cho cây lúa, cây ăn trái hay đại lý phân phối ạ?"
            return _fast_response(greeting, "greeting", brand, start_time)

        if re.search(r"^(cam on|thanks|thank you|da cam on|ok cam on|tks)\b", norm_text):
            thanks = "Dạ ZeO cảm ơn bạn đã quan tâm! Cần hỗ trợ thêm bạn cứ nhắn shop nha." if brand == "zeo" else "Dạ Cò Bay cảm ơn bạn! Chúc bạn một vụ mùa bội thu ạ."
            return _fast_response(thanks, "thanks", brand, start_time)

        if re.search(r"^(ok|oke|okay|da|vang|uh|um|roi|duoc|biet roi|hieu roi)\b", norm_text):
            ack = "Dạ vâng ạ! Bạn cần thêm thông tin gì cứ nhắn ZeO nhé." if brand == "zeo" else "Dạ vâng ạ! Khi nào cần phân bón chất lượng cao bạn cứ nhắn Cò Bay nha."
            return _fast_response(ack, "acknowledgement", brand, start_time)

        if re.fullmatch(r"0?2", norm_text):
            previous_bot = _normalize_vn(existing_session.get("last_bot_reply", ""))
            if "1900 5307" in previous_bot or "phim nhanh" in previous_bot or "phim nhanh so 02" in previous_bot or "phim nhanh so 2" in previous_bot:
                branch_msg = (
                    "Dạ số 02 là phím nhánh mua hàng khi bạn gọi hotline 1900 5307. "
                    "Nếu bạn đang nhắn tại đây, bạn có thể gửi tên sản phẩm cần mua hoặc số điện thoại để admin hỗ trợ tiếp nha."
                )
                return _fast_response(branch_msg, "hotline_branch_02", brand, start_time, lead_stage="browsing_catalog")
            clarify_msg = "Dạ bạn muốn chọn mục nào ạ? Bạn nhắn giúp mình nhu cầu như xem sản phẩm, link website, mua hàng hoặc cần hỗ trợ đơn hàng nha."
            return _fast_response(clarify_msg, "short_numeric_clarify", brand, start_time)

        if re.search(r"^(it vay|it the|it vay thoi|chi vay|chi co vay|co vay thoi)\b", norm_text):
            if brand == "zeo":
                expand_msg = (
                    "Dạ không chỉ một nhóm đâu ạ. ZeO Vietnam hiện có 4 nhóm chính: "
                    "Giặt giũ, Rửa chén, Lau sàn và Tẩy rửa vệ sinh. "
                    "Nếu bạn muốn, mình có thể liệt kê chi tiết từng nhóm sản phẩm cho bạn nha."
                )
            else:
                expand_msg = (
                    "Dạ Cò Bay hiện tập trung vào phân bón, gồm các dòng như NPK và phân hữu cơ. "
                    "Bạn cho mình biết loại cây trồng để bên mình tư vấn dòng phù hợp hơn ạ."
                )
            return _fast_response(expand_msg, "catalog_followup_expand", brand, start_time, lead_stage="browsing_catalog")

    # ─────────────────────────────────────────────────────────────
    # FAST-PATH 3: PHÁT HIỆN KHIẾU NẠI GAY GẮT / CẢNH BÁO (< 15ms)
    # ─────────────────────────────────────────────────────────────
    COMPLAINT_TRIGGERS = [
        "bot ngu", "tra loi gi ky", "khong lien quan", "chui", "chan ghe", "that vong",
        "lua dao", "hang gia", "hang kem chat luong", "gian lan", "an quyt", "thai do kem", "to cao"
    ]
    if any(k in norm_text for k in COMPLAINT_TRIGGERS):
        lead_stage = "escalated"
        complaint_msg = (
            "Dạ xin lỗi bạn vì trải nghiệm chưa tốt vừa rồi. Vấn đề này em xin phép chuyển thẳng cho Admin phụ trách xử lý ngay. "
            "Bạn để lại số điện thoại hoặc mô tả chi tiết giúp em nhé ạ!"
        )
        asyncio.create_task(notify_admin_unanswered(brand=brand, query=raw_text, sender_id=sender_id, score=0.0))
        return _fast_response(complaint_msg, "bot_complaint_escalate", brand, start_time, lead_stage="escalated")

    # ─────────────────────────────────────────────────────────────
    # PATH 3.4: INTENT-FIRST ROUTER CHỐNG RAG BẮT NHẦM (< 15ms)
    # ─────────────────────────────────────────────────────────────
    brand_display = "ZeO Vietnam" if brand == "zeo" else "CFC Cò Bay"

    if _detect_language_request(norm_text):
        msg = (
            f"Dạ hiện {brand_display} hỗ trợ tư vấn chính bằng tiếng Việt để đảm bảo thông tin sản phẩm, giá và chính sách không bị sai lệch. "
            "Bạn cứ nhắn nhu cầu bằng tiếng Việt, mình sẽ hỗ trợ đúng theo dữ liệu hệ thống nha."
        )
        return _fast_response(msg, "language_support_vi", brand, start_time)

    if _detect_out_of_scope_general_question(norm_text):
        msg = (
            f"Dạ câu này nằm ngoài dữ liệu tư vấn sản phẩm/dịch vụ của {brand_display}, "
            "nên mình không dùng FAQ để đoán trả lời. "
            "Bạn cần xem sản phẩm, giá, giao hàng hay thông tin liên hệ bên mình không ạ?"
        )
        return _fast_response_remember(msg, "out_of_scope_general_question", stage=lead_stage)

    if _detect_customer_correction(norm_text):
        msg = (
            "Dạ mình ghi nhận góp ý/cập nhật thông tin của bạn rồi ạ. "
            "Phần này mình sẽ chuyển admin kiểm tra với dữ liệu chính thức trước khi cập nhật, để tránh tự sửa sai hoặc trả lời nhầm cho khách khác nha."
        )
        asyncio.create_task(notify_admin_unanswered(brand=brand, query=raw_text, sender_id=sender_id, score=0.0))
        return _fast_response(msg, "customer_correction_review", brand, start_time, lead_stage="escalated")

    if _detect_competitor_product(norm_text, brand):
        msg = (
            "Dạ hiện dữ liệu ZeO chưa có thông tin sản phẩm/thương hiệu bạn vừa hỏi. "
            "ZeO Vietnam đang có các nhóm giặt giũ, rửa chén, lau sàn và tẩy rửa vệ sinh thuộc hệ ZeO/PANO/Oplus. "
            "Bạn muốn mình gửi danh mục ZeO hiện có để chọn đúng sản phẩm không ạ?"
        )
        return _fast_response(msg, "competitor_product_unavailable", brand, start_time, lead_stage="browsing_catalog")

    if _detect_cfc_cross_brand(norm_text, brand):
        return await _sheet_fast_response(
            brand,
            start_time,
            "cfc_cross_brand_out_of_scope",
            lead_stage="browsing_catalog",
            unavailable_answer=(
                "Dạ CFC Cò Bay hiện là thương hiệu phân bón nông nghiệp. "
                "Các sản phẩm tẩy rửa gia dụng như nước giặt/nước rửa chén/lau sàn thuộc hệ ZeO/PANO/Oplus nha."
            ),
        )

    if _detect_new_product_request(norm_text):
        msg = (
            f"Dạ hiện hệ thống kiến thức của {brand_display} chưa có mục xác nhận sản phẩm mới nhất/mới ra mắt. "
            "Để tránh báo sai, bạn cho mình biết nhóm sản phẩm đang quan tâm hoặc để lại số điện thoại, admin sẽ kiểm tra thông tin mới nhất giúp mình nha."
        )
        return _fast_response(msg, "new_product_unverified", brand, start_time, lead_stage="browsing_catalog")

    proof_intent = _detect_proof_or_certification_intent(norm_text, brand, previous_intent)
    if proof_intent:
        return await _sheet_response_remember(proof_intent, stage="browsing_catalog")

    contact_intent = _detect_contact_intent(norm_text, brand)
    if contact_intent:
        return await _sheet_response_remember(
            contact_intent,
            stage="browsing_catalog",
            unavailable_intent="company_contact_information_unavailable",
            unavailable_answer=(
                f"Dạ hiện dữ liệu chưa có số hotline chính thức của {brand_display} để mình báo chắc chắn. "
                "Bạn để lại số điện thoại hoặc nhu cầu, admin sẽ kiểm tra và phản hồi thông tin liên hệ chính xác nha."
            ),
        )

    company_overview_intent = _detect_company_overview_intent(norm_text, brand)
    if company_overview_intent:
        return await _sheet_response_remember(company_overview_intent, stage="browsing_catalog")

    address_intent = _detect_address_intent(norm_text, brand)
    if address_intent:
        return await _sheet_response_remember(address_intent, stage="browsing_catalog")

    official_channel_intent = _detect_official_channel_request(norm_text)
    if official_channel_intent and not _is_internal_content_request(norm_text):
        msg = (
            f"Dạ hiện hệ thống kiến thức của {brand_display} chưa có link chính thức cho kênh bạn vừa hỏi. "
            "Để tránh gửi nhầm link giả, bạn có thể dùng website chính thức hoặc để lại nhu cầu, admin sẽ kiểm tra và gửi đúng kênh chính thức nha."
        )
        return _fast_response(msg, official_channel_intent, brand, start_time, lead_stage="browsing_catalog")

    if reference_resolution.get("references_previous_turn"):
        resolved_product = reference_resolution.get("product", "")
        if reference_resolution.get("resolved") and _has_price_signal(norm_text):
            msg = (
                f"Dạ mình hiểu bạn đang hỏi giá của {resolved_product}. "
                "Hiện hệ thống chưa có giá chính xác cho sản phẩm/nhóm này nên mình không tự báo giá để tránh sai. "
                "Bạn gửi thêm quy cách cần mua hoặc số điện thoại/khu vực, admin sẽ kiểm tra báo giá đúng cho mình nha."
            )
            return _fast_response_remember(msg, "contextual_price_unverified", stage="browsing_catalog")

        if reference_resolution.get("resolved") and _looks_like_availability_request(norm_text):
            msg = (
                f"Dạ mình hiểu bạn đang hỏi {resolved_product} còn hàng không. "
                "Hiện hệ thống chat chưa có dữ liệu tồn kho realtime, nên mình chưa xác nhận chắc được. "
                "Bạn để lại số điện thoại/khu vực hoặc nhắn quy cách cần mua, admin sẽ kiểm tra tồn kho chính xác giúp mình nha."
            )
            return _fast_response_remember(msg, "contextual_availability_unverified", stage="collecting_contact")

        if reference_resolution.get("resolved") and _looks_like_shipping_request(norm_text):
            shipping_intent = "nationwide_shipping_no_cod" if brand.lower() == "zeo" else "shipping_methods"
            item = await get_faq_by_intent(brand, shipping_intent)
            sheet_answer = item.get("answer", "").strip()
            if sheet_answer:
                msg = f"Dạ mình đang hiểu bạn hỏi giao hàng cho {resolved_product}.\n\n{sheet_answer}"
                _remember_response(msg, "contextual_shipping", "browsing_catalog", source_id=item.get("source_id", ""))
                return _fast_response(msg, "contextual_shipping", brand, start_time, lead_stage="browsing_catalog")
            return await _sheet_response_remember(shipping_intent, stage="browsing_catalog")

        if not reference_resolution.get("resolved") and (
            _has_price_signal(norm_text) or _looks_like_availability_request(norm_text) or _looks_like_shipping_request(norm_text)
        ):
            msg = (
                "Dạ bạn đang hỏi sản phẩm/nhóm nào trong danh sách vừa rồi ạ? "
                "Bạn nhắn tên sản phẩm hoặc số thứ tự như số 1, số 2 để mình kiểm tra đúng thông tin nha."
            )
            return _fast_response_remember(msg, "context_reference_clarify", stage="browsing_catalog")

    if _detect_usage_safety_gap(norm_text, brand):
        if brand == "cfc":
            usage_intent = "cfc_dosage_usage_review"
            return await _sheet_response_remember(usage_intent, stage="collecting_contact")
        msg = (
            "Dạ phần liều lượng/cách dùng hoặc tình huống an toàn cần kiểm tra theo đúng sản phẩm và hướng dẫn trên bao bì. "
            "Hiện hệ thống chưa có đủ dữ liệu để mình tự hướng dẫn chi tiết. Bạn gửi tên sản phẩm hoặc số điện thoại, admin sẽ tư vấn chính xác hơn nha."
        )
        return _fast_response_remember(msg, "zeo_usage_safety_review", stage="collecting_contact")

    specific_product_intent = _detect_specific_product_intent(norm_text, brand)
    if specific_product_intent and not (_has_price_signal(norm_text) or any(k in norm_text for k in ["ship", "giao hang", "phi", "doi tra", "bao hanh", "loi", "hong"])):
        return await _sheet_response_remember(specific_product_intent, stage="browsing_catalog")

    # ─────────────────────────────────────────────────────────────
    # PATH 3.5: PROMOTIONS, DEALS & VOUCHERS (< 15ms)
    # ─────────────────────────────────────────────────────────────
    from shopee_matcher import is_promotion_inquiry, match_promotions_and_deals
    if is_promotion_inquiry(raw_text):
        promo_res = match_promotions_and_deals(raw_text, brand=brand)
        if promo_res:
            return ChatPipelineResponse(
                answer=_prettify_answer(promo_res["suggested_reply"]),
                intent="promotion_deals",
                confidence="high",
                score=0.96,
                brand=brand.upper(),
                has_phone=has_phone,
                phone=phone,
                area=area,
                lead_stage=lead_stage,
                shopee_url=promo_res.get("shopee_url"),
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

    # ─────────────────────────────────────────────────────────────
    # PATH 3.6: HOTLINE & PRICE INQUIRY (< 15ms)
    # ─────────────────────────────────────────────────────────────
    if re.search(r"(website|web site|trang web|link website|link web|xin link website|xin link web|co link website|co link web|zeo vn|zeo\.vn|cfc web|co bay web|cfccobay|cfc co bay)\b", norm_text):
        website_intent = "company_website" if brand.lower() == "zeo" else "cfc_company_website"
        return await _sheet_response_remember(website_intent, stage="browsing_catalog")

    if re.search(r"(hotline|so dien thoai cong ty|tong dai|so hotline|lien he so nao)\b", norm_text):
        hotline_intent = "company_contact_information" if brand.lower() == "zeo" else "cfc_company_website"
        return await _sheet_response_remember(
            hotline_intent,
            stage="browsing_catalog",
            unavailable_intent="company_contact_information_unavailable",
            unavailable_answer="Dạ hiện dữ liệu chưa có số hotline chính thức để mình báo chắc chắn. Bạn để lại số điện thoại hoặc nhu cầu, admin sẽ kiểm tra và phản hồi thông tin liên hệ chính xác nha.",
        )

    if re.search(r"(gia(?: .{1,80})? bao nhieu|bao nhieu tien|bang gia|xin gia|gia ban|gia ca|nhieu tien|bao gia)\b", norm_text) and not any(k in norm_text for k in ["ship", "phi", "van chuyen", "cuoc"]):
        price_intent = "zeo_price_inquiry_general" if brand.lower() == "zeo" else "cfc_price_unverified"
        return await _sheet_response_remember(price_intent, stage="browsing_catalog")

    # ─────────────────────────────────────────────────────────────
    # PATH 3.7: WHOLESALE & DISTRIBUTOR INQUIRY (< 15ms)
    # ─────────────────────────────────────────────────────────────
    if re.search(r"(lay si|muon lam dai ly|dang ky dai ly|nhap hang|phan phoi|chinh sach si|nhap so luong lon|kinh doanh zeo|dai li)\b", norm_text):
        wholesale_intent = "wholesale_inquiry" if brand.lower() == "zeo" else "wholesale_dealer"
        return await _sheet_response_remember(wholesale_intent, stage="collecting_contact")

    # ─────────────────────────────────────────────────────────────
    # PATH 3.7.5: PRODUCT GROUP VIEW INQUIRY (< 15ms)
    # ─────────────────────────────────────────────────────────────
    product_group_intent = _detect_product_group_intent(norm_text, brand)
    if product_group_intent and not (_has_price_signal(norm_text) or any(k in norm_text for k in ["ship", "giao hang", "phi", "doi tra", "bao hanh", "loi", "hong"])):
        return await _sheet_response_remember(product_group_intent, stage="browsing_catalog")

    # ─────────────────────────────────────────────────────────────
    # PATH 3.8: GENERAL CATALOG OVERVIEW INQUIRY (< 15ms)
    # ─────────────────────────────────────────────────────────────
    if re.search(r"(cac san pham|nhung san pham|danh muc san pham|co san pham gi|co san pham nao|san pham nao|co nhung gi|co nhung loai nao|cac dong san pham|dong san pham|co dong nao|co nhom nao|gioi thieu san pham|hoi ve cac san pham|ban nhung gi|nhom san pham|mat hang nao|co phan bon gi|phan bon gi|phan bon nao|cac loai phan bon)", norm_text) and not any(k in norm_text for k in ["doi tra", "doi", "tra", "bao hanh", "chinh sach", "loi", "hong", "hoan tien"]):
        catalog_intent = "zeo_product_catalog_overview" if brand.lower() == "zeo" else "product_lines"
        catalog_item = await get_faq_by_intent(brand, catalog_intent)
        catalog_reply = catalog_item.get("answer", "").strip()
        if catalog_reply:
            _remember_response(catalog_reply, catalog_intent, "browsing_catalog", source_id=catalog_item.get("source_id", ""))
            return _fast_response(catalog_reply, catalog_intent, brand, start_time, lead_stage="browsing_catalog")

        fallback_msg = (
            "Dạ hiện danh mục sản phẩm chưa tải được từ hệ thống kiến thức. "
            "Bạn nhắn rõ nhóm sản phẩm muốn xem, hoặc admin sẽ kiểm tra lại dữ liệu giúp mình nha."
        )
        return _fast_response_remember(fallback_msg, "catalog_overview_unavailable", stage="browsing_catalog")

    # ─────────────────────────────────────────────────────────────
    # PATH 3.9: OPENING HOURS (< 15ms)
    # ─────────────────────────────────────────────────────────────
    if re.search(r"(mo cua|dong cua|may gio|gio mo cua|gio lam viec|cuoi tuan|mo cua luc|lam viec den may gio)\b", norm_text) and not (_has_price_signal(norm_text) or any(k in norm_text for k in ["ship", "phi", "doi tra"])):
        hours_intent = "shop_opening_hours" if brand.lower() == "zeo" else "opening_hours"
        return await _sheet_response_remember(hours_intent)

    # ─────────────────────────────────────────────────────────────
    # PATH 3.10: PANO FRAGRANCES & TECH FAST-PATH (< 15ms)
    # ─────────────────────────────────────────────────────────────
    if re.search(r"(mui huong|huong gi|may mau|do xanh hong cam tim|chon huong|tuy chon huong)\b", norm_text) and "pano" in norm_text:
        if brand.lower() == "zeo":
            return await _sheet_response_remember("pano_laundry_fragrance_options", stage="browsing_catalog")

    if re.search(r"(enzyme|thuy dien|cong nghe gi|cong nghe lam sach|tay vet ban|diet khuan)\b", norm_text) and any(k in norm_text for k in ["zeo", "bot giat", "nuoc giat"]):
        if brand.lower() == "zeo":
            return await _sheet_response_remember("zeo_detergent_technology", stage="browsing_catalog")

    if re.search(r"(chinh sach doi tra|quy trinh doi tra|thoi han doi tra|doi tra nhu the nao|duoc doi tra khong|doi tra ap dung|kenh nao duoc doi tra)\b", norm_text):
        if brand.lower() == "zeo":
            return await _sheet_response_remember("return_policy_scope", stage="browsing_catalog")

    # ─────────────────────────────────────────────────────────────
    # PATH 4: SHOPEE LINK & PRODUCT MATCHER (< 20ms)
    # ─────────────────────────────────────────────────────────────
    shopee_match = None
    # Nếu câu hỏi có từ khóa đổi trả -> Nhường cho Policy RAG
    if is_shopee_inquiry(raw_text) and not any(k in norm_text for k in ["doi", "tra", "loi", "hong", "bao hanh"]):
        shopee_match = match_shopee_product(raw_text, brand=brand)
        if shopee_match:
            return ChatPipelineResponse(
                answer=_prettify_answer(shopee_match["suggested_reply"]),
                intent=shopee_match.get("intent", "shopee_product_link"),
                confidence="high",
                score=0.95,
                brand=brand.upper(),
                has_phone=has_phone,
                phone=phone,
                area=area,
                lead_stage=lead_stage,
                shopee_url=shopee_match.get("shopee_url") or shopee_match.get("matched_product", {}).get("shopee_url"),
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

    # ─────────────────────────────────────────────────────────────
    # PATH 5: REDISEARCH SEMANTIC VECTOR SEARCH (< 50ms)
    # ─────────────────────────────────────────────────────────────
    rag_query = reference_resolution.get("resolved_query") if reference_resolution.get("resolved") else raw_text
    rag_result = await semantic_search(query=rag_query or raw_text, brand=brand, top_k=10)
    best_score = rag_result.get("score", 0.0)
    intent = rag_result.get("intent", "general_faq")
    raw_answer = rag_result.get("answer", "")
    answer_mode = rag_result.get("answer_mode", "direct")

    # ─────────────────────────────────────────────────────────────
    # PATH 6: SEMANTIC ANCHOR GUARDRAILS (Chống Bắt Nhầm Lạc Đề)
    # ─────────────────────────────────────────────────────────────
    def _check_intent_guardrails(target_intent: str, query_norm: str) -> bool:
        """Kiểm tra từ khóa neo bắt buộc để tránh gán nhầm câu hỏi không liên quan."""
        # 1. Đổi trả / Bảo hành (Chỉ áp dụng khi hỏi về đổi / trả / lỗi / hỏng)
        if "return" in target_intent or "policy" in target_intent or "warranty" in target_intent:
            return any(k in query_norm for k in ["doi", "tra", "loi", "hong", "bao hanh", "hoan tien", "rach"])
        # 2. Thanh toán / Chuyển khoản (Trừ khi là intent giao hàng shipping)
        if ("payment" in target_intent or "cod_payment" in target_intent) and "shipping" not in target_intent:
            return any(k in query_norm for k in ["thanh toan", "chuyen khoan", "momo", "tien mat", "cod", "ngan hang", "stk", "tra sau"])
        # 3. Giờ mở cửa
        if "opening_hours" in target_intent or "hours" in target_intent:
            return any(k in query_norm for k in ["gio", "mo cua", "dong cua", "may gio", "cuoi tuan", "thoi gian"])
        # 4. Địa chỉ
        if "address" in target_intent or "location" in target_intent:
            if _detect_company_overview_intent(query_norm, brand):
                return False
            return any(k in query_norm for k in ["dia chi", "o dau", "nha may", "tru so", "van phong", "tai dau"])
        # 5. Đại lý sỉ
        if "wholesale" in target_intent or "dealer" in target_intent:
            return any(k in query_norm for k in ["si", "dai ly", "nhap hang", "phan phoi", "so luong lon", "hop tac"])
        # 6. Đặt hàng trực tiếp (order_request) - Bắt buộc phải có hành động đặt mua cụ thể
        if "order_request" in target_intent:
            return any(k in query_norm for k in ["dat hang", "chot don", "lay 1", "lay 2", "lay 3", "mua 1", "mua 2", "mua 3", "cho 1", "cho 2", "cho minh 1", "cho minh 2", "toi muon 2kg", "toi muon mua 2kg"])
        # 7. Thông tin liên hệ / Hotline
        if "contact" in target_intent or "hotline" in target_intent:
            return any(k in query_norm for k in ["hotline", "so dien thoai", "lien he", "tong dai", "sdt", "call"])
        if "tiktok" in target_intent or "zalo" in target_intent:
            return _is_internal_content_request(query_norm)
        return True

    is_guardrail_passed = _check_intent_guardrails(intent, norm_text)

    # ─────────────────────────────────────────────────────────────
    # PATH 7: TIERED RESPONSE SELECTION (Chuẩn Hóa Ngưỡng Vector BGE-M3)
    # ─────────────────────────────────────────────────────────────
    confidence = "low"
    final_answer = ""

    if best_score >= 0.65 and is_guardrail_passed:
        # Độ tương đồng tốt VÀ vượt qua Guardrail -> Trả lời câu FAQ chuẩn từ Google Sheet / Redis
        confidence = "high"
        final_answer = raw_answer
    elif best_score >= 0.52 and is_guardrail_passed:
        # Độ tương đồng trung bình -> Vẫn trả lời FAQ chuẩn nếu có
        confidence = "medium"
        final_answer = raw_answer
    else:
        # Thực sự không có trong FAQ (< 0.52) hoặc bị Guardrail chặn bắt nhầm -> Fallback trung thực
        confidence = "low"
        brand_display = "ZeO Vietnam" if brand.lower() == "zeo" else "CFC Cò Bay"

        purchase_signal = _has_price_signal(norm_text) or bool(
            re.search(r"(^|\s)(mua|dat|chai|lit|kg)(\s|$)", norm_text)
            or re.search(r"(bao phan|\d+\s*bao)", norm_text)
        )
        if purchase_signal and not any(w in norm_text for w in ["co nhung", "cac san pham", "san pham nao", "dong san pham", "gioi thieu"]):
            fallback_intent = "zeo_price_request_needs_product" if brand.lower() == "zeo" else "cfc_price_unverified"
            fallback_item = await get_faq_by_intent(brand, fallback_intent)
            final_answer = fallback_item.get("answer", "").strip() or (
                f"Dạ hiện dữ liệu chưa đủ để báo chính xác. Bạn nhắn rõ tên sản phẩm và nhu cầu cụ thể, "
                f"hoặc gửi số điện thoại/khu vực để admin {brand_display} kiểm tra và phản hồi nha."
            )
            lead_stage = "browsing_catalog"
        elif any(w in norm_text for w in ["dai ly", "si", "nhap", "hop tac", "npp", "phan phoi"]):
            fallback_intent = "wholesale_inquiry" if brand.lower() == "zeo" else "wholesale_dealer"
            fallback_item = await get_faq_by_intent(brand, fallback_intent)
            final_answer = fallback_item.get("answer", "").strip() or (
                f"Dạ bạn gửi giúp mình số điện thoại và khu vực dự kiến kinh doanh. "
                f"Admin {brand_display} sẽ kiểm tra thông tin phù hợp và phản hồi chính xác nha."
            )
            lead_stage = "collecting_contact"
        else:
            final_answer = (
                f"Dạ câu hỏi này mình chưa có sẵn thông tin chính xác trong hệ thống. "
                f"Bạn có thể nói rõ hơn nhu cầu (như mua hàng, xem sản phẩm hay cần hỗ trợ đơn hàng) để mình hỗ trợ đúng trọng tâm nhé ạ! "
                f"Hoặc bạn để lại số điện thoại để admin liên hệ giải đáp cho mình nha."
            )
            lead_stage = "collecting_contact"

        # Tự động đẩy vào Learning Queue để Admin duyệt
        asyncio.create_task(notify_admin_unanswered(brand=brand, query=raw_text, sender_id=sender_id, score=best_score))

    # ─────────────────────────────────────────────────────────────
    # ASYNC SAVE SESSION & CHAT HISTORY (Không làm chậm response)
    # ─────────────────────────────────────────────────────────────
    final_answer = _prettify_answer(final_answer)
    final_intent = intent if confidence in {"high", "medium"} else "unanswered_query"
    final_state = _build_next_conversation_state(
        conversation_state,
        brand=brand,
        user_message=raw_text,
        bot_reply=final_answer,
        intent=final_intent,
        lead_stage=lead_stage,
        query_entities=query_entities,
        reference_resolution=reference_resolution,
        source_id=rag_result.get("source_id", ""),
    )
    trace = {
        "normalized_text": norm_text,
        "rag_query": rag_query,
        "matched_intent": intent,
        "final_intent": final_intent,
        "score": best_score,
        "vector_score": rag_result.get("vector_score"),
        "rerank_adjustment": rag_result.get("rerank_adjustment"),
        "source_id": rag_result.get("source_id", ""),
        "guardrail_passed": is_guardrail_passed,
        "confidence": confidence,
        "reference": {
            "used": bool(reference_resolution.get("references_previous_turn")),
            "resolved": bool(reference_resolution.get("resolved")),
            "reason": reference_resolution.get("reason", ""),
            "product": reference_resolution.get("product", ""),
        },
        "query_entities": query_entities,
    }
    asyncio.create_task(_async_save_session(
        brand=brand,
        sender_id=sender_id,
        user_message=raw_text,
        bot_reply=final_answer,
        intent=final_intent,
        lead_stage=lead_stage,
        conversation_state=final_state,
        trace=trace,
    ))

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return ChatPipelineResponse(
        answer=final_answer,
        intent=final_intent,
        confidence=confidence,
        score=best_score,
        brand=brand.upper(),
        has_phone=has_phone,
        phone=phone,
        area=area,
        lead_stage=lead_stage,
        latency_ms=elapsed_ms,
    )


def _fast_response(answer: str, intent: str, brand: str, start_time: float, lead_stage: str = "new") -> ChatPipelineResponse:
    return ChatPipelineResponse(
        answer=_prettify_answer(answer),
        intent=intent,
        confidence="high",
        score=1.0,
        brand=brand.upper(),
        lead_stage=lead_stage,
        latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
    )


async def _async_save_profile_and_notify(brand: str, sender_id: str, profile: dict, phone: str, area: str, fb_name: str, need: str):
    """Cập nhật Redis profile và gửi thông báo Telegram trong nền."""
    try:
        r = await get_redis()
        customer_key = f"{brand}:customer:messenger:{sender_id}"
        await r.set(customer_key, json.dumps(profile, ensure_ascii=False))
        if phone:
            await notify_new_lead(
                brand=brand,
                phone=phone,
                area=area,
                fb_name=fb_name,
                need=need,
                sender_id=sender_id,
            )
    except Exception as e:
        logger.warning("Error in _async_save_profile_and_notify: %s", e)


async def _async_save_session(
    brand: str,
    sender_id: str,
    user_message: str,
    bot_reply: str,
    intent: str,
    lead_stage: str,
    conversation_state: Optional[dict[str, Any]] = None,
    trace: Optional[dict[str, Any]] = None,
):
    """Lưu session và lịch sử hội thoại trong nền."""
    try:
        r = await get_redis()
        session_key = f"{brand}:session:messenger:{sender_id}"
        history_key = f"{brand}:history:messenger:{sender_id}"
        now_str = datetime.now(timezone.utc).isoformat()

        session_data = {
            "sender_id": sender_id,
            "brand": brand.upper(),
            "last_user_message": user_message,
            "last_bot_reply": bot_reply,
            "last_intent": intent,
            "lead_stage": lead_stage,
            "last_seen_at": now_str,
        }
        if conversation_state:
            active_entities = conversation_state.get("active_entities", {})
            session_data.update({
                "conversation_state": conversation_state,
                "current_product": active_entities.get("product", ""),
                "current_category": active_entities.get("category", ""),
                "last_products_shown": conversation_state.get("last_products_shown", []),
                "conversation_summary": conversation_state.get("conversation_summary", ""),
                "last_source_id": conversation_state.get("last_source_id", ""),
            })
        if trace:
            session_data["last_trace"] = trace
        await r.set(session_key, json.dumps(session_data, ensure_ascii=False))

        # Lưu 10 tin nhắn gần nhất vào chat history
        msg_record = json.dumps({
            "user_message": user_message,
            "bot_reply": bot_reply,
            "intent": intent,
            "trace": trace or {},
            "timestamp": now_str,
        }, ensure_ascii=False)
        await r.rpush(history_key, msg_record)
        await r.ltrim(history_key, -50, -1)  # Giữ tối đa 50 tin
    except Exception as e:
        logger.warning("Error in _async_save_session: %s", e)
