# Tóm Tắt Hệ Thống Chatbot ZeO/CFC Để Phân Tích Và Nâng Cấp

Ngày cập nhật: 2026-08-17

Tài liệu này mô tả ngắn gọn hệ thống chatbot hiện tại gồm n8n, Python FastAPI, Google Sheet, Redis Vector DB, Ollama và RAG. Mục tiêu là giúp người đọc/ChatGPT hiểu kiến trúc hiện tại để đề xuất cách triển khai, tối ưu và nâng cấp.

Lưu ý bảo mật: Không đưa mật khẩu Redis, token n8n, API key hoặc credential thật vào tài liệu phân tích bên ngoài.

## 1. Mục Tiêu Hệ Thống

Hệ thống dùng để trả lời khách hàng tự động cho 2 nhóm thương hiệu:

- ZeO / PANO / Oplus: sản phẩm chăm sóc gia đình như giặt giũ, nước rửa chén, lau sàn, tẩy rửa vệ sinh.
- CFC Cò Bay: phân bón nông nghiệp như NPK, phân hữu cơ, tư vấn đại lý/phân phối.

Nguyên tắc quan trọng:

- Google Sheet là nguồn kiến thức sống còn.
- Nếu Sheet không có dữ liệu thì chatbot không được tự bịa.
- Không tự bịa giá, địa chỉ, chính sách, liều lượng, chứng nhận, link kênh bán hàng.
- Câu không chắc phải hỏi lại, chuyển admin hoặc lưu vào learning queue.

## 2. Các Thành Phần Chính

### 2.1 n8n

n8n đang xử lý webhook Messenger và đồng bộ kiến thức từ Google Sheet.

Workflow chính:

- `zeo_chatbot.workflow.ts`: nhận tin nhắn Messenger của ZeO, gọi Python FastAPI, chuẩn bị reply và gửi lại khách.
- `cfc_cobay_chatbot.workflow.ts`: luồng tương tự cho CFC Cò Bay.
- `zeo_knowledge_sync_basic.workflow.ts`: đọc Google Sheet ZeO, chuẩn hóa row, ghi snapshot vào Redis, gọi API rebuild vector index.
- `cfc_knowledge_sync_basic.workflow.ts`: đọc Google Sheet CFC, chuẩn hóa row, ghi snapshot vào Redis, gọi API rebuild vector index.

Luồng knowledge sync:

```text
Google Sheet
→ n8n Read FAQ Rows
→ Normalize Knowledge
→ Write Redis Snapshot
→ Write Redis Sync Metadata
→ POST /sync?brand=zeo hoặc /sync?brand=cfc
→ Python tạo embedding
→ Redis Vector Index
```

Luồng chatbot:

```text
Messenger
→ n8n Facebook Trigger
→ lọc input
→ gọi Python FastAPI chat pipeline
→ nhận answer/intent/confidence
→ gửi reply lại Messenger
```

### 2.2 Google Sheet / CSV

File dữ liệu hiện tại:

- `ChatbotN8n/google_upload/zeo_faq_google_sheet_from_ZeoN8n_2026_08_13.csv`
- `ChatbotN8n/google_upload/cfc_faq_google_sheet_from_CfcCoBayN8n_2026_08_13.csv`

Schema hiện tại:

```csv
active,brand,category,intent,question_examples,answer,priority,source_id,updated_at,audience,answer_mode,risk_level,learning_tags,profile_slots,escalation_policy
```

Tình trạng dữ liệu hiện tại:

- ZeO: 79 dòng active.
- CFC: 19 dòng active.
- ZeO categories: `brand`, `faq`, `operations`, `policy`, `product`, `sales`, `shipping`, `support`.
- CFC categories: `company`, `faq`, `operations`, `product`, `sales`, `shipping`, `support`, `wholesale`.

Vai trò các cột quan trọng:

- `active`: dòng có được dùng hay không.
- `brand`: thương hiệu áp dụng.
- `category`: nhóm kiến thức.
- `intent`: mã ý định, ví dụ `company_overview`, `zeo_product_catalog_overview`.
- `question_examples`: các cách khách có thể hỏi, phân tách bằng dấu `;`.
- `answer`: câu trả lời chuẩn.
- `priority`: độ ưu tiên khi nhiều câu gần nhau.
- `audience`: `customer` hoặc `internal/agent`; dòng nội bộ không nên trả trực tiếp cho khách.
- `answer_mode`: trả trực tiếp hay rewrite.
- `risk_level`: mức rủi ro nếu trả sai.
- `learning_tags`, `profile_slots`, `escalation_policy`: phục vụ phân loại, thu thập thông tin và chuyển admin.

### 2.3 Python FastAPI Server

Thư mục chính:

```text
ChatbotN8n/javis/server/
```

File chính:

- `main.py`: FastAPI app, health check, sync, search, rewrite, admin dashboard.
- `chat_pipeline.py`: pipeline trả lời khách hàng.
- `rag_search.py`: tìm kiếm vector trong Redis + rerank.
- `knowledge_sync.py`: đọc snapshot Redis, tạo embedding, ghi vào RediSearch.
- `embedder.py`: gọi Ollama local để tạo embedding bằng `bge-m3`.
- `shopee_matcher.py`: match sản phẩm/link Shopee nếu có.
- `admin_routes.py`: dashboard/admin APIs.
- `eval_test_suite.py`: bộ test intent/case lỗi.

Endpoint chính:

```text
GET  /health
POST /sync?brand=zeo
POST /sync?brand=cfc
POST /sync?brand=all
POST /search
POST /rewrite
GET  /admin
```

### 2.4 Redis / RediSearch

Redis dùng cho:

- Lưu snapshot kiến thức từ n8n.
- Lưu vector index để RAG search.
- Lưu session chat.
- Lưu customer profile.
- Lưu learning queue các câu chưa trả lời chắc.

Redis keys/index quan trọng:

```text
zeo:kb:basic:active
cfc:kb:basic:active
zeo:vec:faq
cfc:vec:faq
zeo:session:messenger:{sender_id}
cfc:session:messenger:{sender_id}
zeo:customer:messenger:{sender_id}
cfc:customer:messenger:{sender_id}
zeo:learning:queue
cfc:learning:queue
```

Vector index dùng RediSearch HNSW với cosine distance.

### 2.5 Ollama / Embedding

Ollama chạy local:

```text
http://127.0.0.1:11434
```

Model embedding:

```text
bge-m3
```

Embedding dimension:

```text
1024
```

Vai trò:

- Khi sync kiến thức: tạo embedding cho từng FAQ item.
- Khi khách hỏi: tạo embedding cho câu hỏi, search trong Redis vector index.

## 3. Luồng RAG Hiện Tại

### 3.1 Khi cập nhật kiến thức

```text
Google Sheet
→ n8n đọc từng row
→ n8n normalize dữ liệu
→ n8n ghi JSON snapshot vào Redis
→ n8n gọi Python POST /sync
→ Python đọc snapshot Redis
→ Python build text embedding gồm intent + examples + answer
→ Ollama bge-m3 tạo vector
→ Python ghi HASH vào Redis Vector Index
```

### 3.2 Khi khách hỏi

```text
Messenger message
→ n8n nhận webhook
→ Python chat_pipeline
→ normalize tiếng Việt
→ check phone/profile/session
→ fast-path greeting/thanks/complaint
→ intent-first router
→ Shopee matcher nếu hỏi Shopee
→ RAG semantic search
→ rerank top-k
→ guardrail chống bắt nhầm
→ trả answer từ Sheet/Redis
→ lưu session/history/profile
→ nếu không chắc thì push learning queue/admin
```

## 4. Những Nâng Cấp Đã Làm Gần Đây

### 4.1 Bỏ hardcode catalog quan trọng

Các câu trả lời catalog/sản phẩm không nên hardcode trong code. Hệ thống đã chuyển nhiều fast-path sang đọc theo `intent` từ Sheet/Redis bằng `get_faq_by_intent`.

### 4.2 Format output đẹp hơn

Đã thêm `_prettify_answer()` để:

- Dọn khoảng trắng.
- Xuống dòng danh sách đánh số.
- Tránh trả lời dính một đoạn dài khó đọc.

### 4.3 Thêm Intent-first Router

Đã thêm lớp nhận diện intent trước khi RAG search để tránh các lỗi:

- `Giới thiệu cty đi` bị trả địa chỉ.
- `Dòng sản phẩm ZiF` bị trả catalog tổng.
- `Sdt` không hiểu là hỏi hotline.
- `Tiktok`/`Zalo` bị lôi dòng nội bộ.
- `Có bột giặt Omo không` bị nhận nhầm là ZeO.
- `Sai địa chỉ rồi` bị trả lời lung tung.
- `1kg bột cho 5 bộ đồ` bị bịa liều lượng.

Các nhóm detector đã thêm:

- Company overview.
- Address.
- Contact/hotline.
- Official channel/social link.
- Customer correction/feedback.
- Language request.
- New product/unverified.
- Competitor/out-of-scope product.
- CFC cross-brand.
- Certification/proof.
- Usage/safety/dosage gap.
- Specific product intent: ZIF, PANO, Oplus, NPK, hữu cơ.

### 4.4 RAG Rerank

Trước đây Redis trả top-k theo vector score. Hiện tại có thêm rerank nhẹ:

- Boost nếu query khớp entity như ZIF, PANO, Oplus, NPK.
- Phạt catalog tổng nếu khách hỏi sản phẩm cụ thể.
- Boost `company_overview` nếu khách hỏi giới thiệu công ty.
- Phạt `address` nếu khách không hỏi địa chỉ.
- Phạt dòng `audience=agent/internal` nếu khách chỉ hỏi kênh như TikTok/Zalo.
- Boost intent giá nếu câu hỏi có tín hiệu giá.

## 5. Các Lỗi Từng Gặp Và Cách Xử Lý

| Câu khách hỏi | Lỗi cũ | Cách xử lý mới |
|---|---|---|
| `Dòng sản phẩm ZiF` | Trả catalog tổng | Ưu tiên ZIF/Nước rửa chén |
| `Giới thiệu cty đi` | Trả địa chỉ | Route `company_overview` |
| `Sơ lược về cty` | Trả địa chỉ | Route `company_overview` |
| `Sdt` | Fallback | Route contact/hotline |
| `Sdt công tu` | Không hiểu typo | Route contact/hotline |
| `Có bột giặt Omo không` | Trả nhóm giặt giũ ZeO | Báo chưa có dữ liệu thương hiệu đó |
| `Tiktok` | Trả nội dung TikTok nội bộ | Báo chưa có link chính thức nếu Sheet chưa có |
| `Zalo` | Trả sai catalog/nội dung nội bộ | Báo chưa có link chính thức nếu Sheet chưa có |
| `Sản phẩm mới nhất` | Trả catalog, dễ hiểu sai | Báo chưa có dữ liệu sản phẩm mới |
| `Sai địa chỉ rồi` | Trả nhầm policy/fallback | Ghi nhận, chuyển admin duyệt |
| `Có giấy tờ chứng minh công nghệ đó không` | Trả lạc | Route chứng nhận/kiểm định |
| `1kg bột cho 5 bộ đồ` | Fallback hoặc dễ bịa | Không hướng dẫn liều lượng nếu Sheet chưa có |

## 6. Điểm Mạnh Hiện Tại

- Có Google Sheet làm nguồn dữ liệu chính.
- Có Redis snapshot và Redis vector index.
- Có embedding tiếng Việt bằng BGE-M3.
- Có FastAPI server riêng, nhanh hơn xử lý logic nặng trong n8n.
- Có session/profile để nhớ số điện thoại/khu vực khách đã gửi.
- Có learning queue cho câu không chắc.
- Có guardrail chống trả sai ở một số nhóm nhạy cảm.
- Có test cases để kiểm tra regression.

## 7. Điểm Yếu / Rủi Ro Hiện Tại

### 7.1 Vẫn còn phụ thuộc nhiều vào regex/router

Intent-first router giúp chặn sai nhanh, nhưng nếu mở rộng nhiều brand/sản phẩm thì regex sẽ phình to.

### 7.2 RAG chưa phải hybrid search hoàn chỉnh

Hiện có vector search + rerank thủ công. Chưa có BM25/keyword search riêng rồi merge với vector.

### 7.3 Chưa có LLM intent classifier có kiểm soát

Có thể cần một lớp phân loại intent bằng model nhỏ/LLM JSON mode, nhưng phải có schema cứng và confidence rõ ràng.

### 7.4 Sheet chưa có đầy đủ negative examples

Ví dụ `company_address` nên có negative keyword như: `giới thiệu`, `công ty là gì`, `thuộc công ty nào`.

### 7.5 Chưa có eval tự động đủ lớn

Đã có test, nhưng nên mở rộng thành vài trăm/vài ngàn câu thật từ Messenger logs.

### 7.6 Chưa có dashboard review learning queue hoàn chỉnh

Learning queue có thể lưu câu lỗi, nhưng cần quy trình admin duyệt:

```text
Câu khách hỏi
→ Bot không chắc
→ Lưu learning queue
→ Admin phân loại intent đúng
→ Gợi ý thêm question_examples vào Sheet
→ Sync lại Redis vector
```

## 8. Hướng Nâng Cấp Đề Xuất

### Phase 1: Làm hệ thống ổn định hơn

- Chuẩn hóa toàn bộ intent trong Sheet.
- Thêm `keywords` và `negative_keywords` vào schema Sheet.
- Thêm `entity_aliases` cho sản phẩm/thương hiệu.
- Tách rõ dòng `customer` và `agent/internal`.
- Bắt buộc các intent nhạy cảm có guardrail.

### Phase 2: Hybrid Retrieval

Thay vì chỉ vector search:

```text
Query
→ Normalize
→ Intent classifier
→ Keyword/BM25 search
→ Vector search BGE-M3
→ Merge candidates
→ Reranker
→ Guardrail
→ Answer
```

Điểm cần có:

- Exact match theo sản phẩm.
- Keyword match theo intent.
- Vector semantic match.
- Reranker theo entity/category/risk.
- Confidence threshold riêng cho từng category.

### Phase 3: Controlled LLM

LLM/Ollama không nên tự bịa kiến thức. Chỉ nên dùng để:

- Phân loại intent theo JSON schema.
- Viết lại câu trả lời đã được grounding.
- Tóm tắt lịch sử hội thoại.
- Gợi ý câu hỏi làm rõ.

Không cho LLM tự tạo:

- Giá.
- Công dụng mới.
- Chứng nhận.
- Địa chỉ.
- Hotline.
- Link mua hàng.
- Liều lượng phân bón.
- Hướng dẫn an toàn hóa chất.

### Phase 4: Eval và Observability

Mỗi câu trả lời nên log:

```json
{
  "brand": "zeo",
  "raw_text": "...",
  "normalized_text": "...",
  "detected_intent": "...",
  "matched_intent": "...",
  "score": 0.82,
  "vector_score": 0.74,
  "rerank_adjustment": 0.08,
  "source_id": "...",
  "confidence": "high",
  "fallback_reason": "",
  "answer_mode": "direct"
}
```

Cần dashboard xem:

- Top câu fallback.
- Top intent bị nhầm.
- Top query score thấp.
- Câu khách hỏi nhiều nhưng chưa có trong Sheet.
- Case cần admin duyệt.

## 9. File Quan Trọng

```text
ChatbotN8n/javis/server/main.py
ChatbotN8n/javis/server/chat_pipeline.py
ChatbotN8n/javis/server/rag_search.py
ChatbotN8n/javis/server/knowledge_sync.py
ChatbotN8n/javis/server/embedder.py
ChatbotN8n/javis/server/shopee_matcher.py
ChatbotN8n/javis/server/eval_test_suite.py
ChatbotN8n/workflows/local-n8n/zeo_chatbot.workflow.ts
ChatbotN8n/workflows/local-n8n/cfc_cobay_chatbot.workflow.ts
ChatbotN8n/workflows/local-n8n/zeo_knowledge_sync_basic.workflow.ts
ChatbotN8n/workflows/local-n8n/cfc_knowledge_sync_basic.workflow.ts
ChatbotN8n/google_upload/zeo_faq_google_sheet_from_ZeoN8n_2026_08_13.csv
ChatbotN8n/google_upload/cfc_faq_google_sheet_from_CfcCoBayN8n_2026_08_13.csv
test.md
```

## 10. Câu Hỏi Cần ChatGPT/AI Architect Phân Tích Tiếp

1. Có nên chuyển từ regex router sang intent classifier bằng model không?
2. Nên thiết kế schema Google Sheet thế nào để scale lên nhiều brand/sản phẩm?
3. Nên dùng Redis Search hybrid hay tách thêm BM25 engine?
4. Nên dùng reranker model riêng hay rerank rule-based là đủ?
5. Nên log/eval chatbot thế nào để biết câu nào đang sai?
6. Nên thiết kế learning queue/admin review ra sao để dữ liệu Sheet tự tốt lên?
7. Nên tách knowledge theo product/company/policy/sales/support như thế nào?
8. Với câu hỏi ngắn như `Sdt`, `Zalo`, `PANO`, `Giá sao`, nên dùng context hội thoại ra sao?
9. Với dữ liệu giá chưa có, làm sao đảm bảo bot không bao giờ bịa giá?
10. Với phân bón CFC, làm sao chặn bot tự bịa liều lượng/công dụng nông nghiệp?

## 11. Mục Tiêu Cuối Cùng

Hệ thống nên tiến tới dạng:

```text
Google Sheet chuẩn
→ Sync tự động
→ Vector + keyword index
→ Intent classifier
→ Hybrid retrieval
→ Reranker
→ Grounded answer composer
→ Guardrail
→ Admin learning loop
→ Eval tự động trước khi deploy
```

Mục tiêu không phải là bot trả lời mọi thứ. Mục tiêu đúng là:

- Câu có dữ liệu thì trả đúng, rõ, đẹp.
- Câu không có dữ liệu thì không bịa.
- Câu rủi ro thì hỏi thêm hoặc chuyển admin.
- Câu bị sai phải được ghi nhận để cải thiện Sheet.
- Mỗi lần cập nhật Google Sheet, Redis/RAG phải phản ánh đúng dữ liệu mới.
