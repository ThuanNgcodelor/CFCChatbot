# 11A — Intelligence Baseline

Ngày đo: 2026-08-22  
Phạm vi: hiểu tiếng Việt tự nhiên, giữ ngữ cảnh, routing/retrieval, trả lời grounded cho ZeO/CFC.  
Điều kiện chạy: local sandbox degraded; Redis/Ollama/Groq không truy cập được từ sandbox, Shopee catalog fallback CSV local.

## 1. Baseline trước thay đổi

| Bộ kiểm tra | Kết quả trước | Ghi chú |
|---|---:|---|
| Unit tests `tests/test_*.py` | 26/26 PASS | Chưa có test QueryPlan riêng |
| `eval_test_suite.py` | 112/112 PASS, ~2.8ms/câu | Runner chủ yếu kiểm intent/keyword; dependency degraded |
| `run_test_md_scenarios.py --all` | 48/55 PASS (87.3%) | 11 scenario thực tế; còn sai route ở toilet, brand ecosystem, PANO washer, CFC lúa |

## 2. Nhóm lỗi quan trọng quan sát được

| Nhóm | Ví dụ | Hành vi trước | Nguyên nhân |
|---|---|---|---|
| Toilet/cặn vôi bị hiểu là quần áo | “Bồn cầu bị cặn vôi ố vàng...” | Route sang `laundry_stain_removal_guide` | Detector vết ố/vết bẩn quá rộng |
| Câu hỏi mùi tẩy toilet kéo sang link | “Có bị nồng nặc mùi hôi...” | Trả link sản phẩm | Context cleaning chưa được ưu tiên trước Shopee link |
| Hệ thương hiệu | “ZeO, PANO, Oplus là 3 hãng khác nhau?” | Route `pano_product_type` | Bắt entity PANO quá sớm |
| Máy giặt cửa trước PANO 3.5kg | “PANO 3.5kg có bị trào bọt không?” | Không có intent riêng ổn định | Thiếu QueryPlan attribute compatibility |
| CFC lúa | “Xuống giống 3 hecta lúa...” | `unanswered_query` | Thiếu route an toàn cho advisory nông nghiệp |
| Unsupported claims | Da tay/vết máu/máy giặt | Có câu tuyệt đối như “100%”, “hoàn toàn” | Text hardcode chưa đi qua validator nguồn |

## 3. Baseline mẫu 30 câu đại diện

| # | Query | Producer chính | Kết luận baseline |
|---:|---|---|---|
| 1 | Xin chào shop | Fast-path greeting | Đúng |
| 2 | ZeO có những sản phẩm gì? | FAQ deterministic | Đúng |
| 3 | Có sản phẩm dưới 100k không? | Shopee budget matcher | Đúng với catalog fallback |
| 4 | Khoảng 200k có gì? | Shopee budget matcher | Đúng, có mở rộng khoảng |
| 5 | Xin link sản phẩm đó | Reference resolver + Shopee matcher | Đúng sau patch cũ |
| 6 | Sản phẩm nào mắc nhất? | Price extreme matcher | Đúng theo snapshot |
| 7 | Giá cái nào mắc nhất | Price extreme matcher | Đúng |
| 8 | Mua nước xả | Fabric softener matcher | Đúng |
| 9 | Xả vải ZeO | Fabric softener matcher | Đúng |
| 10 | Bồn cầu bị cặn vôi ố vàng | Trước: stain matcher | Sai trước thay đổi |
| 11 | Có bị nồng nặc mùi hôi không? | Trước: Shopee link | Sai trước thay đổi |
| 12 | Cách dùng sao shop? | FAQ `cleaning_usage_instruction` | Đúng nội dung; runner alias REVIEW |
| 13 | ZeO/PANO/Oplus khác nhau? | Trước: PANO product type | Sai trước thay đổi |
| 14 | PANO có mùi hương nào? | FAQ `pano_laundry_fragrance_options` | Đúng nội dung; runner alias REVIEW |
| 15 | Máy giặt cửa trước dùng gì ít bọt? | Front-load matcher | Đúng intent cũ, text cần thận trọng |
| 16 | PANO 3.5kg có trào bọt không? | Trước: thiếu route ổn định | Sai trước thay đổi |
| 17 | Giá bao nhiêu 1 túi 3.5kg? | Specific price matcher | Đúng tương đối theo context/catalog |
| 18 | Nước rửa chén ăn da tay không? | Skin-care matcher | Đúng hướng; text cũ quá tuyệt đối |
| 19 | Quần áo em bé dùng gì? | Sensitive laundry matcher | Đúng hướng; text cũ có claim da liễu |
| 20 | Vết máu tẩy được không? | Stain matcher | Đúng intent; text cũ cam kết 100% |
| 21 | Có giao về Rạch Giá không? | Shipping FAQ | Đúng |
| 22 | Trả hàng | Return FAQ | Đúng |
| 23 | Liên hệ sao để trả hàng | Return flow state | Đúng |
| 24 | Điện có tốn phí không | Return flow state | Đúng |
| 25 | Thông tin khách hàng David Nguyen | Privacy guard | Đúng |
| 26 | Hôm nay thứ mấy | Out-of-scope guard | Đúng |
| 27 | CFC có những dòng phân nào? | CFC FAQ | Đúng |
| 28 | Xuống giống 3 hecta lúa bón gì? | Trước: unanswered | Cần route advisory an toàn |
| 29 | Bao 25kg NPK giá bao nhiêu? | CFC price fallback | Có thể bị context kéo sai |
| 30 | SĐT tui là... | Lead capture | Đúng, cần không bị advisory bắt nhầm |

## 4. Kết luận baseline

Hệ thống đã có nhiều deterministic matcher tốt, nhưng thiếu một lớp QueryPlan rõ ràng để ghi nhận: khách đang hỏi thuộc tính gì, đang tham chiếu cái gì, cần tool sản phẩm hay FAQ/RAG. Vì vậy một số regex chuyên biệt bắt quá sớm và có câu trả lời hardcode vượt quá nguồn dữ liệu.
