# 11B — QueryPlan Design

## 1. Mục tiêu

QueryPlan là lớp hiểu câu hỏi trước khi retrieval/tool chạy. Nó không sinh fact và không trả lời khách. Nhiệm vụ là biến câu tiếng Việt tự nhiên thành kế hoạch có cấu trúc để router biết nên dùng context, FAQ/RAG hay product catalog.

## 2. Contract hiện triển khai

File: `ChatbotN8n/javis/server/query_understanding.py`

```text
QueryPlan
├── original_query
├── normalized_query
├── brand
├── intent
├── intent_confidence
├── entities
├── references
├── attributes
├── constraints
├── needs_context
├── needs_retrieval
├── needs_product_tool
├── rewritten_query
└── ambiguity_reason
```

## 3. Intent/attribute lớp đầu

| Intent | Mục đích |
|---|---|
| `product_price_query` | Hỏi giá |
| `price_extreme` | Mắc nhất/đắt nhất/cao nhất |
| `product_link_query` | Xin link |
| `product_availability_query` | Còn hàng/tồn kho |
| `multi_attribute_product_query` | Cùng lúc hỏi giá/link/tồn |
| `product_fragrance_need` | Hỏi thơm/mùi/lưu hương |
| `product_safety_need` | Hỏi da tay/em bé/nhạy cảm |
| `product_compatibility` | Máy giặt cửa trước/cửa ngang/ít bọt/trào bọt |
| `cleaning_toilet_stain` | Bồn cầu/toilet/cặn vôi/ố vàng |
| `brand_ecosystem_overview` | ZeO/PANO/Oplus khác nhau hay cùng hệ |
| `agriculture_advisory_query` | Câu tư vấn nông nghiệp CFC cần kỹ sư |

## 4. Nguyên tắc grounding

- QueryPlan chỉ chứa “ý định cần tìm”, không chứa giá/link/tồn kho tự tạo.
- Nếu có reference chưa resolve (`cái đó`, `loại này`, `số 2`) thì `needs_context=true`.
- Nếu là ZeO product query thì `needs_product_tool=true`, nhưng matcher vẫn phải đọc catalog thật.
- Nếu là CFC tư vấn kỹ thuật thì route trả lời an toàn, xin thêm dữ liệu/kỹ sư; không tự đưa liều lượng.

## 5. Vì sao chưa dùng Ollama làm planner chính

Ollama có thể hỗ trợ NLU ở `shadow/assist`, nhưng với dữ liệu giá/link/tồn kho, deterministic parser + catalog matcher dễ kiểm soát hơn. QueryPlan hiện là deterministic để:

- test được bằng unit test;
- không phụ thuộc model;
- tránh LLM “hiểu đúng nhưng tự bịa fact”.

## 6. Hướng mở rộng

- Thêm `constraints.price`, `constraints.category`, `constraints.location`.
- Thêm `negative_entities` để chống match nhầm đối thủ.
- Thêm benchmark riêng cho parse accuracy trước khi bật Ollama `assist`.
