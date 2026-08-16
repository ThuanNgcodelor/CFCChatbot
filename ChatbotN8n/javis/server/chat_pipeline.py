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
from typing import Optional, Tuple

import redis.asyncio as aioredis
from pydantic import BaseModel

from rag_search import get_redis, semantic_search
from shopee_matcher import match_shopee_product, is_shopee_inquiry
from telegram_notifier import notify_new_lead, notify_admin_unanswered

logger = logging.getLogger(__name__)

# Cấu hình từ viết tắt tiếng Việt
VIETNAMESE_ALIASES = {
    "k": "khong", "ko": "khong", "kh": "khong", "hok": "khong", "hem": "khong", "hong": "khong",
    "dc": "duoc", "dk": "duoc", "sp": "san pham", "ib": "nhan tin", "nt": "nhan tin",
    "bn": "ban", "mn": "minh", "ship": "giao hang", "cty": "cong ty",
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


async def process_chat_pipeline(req: ChatPipelineRequest) -> ChatPipelineResponse:
    start_time = time.perf_counter()
    brand = req.brand.lower()
    raw_text = (req.text or "").strip()
    sender_id = req.sender_id.strip()
    fb_name = (req.fb_name or "").strip()
    
    if not raw_text:
        return ChatPipelineResponse(
            answer="Dạ bạn cần bên mình hỗ trợ thông tin gì ạ?",
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
            answer=final_reply,
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
            answer=final_reply,
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
    # PATH 3.5: PROMOTIONS, DEALS & VOUCHERS (< 15ms)
    # ─────────────────────────────────────────────────────────────
    from shopee_matcher import is_promotion_inquiry, match_promotions_and_deals
    if is_promotion_inquiry(raw_text):
        promo_res = match_promotions_and_deals(raw_text, brand=brand)
        if promo_res:
            return ChatPipelineResponse(
                answer=promo_res["suggested_reply"],
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
    if re.search(r"(website|web site|trang web|link website|link web|xin link website|xin link web|co link website|co link web|zeo vn|zeo\.vn)\b", norm_text):
        if brand.lower() == "zeo":
            website_msg = (
                "Dạ website chính thức của ZeO Vietnam là:\n\n"
                "👉 https://zeo.vn/\n\n"
                "Bạn có thể vào website để xem thông tin thương hiệu và sản phẩm chính thức nha."
            )
        else:
            website_msg = (
                "Dạ website chính thức của CFC Cò Bay là:\n\n"
                "👉 https://cfccobay.com\n\n"
                "Bạn có thể vào website để xem thông tin thương hiệu và sản phẩm chính thức nha."
            )
        return _fast_response(website_msg, "company_website", brand, start_time)

    if re.search(r"(hotline|so dien thoai cong ty|tong dai|so hotline|lien he so nao)\b", norm_text):
        hotline_msg = (
            "Dạ hotline hỗ trợ chính thức của ZeO Vietnam là:\n\n"
            "📞 **1900 5307** (Chọn phím nhánh số 02)\n"
            "📞 Hotline CSKH: **0907 902 546** (Hỗ trợ từ 8:00 đến 21:00 mỗi ngày)\n\n"
            "Bạn có thể gọi trực tiếp hoặc nhắn tin tại đây để được hỗ trợ nhanh nhất nhé ạ! 💙"
        )
        return _fast_response(hotline_msg, "company_contact_information", brand, start_time)

    if re.search(r"(gia bao nhieu|bao nhieu tien|bang gia|xin gia|gia ban|gia ca|nhieu tien|bao gia)\b", norm_text) and not any(k in norm_text for k in ["ship", "phi", "van chuyen", "cuoc"]):
        if brand.lower() == "zeo":
            price_msg = (
                "Dạ hiện tại giá bán lẻ chi tiết của từng sản phẩm cùng các mã giảm giá được niêm yết trực tiếp trên gian hàng chính thức Shopee Mall:\n\n"
                "👉 https://shopee.vn/zeovietnamofficial\n\n"
                "Bạn có thể vào link trên để xem giá ưu đãi và đặt hàng giao tận nơi. Nếu bạn cần báo giá sỉ hoặc mua số lượng lớn, bạn gửi giúp mình Số Điện Thoại và Khu Vực để nhân viên kinh doanh liên hệ báo giá tốt nhất nhé ạ! 💙"
            )
        else:
            price_msg = (
                "Dạ giá các dòng phân bón CFC Cò Bay Cần Thơ tùy thuộc vào quy cách (Can 5L, Bao 25kg, Bao 50kg) và số lượng đặt hàng. "
                "Bạn gửi giúp mình Số Điện Thoại và Cây Trồng cần bón để kỹ sư Cò Bay báo giá tốt nhất cho mình nhé ạ!"
            )
        return _fast_response(price_msg, "zeo_price_inquiry_general", brand, start_time, lead_stage="browsing_catalog")

    # ─────────────────────────────────────────────────────────────
    # PATH 3.7: WHOLESALE & DISTRIBUTOR INQUIRY (< 15ms)
    # ─────────────────────────────────────────────────────────────
    if re.search(r"(lay si|muon lam dai ly|dang ky dai ly|nhap hang|phan phoi|chinh sach si|nhap so luong lon|kinh doanh zeo|dai li)\b", norm_text):
        wholesale_msg = (
            "Dạ bạn vui lòng để lại **Số Điện Thoại** và **Khu Vực** muốn kinh doanh nhé. "
            "Admin sẽ chuyển thông tin đến nhà phân phối hoặc nhân viên phụ trách khu vực để liên hệ gửi bảng giá sỉ và điều kiện hợp tác sớm nhất ạ! 💙"
        )
        return _fast_response(wholesale_msg, "wholesale_inquiry", brand, start_time, lead_stage="collecting_contact")

    # ─────────────────────────────────────────────────────────────
    # PATH 3.8: GENERAL CATALOG OVERVIEW INQUIRY (< 15ms)
    # ─────────────────────────────────────────────────────────────
    if re.search(r"(cac san pham|nhung san pham|danh muc san pham|co san pham gi|co san pham nao|san pham nao|co nhung gi|co nhung loai nao|cac dong san pham|dong san pham nao|dong san pham|co dong nao|co nhom nao|gioi thieu san pham|hoi ve cac san pham|ban nhung gi|nhom san pham|mat hang nao)", norm_text):
        if brand.lower() == "zeo":
            catalog_reply = (
                "Dạ ZeO Vietnam hiện có 4 nhóm sản phẩm chăm sóc gia đình chính:\n\n"
                "1. 🧺 **Giặt giũ:** Bột giặt & Nước giặt sinh học ZeO, PANO (Nâng niu cảm xúc), Oplus (Công nghệ ION tẩy trắng).\n"
                "2. 🍽️ **Rửa chén:** Nước rửa chén ZeO/ZIF 100% nước cốt chanh, PANO Chanh, PANO Vitamin E dưỡng da tay, Oplus.\n"
                "3. 🌿 **Lau sàn:** Nước lau sàn sinh học ZeO & Oplus đậm đặc 2X (Hương Quế, Y Lan, Bạc Hà, Sả Chanh, Baby).\n"
                "4. 🧼 **Tẩy rửa vệ sinh:** Javen ZeO, Tẩy Toilet diệt khuẩn 99.9%, Tẩy màu ZeO, Lau kính ZeO & Xịt tẩy đa năng PANO.\n\n"
                "👉 Bạn đang quan tâm nhóm sản phẩm nào để mình gửi thông tin và ưu đãi chi tiết nha! 💙"
            )
        else:
            catalog_reply = (
                "Dạ Phân bón CFC Cò Bay Cần Thơ có các dòng sản phẩm chính phục vụ nông nghiệp:\n\n"
                "1. 🌾 **Dinh dưỡng cây trồng cao cấp CFC Cò Bay** (Can 5L)\n"
                "2. 🌱 **Phân bón hữu cơ sinh học CFC Cò Bay Cần Thơ** (Bao 25kg)\n"
                "3. 🌿 **Phân bón NPK chuyên dùng cho lúa, cây ăn trái và rau màu**\n\n"
                "👉 Bạn đang cần tư vấn phân bón cho loại cây trồng nào để kỹ sư nông nghiệp bên mình hỗ trợ chi tiết ạ!"
            )
        return _fast_response(catalog_reply, "catalog_overview", brand, start_time, lead_stage="browsing_catalog")

    # ─────────────────────────────────────────────────────────────
    # PATH 3.9: OPENING HOURS (< 15ms)
    # ─────────────────────────────────────────────────────────────
    if re.search(r"(mo cua|dong cua|may gio|gio mo cua|gio lam viec|cuoi tuan|mo cua luc|lam viec den may gio)\b", norm_text) and not any(k in norm_text for k in ["gia", "ship", "phi", "doi tra"]):
        hours_msg = "Dạ shop mở cửa từ 8:00 đến 21:00 mỗi ngày nha bạn. Bạn cần hỗ trợ gì cứ nhắn tin cho shop nhé! 💙"
        return _fast_response(hours_msg, "shop_opening_hours", brand, start_time)

    # ─────────────────────────────────────────────────────────────
    # PATH 3.10: PANO FRAGRANCES & TECH FAST-PATH (< 15ms)
    # ─────────────────────────────────────────────────────────────
    if re.search(r"(mui huong|huong gi|may mau|do xanh hong cam tim|chon huong|tuy chon huong)\b", norm_text) and "pano" in norm_text:
        pano_frag_msg = "Dạ bột giặt và nước giặt PANO có nhiều tùy chọn hương được nhận diện theo các màu Đỏ, Xanh, Hồng, Cam và Tím, phù hợp với sở thích của từng gia đình nha bạn."
        return _fast_response(pano_frag_msg, "pano_laundry_fragrance_options", brand, start_time)

    if re.search(r"(enzyme|thuy dien|cong nghe gi|cong nghe lam sach|tay vet ban|diet khuan)\b", norm_text) and any(k in norm_text for k in ["zeo", "bot giat", "nuoc giat"]):
        tech_msg = "Dạ bột giặt và nước giặt ZeO sử dụng Enzyme Thụy Điển, giúp tẩy sạch sâu các vết bẩn cứng đầu như dầu mỡ, bùn đất và mồ hôi, kể cả khi giặt bằng nước lạnh nha bạn."
        return _fast_response(tech_msg, "zeo_detergent_technology", brand, start_time)

    if re.search(r"(chinh sach doi tra|quy trinh doi tra|thoi han doi tra|doi tra nhu the nao|duoc doi tra khong|doi tra ap dung|kenh nao duoc doi tra)\b", norm_text):
        policy_msg = "Dạ chính sách đổi trả áp dụng cho các sản phẩm PANO, ZeO và Oplus được bán qua cửa hàng đại lý, TikTok Shop, Shopee, Tiki và kênh phân phối trực tiếp của Công ty nha bạn. Thời hạn tiếp nhận đổi trả là trong vòng 7 ngày làm việc ạ."
        return _fast_response(policy_msg, "return_policy_scope", brand, start_time)

    # ─────────────────────────────────────────────────────────────
    # PATH 4: SHOPEE LINK & PRODUCT MATCHER (< 20ms)
    # ─────────────────────────────────────────────────────────────
    shopee_match = None
    # Nếu câu hỏi có từ khóa đổi trả -> Nhường cho Policy RAG
    if is_shopee_inquiry(raw_text) and not any(k in norm_text for k in ["doi", "tra", "loi", "hong", "bao hanh"]):
        shopee_match = match_shopee_product(raw_text, brand=brand)
        if shopee_match:
            return ChatPipelineResponse(
                answer=shopee_match["suggested_reply"],
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
    rag_result = await semantic_search(query=raw_text, brand=brand, top_k=5)
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
            return any(k in query_norm for k in ["dia chi", "o dau", "cong ty", "nha may", "tru so", "van phong", "tai dau"])
        # 5. Đại lý sỉ
        if "wholesale" in target_intent or "dealer" in target_intent:
            return any(k in query_norm for k in ["si", "dai ly", "nhap hang", "phan phoi", "so luong lon", "hop tac"])
        # 6. Đặt hàng trực tiếp (order_request) - Bắt buộc phải có hành động đặt mua cụ thể
        if "order_request" in target_intent:
            return any(k in query_norm for k in ["dat hang", "chot don", "lay 1", "lay 2", "lay 3", "mua 1", "mua 2", "mua 3", "cho 1", "cho 2", "cho minh 1", "cho minh 2", "toi muon 2kg", "toi muon mua 2kg"])
        # 7. Thông tin liên hệ / Hotline
        if "contact" in target_intent or "hotline" in target_intent:
            return any(k in query_norm for k in ["hotline", "so dien thoai", "lien he", "tong dai", "sdt", "call"])
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
        shopee_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"

        if any(w in norm_text for w in ["gia", "mua", "ban", "can", "chai", "lit", "kg", "bao nhieu"]) and not any(w in norm_text for w in ["co nhung", "cac san pham", "san pham nao", "dong san pham", "gioi thieu"]):
            final_answer = (
                f"Dạ hiện tại thông tin chi tiết về sản phẩm này chưa có sẵn trong danh mục tra cứu nhanh của {brand_display}. "
                f"Bạn có thể ghé xem toàn bộ sản phẩm chính hãng, bảng giá niêm yết và mã giảm giá tại gian hàng Shopee Mall:\n"
                f"👉 {shopee_link}\n\n"
                f"Hoặc bạn nhắn rõ tên sản phẩm/dung tích cụ thể để mình kiểm tra và báo giá ngay cho bạn nhé ạ! 💙"
            )
            lead_stage = "browsing_catalog"
        elif any(w in norm_text for w in ["dai ly", "si", "nhap", "hop tac", "npp", "phan phoi"]):
            final_answer = (
                f"Dạ về chính sách đại lý & giá sỉ số lượng lớn của {brand_display}, "
                f"bạn gửi giúp mình Số Điện Thoại và Khu Vực dự kiến kinh doanh nhé. "
                f"Phòng kinh doanh sẽ liên hệ gửi bảng giá chiết khấu và điều kiện hợp tác chi tiết cho bạn ngay ạ!"
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
    asyncio.create_task(_async_save_session(
        brand=brand,
        sender_id=sender_id,
        user_message=raw_text,
        bot_reply=final_answer,
        intent=intent if confidence == "high" else "unanswered_query",
        lead_stage=lead_stage,
    ))

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return ChatPipelineResponse(
        answer=final_answer,
        intent=intent if confidence == "high" else "unanswered_query",
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
        answer=answer,
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


async def _async_save_session(brand: str, sender_id: str, user_message: str, bot_reply: str, intent: str, lead_stage: str):
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
        await r.set(session_key, json.dumps(session_data, ensure_ascii=False))

        # Lưu 10 tin nhắn gần nhất vào chat history
        msg_record = json.dumps({
            "user_message": user_message,
            "bot_reply": bot_reply,
            "intent": intent,
            "timestamp": now_str,
        }, ensure_ascii=False)
        await r.rpush(history_key, msg_record)
        await r.ltrim(history_key, -50, -1)  # Giữ tối đa 50 tin
    except Exception as e:
        logger.warning("Error in _async_save_session: %s", e)
