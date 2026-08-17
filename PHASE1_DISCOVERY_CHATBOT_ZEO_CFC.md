# Phase 1 Discovery - Chatbot ZeO/CFC Conversational AI

Ngày: 2026-08-17

Mục tiêu phase này: đọc hệ thống đang chạy, trace runtime thực tế, xác định kiến trúc hiện tại và bottleneck chính. Phase này **không sửa runtime code**.

Lưu ý: Không đưa credential thật, mật khẩu Redis, token n8n hoặc API key vào báo cáo.

## 1. Executive Summary

Hệ thống hiện tại đã có nền tốt:

- n8n nhận Messenger webhook và sync Google Sheet.
- Python FastAPI xử lý nhanh chat pipeline.
- Redis lưu knowledge snapshot, vector index, profile, session và learning queue.
- BGE-M3 qua Ollama tạo embedding tiếng Việt.
- RediSearch dùng vector HNSW để RAG.
- Gần đây đã thêm intent-first router và rerank nhẹ để giảm lỗi hỏi một đằng trả lời một nẻo.

Nhưng để thành conversational AI mạnh hơn, bottleneck chính hiện tại là:

- Memory Python còn mỏng, chưa lưu structured state như active product/category, last products shown, reference targets.
- Query phụ thuộc context như `cái đầu tiên`, `loại đó`, `con hồi nãy`, `còn hong` chưa có resolver chuẩn trước retrieval.
- Runtime có 2 lớp logic: Python pipeline là đường chính khi FastAPI chạy tốt, n8n legacy RAG là đường fallback khi FastAPI lỗi. Hai lớp này có thể lệch logic.
- Retrieval hiện là vector search + rule rerank, chưa phải hybrid retrieval đầy đủ có exact match/BM25/metadata filters/grounding engine.
- Learning queue có nhưng record còn chưa đủ trace để debug đầy đủ.
- Eval đã có nhưng cần baseline tự động và nhiều case multi-turn/context-dependent hơn.

## 2. Project Map

| Component | File | Role | Depends On | Used By |
|---|---|---|---|---|
| FastAPI app | `ChatbotN8n/javis/server/main.py` | API chính: health, sync, search, rewrite, chat pipeline, admin static | `knowledge_sync`, `rag_search`, `embedder`, `admin_routes`, `chat_pipeline` | n8n, dashboard, manual tests |
| Chat pipeline | `ChatbotN8n/javis/server/chat_pipeline.py` | Xử lý message khách: normalize, profile/session, intent-first router, Shopee, RAG, guardrail, fallback, save session | Redis, `rag_search`, `shopee_matcher`, Telegram notifier | `POST /api/chat-pipeline` |
| RAG search | `ChatbotN8n/javis/server/rag_search.py` | Embed query, RediSearch KNN, parse candidates, rerank, return best answer | Redis, Ollama embedding | `chat_pipeline`, `/search` |
| Knowledge sync | `ChatbotN8n/javis/server/knowledge_sync.py` | Đọc Redis snapshot, tạo embedding cho FAQ, upsert vector index, xóa stale docs | Redis, Ollama BGE-M3 | `POST /sync` |
| Embedder | `ChatbotN8n/javis/server/embedder.py` | Gọi Ollama `/api/embed`, convert vector sang bytes | Ollama local | `knowledge_sync`, `rag_search` |
| Shopee matcher | `ChatbotN8n/javis/server/shopee_matcher.py` | Match intent/link Shopee và promotion nếu có dữ liệu | Shopee sheet/cache | `chat_pipeline` |
| Admin routes | `ChatbotN8n/javis/server/admin_routes.py` | Dashboard, settings, customer/session, learning queue, documents, Shopee, analytics | Redis, n8n API, Telegram | FastAPI `/admin` và APIs |
| Eval suite | `ChatbotN8n/javis/server/eval_test_suite.py` | Test intent/response nhanh qua `process_chat_pipeline` | Python pipeline, Redis/Ollama nếu cần | Dev/test |
| ZeO chatbot n8n | `ChatbotN8n/workflows/local-n8n/zeo_chatbot.workflow.ts` | Messenger workflow ZeO, gọi FastAPI, fallback legacy RAG nếu FastAPI lỗi | Messenger, Redis, Ollama, Python | n8n production workflow |
| CFC chatbot n8n | `ChatbotN8n/workflows/local-n8n/cfc_cobay_chatbot.workflow.ts` | Messenger workflow CFC, tương tự ZeO | Messenger, Redis, Ollama, Python | n8n production workflow |
| ZeO knowledge n8n | `ChatbotN8n/workflows/local-n8n/zeo_knowledge_sync_basic.workflow.ts` | Đọc Sheet ZeO, normalize, ghi Redis snapshot, gọi `/sync?brand=zeo` | Google Sheet, Redis, Python | Knowledge sync |
| CFC knowledge n8n | `ChatbotN8n/workflows/local-n8n/cfc_knowledge_sync_basic.workflow.ts` | Đọc Sheet CFC, normalize, ghi Redis snapshot, gọi `/sync?brand=cfc` | Google Sheet, Redis, Python | Knowledge sync |
| ZeO CSV | `ChatbotN8n/google_upload/zeo_faq_google_sheet_from_ZeoN8n_2026_08_13.csv` | Source of truth export cho ZeO/PANO/Oplus | Google Sheet | n8n sync |
| CFC CSV | `ChatbotN8n/google_upload/cfc_faq_google_sheet_from_CfcCoBayN8n_2026_08_13.csv` | Source of truth export cho CFC | Google Sheet | n8n sync |

## 3. Current Chat Runtime Flow

### 3.1 Primary Path: FastAPI Success

Runtime path chính theo n8n workflow:

```text
MessengerTrigger
→ LocDauVao
→ GoiFastApiChatPipeline
→ PrepareMessengerReply
→ NhanKhachAuto
```

Evidence:

- `zeo_chatbot.workflow.ts` và `cfc_cobay_chatbot.workflow.ts` có node `GoiFastApiChatPipeline`.
- URL gọi: `http://127.0.0.1:8000/api/chat-pipeline`.
- Nếu HTTP request thành công, node `PrepareMessengerReply` lấy `pipelineRes.answer`, `intent`, `confidence`, `score`, `has_phone`, `latency_ms` rồi gửi qua Graph API.

FastAPI endpoint:

```text
main.py
POST /api/chat-pipeline
→ process_chat_pipeline(req)
```

Python pipeline thực tế:

```text
ChatPipelineRequest
→ normalize raw text
→ extract phone/area
→ read Redis customer profile + session
→ merge stored phone/area
→ fast-path phone provided
→ profile recall
→ greeting/thanks/ack
→ complaint escalation
→ intent-first router
→ promotion matcher
→ website/contact/price/wholesale fast path
→ product group fast path
→ catalog/hours/tech/policy fast path
→ Shopee matcher
→ semantic_search Redis vector
→ guardrail by intent
→ tiered confidence/fallback
→ async save session/history
→ return ChatPipelineResponse
```

### 3.2 Fallback Path: FastAPI Error

n8n workflow vẫn giữ legacy route khi `GoiFastApiChatPipeline` lỗi:

```text
GoiFastApiChatPipeline.error()
→ GetCustomerProfile
→ MergeCustomerProfile
→ GetSession
→ GoiOllamaNluLocal
→ DialogueManager
→ GetKnowledgeSnapshot
→ RagTimKiem
→ RouterCoNguon
→ optional GoiOllamaLocal rewrite
→ KiemChung
→ RouterGuardrail
→ SaveCustomerProfile
→ SaveSession
→ QueueLearningReview nếu cần
→ NotifyTelegramOperations nếu cần
→ NhanKhachAuto hoặc NhanKhachFallback
```

Điểm cần chú ý:

- Đây là fallback khi FastAPI lỗi, không phải đường chính nếu Python chạy ổn.
- n8n fallback có logic NLU/RAG/session riêng và khá dài.
- Nếu Python và n8n fallback không cùng logic, khi Python lỗi bot có thể trả khác hành vi bình thường.

## 4. Current Knowledge Flow

### 4.1 n8n Knowledge Sync

Luồng ZeO và CFC tương tự nhau:

```text
ManualTrigger hoặc ScheduleTrigger
→ Read FAQ Rows từ Google Sheets
→ Normalize Knowledge
→ Write Redis Snapshot
→ Write Redis Sync Metadata
→ Rebuild Vector Index: POST http://127.0.0.1:8000/sync?brand=...
```

Redis snapshot keys:

```text
zeo:kb:basic:active
cfc:kb:basic:active
```

Metadata keys:

```text
zeo:sync:faq:basic:last-success
cfc:sync:faq:basic:last-success
```

n8n normalize đang làm:

- Chuẩn hóa text.
- Split `question_examples`.
- Split `learning_tags`, `profile_slots`.
- Xác định `audience`.
- Lọc active rows.
- Lọc rows thiếu answer/intent.
- Lọc brand đúng scope.
- Lọc `audience === customer`.
- Check duplicate intents.
- Check thiếu `question_examples`.
- Ghi JSON snapshot vào Redis.

### 4.2 Python Vector Sync

Endpoint:

```text
POST /sync?brand=zeo
POST /sync?brand=cfc
POST /sync?brand=all
```

Flow trong `knowledge_sync.py`:

```text
sync_brand(brand)
→ read Redis snapshot key
→ parse_snapshot()
→ ensure RediSearch index
→ loop each active FAQ item
→ build_embed_text(intent + examples + answer + no-accent text)
→ embed_text() via Ollama bge-m3
→ HSET doc into Redis vector index
→ scan stale docs and delete
```

Vector index names:

```text
zeo:vec:faq
cfc:vec:faq
```

Vector doc key pattern:

```text
{index_name}:doc:{source_id}:{intent}
```

Current embedding text:

```text
intent + question_examples + answer + no-accent version
```

Good:

- Có cả bản tiếng Việt có dấu và không dấu.
- Dữ liệu stale được xóa khi sync lại.
- Không embed row inactive/thiếu answer/thiếu intent.

Risk:

- Schema Redis index hiện chưa index full metadata như `question_examples`, `learning_tags`, `profile_slots`, `escalation_policy`, `audience`.
- Mapping có lưu `question_examples`, `learning_tags`, `profile_slots`, `escalation_policy`, nhưng không lưu `audience`.
- RAG rerank có đọc `audience`, nhưng với vector docs từ Python field này có thể rỗng. Do n8n đã lọc `audience=customer` nên rủi ro không lớn, nhưng metadata không thống nhất.

## 5. Current Retrieval Flow

File: `rag_search.py`

Flow:

```text
semantic_search(query, brand, top_k)
→ _build_vi_embedding_query()
→ embed_text(query) bằng Ollama bge-m3
→ FT.SEARCH Redis KNN top_k
→ parse fields
→ convert cosine distance to similarity score
→ _rerank_results()
→ compute confidence by threshold + score margin
→ return best + parsed candidates
```

Current thresholds từ settings:

```text
high_confidence_threshold = 0.78
medium_confidence_threshold = 0.55
```

Tuy nhiên `chat_pipeline.py` đang dùng tier riêng:

```text
best_score >= 0.65 → high nếu guardrail pass
best_score >= 0.52 → medium nếu guardrail pass
else fallback
```

Good:

- Có query expansion tiếng Việt.
- Có alias như `sp`, `sdt`, `cty`, `web`, `shoppe`, `sopi`.
- Có rerank theo overlap token.
- Có boost entity như `zif`, `pano`, `oplus`, `npk`.
- Có phạt catalog tổng nếu query có entity cụ thể.
- Có phạt address khi query là company overview.
- Có phạt nội dung agent/internal khi khách hỏi social channel.

Risk:

- Chưa có exact match table riêng cho product/entity/SKU.
- Chưa có BM25/keyword retrieval riêng.
- Chưa có metadata filter mạnh theo category/risk/brand/audience.
- Confidence hiện vẫn chủ yếu dựa vào score đã chỉnh tay.
- Chưa có candidate consistency check.

## 6. Current Session / Memory Flow

### 6.1 Python Memory

Redis keys:

```text
{brand}:customer:messenger:{sender_id}
{brand}:session:messenger:{sender_id}
{brand}:history:messenger:{sender_id}
```

Profile fields Python đang lưu khi khách gửi SĐT:

```json
{
  "brand": "ZEO",
  "sender_id": "...",
  "fb_name": "...",
  "phone": "...",
  "customer_phone": "...",
  "area": "...",
  "customer_location": "...",
  "lead_stage": "lead_ready",
  "last_intent": "contact_phone_provided",
  "last_seen_at": "..."
}
```

Session fields Python đang lưu:

```json
{
  "sender_id": "...",
  "brand": "ZEO",
  "last_user_message": "...",
  "last_bot_reply": "...",
  "last_intent": "...",
  "lead_stage": "...",
  "last_seen_at": "..."
}
```

History list:

```json
{
  "user_message": "...",
  "bot_reply": "...",
  "intent": "...",
  "timestamp": "..."
}
```

History giữ tối đa 50 tin bằng `LTRIM -50 -1`.

Observed limitation:

- Python session chưa lưu structured conversation state.
- Chưa có `active_entities`, `current_product`, `current_category`, `last_products_shown`, `pending_reference`, `last_source_id`.
- Chưa thấy TTL/expire cho Python session/profile trong `chat_pipeline.py`.
- Chưa có resolver cho `cái đầu tiên`, `loại đó`, `con hồi nãy`, `cái trên`, `còn hong`.

### 6.2 n8n Legacy Memory

n8n fallback flow có state giàu hơn Python:

- `conversation_summary`
- `last_source_id`
- `current_product`
- `current_topic`
- `pending_slots`
- `history`
- `response_plan`
- `nlu`
- `order_items`

Save session trong n8n dùng Redis `expire: true` ở workflow, nhưng cần kiểm tra TTL cụ thể trong exported workflow/n8n config.

Risk:

- Python primary path và n8n fallback path không lưu state cùng schema.
- Khi cần build conversation brain, nên thống nhất một schema memory duy nhất, ưu tiên nằm trong Python để runtime chính và fallback không lệch.

## 7. Current Fallback Flow

### 7.1 Python Fallback

Các nguyên nhân fallback trong Python:

- Empty input → hỏi lại nhu cầu.
- Redis/vector index lỗi → RAG trả low/error.
- Score thấp hoặc guardrail fail.
- Purchase/price signal nhưng chưa đủ sản phẩm → trả intent giá cần thêm thông tin.
- Wholesale signal → trả intent đại lý/lấy sỉ.
- Otherwise → generic fallback.

Generic fallback hiện tại:

```text
Dạ câu hỏi này mình chưa có sẵn thông tin chính xác trong hệ thống...
```

Python fallback side effects:

- `notify_admin_unanswered(...)`
- `save_session(...)` intent `unanswered_query`

### 7.2 RAG Fallback

Trong `rag_search.py`, nếu confidence low:

- Nếu best answer rỗng hoặc score < 0.35 thì dùng fallback message.
- Push item vào `{brand}:learning:queue`.
- Notify admin.

Risk:

- Có thể double notify: RAG low confidence notify và chat_pipeline fallback notify.
- Learning queue record từ `rag_search.py` còn ít fields: query, confidence, brand, bot_reply, timestamp.
- Chat pipeline fallback không push structured queue trực tiếp, chủ yếu notify admin.

### 7.3 n8n Fallback

n8n legacy flow có nhiều `fallbackReason`:

- `knowledge_snapshot_missing`
- `low_confidence`
- `clarification_needed`
- `price_unverified`
- `bot_answer_complaint`
- `sensitive_case`
- `out_of_scope`
- `unsupported_input_language`
- `prompt_injection`
- `lead_contact_ready`
- `order_contact_missing`
- `distributor_availability_check`

Good:

- n8n fallback có reason code tốt hơn Python.

Risk:

- Reason code chưa được thống nhất với Python response.
- Khi FastAPI success, n8n fallback reason không chạy.

## 8. Current Strengths

- Source of truth rõ: Google Sheet.
- Data sync có validation cơ bản: active, brand, answer, intent, duplicate intent, question examples.
- Python path nhanh và rõ hơn n8n legacy path.
- Có Redis vector index và BGE-M3 phù hợp tiếng Việt.
- Có no-accent normalization.
- Có profile/session cơ bản.
- Có intent-first router cho các lỗi thực tế gần đây.
- Có rerank nhẹ giúp giảm mismatch entity/company/address.
- Có admin dashboard và learning queue endpoint.
- Có eval suite và `test.md`.

## 9. Current Bottlenecks / Issues

### CRITICAL - Memory chưa đủ cho multi-turn reference

Evidence:

- `chat_pipeline.py` chỉ lưu session: `last_user_message`, `last_bot_reply`, `last_intent`, `lead_stage`.
- Không thấy state như `last_products_shown`, `active_entities`, `current_product`, `current_category`.

Current behavior:

- Các câu như `cái đầu tiên giá nhiu`, `con hồi nãy ship cần thơ hong`, `còn hong` chưa thể resolve chắc trong Python path.

Recommended fix:

- Thiết kế `conversation_state` trong Redis.
- Lưu structured entities sau mỗi answer.
- Thêm reference resolver chạy trước intent/router/RAG.

Expected impact:

- Tăng mạnh khả năng hội thoại tự nhiên và follow-up.

### HIGH - Runtime có 2 logic chat khác nhau

Evidence:

- n8n gọi `GoiFastApiChatPipeline` trước.
- Nếu lỗi thì chạy legacy NLU/RAG/session trong n8n.
- Python và n8n có các rule/fallback/session schema khác nhau.

Current behavior:

- Khi Python chạy ổn: bot theo Python logic.
- Khi Python lỗi: bot theo n8n legacy logic, có thể trả khác.

Recommended fix:

- Quyết định Python là canonical runtime.
- n8n fallback chỉ nên gửi lỗi/handoff tối giản hoặc gọi cùng Python fallback endpoint.
- Nếu giữ legacy n8n, cần đồng bộ schema và test.

Expected impact:

- Giảm hành vi không nhất quán.

### HIGH - Retrieval chưa hybrid đầy đủ

Evidence:

- `rag_search.py` dùng `FT.SEARCH ... KNN`.
- Rerank hiện là rule-based sau vector.
- Chưa thấy exact entity dictionary/BM25 merge riêng trong Python path.

Current behavior:

- Query ngắn hoặc entity cụ thể có thể vẫn phụ thuộc vào router/rerank thủ công.

Recommended fix:

- Thêm entity dictionary từ Sheet/config.
- Thêm exact match stage.
- Thêm keyword/BM25 stage bằng RediSearch text fields.
- Merge candidates trước rerank.

Expected impact:

- Tăng Top1 accuracy, giảm hallucination do retrieval sai.

### HIGH - Learning queue thiếu trace đầy đủ

Evidence:

- `rag_search.py` push learning queue chỉ có query, confidence, brand, bot_reply, timestamp.
- n8n legacy queue có record giàu hơn nhưng chỉ chạy fallback path.

Current behavior:

- Khi bot trả sai hoặc fallback, thiếu đủ thông tin để debug: normalized query, top candidates, scores, guardrail reason, selected source.

Recommended fix:

- Chuẩn hóa learning event trong Python.
- Include request_id, normalized query, detected intent, candidates, selected source, fallback reason, session snapshot.

Expected impact:

- Admin/AI có thể cải thiện Sheet có hệ thống.

### MEDIUM - Google Sheet schema chưa đủ semantic metadata

Current schema tốt cho FAQ, nhưng thiếu:

- `keywords`
- `negative_keywords`
- `entity_aliases`
- `required_entities`
- `related_intents`
- `verification_status`
- `valid_from`
- `valid_until`

Recommended fix:

- Không migration vội.
- Thêm cột mới tương thích ngược.
- Update n8n normalize và Python sync đọc thêm metadata.

### MEDIUM - Confidence engine còn đơn giản

Evidence:

- RAG confidence dựa score/margin.
- Chat pipeline dùng threshold 0.65/0.52 và guardrail.

Recommended fix:

- Confidence phải xét: vector score, exact match, keyword score, entity match, brand match, risk, context completeness, candidate consistency.

### MEDIUM - LLM chưa được dùng như classifier có kiểm soát trong Python path

Evidence:

- n8n legacy có Ollama NLU.
- Python primary path chủ yếu regex/router + RAG.

Recommended fix:

- Giữ regex deterministic cho phone/greeting/thanks/exact.
- Thêm controlled LLM classifier JSON schema cho semantic intent/entity.
- Classifier không được trả lời khách.

### LOW - Output composer còn chủ yếu trả answer sheet trực tiếp

Good:

- Giảm hallucination.

Limitation:

- Câu có thể chưa tự nhiên theo context.

Recommended fix:

- Grounded answer composer chỉ nhận verified knowledge và response rules.
- Output structured: `answer`, `used_source_ids`, `needs_escalation`.

## 10. Scorecard Hiện Trạng

| Area | Score | Evidence |
|---|---:|---|
| Vietnamese Understanding | 6.5/10 | Có normalization/aliases và BGE-M3, nhưng slang/context ngắn vẫn cần resolver/classifier |
| Intent Classification | 6/10 | Intent-first router đã cải thiện, nhưng còn regex nhiều và chưa có classifier schema |
| Entity Resolution | 4.5/10 | Có entity rules ZIF/PANO/Oplus/NPK, chưa có dictionary chính thức |
| Conversation Memory | 3.5/10 | Python chỉ nhớ last intent/message/phone/area, chưa có structured state |
| Retrieval | 6/10 | Vector BGE-M3 tốt, nhưng chưa hybrid exact/BM25 |
| Reranking | 5.5/10 | Có rerank rule-based, chưa có candidate consistency/reranker model |
| Grounding | 6.5/10 | Trả từ Sheet/Redis, có guardrail; nhưng confidence engine còn đơn giản |
| Natural Output | 6/10 | Có prettify; chưa có composer contextual chuẩn |
| Learning Loop | 4.5/10 | Có queue/admin endpoint, record chưa đủ trace và chưa clustering |
| Observability | 4/10 | Có score/intent trong response, thiếu request trace đầy đủ |
| Performance | 7/10 | Python fast path nhanh, Redis/Ollama local; thêm classifier/hybrid cần benchmark |

Target sau P0/P1:

| Area | Target |
|---|---:|
| Vietnamese Understanding | 8/10 |
| Intent Classification | 8/10 |
| Entity Resolution | 8/10 |
| Conversation Memory | 8/10 |
| Retrieval | 8/10 |
| Reranking | 7.5/10 |
| Grounding | 8.5/10 |
| Learning Loop | 7/10 |
| Observability | 8/10 |

## 11. Trả Lời Các Câu Hỏi Bắt Buộc Sau Discovery

### Runtime path thực tế của một Messenger message là gì?

Đường chính:

```text
Messenger → n8n LocDauVao → POST /api/chat-pipeline → Python process_chat_pipeline → PrepareMessengerReply → Messenger reply
```

Đường fallback khi FastAPI lỗi:

```text
Messenger → n8n LocDauVao → FastAPI error → n8n Redis profile/session → n8n Ollama NLU → n8n JS RAG → optional Ollama rewrite → guardrail → save Redis → Messenger reply
```

### Chatbot hiện tại lưu memory gì và còn thiếu gì?

Đang lưu:

- Phone.
- Area/location.
- Lead stage.
- Last user message.
- Last bot reply.
- Last intent.
- History list tối đa 50 item.

Còn thiếu:

- Active product/entity.
- Current category/topic chuẩn.
- Last products shown.
- Reference map cho `cái đầu`, `cái thứ 2`, `loại đó`.
- Structured conversation summary trong Python path.
- Pending slots theo intent.
- Last selected source/candidates.

### Tại sao query ngắn/context-dependent thất bại?

Vì Python primary path chưa có reference resolver. Query ngắn như `giá?`, `còn hong?`, `ship cần thơ hong?`, `cái đầu tiên` không tự đủ nghĩa. Nếu không resolve bằng state trước retrieval, vector search hoặc regex sẽ đoán theo từ khóa chung, dễ fallback hoặc match sai.

### Regex router đang chi phối hệ thống đến mức nào?

Khá nhiều. Python path hiện dùng regex/router cho:

- greeting/thanks/ack
- phone/profile recall
- complaint
- language request
- correction
- competitor/cross-brand
- new product
- proof/certification
- contact/company/address
- social channel
- usage/safety
- specific product
- website/price/wholesale/catalog/hours/policy

Điều này giúp chặn lỗi nhanh nhưng không scale tốt nếu số intent/product tăng lớn.

## 12. Recommended Phase 2 Diagnosis Plan

Chạy benchmark có trace cho từng case:

```text
RAW QUERY
NORMALIZED
SESSION BEFORE
RESOLVED QUERY
DETECTED INTENT
ENTITIES
ROUTER RESULT
VECTOR QUERY
TOP K
RERANKED TOP K
GUARDRAIL RESULT
SELECTED KNOWLEDGE
FINAL RESPONSE
SESSION AFTER
```

Nhóm case cần ưu tiên:

- Query ngắn: `giá?`, `sdt?`, `zalo?`, `pano?`, `ship?`
- No accent/slang: `ship can tho dc hong`, `bn tien`, `con hang k`
- Product/entity: `ZIF`, `PANO`, `Oplus`, `NPK`, `hữu cơ`
- Context-dependent: `cái đầu tiên`, `loại đó`, `con hồi nãy`
- Out-of-scope: `Omo`, `Ariel`, sản phẩm không có trong Sheet
- High-risk: giá, liều lượng phân bón, hóa chất vào mắt, chứng nhận, địa chỉ/hotline

## 13. Recommended Phase 3 Design Direction

Không rewrite toàn bộ. Giữ stack hiện tại và thêm từng lớp:

```text
Input
→ Normalize
→ Conversation State Loader
→ Reference Resolver
→ Deterministic Fast Path
→ Controlled LLM Intent/Entity Classifier
→ Query Planner
→ Exact Match
→ Keyword/BM25 Search
→ BGE-M3 Vector Search
→ Candidate Merge
→ Rerank
→ Grounding Confidence Engine
→ Grounded Answer Composer
→ Memory Update
→ Learning Queue/Observability
```

## 14. Recommended Implementation Order

P0:

- Thiết kế unified `conversation_state` trong Python.
- Lưu `active_entities`, `current_product`, `current_category`, `last_products_shown`, `last_source_id`.
- Thêm reference resolver.
- Thêm trace object cho mỗi request.

P1:

- Tạo entity dictionary từ Sheet/config.
- Thêm exact match stage.
- Thêm keyword/BM25 stage bằng RediSearch text fields.
- Merge exact + keyword + vector candidates.

P2:

- Controlled LLM classifier JSON schema.
- Grounded answer composer.
- Clarification generator.

P3:

- Learning queue v2.
- Failure clustering.
- Admin review workflow.
- Eval baseline/compare before-after.

## 15. Acceptance Tests Cần Có Trước Khi Rollout Lớn

```text
PANO có những loại nào?
→ cái đầu tiên giá nhiu?

con hồi nãy ship cần thơ hong?

Có bột giặt Omo không?

1kg bột cho 5 bộ đồ được không?

sdt công tu

giới thiệu cty đi

còn hong?
```

Expected:

- Resolve context nếu có state.
- Không bịa giá/liều lượng.
- Không nhận nhầm competitor là sản phẩm của mình.
- Không trả address khi hỏi company overview.
- Nếu thiếu context thì hỏi clarification.

## 16. Phase 1 Conclusion

Hệ thống hiện tại không yếu ở dữ liệu nền. Google Sheet, Redis, BGE-M3 và FastAPI đều là nền tốt.

Điểm yếu nằm ở lớp conversational intelligence:

- Chưa có state hội thoại đủ giàu.
- Chưa resolve reference trước retrieval.
- Chưa hybrid retrieval hoàn chỉnh.
- Chưa có confidence engine dựa nhiều tín hiệu.
- Chưa có trace đủ sâu để debug từng câu.

Kết luận kỹ thuật: bước tiếp theo nên là **P0 Conversation Brain**, không phải fine-tune model và không phải thêm vector database mới.
