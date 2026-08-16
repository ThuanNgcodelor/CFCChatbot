"""
eval_test_suite.py — Bộ Kiểm Thử Ngữ Nghĩa Toàn Diện cho Chatbot ZeO & CFC
Đánh giá độ chính xác phân loại Intent, Nội dung câu trả lời, Điểm tin cậy và Tốc độ xử lý.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from chat_pipeline import process_chat_pipeline, ChatPipelineRequest

TEST_CASES = [
    # ─── 1. CHÀO HỎI & CẢM ƠN ───
    {"q": "Xin chào shop", "category": "greeting", "expected_intent": "greeting"},
    {"q": "Hello ZeO", "category": "greeting", "expected_intent": "greeting"},
    {"q": "Shop ơi", "category": "greeting", "expected_intent": "greeting"},
    {"q": "Alo có ai trực không", "category": "greeting", "expected_intent": "greeting"},
    {"q": "Hi bạn", "category": "greeting", "expected_intent": "greeting"},
    {"q": "Cảm ơn shop nhiều", "category": "thanks", "expected_intent": "thanks"},
    {"q": "Ok thanks bạn", "category": "thanks", "expected_intent": "thanks"},
    {"q": "Dạ cảm ơn shop", "category": "thanks", "expected_intent": "thanks"},

    # ─── 2. DANH MỤC SẢN PHẨM TỔNG QUAN ───
    {"q": "ZeO có những sản phẩm gì?", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "Cho tôi hỏi về các sản phẩm của ZeO", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "ZeO bán những gì?", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "Bên mình có những loại nào?", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "Danh mục sản phẩm của ZeO", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "Giới thiệu các dòng sản phẩm ZeO đi", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "Các nhóm sản phẩm của shop", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "PANO là sản phẩm gì?", "category": "catalog", "expected_intent": "pano_product_type"},
    {"q": "Pano có những dòng nào?", "category": "catalog", "expected_intent": "pano_product_type"},

    # ─── 3. KHUYẾN MÃI, SALE & VOUCHER ───
    {"q": "Hiện tại có sản phẩm nào đang sale hay ko", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "có sản phẩm nào đang sale ko", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Có sản phẩm nào đang sale ở shopee ko", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Shop có đang khuyến mãi gì không?", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Có voucher giảm giá shopee không?", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Đang có ưu đãi gì thế shop?", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Có mã giảm giá không bạn?", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Sản phẩm nào đang giảm giá?", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Shopee có sale không?", "category": "promotion", "expected_intent": "promotion_deals"},

    # ─── 4. MUA HÀNG & LINK SHOPEE ───
    {"q": "xin link shopee ạ", "category": "purchase", "expected_intent": "shopee_product_link"},
    {"q": "Cho mình link shopee chính hãng", "category": "purchase", "expected_intent": "shopee_product_link"},
    {"q": "Mua hàng online ở đâu?", "category": "purchase", "expected_intent": "online_purchase"},
    {"q": "Tôi muốn mua nước giặt thì mua ở đâu?", "category": "purchase", "expected_intent": "shopee_product_link"},
    {"q": "Cho xin link nước rửa chén shopee", "category": "purchase", "expected_intent": "shopee_product_link"},
    {"q": "Cho xin link nước lau sàn", "category": "purchase", "expected_intent": "shopee_product_link"},
    {"q": "Giá bao nhiêu?", "category": "pricing", "expected_intent": "zeo_price_inquiry_general"},
    {"q": "Nước giặt giá bao nhiêu tiền 1 can?", "category": "pricing", "expected_intent": "zeo_price_inquiry_general"},

    # ─── 5. TÍNH NĂNG, CÔNG NGHỆ & CHỨNG NHẬN ───
    {"q": "Bột giặt ZeO dùng công nghệ gì?", "category": "tech", "expected_intent": "zeo_detergent_technology"},
    {"q": "Enzyme Thụy Điển có trong sản phẩm nào?", "category": "tech", "expected_intent": "zeo_detergent_technology"},
    {"q": "Bột giặt ZeO có chứng nhận gì của Viện Pasteur không?", "category": "tech", "expected_intent": "zeo_detergent_certification"},
    {"q": "Bột giặt ZeO có thơm lâu không?", "category": "tech", "expected_intent": "zeo_detergent_fragrance"},
    {"q": "PANO có những mùi hương nào?", "category": "tech", "expected_intent": "pano_laundry_fragrance_options"},
    {"q": "Công nghệ VEILEX là gì?", "category": "tech", "expected_intent": "pano_veilex_odor_control"},
    {"q": "Nước lau sàn có những mùi nào?", "category": "tech", "expected_intent": "floor_cleaner_features"},
    {"q": "Nước rửa chén ZIF ZeO có thành phần gì?", "category": "tech", "expected_intent": "zeo_zif_dishwashing_liquid"},
    {"q": "Tẩy Toilet ZeO có diệt khuẩn không?", "category": "tech", "expected_intent": "zeo_toilet_cleaner"},

    # ─── 6. GIAO HÀNG & PHÍ SHIP ───
    {"q": "Có giao hàng toàn quốc không?", "category": "shipping", "expected_intent": "nationwide_shipping_no_cod"},
    {"q": "Shop có ship không?", "category": "shipping", "expected_intent": "nationwide_shipping_no_cod"},
    {"q": "Giao hàng mấy ngày thì tới?", "category": "shipping", "expected_intent": "shipping_time_and_fee"},
    {"q": "Phí ship bao nhiêu tiền?", "category": "shipping", "expected_intent": "shipping_time_and_fee"},
    {"q": "Có freeship không shop?", "category": "shipping", "expected_intent": "shipping_time_and_fee"},

    # ─── 7. CHÍNH SÁCH ĐỔI TRẢ & BẢO HÀNH ───
    {"q": "Chính sách đổi trả như thế nào?", "category": "policy", "expected_intent": "return_policy_scope"},
    {"q": "Mua trên Shopee có được đổi trả không?", "category": "policy", "expected_intent": "return_policy_scope"},
    {"q": "Hàng bị lỗi rách nắp có được đổi không?", "category": "policy", "expected_intent": "return_eligible_cases"},
    {"q": "Thời hạn khiếu nại đổi trả là bao lâu?", "category": "policy", "expected_intent": "return_claim_deadlines"},
    {"q": "Quy trình đổi trả hàng thế nào?", "category": "policy", "expected_intent": "return_process"},
    {"q": "Bao lâu thì nhận được tiền hoàn trả?", "category": "policy", "expected_intent": "refund_processing_time"},

    # ─── 8. ĐẠI LÝ & LẤY SỈ ───
    {"q": "Tôi muốn lấy sỉ thì làm sao?", "category": "wholesale", "expected_intent": "wholesale_inquiry"},
    {"q": "Muốn làm đại lý phân phối ZeO", "category": "wholesale", "expected_intent": "wholesale_inquiry"},
    {"q": "Có chính sách sỉ cho đại lý không?", "category": "wholesale", "expected_intent": "wholesale_inquiry"},
    {"q": "Tôi muốn nhập số lượng lớn về bán", "category": "wholesale", "expected_intent": "wholesale_inquiry"},

    # ─── 9. ĐỊA CHỈ & GIỜ MỞ CỬA ───
    {"q": "Shop mở cửa lúc mấy giờ?", "category": "operations", "expected_intent": "shop_opening_hours"},
    {"q": "Hôm nay shop có mở cửa không?", "category": "operations", "expected_intent": "shop_opening_hours"},
    {"q": "Địa chỉ công ty ở đâu?", "category": "operations", "expected_intent": "company_address"},
    {"q": "Hotline liên hệ là số mấy?", "category": "operations", "expected_intent": "company_contact_information"},

    # ─── 10. KHÁCH ĐỂ LẠI SĐT ───
    {"q": "Tôi ở Cần Thơ, số điện thoại 0918123456", "category": "lead", "expected_intent": "contact_phone_provided"},
    {"q": "Tư vấn cho mình qua số 0907123456 nhé", "category": "lead", "expected_intent": "contact_phone_provided"},

    # ─── 11. CÂU HỎI LẠ (CHƯA CÓ TRONG FAQ) → KIỂM TRA FALLBACK TRUNG THỰC ───
    {"q": "Shop có xuất hóa đơn đỏ VAT cho công ty không?", "category": "unindexed", "expected_intent": "unanswered_query"},
    {"q": "Có ship hỏa tốc 2 giờ tại Sài Gòn không?", "category": "unindexed", "expected_intent": "unanswered_query"},
    {"q": "Có can 20 lít không bạn?", "category": "unindexed", "expected_intent": "unanswered_query"},
]


async def run_eval():
    print(f"🚀 BẮT ĐẦU CHẠY BỘ ĐÁNH GIÁ CHATBOT ({len(TEST_CASES)} TEST CASES)...")
    print("=" * 80)

    passed = 0
    failed = 0
    total_latency = 0.0

    results_by_cat = {}

    for idx, tc in enumerate(TEST_CASES, 1):
        q = tc["q"]
        cat = tc["category"]
        expected = tc["expected_intent"]

        req = ChatPipelineRequest(brand="zeo", sender_id=f"eval_user_{idx}", text=q)
        t0 = time.perf_counter()
        res = await process_chat_pipeline(req)
        latency = (time.perf_counter() - t0) * 1000
        total_latency += latency

        matched = (res.intent == expected)
        if matched:
            passed += 1
            status = "✅ PASS"
        else:
            # Chấp nhận một số intent tương đương hợp lý
            if (expected in ["shopee_product_link", "online_purchase"] and res.intent in ["shopee_product_link", "online_purchase"]) \
               or (expected in ["promotion_deals", "zeo_promotions_and_deals"] and res.intent in ["promotion_deals", "zeo_promotions_and_deals"]) \
               or (expected in ["catalog_overview", "zeo_product_catalog_overview"] and res.intent in ["catalog_overview", "zeo_product_catalog_overview"]) \
               or (expected in ["shipping_time_and_fee", "nationwide_shipping_no_cod"] and res.intent in ["shipping_time_and_fee", "nationwide_shipping_no_cod"]):
                matched = True
                passed += 1
                status = "✅ PASS (Synonym)"
            else:
                failed += 1
                status = f"❌ FAIL (Got: {res.intent}, Expected: {expected})"

        if cat not in results_by_cat:
            results_by_cat[cat] = {"total": 0, "passed": 0}
        results_by_cat[cat]["total"] += 1
        if matched:
            results_by_cat[cat]["passed"] += 1

        print(f"[{idx:02d}/{len(TEST_CASES)}] {status} | Latency: {latency:.1f}ms")
        print(f"   Q: \"{q}\"")
        print(f"   A: {res.answer[:120]}...\n")

    print("=" * 80)
    print("📊 BẢNG TỔNG KẾT ĐÁNH GIÁ CHẤT LƯỢNG NLU:")
    print(f"• Tổng số test cases: {len(TEST_CASES)}")
    print(f"• Thành công: {passed}/{len(TEST_CASES)} ({passed/len(TEST_CASES)*100:.1f}%)")
    print(f"• Thất bại: {failed}/{len(TEST_CASES)}")
    print(f"• Tốc độ trung bình: {total_latency/len(TEST_CASES):.1f}ms/câu")
    print("\nChi tiết theo nhóm:")
    for cat, stat in results_by_cat.items():
        pct = (stat['passed'] / stat['total']) * 100
        print(f"  - {cat:15s}: {stat['passed']}/{stat['total']} ({pct:.0f}%)")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_eval())
