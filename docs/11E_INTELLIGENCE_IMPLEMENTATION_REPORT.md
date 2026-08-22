# 11E — Intelligence Implementation Report

Ngày triển khai: 2026-08-22

## 1. File đã thay đổi

| File | Thay đổi |
|---|---|
| `ChatbotN8n/javis/server/query_understanding.py` | Thêm QueryPlan deterministic |
| `ChatbotN8n/javis/server/chat_pipeline.py` | Tích hợp QueryPlan vào trace/router; thêm guard toilet, brand ecosystem, compatibility, CFC lúa |
| `ChatbotN8n/javis/server/shopee_matcher.py` | Gỡ/giảm các claim tuyệt đối chưa grounded |
| `ChatbotN8n/javis/server/ai_engine.py` | Không gọi CSKH LLM khi không có retrieved facts/catalog products |
| `ChatbotN8n/javis/server/tests/test_query_understanding.py` | Thêm unit tests QueryPlan |

## 2. Thay đổi hành vi chính

1. Câu bồn cầu/toilet/cặn vôi/ố vàng không còn bị route sang vết bẩn quần áo.
2. Câu hỏi mùi/hắc của tẩy toilet dùng fact từ FAQ `zeo_toilet_cleaner`, không tự chuyển sang gửi link mua.
3. Câu “ZeO, PANO, Oplus là 3 hãng khác nhau?” trả overview hệ thương hiệu từ `company_overview`.
4. Câu PANO/Oplus/ZeO + máy cửa trước/trào bọt trả lời thận trọng, không khẳng định bảo vệ vi mạch.
5. Câu CFC xuống giống lúa được nhận diện là advisory nông nghiệp và fallback an toàn cho kỹ sư/đại lý, không bịa công thức.
6. Câu có số điện thoại vẫn ưu tiên lead capture, không bị route advisory bắt nhầm.
7. Câu CFC hỏi giá NPK/bao/kg rõ ràng không bị context cũ kéo sang contextual price.

## 3. Guardrail grounded synthesis

Đã giảm các claim chưa có nguồn trong `shopee_matcher.py`:

- bỏ “HOÀN TOÀN KHÔNG ĂN DA TAY”;
- bỏ “đã qua kiểm nghiệm an toàn da liễu” nếu chưa có fact nguồn;
- bỏ claim hỏng vi mạch máy giặt;
- bỏ “tẩy vết máu 100%”;
- thay bằng ngôn ngữ thận trọng: thử lượng nhỏ, dùng đúng hướng dẫn bao bì, admin/kỹ sư kiểm tra thêm.

`reason_and_answer_cskh()` không còn được gọi khi không có fact/catalog. Nếu retrieval không có dữ liệu, pipeline deterministic sẽ fallback/hỏi rõ/chuyển admin.

## 4. Kết quả test

```text
unittest discovery: 34/34 PASS
eval_test_suite.py: 112/112 PASS, ~2.6-2.8ms/câu
run_test_md_scenarios.py --all: 53/55 PASS (96.4%)
```

Điều kiện test degraded: Redis/Ollama/Groq không truy cập được từ sandbox. Cần chạy lại trên máy local đang bật Redis/Ollama để xác nhận live behavior.

## 5. Việc chưa làm

- Chưa đổi vector DB/model.
- Chưa bật Ollama NLU assist mặc định.
- Chưa làm GraphRAG/LangGraph.
- Chưa sửa RBAC/admin dashboard.
- Chưa rewrite toàn bộ router.
- Chưa sửa alias trong scenario runner (`usage_instructions`, `pano_fragrance_options`).

## 6. Khuyến nghị tiếp theo

1. Chạy lại live với Redis/Ollama thật.
2. Thêm alias intent trong scenario runner thay vì đổi source intent.
3. Đưa các claim da tay/máy giặt/vết bẩn vào Sheet nếu muốn trả lời mạnh hơn.
4. Thêm output validator cho CSKH synthesis trước khi bật LLM nhiều hơn.
