"""
chat_pipeline.py — High-Performance Fast-Path Chatbot Pipeline cho ZeO & CFC
Đạt tốc độ phản hồi < 50ms - 300ms (Nhanh gấp 20 - 50 lần flow n8n cũ)

Quy trình:
  1. Per-Sender Request Sequencing (Chống race condition / lock theo sender_id)
  2. Fast-Path Regex & Normalize: Chào hỏi, cảm ơn, nhận diện SĐT, khiếu nại (< 5ms)
  3. Bóc tách Customer Profile Recall: Đọc trực tiếp từ Redis Profile, cách ly 100% khỏi RAG
  4. Shopee Catalog Matcher: Khớp link Shopee Mall chính hãng (< 10ms)
  5. In-Memory Lexical & RediSearch KNN RAG: Tra cứu FAQ chuẩn xác (< 5ms)
  6. Context Memory & Covered Fact Exclusion: Loại trừ fact cũ khi khách hỏi follow-up
  7. Granular Fallback Reasons: Phân loại nguyên nhân fallback chính xác
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

from rag_search import get_redis, get_faq_by_intent, semantic_search, refresh_knowledge_cache
from shopee_matcher import (
    match_shopee_product,
    is_shopee_inquiry,
    is_budget_inquiry,
    match_products_by_budget,
    match_specific_product_price,
    is_bestseller_inquiry,
    is_new_arrival_inquiry,
    match_best_sellers,
    match_new_arrivals,
    match_need_preference,
    is_bulk_or_restaurant_inquiry,
    match_bulk_or_restaurant_need,
    is_skin_care_dishwashing_inquiry,
    match_skin_care_dishwashing,
)
from telegram_notifier import notify_new_lead, notify_admin_unanswered

logger = logging.getLogger(__name__)

# Lock per-sender để tuần tự hóa các tin nhắn gửi dồn dập
_sender_locks: dict[str, asyncio.Lock] = {}
_global_lock = asyncio.Lock()


async def _get_sender_lock(lock_key: str) -> asyncio.Lock:
    async with _global_lock:
        if lock_key not in _sender_locks:
            _sender_locks[lock_key] = asyncio.Lock()
        return _sender_locks[lock_key]


# Cấu hình từ viết tắt tiếng Việt
VIETNAMESE_ALIASES = {
    "k": "khong", "ko": "khong", "kh": "khong", "hok": "khong", "hem": "khong", "hong": "khong",
    "dc": "duoc", "dk": "duoc", "sp": "san pham", "ib": "nhan tin", "nt": "nhan tin",
    "nhiu": "nhieu", "oplis": "oplus", "oplus": "oplus",
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
    "zeo_detergent_technology": [
        {"name": "Bột giặt ZeO", "category": "laundry", "intent": "zeo_detergent_technology"},
    ],
    "zeo_detergent_certification": [
        {"name": "Bột giặt ZeO", "category": "laundry", "intent": "zeo_detergent_certification"},
    ],
    "zeo_detergent_fragrance": [
        {"name": "Bột giặt ZeO", "category": "laundry", "intent": "zeo_detergent_fragrance"},
    ],
    "oplus_detergent_ion_technology": [
        {"name": "Bột giặt Oplus", "category": "laundry", "intent": "oplus_detergent_ion_technology"},
    ],
    "oplus_detergent_features": [
        {"name": "Bột giặt Oplus", "category": "laundry", "intent": "oplus_detergent_features"},
    ],
    "oplus_detergent_usp": [
        {"name": "Bột giặt Oplus", "category": "laundry", "intent": "oplus_detergent_usp"},
    ],
    "pano_laundry_fragrance_options": [
        {"name": "Bột giặt & Nước giặt PANO", "category": "laundry", "intent": "pano_laundry_fragrance_options"},
    ],
    "pano_veilex_odor_control": [
        {"name": "Bột giặt & Nước giặt PANO", "category": "laundry", "intent": "pano_veilex_odor_control"},
    ],
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
        {"name": "Tẩy Toilet ZeO", "category": "cleaning_hygiene", "intent": "zeo_toilet_cleaner"},
        {"name": "Tẩy màu ZeO", "category": "cleaning_hygiene", "intent": "zeo_color_bleach"},
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

TECH_CONTEXT_INTENTS = {
    "zeo_detergent": {
        "intents": ["zeo_detergent_technology", "zeo_detergent_certification", "zeo_detergent_fragrance"],
        "product_pattern": r"bot giat zeo|\bzeo\b",
        "technology_intent": "zeo_detergent_technology",
        "related_intents": ["zeo_detergent_technology", "zeo_detergent_certification", "zeo_detergent_fragrance", "oplus_detergent_ion_technology", "pano_veilex_odor_control"],
    },
    "oplus_detergent": {
        "intents": ["oplus_detergent_ion_technology", "oplus_detergent_features", "oplus_detergent_usp"],
        "product_pattern": r"bot giat oplus|\boplus\b",
        "technology_intent": "oplus_detergent_ion_technology",
        "related_intents": ["oplus_detergent_ion_technology", "oplus_detergent_features", "oplus_detergent_usp", "zeo_detergent_technology", "pano_veilex_odor_control"],
    },
    "pano_laundry": {
        "intents": ["pano_product_type", "pano_laundry_fragrance_options", "pano_veilex_odor_control"],
        "product_pattern": r"pano|nuoc giat pano|bot giat pano",
        "technology_intent": "pano_veilex_odor_control",
        "related_intents": ["pano_veilex_odor_control", "pano_laundry_fragrance_options", "pano_product_type", "zeo_detergent_technology"],
    },
}

PRODUCT_ENTITY_PATTERNS = [
    ("zeo_detergent_technology", "Bột giặt ZeO", "laundry", r"bot giat zeo|enzyme thuy dien"),
    ("pano_product_type", "Bột giặt & Nước giặt PANO", "laundry", r"bot giat pano|nuoc giat pano"),
    ("oplus_detergent_features", "Bột giặt Oplus", "laundry", r"bot giat oplus"),
    ("zeo_zif_dishwashing_liquid", "Nước rửa chén ZeO/ZIF", "dishwashing", r"\bzif\b|nuoc rua chen zeo|rua chen zeo"),
    ("pano_product_type", "PANO", "product_family", r"\bpano\b"),
    ("oplus_detergent_features", "Oplus", "product_family", r"\boplus\b"),
    ("zeo_laundry_product_overview", "Giặt giũ ZeO/PANO/Oplus", "laundry", r"giat giu|nuoc giat|bot giat|giat quan ao"),
    ("zeo_dishwashing_product_overview", "Rửa chén ZeO/ZIF/PANO/Oplus", "dishwashing", r"nuoc rua chen|rua chen|rua bat"),
    ("zeo_floor_cleaner_product_overview", "Lau sàn ZeO/Oplus", "floor_cleaner", r"nuoc lau san|lau san|lau nha|tay san|san nha|tay san nha|lau san nha"),
    ("zeo_toilet_cleaner", "Tẩy Toilet ZeO", "cleaning_hygiene", r"toilet|bon cau|tay toilet"),
    ("zeo_cleaning_hygiene_product_overview", "Tẩy rửa vệ sinh ZeO/PANO", "cleaning_hygiene", r"javen|ve sinh|lau kinh|xit tay|tay mau"),
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

    area = ""
    # Nếu là câu hỏi hỏi vị trí (mua ở đâu, địa chỉ ở đâu) -> Không phải cung cấp khu vực
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
        "covered_fact_ids": [],
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
    if not isinstance(state.get("covered_fact_ids"), list):
        state["covered_fact_ids"] = []
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
        r"\b(vua hoi|vua noi|hoi nay|luc nay|o tren|y la gia|y la|gia cua can|gia can|can to|can lon|tui to|tui lon)\b",
        r"\b(\d+[\s\.]*\d*\s*(?:kg|g|ml|lit|can|tui|chai)|can\s+\d+|tui\s+\d+|chai\s+\d+)\b",
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
    products = [
        _copy_product_item(item)
        for item in (conversation_state.get("last_products_shown") or [])
        if isinstance(item, dict) and item.get("name")
    ]
    active = conversation_state.get("active_entities") or {}

    if not _has_reference_signal(norm_text) or (not products and not active.get("product")):
        return {
            "references_previous_turn": False,
            "resolved": False,
            "product": "",
            "product_intent": "",
            "category": "",
            "resolved_query": raw_text,
            "reason": "no_reference",
        }
    idx = _ordinal_reference_index(norm_text)
    chosen: dict[str, str] = {}
    reason = "unresolved"

    if idx is not None and 0 <= idx < len(products):
        chosen = products[idx]
        reason = "ordinal"
    else:
        # Tìm theo biến thể / quy cách xuất hiện trong last_products_shown
        if products:
            for p in products:
                p_name_norm = _normalize_vn(p.get("name", ""))
                if any(_normalize_vn(term) in norm_text and _normalize_vn(term) in p_name_norm for term in ["3.8kg", "9kg", "5.5kg", "3.5kg", "2.4kg", "650ml", "400g", "720g", "vitamin e", "nha dam"]):
                    chosen = p
                    reason = "variant_match"
                    break
        if not chosen and active.get("product"):
            chosen = {
                "name": str(active.get("product", "")),
                "intent": str(active.get("product_intent", "")),
                "category": str(active.get("category", "")),
            }
            reason = "active_entity"
        elif not chosen and len(products) == 1:
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


def _detect_need_choice(norm_text: str) -> Optional[str]:
    """Nhận diện lựa chọn nhu cầu của khách hàng (tiết kiệm, thơm lâu, sạch sâu, dịu nhẹ)."""
    # Nếu câu hỏi dạng 'có ... không' (vd: có thơm lâu không, có sạch không) -> Factual FAQ, không phải chọn nhu cầu
    if re.search(r"\bco\s+.*\s+(khong|hong|ko|k)\b", norm_text):
        return None

    # Nếu là câu hỏi về sản phẩm cụ thể
    if any(p in norm_text for p in ["bot giat zeo", "bot giat oplus", "nuoc giat pano", "zif", "javen"]):
        return None

    # 1. Tiết kiệm
    if re.search(r"\b(nhu cau tiet kiem|tiet kiem|loai re|re nhat|gia re nhat|it tien|kinh te|re tien|tiet kiem tien|re hon|muon re|re nhat di)\b", norm_text):
        return "tiet_kiem"
    # 2. Thơm lâu
    if re.search(r"\b(nhu cau thom|thom lau|mui nuoc hoa|nuoc hoa|luu huong|thom nhat|mui thom|huong thom|thom nhat di)\b", norm_text):
        return "thom_lau"
    # 3. Sạch sâu
    if re.search(r"\b(nhu cau sach|sach sau|vet ban|vet ban cung dau|sach manh|tay sach|danh bay vet ban|sach sau di)\b", norm_text):
        return "sach_sau"
    # 4. Dịu nhẹ
    if re.search(r"\b(nhu cau diu|diu nhe|duong da|em be|da tay|da nhay cam|an toan cho da|khong hai da|diu nhe di)\b", norm_text):
        return "diu_nhe"
    return None


def _active_product_context_key(conversation_state: dict[str, Any], previous_intent: str = "") -> str:
    active = conversation_state.get("active_entities") or {}
    candidates = [
        str(active.get("product_intent", "")),
        previous_intent,
        str(active.get("product", "")),
    ]
    products = conversation_state.get("last_products_shown") or []
    if len(products) == 1 and isinstance(products[0], dict):
        candidates.extend([str(products[0].get("intent", "")), str(products[0].get("name", ""))])

    combined = _normalize_vn(" ".join(candidates))
    for context_key, spec in TECH_CONTEXT_INTENTS.items():
        if any(intent in candidates for intent in spec["intents"]):
            return context_key
        if re.search(spec["product_pattern"], combined):
            return context_key
    return ""


def _detect_contextual_technology_request(norm_text: str) -> bool:
    return _has_any(norm_text, [
        r"^(co )?cong nghe gi$",
        r"^(co )?cong nghe nao khac( khong| ko| hong)?$",
        r"^(con )?cong nghe nao( nua| khac)?( khong| ko| hong)?$",
        r"^cong nghe gi nua( khong| ko)?$",
    ])


def _detect_vague_more_followup(norm_text: str) -> bool:
    return _has_any(norm_text, [
        r"^(con gi nua|con gi nua khong|con gi nua ko|con gi nua hong|con nua khong|con nua hong|con nua ko|co gi nua|co gi nua khong|them gi nua|nua khong|nua ko)$",
        r"^(con.*khac.*khong|con.*khac.*ko|con.*khac.*hong)$",
        r"^(ngoai ra.*gi|ngoai.*cai.*do.*con.*gi)$",
    ])


async def _build_contextual_more_info_answer(
    brand: str,
    context_key: str,
    only_technology: bool = False,
    covered_facts: Optional[list[str]] = None,
) -> tuple[str, str, str]:
    """Tạo câu trả lời bổ sung thông tin, tự động loại trừ các fact đã trả lời trước đó."""
    if brand.lower() != "zeo" or context_key not in TECH_CONTEXT_INTENTS:
        return "", "", ""

    spec = TECH_CONTEXT_INTENTS[context_key]
    candidate_intents = spec["related_intents"] if not only_technology else [spec["technology_intent"], "oplus_detergent_ion_technology", "pano_veilex_odor_control"]
    covered_set = set(covered_facts or [])

    # Lọc ra các intent chưa được trả lời
    remaining_intents = [it for it in candidate_intents if it not in covered_set]
    if not remaining_intents:
        remaining_intents = [spec["technology_intent"]]

    chosen_intent = remaining_intents[0]
    # pyrefly: ignore [bad-argument-type]
    item = await get_faq_by_intent(brand, chosen_intent)
    answer = str(item.get("answer", "")).strip()
    if not answer:
        return "", "", ""

    product_name = {
        "zeo_detergent": "Bột giặt ZeO",
        "oplus_detergent": "Bột giặt Oplus",
        "pano_laundry": "Bột giặt & Nước giặt PANO",
    }.get(context_key, "sản phẩm này")

    if only_technology:
        msg = (
            f"Dạ với {product_name}, hiện hệ thống đang có thông tin công nghệ đã xác nhận là:\n\n"
            f"1. {answer}\n\n"
            f"Mình chưa thấy dữ liệu xác nhận công nghệ khác ngoài các thông tin trên, nên mình không tự bổ sung thêm nha."
        )
        # pyrefly: ignore [bad-return]
        return msg, "contextual_technology_more_info", chosen_intent

    msg = (
        f"Dạ với {product_name}, hiện hệ thống đang có các thông tin đã xác nhận:\n\n"
        f"1. {answer}\n\n"
        f"Bạn muốn mình kiểm tra tiếp giá, quy cách hay cách mua hàng cho sản phẩm này không ạ?"
    )
    # pyrefly: ignore [bad-return]
    return msg, "contextual_product_more_info", chosen_intent


def _product_memory_for_intent(intent: str, answer: str, brand: str) -> list[dict[str, str]]:
    products = []

    # 1. Bóc tách các sản phẩm cụ thể xuất hiện trong bot_reply (từ Shopee Catalog) - ƯU TIÊN CAO NHẤT
    bold_items = re.findall(r"\*\*(.+?)\*\*", answer)
    for b_item in bold_items:
        b_clean = b_item.strip()
        b_norm = _normalize_vn(b_clean)
        if len(b_clean) > 10 and any(k in b_norm for k in ["giat", "rua chen", "lau san", "tay", "javen", "zif", "pano", "zeo", "oplus"]):
            item = {"name": b_clean, "category": "shopee_product", "intent": intent}
            if item not in products:
                products.append(item)

    if products:
        return products[:8]

    if intent in PRODUCT_MEMORY_BY_INTENT:
        return [_copy_product_item(item) for item in PRODUCT_MEMORY_BY_INTENT[intent]]

    norm_answer = _normalize_vn(answer)
    if not norm_answer:
        return []

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

    # Cập nhật covered_fact_ids
    covered = state.get("covered_fact_ids") or []
    if source_id and source_id not in covered:
        covered.append(source_id)
    if intent and intent not in covered:
        covered.append(intent)
    state["covered_fact_ids"] = covered[-10:]

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
        r"(muon xem|xem ve|xem dong|cho.*xem|tim hieu|hoi ve|thong tin ve|tu van|can xem|gui.*thong tin|co.*gi|co.*loai nao|co.*cai nao|co.*dong nao|co.*dong phan|gom nhung gi|dong san pham|san pham nao|san pham gi|can mua|muon mua|mua cho|dung cho|quan an|nha hang|bep an|can lon|can to|\bco\b.*\b(khong|hong|ko|k)\b)",
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
        ("zeo_floor_cleaner_product_overview", r"(nuoc lau san|lau san|nuoc lau nha|lau nha|tay san|san nha|tay san nha|lau san nha)"),
        ("zeo_toilet_cleaner", r"(tay toilet|toilet|bon cau|nuoc tay bon cau)"),
        ("zeo_cleaning_hygiene_product_overview", r"(tay rua ve sinh|tay rua|ve sinh|javen|lau kinh|xit tay|tay mau|nha tam)"),
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
    # Nếu đang hỏi về danh mục các dòng sản phẩm -> Nhường cho Catalog Overview
    if re.search(r"(dong san pham|cac san pham|danh muc san pham|co san pham gi|nhung san pham)", norm_text):
        return None
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
        r"\b(cty|cong ty|shop) o dau\b",
        r"^dia chi o dau$",
        r"^dia chi cong ty o dau$",
        r"^dia chi cong ty\b",
    ]):
        return "company_address" if brand.lower() == "zeo" else "address"
    return None


def _detect_contact_intent(norm_text: str, brand: str) -> Optional[str]:
    if _has_any(norm_text, [
        r"^(so dien thoai|dien thoai|hotline|tong dai|lien he|sdt|sdt cong tu|sdt cong ty)$",
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
    if _has_any(norm_text, [
        r"^soan$",
        r"^viet cho (zeo|zeo vietnam|zeo viet nam|cfc|co bay|cfc co bay)$",
        r"^(viet|soan) (tin|bai|noi dung)$",
    ]):
        return True

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


def _detect_out_of_scope_personal_question(norm_text: str) -> bool:
    """Bắt các câu hỏi cá nhân, nhân sự nội bộ, hỏi về sếp, anh Thuận, ai làm ra bot."""
    return _has_any(norm_text, [
        r"\b(co biet|biet khong|biet ko|la ai|la nguoi nao)\b.{0,30}\b(anh|chi|em|ong|ba|ban|sep|chu tich|giam doc|thuan|tuan|nguyen|nam|duc)\b",
        r"\b(anh|chi|ong|ba)\s+(thuan|tuan|dung|hoa|nam|hung|duc|hien)\s+(la ai|la nguoi nao|o dau|lam gi)\b",
        r"\b(ai tao ra|ai lam ra|ai viet ra|ai sinh ra|ai lap trinh)\s+(bot|ban|em|chatbot|may)\b",
        r"\b(ten gi|bao nhieu tuoi|que o dau|co nguoi yeu chua|doc than khong|yeu ai|cuoi chua)\b",
    ])


def _detect_purchase_signal(norm_text: str) -> bool:
    return _has_any(norm_text, [
        r"\b(muon mua|can mua|dat hang|chot don|lay hang|lay \d+|mua \d+|cho minh \d+|cho toi \d+)\b",
        r"\b(mua|dat|lay)\s+(oplus|pano|zeo|zif|javen|nuoc giat|bot giat|nuoc rua chen|nuoc tay|lau san|toilet)\b",
    ])


def _detect_contextual_dosage_followup(norm_text: str, previous_intent: str) -> bool:
    if previous_intent not in {"zeo_usage_safety_review", "cfc_dosage_usage_review"}:
        return False
    return _has_any(norm_text, [
        r"^(vay|the|neu vay).{0,20}\d+\s*(bo|kg|lit|ml|cong|bao)",
        r"^\d+\s*(bo|kg|lit|ml|cong|bao).{0,30}(sao|duoc khong|duoc ko|thi sao)?$",
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
        r"(lieu luong|dung bao nhieu|bao nhieu ml|bao nhieu kg|may bo do|\d+\s*(bo|kg|lit|ml).{0,20}(bo do|bo|quan ao)|bao nhieu nuoc)",
        r"(uong duoc|vao mat|dinh vao mat|nuot phai|an phai)",
    ])


def _detect_specific_product_intent(norm_text: str, brand: str) -> Optional[str]:
    if brand.lower() == "cfc":
        if re.search(r"\bnpk\b", norm_text):
            return "cfc_npk_product_info"
        if re.search(r"(huu co|sinh hoc)", norm_text):
            return "cfc_organic_fertilizer_info"
        return None

    # 1. Enzyme / Công nghệ Thụy Điển
    if _has_any(norm_text, [r"\benzyme\b", r"thuy dien"]):
        return "zeo_detergent_technology"

    # 2. Tẩy Toilet (Ưu tiên trước general detergent)
    if _has_any(norm_text, [r"tay toilet", r"bon cau", r"nuoc tay bon cau", r"tay bon cau"]):
        return "zeo_toilet_cleaner"

    # 3. ZIF Rửa chén
    if re.search(r"\bzif\b", norm_text):
        return "zeo_zif_dishwashing_liquid"

    # 3.5. VEILEX Khử mùi
    if "veilex" in norm_text:
        return "pano_veilex_odor_control"

    # 4. PANO
    if "pano" in norm_text:
        if re.search(r"(rua chen|rua bat)", norm_text):
            return "pano_dishwashing_lemon_and_vitamin_e"
        if re.search(r"(mui|huong|mau|do xanh hong cam tim)", norm_text):
            return "pano_laundry_fragrance_options"
        if re.search(r"(veilex|khu mui)", norm_text):
            return "pano_veilex_odor_control"
        if re.search(r"(quy cach|tui|can|dong goi)", norm_text):
            return "pano_laundry_packaging_and_segment"
        if re.search(r"(nuoc giat|bot giat|giat)", norm_text):
            return "pano_product_type"
        return "pano_product_type"

    # 5. Oplus
    if "oplus" in norm_text:
        if re.search(r"(rua chen|rua bat)", norm_text):
            return "oplus_dishwashing_liquid"
        if re.search(r"(cong nghe|ion|trang sang)", norm_text):
            return "oplus_detergent_ion_technology"
        if re.search(r"(nuoc xa|xa vai)", norm_text):
            return "oplus_fabric_softener_unverified"
        if re.search(r"(bot giat|giat)", norm_text):
            return "oplus_detergent_features"

    # 6. Lau sàn / Tẩy sàn nhà
    if re.search(r"(lau san|nuoc lau nha|lau nha|tay san|tay san nha|san nha|lau san nha)", norm_text):
        return "zeo_floor_cleaner_product_overview"

    # 7. ZeO Bột giặt
    if re.search(r"(bot giat|nuoc giat).{0,20}\bzeo\b|\bzeo\b.{0,20}(bot giat|nuoc giat)", norm_text):
        if re.search(r"(chung nhan|pasteur|kiem dinh|kiem nghiem|giay to|chung minh)", norm_text):
            return "zeo_detergent_certification"
        if re.search(r"(mui|huong|thom)", norm_text):
            return "zeo_detergent_fragrance"
        return "zeo_detergent_technology"

    # 8. Tẩy màu / Javen
    if re.search(r"(tay mau|tay quan ao mau|ao trang bi o vang)", norm_text):
        return "zeo_color_bleach"
    if re.search(r"(javen|nuoc tay|thuoc tay|tay trang)", norm_text):
        return "zeo_javen_bleach"

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
    fallback_reason: Optional[str] = ""
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

    # Khóa theo sender_id để xử lý tuần tự (Tránh race condition ghi đè session)
    lock_key = f"{brand}:{sender_id}"
    sender_lock = await _get_sender_lock(lock_key)

    async with sender_lock:
        norm_text = _normalize_vn(raw_text)
        phone, area = _extract_phone_and_area(raw_text, norm_text)
        has_phone = bool(phone)

        # Đọc profile & session cũ từ Redis
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

        def _fast_response_remember(answer: str, intent: str, *, stage: str = "new", fallback_reason: str = "") -> ChatPipelineResponse:
            _remember_response(answer, intent, stage, fallback_reason=fallback_reason)
            return _fast_response(answer, intent, brand, start_time, lead_stage=stage, fallback_reason=fallback_reason)

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
        # FAST-PATH 1.5: CUSTOMER PROFILE RECALL (Cách ly 100% khỏi FAQ) (< 10ms)
        # ─────────────────────────────────────────────────────────────
        # Phải loại trừ trường hợp hỏi địa chỉ công ty hoặc hỏi mua ở đâu
        is_asking_company_address = _detect_address_intent(norm_text, brand) is not None
        is_asking_buy_online = bool(re.search(r"(mua|ban|dat).*(o dau|cho nao|tai dau)", norm_text))

        asks_saved_phone = not is_asking_company_address and not is_asking_buy_online and bool(
            re.search(r"(so dien thoai|dien thoai|sdt)\s+(cua\s+)?(toi|minh|em|anh|chi)\b", norm_text)
            or re.search(r"(ban|shop|ad|admin)\s+(con nho|nho|co luu|da luu)\s+(so dien thoai|dien thoai|sdt|so cua)\b", norm_text)
            or re.search(r"(toi|minh|em|anh|chi)\s+(da gui|co gui|gui roi)\s+(so dien thoai|dien thoai|sdt)\b", norm_text)
            or re.search(r"(shop|ban)\s+nho\s+so\s+toi\b", norm_text)
        )
        asks_saved_area = not is_asking_company_address and not is_asking_buy_online and bool(
            re.search(r"(dia chi|khu vuc|noi o|tinh thanh)\s+(cua\s+)?(toi|minh|em|anh|chi)\b", norm_text)
            or re.search(r"(ban|shop|ad|admin)\s+(con nho|nho|co luu|da luu)\s+(dia chi|khu vuc|noi o|tinh thanh|cho o)\b", norm_text)
            or re.search(r"(toi|minh|em|anh|chi)\s+(dang o dau|o tinh nao|o khu vuc nao)", norm_text)
        )
        asks_profile_recall = not is_asking_company_address and not is_asking_buy_online and bool(
            re.search(r"(thong tin|ho so)\s+(cua\s+)?(toi|minh|em|anh|chi)\b", norm_text)
            or re.search(r"(ban|shop|ad|admin)\s+(con nho|nho|co luu|da luu)\s+(toi|minh|em|anh|chi)\b", norm_text)
            or re.search(r"^ban con nho toi khong$", norm_text)
            or re.search(r"^shop con nho toi khong$", norm_text)
            or re.search(r"^toi ten gi$", norm_text)
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
                fallback_reason="PROFILE_RECALL",
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

        # ─────────────────────────────────────────────────────────────
        # FAST-PATH 2: CHÀO HỎI, CẢM ƠN, XÁC NHẬN (< 10ms)
        # ─────────────────────────────────────────────────────────────
        token_count = len(norm_text.split())
        # 0. Dấu chấm hỏi / thắc mắc ngắn dạng '???', 'là sao', 'sao vậy'
        if re.match(r"^[\?\!！？\s\.\,\…]+$", raw_text.strip()) or norm_text in ["la sao", "sao vay", "y la sao", "nghia la sao", "sao the"]:
            clarify_msg = "Dạ bạn cần bên mình giải thích rõ hơn phần nào hoặc cần tư vấn sản phẩm nào ạ? Bạn cứ nhắn chi tiết mình hỗ trợ ngay nha! 💙" if brand == "zeo" else "Dạ bạn cần Cò Bay tư vấn thêm thông tin nào ạ? Bạn cứ nhắn cho mình nha!"
            return _fast_response(clarify_msg, "clarification_request", brand, start_time)

        # 0.5. Từ chối / Không quan tâm / Thôi khỏi ('ko quan tam', 'ko can', 'ko can biet', 'thoi khoi')
        if re.search(r"\b(ko quan tam|khong quan tam|ko can|khong can|ko can biet|khong can biet|thoi khoi|thoi bo qua|khong can dau|khoi can)\b", norm_text):
            dismiss_msg = "Dạ vâng ạ! Nếu sau này bạn cần tìm hiểu thêm về sản phẩm hoặc cần hỗ trợ đặt hàng, bạn cứ nhắn tin lại cho bên mình bất kỳ lúc nào nhé! Chúc bạn một ngày tốt lành ạ! 💙" if brand == "zeo" else "Dạ vâng ạ! Khi nào cần tư vấn phân bón hoặc kỹ thuật canh tác, bạn cứ nhắn lại cho Cò Bay nha!"
            return _fast_response(dismiss_msg, "customer_dismiss_polite", brand, start_time)

        if token_count <= 6:
            # 1. Cảm ơn (Ưu tiên trước acknowledgement)
            if re.search(r"(cam on|thanks|thank you|da cam on|ok cam on|tks)\b", norm_text):
                thanks = "Dạ ZeO cảm ơn bạn đã quan tâm! Cần hỗ trợ thêm bạn cứ nhắn shop nha." if brand == "zeo" else "Dạ Cò Bay cảm ơn bạn! Chúc bạn một vụ mùa bội thu ạ."
                return _fast_response(thanks, "thanks", brand, start_time)

            # 2. Chào hỏi (Không bắt nhầm các câu 'shop có ship không', 'shop mở cửa lúc mấy giờ')
            is_pure_greeting = bool(re.search(r"^(xin chao|chao|hello|hi|alo|alo shop|alo co ai truc khong|shop oi|admin oi|ad oi)$|^shop$", norm_text)) or bool(
                re.search(r"^(xin chao|chao ban|hello|hi|alo)\b", norm_text)
                and not any(k in norm_text for k in ["ship", "mo cua", "gia", "san pham", "mua", "dia chi", "hotline", "website", "doi tra"])
            )
            if is_pure_greeting:
                greeting = "Dạ ZeO Vietnam chào bạn! Bạn đang cần tư vấn về nước giặt sinh học, nước rửa chén hay mua hàng ạ?" if brand == "zeo" else "Dạ phân bón Cò Bay (CFC) chào bạn! Bạn đang cần tư vấn phân bón cho cây lúa, cây ăn trái hay đại lý phân phối ạ?"
                return _fast_response(greeting, "greeting", brand, start_time)

            # 3. Xác nhận / Kết thúc hội thoại ('z ok', 'vay ok', 'da ok', 'ok nha', 'the thoi')
            if re.search(r"^(z ok|vay ok|da ok|ok nha|ok nhe|ok shop|oke shop|the thoi|the nha|vay dc roi|vay duoc roi|ok roi|ok|oke|okay|da|vang|uh|um|roi|duoc|biet roi|hieu roi)\b", norm_text) and not re.search(r"(cam on|thanks)", norm_text):
                ack = "Dạ vâng ạ! Bạn cần thêm thông tin gì cứ nhắn ZeO nhé." if brand == "zeo" else "Dạ vâng ạ! Khi nào cần phân bón chất lượng cao bạn cứ nhắn Cò Bay nha."
                return _fast_response(ack, "acknowledgement", brand, start_time)

            # 4. Phím nhánh hotline 02
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
                "nên mình xin từ chối trả lời ạ. "
                "Bạn cần xem sản phẩm, giá, giao hàng hay thông tin liên hệ bên mình không ạ?"
            )
            return _fast_response_remember(msg, "out_of_scope_general_question", stage=lead_stage, fallback_reason="OUT_OF_SCOPE")

        if _detect_out_of_scope_personal_question(norm_text):
            msg = (
                f"Dạ mình là trợ lý tư vấn tự động của {brand_display}, chuyên hỗ trợ thông tin sản phẩm, báo giá, khuyến mãi và đơn hàng ạ. "
                "Bạn cần mình hỗ trợ thông tin gì về sản phẩm hay dịch vụ bên mình không ạ? 💙"
            )
            return _fast_response(msg, "out_of_scope_personal_question", brand, start_time)

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

        if brand == "zeo" and _detect_purchase_signal(norm_text) and re.search(r"\boplus\b", norm_text) and not re.search(r"(bot giat|nuoc rua chen|rua chen|lau san)", norm_text):
            msg = (
                "Dạ mình hiểu bạn muốn mua Oplus. Hiện dữ liệu hệ thống có Bột giặt Oplus và Nước rửa chén Oplus. "
                "Bạn muốn mua loại nào, quy cách bao nhiêu, và khu vực giao hàng ở đâu để admin kiểm tra đúng đơn giúp mình nha?"
            )
            return _fast_response_remember(msg, "oplus_purchase_clarify", stage="collecting_contact")

        # ─────────────────────────────────────────────────────────────
        # SMART AI CS ROUTING: BUDGET, NEEDS, PRICING & SHOPEE
        # ─────────────────────────────────────────────────────────────
        is_return_or_claim = bool(re.search(r"\b(doi tra|tra hang|bi loi|bi hong|bao hanh|hoan tien|khieu nai)\b", norm_text))

        # 1. Tầm giá / Ngân sách (vd: dưới 100k, 50k-100k)
        if brand.lower() == "zeo" and is_budget_inquiry(raw_text) and not is_return_or_claim:
            budget_res = match_products_by_budget(raw_text, brand=brand)
            if budget_res:
                _remember_response(budget_res["suggested_reply"], budget_res.get("intent", "shopee_budget_filter"), "browsing_catalog")
                return ChatPipelineResponse(
                    answer=_prettify_answer(budget_res["suggested_reply"]),
                    intent=budget_res.get("intent", "shopee_budget_filter"),
                    confidence="high",
                    score=0.98,
                    brand=brand.upper(),
                    has_phone=has_phone,
                    phone=phone,
                    area=area,
                    lead_stage=lead_stage,
                    shopee_url=budget_res.get("shopee_url"),
                    latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
                )

        # 1.5. Tư vấn chuyên sâu ăn da tay / tróc da tay khi rửa chén
        if brand.lower() == "zeo" and is_skin_care_dishwashing_inquiry(raw_text) and not is_return_or_claim:
            skin_res = match_skin_care_dishwashing(raw_text, brand=brand)
            if skin_res:
                _remember_response(skin_res["suggested_reply"], skin_res.get("intent", "pano_dishwashing_features"), "browsing_catalog")
                return ChatPipelineResponse(
                    answer=_prettify_answer(skin_res["suggested_reply"]),
                    intent=skin_res.get("intent", "pano_dishwashing_features"),
                    confidence="high",
                    score=0.99,
                    brand=brand.upper(),
                    has_phone=has_phone,
                    phone=phone,
                    area=area,
                    lead_stage=lead_stage,
                    shopee_url=skin_res.get("shopee_url"),
                    latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
                )

        # 1.6. Báo giá sản phẩm đích danh có trong Shopee Catalog (kết hợp ngữ cảnh nếu hỏi tắt can/túi)
        if brand.lower() == "zeo" and not is_return_or_claim:
            resolved_text = reference_resolution.get("resolved_query", raw_text)
            specific_price_res = match_specific_product_price(resolved_text, brand=brand, context=conversation_state)
            if specific_price_res:
                _remember_response(specific_price_res["suggested_reply"], specific_price_res.get("intent", "specific_product_pricing"), "browsing_catalog")
                return ChatPipelineResponse(
                    answer=_prettify_answer(specific_price_res["suggested_reply"]),
                    intent=specific_price_res.get("intent", "specific_product_pricing"),
                    confidence="high",
                    score=0.99,
                    brand=brand.upper(),
                    has_phone=has_phone,
                    phone=phone,
                    area=area,
                    lead_stage=lead_stage,
                    shopee_url=specific_price_res.get("shopee_url"),
                    latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
                )

        # 1.7. Tư vấn can lớn / Quán ăn / Nhà hàng / Bếp ăn
        if brand.lower() == "zeo" and is_bulk_or_restaurant_inquiry(raw_text) and not is_return_or_claim:
            bulk_res = match_bulk_or_restaurant_need(raw_text, brand=brand)
            if bulk_res:
                _remember_response(bulk_res["suggested_reply"], bulk_res.get("intent", "pano_dishwashing_product_overview"), "browsing_catalog")
                return ChatPipelineResponse(
                    answer=_prettify_answer(bulk_res["suggested_reply"]),
                    intent=bulk_res.get("intent", "pano_dishwashing_product_overview"),
                    confidence="high",
                    score=0.99,
                    brand=brand.upper(),
                    has_phone=has_phone,
                    phone=phone,
                    area=area,
                    lead_stage=lead_stage,
                    shopee_url=bulk_res.get("shopee_url"),
                    latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
                )

        # 2. Tư vấn theo nhu cầu khách hàng (tiết kiệm, thơm lâu, sạch sâu, dịu nhẹ)
        need_type = _detect_need_choice(norm_text)
        if brand.lower() == "zeo" and need_type and not is_return_or_claim:
            need_res = match_need_preference(need_type, brand=brand)
            if need_res:
                _remember_response(need_res["suggested_reply"], need_res.get("intent", "need_consultation"), "browsing_catalog")
                return ChatPipelineResponse(
                    answer=_prettify_answer(need_res["suggested_reply"]),
                    intent=need_res.get("intent", "need_consultation"),
                    confidence="high",
                    score=0.98,
                    brand=brand.upper(),
                    has_phone=has_phone,
                    phone=phone,
                    area=area,
                    lead_stage=lead_stage,
                    shopee_url=need_res.get("shopee_url"),
                    latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
                )

        # 4. Bán chạy & Mới ra mắt (bao gồm lọc theo danh mục vd: nước rửa chén nào bán chạy)
        if brand.lower() == "zeo" and (is_bestseller_inquiry(raw_text) or is_new_arrival_inquiry(raw_text)) and not is_return_or_claim:
            if is_bestseller_inquiry(raw_text):
                bs_res = match_best_sellers(raw_text, brand=brand)
            else:
                bs_res = match_new_arrivals(raw_text, brand=brand)
            if bs_res:
                _remember_response(bs_res["suggested_reply"], bs_res.get("intent", "bestsellers"), "browsing_catalog")
                return ChatPipelineResponse(
                    answer=_prettify_answer(bs_res["suggested_reply"]),
                    intent=bs_res.get("intent", "bestsellers"),
                    confidence="high",
                    score=0.98,
                    brand=brand.upper(),
                    has_phone=has_phone,
                    phone=phone,
                    area=area,
                    lead_stage=lead_stage,
                    shopee_url=bs_res.get("shopee_url"),
                    latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
                )

        # 5. Shopee Link & Product Matcher
        shopee_match = None
        if is_shopee_inquiry(raw_text) and not is_return_or_claim:
            shopee_match = match_shopee_product(raw_text, brand=brand)
            if shopee_match:
                _remember_response(shopee_match["suggested_reply"], shopee_match.get("intent", "shopee_product_link"), "browsing_catalog")
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

        # Follow-up Technology & More info (Loại trừ fact đã trả lời trước đó)
        context_key = _active_product_context_key(conversation_state, previous_intent)
        covered_facts = conversation_state.get("covered_fact_ids") or []

        if context_key and _detect_contextual_technology_request(norm_text):
            msg, response_intent, source_intent = await _build_contextual_more_info_answer(
                brand,
                context_key,
                only_technology=True,
                covered_facts=covered_facts,
            )
            if msg:
                _remember_response(msg, response_intent, "browsing_catalog", source_id=source_intent)
                return _fast_response(msg, response_intent, brand, start_time, lead_stage="browsing_catalog")

        if context_key and _detect_vague_more_followup(norm_text):
            msg, response_intent, source_intent = await _build_contextual_more_info_answer(
                brand,
                context_key,
                only_technology=False,
                covered_facts=covered_facts,
            )
            if msg:
                _remember_response(msg, response_intent, "browsing_catalog", source_id=source_intent)
                return _fast_response(msg, response_intent, brand, start_time, lead_stage="browsing_catalog")

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
            if reference_resolution.get("resolved") and _has_price_signal(norm_text) and not any(k in norm_text for k in ["gia si", "mua si", "lay si", "chinh sach si", "chiet khau", "dai ly"]):
                msg = (
                    f"Dạ mình hiểu bạn đang hỏi giá của {resolved_product}. "
                    "Hiện hệ thống chưa có giá chính xác cho sản phẩm/nhóm này nên mình không tự báo giá để tránh sai. "
                    "Bạn gửi thêm quy cách cần mua hoặc số điện thoại/khu vực, admin sẽ kiểm tra báo giá đúng cho mình nha."
                )
                return _fast_response_remember(msg, "contextual_price_unverified", stage="browsing_catalog", fallback_reason="NO_KNOWLEDGE")

            if reference_resolution.get("resolved") and _looks_like_availability_request(norm_text):
                msg = (
                    f"Dạ mình hiểu bạn đang hỏi {resolved_product} còn hàng không. "
                    "Hiện hệ thống chat chưa có dữ liệu tồn kho realtime, nên mình chưa xác nhận chắc được. "
                    "Bạn để lại số điện thoại/khu vực hoặc nhắn quy cách cần mua, admin sẽ kiểm tra tồn kho chính xác giúp mình nha."
                )
                return _fast_response_remember(msg, "contextual_availability_unverified", stage="collecting_contact", fallback_reason="NO_KNOWLEDGE")

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
                return _fast_response_remember(msg, "context_reference_clarify", stage="browsing_catalog", fallback_reason="AMBIGUOUS_INTENT")

        if _detect_contextual_dosage_followup(norm_text, previous_intent) or _detect_usage_safety_gap(norm_text, brand):
            if brand == "cfc":
                usage_intent = "cfc_dosage_usage_review"
                return await _sheet_response_remember(usage_intent, stage="collecting_contact")
            msg = (
                "Dạ phần liều lượng/cách dùng hoặc tình huống an toàn cần kiểm tra theo đúng sản phẩm và hướng dẫn trên bao bì. "
                "Hiện hệ thống chưa có đủ dữ liệu để mình tự hướng dẫn chi tiết. Bạn gửi tên sản phẩm hoặc số điện thoại, admin sẽ tư vấn chính xác hơn nha."
            )
            return _fast_response_remember(msg, "zeo_usage_safety_review", stage="collecting_contact", fallback_reason="MISSING_SLOT")

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
        # PATH 3.6: HOTLINE, WEBSITE & PRICE INQUIRY (< 15ms)
        # ─────────────────────────────────────────────────────────────
        if re.search(r"(website|web site|trang web|link website|link web|xin link website|xin link web|co link website|co link web|zeo vn|zeo\.vn|cfc web|co bay web|cfccobay|cfc co bay)\b", norm_text):
            website_intent = "company_website" if brand.lower() == "zeo" else "cfc_company_website"
            return await _sheet_response_remember(website_intent, stage="browsing_catalog")

        if re.search(r"(gia(?: .{1,80})? bao nhieu|bao nhieu tien|bang gia|xin gia|gia ban|gia ca|nhieu tien|bao gia)\b", norm_text) and not any(k in norm_text for k in ["ship", "phi", "van chuyen", "cuoc"]):
            price_intent = "zeo_price_inquiry_general" if brand.lower() == "zeo" else "cfc_price_unverified"
            return await _sheet_response_remember(price_intent, stage="browsing_catalog")

        # ─────────────────────────────────────────────────────────────
        # PATH 3.7: WHOLESALE & DISTRIBUTOR INQUIRY (< 15ms)
        # ─────────────────────────────────────────────────────────────
        if re.search(r"(lay si|muon lam dai ly|dang ky dai ly|nhap hang|phan phoi|chinh sach si|nhap so luong lon|kinh doanh zeo|dai li|gia si|co gia si|mua si|lay gia si)\b", norm_text):
            wholesale_intent = "wholesale_inquiry" if brand.lower() == "zeo" else "wholesale_dealer"
            return await _sheet_response_remember(wholesale_intent, stage="collecting_contact")

        # ─────────────────────────────────────────────────────────────
        # PATH 3.7.5: PRODUCT GROUP VIEW INQUIRY (< 15ms)
        # ─────────────────────────────────────────────────────────────
        product_group_intent = _detect_product_group_intent(norm_text, brand)
        if product_group_intent and not (_has_price_signal(norm_text) or any(k in norm_text for k in ["ship", "giao hang", "phi", "doi tra", "bao hanh", "loi", "hong"])):
            return await _sheet_response_remember(product_group_intent, stage="browsing_catalog")

        # ─────────────────────────────────────────────────────────────
        # PATH 3.7.6: GENERAL SHIPPING & FREESHIP INQUIRY (< 15ms)
        # ─────────────────────────────────────────────────────────────
        if re.search(r"\b(shop co ship|co ship khong|co giao hang khong|ship tinh khong|co ship toan quoc|co freeship|freeship khong|phi ship bao nhieu|cuoc van chuyen|thoi gian giao hang)\b", norm_text) and not is_return_or_claim:
            if re.search(r"\b(freeship|phi ship|cuoc van chuyen|thoi gian giao)\b", norm_text):
                ship_intent = "shipping_time_and_fee" if brand.lower() == "zeo" else "cfc_delivery_time"
            else:
                ship_intent = "nationwide_shipping_no_cod" if brand.lower() == "zeo" else "shipping_methods"
            return await _sheet_response_remember(ship_intent, stage="browsing_catalog")

        # ─────────────────────────────────────────────────────────────
        # PATH 3.7.7: CORPORATE INVOICE & VAT SUPPORT (< 15ms)
        # ─────────────────────────────────────────────────────────────
        if re.search(r"\b(hoa don do|hoa don vat|xuat vat|xuat hoa don|vat khong|vat ko|hoa don tai chinh|mst|ma so thue)\b", norm_text):
            invoice_intent = "corporate_invoice_support"
            return await _sheet_response_remember(invoice_intent, stage="browsing_catalog")

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
            return _fast_response_remember(fallback_msg, "catalog_overview_unavailable", stage="browsing_catalog", fallback_reason="NO_KNOWLEDGE")

        # ─────────────────────────────────────────────────────────────
        # PATH 3.9: OPENING HOURS (< 15ms)
        # ─────────────────────────────────────────────────────────────
        if re.search(r"(mo cua|dong cua|may gio|gio mo cua|gio lam viec|cuoi tuan|mo cua luc|lam viec den may gio)\b", norm_text) and not (_has_price_signal(norm_text) or any(k in norm_text for k in ["phi", "doi tra"])):
            hours_intent = "shop_opening_hours" if brand.lower() == "zeo" else "opening_hours"
            return await _sheet_response_remember(hours_intent)

        # ─────────────────────────────────────────────────────────────
        # PATH 3.10: POLICY & FAST-PATHS (< 15ms)
        # ─────────────────────────────────────────────────────────────
        if re.search(r"(quy trinh doi tra|cac buoc doi tra|lam sao de doi tra)\b", norm_text):
            if brand.lower() == "zeo":
                return await _sheet_response_remember("return_process", stage="browsing_catalog")

        if re.search(r"(chinh sach doi tra|thoi han doi tra|doi tra nhu the nao|duoc doi tra khong|doi tra ap dung|kenh nao duoc doi tra)\b", norm_text):
            if brand.lower() == "zeo":
                return await _sheet_response_remember("return_policy_scope", stage="browsing_catalog")

        # ─────────────────────────────────────────────────────────────
        # PATH 5: HYBRID SEMANTIC SEARCH (IN-MEMORY LEXICAL + REDIS VECTOR) (< 5ms)
        # ─────────────────────────────────────────────────────────────
        rag_query = reference_resolution.get("resolved_query") if reference_resolution.get("resolved") else raw_text
        rag_result = await semantic_search(
            query=rag_query or raw_text,
            brand=brand,
            top_k=10,
            exclude_fact_ids=covered_facts,
        )
        best_score = rag_result.get("score", 0.0)
        intent = rag_result.get("intent", "general_faq")
        raw_answer = rag_result.get("answer", "")
        retrieval_method = rag_result.get("retrieval_method", "redis_vector_knn")

        # ─────────────────────────────────────────────────────────────
        # PATH 6: SEMANTIC ANCHOR GUARDRAILS (Chống Bắt Nhầm Lạc Đề)
        # ─────────────────────────────────────────────────────────────
        def _check_intent_guardrails(target_intent: str, query_norm: str) -> bool:
            """Kiểm tra từ khóa neo bắt buộc để tránh gán nhầm câu hỏi không liên quan."""
            # Ship hỏa tốc 2 giờ / express chưa được verify
            if "shipping" in target_intent and any(k in query_norm for k in ["hoa toc", "2 gio", "2h", "express"]):
                return False
            # 1. Đổi trả / Bảo hành
            if "return" in target_intent or "policy" in target_intent or "warranty" in target_intent:
                return any(k in query_norm for k in ["doi", "tra", "loi", "hong", "bao hanh", "hoan tien", "rach"])
            # 2. Thanh toán / Chuyển khoản
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
            # 6. Đặt hàng trực tiếp
            if "order_request" in target_intent:
                return any(k in query_norm for k in ["dat hang", "chot don", "lay 1", "lay 2", "lay 3", "mua 1", "mua 2", "mua 3", "cho 1", "cho 2", "cho minh 1", "cho minh 2", "toi muon 2kg", "toi muon mua 2kg"])
            # 7. Thông tin liên hệ / Hotline
            if "contact" in target_intent or "hotline" in target_intent:
                return any(k in query_norm for k in ["hotline", "so dien thoai", "lien he", "tong dai", "sdt", "call"])
            # 8. Tẩy Toilet / Bồn cầu
            if target_intent == "zeo_toilet_cleaner":
                return any(k in query_norm for k in ["toilet", "bon cau", "be phot", "men su", "wc", "con vit"])
            # 9. Lau Kính
            if target_intent == "zeo_glass_cleaner":
                return any(k in query_norm for k in ["kinh", "guong", "man hinh"])
            # 10. Lau Sàn
            if target_intent == "zeo_floor_cleaner_product_overview":
                return any(k in query_norm for k in ["lau san", "tay san", "san nha", "lau nha"])
            if "tiktok" in target_intent or "zalo" in target_intent:
                return _is_internal_content_request(query_norm)
            return True

        is_guardrail_passed = _check_intent_guardrails(intent, norm_text)

        # ─────────────────────────────────────────────────────────────
        # PATH 7: TIERED RESPONSE SELECTION
        # ─────────────────────────────────────────────────────────────
        confidence = "low"
        final_answer = ""
        fallback_reason = ""

        if best_score >= 0.65 and is_guardrail_passed:
            confidence = "high"
            final_answer = raw_answer
        elif best_score >= 0.50 and is_guardrail_passed:
            confidence = "medium"
            final_answer = raw_answer
        else:
            confidence = "low"
            brand_display = "ZeO Vietnam" if brand.lower() == "zeo" else "CFC Cò Bay"

            purchase_signal = _has_price_signal(norm_text) or bool(
                re.search(r"(^|\s)(mua|dat|chai|lit|kg)(\s|$)", norm_text)
                or re.search(r"(bao phan|\d+\s*bao)", norm_text)
            )

            # Nếu khách đã nói rõ nhóm ngành sản phẩm (nước rửa chén, giặt giũ...) thì ưu tiên trả về danh mục nhóm đó
            detected_group = _detect_product_group_intent(norm_text, brand)
            if detected_group:
                group_item = await get_faq_by_intent(brand, detected_group)
                if group_item.get("answer"):
                    final_answer = group_item["answer"].strip()
                    intent = detected_group
                    confidence = "medium"
            elif purchase_signal and not any(w in norm_text for w in ["co nhung", "cac san pham", "san pham nao", "dong san pham", "gioi thieu"]):
                fallback_intent = "zeo_price_request_needs_product" if brand.lower() == "zeo" else "cfc_price_unverified"
                fallback_item = await get_faq_by_intent(brand, fallback_intent)
                final_answer = fallback_item.get("answer", "").strip() or (
                    f"Dạ hiện dữ liệu chưa đủ để báo chính xác. Bạn nhắn rõ tên sản phẩm và nhu cầu cụ thể, "
                    f"hoặc gửi số điện thoại/khu vực để admin {brand_display} kiểm tra và phản hồi nha."
                )
                lead_stage = "browsing_catalog"
                fallback_reason = "MISSING_ENTITY"
            elif any(w in norm_text for w in ["dai ly", "si", "nhap", "hop tac", "npp", "phan phoi"]):
                fallback_intent = "wholesale_inquiry" if brand.lower() == "zeo" else "wholesale_dealer"
                fallback_item = await get_faq_by_intent(brand, fallback_intent)
                final_answer = fallback_item.get("answer", "").strip() or (
                    f"Dạ bạn gửi giúp mình số điện thoại và khu vực dự kiến kinh doanh. "
                    f"Admin {brand_display} sẽ kiểm tra thông tin phù hợp và phản hồi chính xác nha."
                )
                lead_stage = "collecting_contact"
                fallback_reason = "MISSING_SLOT"
            else:
                final_answer = (
                    f"Dạ câu hỏi này mình chưa có sẵn thông tin chính xác trong hệ thống. "
                    f"Bạn có thể nói rõ hơn nhu cầu (như mua hàng, xem sản phẩm hay cần hỗ trợ đơn hàng) để mình hỗ trợ đúng trọng tâm nhé ạ! "
                    f"Hoặc bạn để lại số điện thoại để admin liên hệ giải đáp cho mình nha."
                )
                lead_stage = "collecting_contact"
                fallback_reason = "NO_KNOWLEDGE"

            asyncio.create_task(notify_admin_unanswered(brand=brand, query=raw_text, sender_id=sender_id, score=best_score))

        # ─────────────────────────────────────────────────────────────
        # ASYNC SAVE SESSION & CHAT HISTORY
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
            "retrieval_method": retrieval_method,
            "fallback_reason": fallback_reason,
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
            fallback_reason=fallback_reason,
            latency_ms=elapsed_ms,
        )


def _fast_response(answer: str, intent: str, brand: str, start_time: float, lead_stage: str = "new", fallback_reason: str = "") -> ChatPipelineResponse:
    return ChatPipelineResponse(
        answer=_prettify_answer(answer),
        intent=intent,
        confidence="high",
        score=1.0,
        brand=brand.upper(),
        lead_stage=lead_stage,
        fallback_reason=fallback_reason,
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
            # pyrefly: ignore [no-matching-overload]
            session_data.update({
                "conversation_state": conversation_state,
                "current_product": active_entities.get("product", ""),
                "current_category": active_entities.get("category", ""),
                "last_products_shown": conversation_state.get("last_products_shown", []),
                "covered_fact_ids": conversation_state.get("covered_fact_ids", []),
                "conversation_summary": conversation_state.get("conversation_summary", ""),
                "last_source_id": conversation_state.get("last_source_id", ""),
            })
        if trace:
            # pyrefly: ignore [bad-assignment]
            session_data["last_trace"] = trace
        await r.set(session_key, json.dumps(session_data, ensure_ascii=False))

        msg_record = json.dumps({
            "user_message": user_message,
            "bot_reply": bot_reply,
            "intent": intent,
            "trace": trace or {},
            "timestamp": now_str,
        }, ensure_ascii=False)
        # pyrefly: ignore [not-async]
        await r.rpush(history_key, msg_record)
        # pyrefly: ignore [not-async]
        await r.ltrim(history_key, -50, -1)
    except Exception as e:
        logger.warning("Error in _async_save_session: %s", e)
