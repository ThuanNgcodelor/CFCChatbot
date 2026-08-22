"""
query_understanding.py — Deterministic Vietnamese QueryPlan for chatbot routing.

Module này chỉ hiểu câu hỏi và tạo kế hoạch truy xuất. Nó không tạo fact,
không báo giá, không quyết định link/tồn kho. Mọi fact vẫn phải lấy từ
Sheet/Redis/catalog/RAG ở các lớp phía sau.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Optional


@dataclass
class QueryPlan:
    original_query: str
    normalized_query: str
    brand: str
    intent: str = "unknown"
    intent_confidence: float = 0.0
    entities: dict[str, Any] = field(default_factory=dict)
    references: dict[str, Any] = field(default_factory=dict)
    attributes: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    needs_context: bool = False
    needs_retrieval: bool = True
    needs_product_tool: bool = False
    rewritten_query: str = ""
    ambiguity_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _ordinal_index(text: str) -> Optional[int]:
    patterns = [
        (1, r"\b(cai|loai|san pham|sp|muc|so|nhom)?\s*(dau tien|thu nhat|so 1|1)\b"),
        (2, r"\b(cai|loai|san pham|sp|muc|so|nhom)?\s*(thu hai|so 2|2)\b"),
        (3, r"\b(cai|loai|san pham|sp|muc|so|nhom)?\s*(thu ba|so 3|3)\b"),
        (4, r"\b(cai|loai|san pham|sp|muc|so|nhom)?\s*(thu tu|so 4|4)\b"),
        (5, r"\b(cai|loai|san pham|sp|muc|so|nhom)?\s*(thu nam|so 5|5)\b"),
    ]
    for idx, pattern in patterns:
        if re.search(pattern, text):
            return idx
    return None


def _detect_attributes(text: str) -> list[str]:
    attrs: list[str] = []
    if re.search(r"\b(gia|bao nhieu|bao nhieu tien|nhiu|mac nhat|dat nhat|re nhat|duoi|tren|tam|khoang|gan)\b", text):
        attrs.append("price")
    if re.search(r"\b(link|shopee|mua online|dat mua|gian hang)\b", text):
        attrs.append("link")
    if re.search(r"\b(con hang|co san|ton kho|het hang|con khong|con ko)\b", text):
        attrs.append("availability")
    if re.search(r"\b(cach dung|huong dan|su dung|dung sao|dung nhu the nao|lieu luong)\b", text):
        attrs.append("usage")
    if re.search(r"\b(thom|mui|huong|luu huong)\b", text):
        attrs.append("fragrance")
    if re.search(r"\b(an da|hai da|troc da|di ung|da nhay cam|em be|tre nho|so sinh)\b", text):
        attrs.append("safety")
    if re.search(r"\b(cua truoc|cua ngang|it bot|trao bot|may giat)\b", text):
        attrs.append("compatibility")
    if re.search(r"\b(doi tra|tra hang|hoan tien|bao hanh|khieu nai|loi hang)\b", text):
        attrs.append("policy")
    return _unique(attrs)


def _detect_entities(text: str, query_entities: Optional[dict[str, Any]]) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    if query_entities:
        for key in ("product", "product_intent", "category"):
            value = query_entities.get(key)
            if value:
                entities[key] = value

    category_terms = {
        "dishwashing": ["rua chen", "rua bat", "chen dia", "zif"],
        "laundry": ["giat", "bot giat", "nuoc giat", "xa vai", "quan ao"],
        "floor_cleaner": ["lau san", "tay san", "san nha", "lau nha"],
        "toilet_cleaner": ["bon cau", "toilet", "wc", "men su", "can voi", "o vang nha tam"],
        "bleach": ["javen", "nuoc tay", "tay quan ao"],
    }
    for category, terms in category_terms.items():
        if _has_any(text, terms):
            entities.setdefault("category", category)
            break

    brands = [b for b in ["zeo", "pano", "oplus", "zif", "cfc", "co bay"] if b in text]
    if brands:
        entities["mentioned_brands"] = brands

    variant_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(kg|g|gram|lit|l|ml)\b", text)
    if variant_match:
        entities["variant"] = variant_match.group(0)

    return entities


def _detect_intent(text: str, attrs: list[str], entities: dict[str, Any], brand: str) -> tuple[str, float]:
    mentioned = set(entities.get("mentioned_brands", []))
    if {"zeo", "pano", "oplus"}.issubset(mentioned) and re.search(r"\b(khac nhau|hay sao|la sao|cung|thuoc|hang|thuong hieu)\b", text):
        return "brand_ecosystem_overview", 0.90
    if _has_any(text, ["tra hang", "doi tra", "hoan tien", "khieu nai"]):
        return "return_policy_or_claim", 0.92
    if re.search(r"\b(thong tin khach hang|khach hang .* la ai|so dien thoai .* cua)\b", text):
        return "privacy_sensitive_lookup", 0.95
    if _has_any(text, ["bon cau", "toilet", "wc", "men su", "can voi"]) and _has_any(text, ["o vang", "vet o", "tay", "can voi", "sach"]):
        return "cleaning_toilet_stain", 0.93
    if "compatibility" in attrs:
        return "product_compatibility", 0.86
    if len([a for a in attrs if a in {"price", "link", "availability"}]) >= 2:
        return "multi_attribute_product_query", 0.86
    if "price" in attrs:
        if _has_any(text, ["mac nhat", "dat nhat", "cao nhat", "gia chat nhat"]):
            return "price_extreme", 0.92
        return "product_price_query", 0.86
    if "link" in attrs:
        return "product_link_query", 0.84
    if "availability" in attrs:
        return "product_availability_query", 0.84
    if "fragrance" in attrs:
        return "product_fragrance_need", 0.82
    if "safety" in attrs:
        return "product_safety_need", 0.80
    if entities.get("category") or entities.get("product") or entities.get("product_intent"):
        return "product_information_query", 0.72
    if brand == "cfc" and _has_any(text, ["lua", "cay", "phan bon", "npk"]):
        return "agriculture_advisory_query", 0.72
    return "unknown", 0.35


def _build_rewritten_query(original: str, entities: dict[str, Any], references: dict[str, Any], attrs: list[str]) -> str:
    parts: list[str] = []
    product = references.get("product") or entities.get("product") or ""
    if product:
        parts.append(str(product))
    category = entities.get("category") or references.get("category") or ""
    if category and category not in parts:
        parts.append(str(category))
    variant = entities.get("variant")
    if variant:
        parts.append(str(variant))
    parts.extend(attrs)
    return " ".join(parts).strip() or original


def build_query_plan(
    *,
    raw_text: str,
    norm_text: str,
    brand: str,
    query_entities: Optional[dict[str, Any]] = None,
    reference_resolution: Optional[dict[str, Any]] = None,
    conversation_state: Optional[dict[str, Any]] = None,
) -> QueryPlan:
    """Build a fact-free QueryPlan used for routing, tracing and tests."""
    reference_resolution = reference_resolution or {}
    conversation_state = conversation_state or {}
    attrs = _detect_attributes(norm_text)
    entities = _detect_entities(norm_text, query_entities)

    references: dict[str, Any] = {
        "mentions_previous_turn": bool(
            reference_resolution.get("references_previous_turn")
            or re.search(r"\b(cai nay|cai do|san pham do|loai do|loai nay|no|cai kia|muc do|cai dau tien|cai thu|so \d)\b", norm_text)
        ),
        "resolved": bool(reference_resolution.get("resolved")),
    }
    ordinal = _ordinal_index(norm_text)
    if ordinal:
        references["ordinal"] = ordinal
    for key in ("product", "product_intent", "category", "product_id", "shopee_url", "price"):
        if reference_resolution.get(key):
            references[key] = reference_resolution[key]

    intent, confidence = _detect_intent(norm_text, attrs, entities, brand.lower())
    needs_context = bool(references.get("mentions_previous_turn") and not references.get("resolved"))
    needs_product_tool = bool(
        brand.lower() == "zeo"
        and (
            intent in {
                "product_price_query",
                "price_extreme",
                "product_link_query",
                "product_availability_query",
                "multi_attribute_product_query",
                "product_fragrance_need",
                "product_safety_need",
                "product_compatibility",
            }
            or entities.get("category") in {"dishwashing", "laundry", "floor_cleaner", "toilet_cleaner", "bleach"}
        )
    )

    plan = QueryPlan(
        original_query=raw_text,
        normalized_query=norm_text,
        brand=brand.lower(),
        intent=intent,
        intent_confidence=confidence,
        entities=entities,
        references=references,
        attributes=attrs,
        constraints={},
        needs_context=needs_context,
        needs_retrieval=not needs_product_tool or intent in {"unknown", "return_policy_or_claim", "agriculture_advisory_query"},
        needs_product_tool=needs_product_tool,
        rewritten_query=_build_rewritten_query(raw_text, entities, references, attrs),
        ambiguity_reason="UNRESOLVED_REFERENCE" if needs_context else "",
    )
    return plan
