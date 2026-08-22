# 11D — Retrieval Benchmark

Ngày chạy: 2026-08-22  
Điều kiện: sandbox degraded; Redis/Ollama/Groq không truy cập được, Shopee catalog fallback CSV local.

## 1. Kết quả trước/sau

| Bộ kiểm tra | Trước | Sau | Nhận xét |
|---|---:|---:|---|
| Unit tests | 26/26 | 34/34 | Thêm 8 test QueryPlan |
| `eval_test_suite.py` | 112/112, ~2.8ms | 112/112, ~2.6–2.8ms | Không làm hỏng regression cũ |
| `run_test_md_scenarios.py --all` | 48/55 | 53/55 | Cải thiện +5 lượt thực tế |

## 2. Các case cải thiện

| Case | Trước | Sau |
|---|---|---|
| Bồn cầu/cặn vôi/ố vàng | `laundry_stain_removal_guide` | `zeo_cleaning_hygiene_product_overview` |
| Mùi tẩy toilet/con vịt | Shopee product link | `cleaning_fragrance_safety` từ source `zeo_toilet_cleaner` |
| ZeO/PANO/Oplus là gì | `pano_product_type` | `brand_ecosystem_overview` từ source `company_overview` |
| PANO 3.5kg trào bọt | Không ổn định | `pano_washing_machine_compatibility`, trả lời thận trọng |
| CFC xuống giống lúa | `unanswered_query` | `cfc_rice_fertilizer_guide`, không bịa liều lượng |
| CFC NPK 25kg hỏi giá sau lúa | `contextual_price_unverified` | `cfc_price_unverified` |

## 3. Hai lượt còn REVIEW

| Case | Bot trả | Runner expected | Đánh giá |
|---|---|---|---|
| `Cách dùng sao shop?` | `cleaning_usage_instruction` | `usage_instructions` | Nội dung đúng; alias intent của runner chưa đồng bộ |
| `PANO có những mùi hương nào vậy bạn?` | `pano_laundry_fragrance_options` | `pano_fragrance_options` | Nội dung đúng; source intent hiện hành là `pano_laundry_fragrance_options` |

Không đổi code để “ăn điểm” hai case này vì source/FAQ đang dùng intent hiện hành khác tên expected. Nên sửa runner alias nếu muốn báo cáo 55/55.

## 4. Ghi chú hiệu năng

Số ms ở đây chỉ đo pipeline local/degraded. Vì Redis/Ollama bị sandbox chặn, kết quả không đại diện production Messenger → n8n → FastAPI → Facebook Graph API.

## 5. Kết luận benchmark

Thay đổi QueryPlan không làm giảm regression chính và cải thiện scenario thực tế từ 87.3% lên 96.4%. Các lỗi còn lại là alias test, không phải lỗi nội dung trả lời.
