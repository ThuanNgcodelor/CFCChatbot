# Kết luận và khuyến nghị cuối

Ngày audit: 2026-08-22  
Phạm vi kết luận: source/workspace và một số kiểm tra local read-only. Trạng thái n8n production, Facebook Messenger end-to-end và tải thực tế chưa được xác minh trong đợt này.

## Executive summary

ZeO/CFC đã vượt mức chatbot FAQ đơn giản: có deterministic business tools, structured product memory, lexical/vector retrieval, Redis state, guardrails và regression cases. Nền tảng hiện tại đủ tốt để cải tiến tuần tự; không cần rewrite hay thay stack.

Tuy nhiên chưa nên gọi hệ thống “production-grade zero hallucination”. Ba blocker là:

1. boundary bảo mật admin rất yếu;
2. một số câu trả lời/LLM output chưa có nguồn và validator;
3. data/state/test contracts chưa đủ để chứng minh đúng khi sync lỗi, nhiều worker, duplicate event hoặc câu ngoài case hiện có.

Ưu tiên trước mắt không phải “cho Ollama suy nghĩ hai lần”. Ưu tiên là làm cho mọi answer producer trả facts có nguồn, validate output, bảo vệ admin, publish data atomic và biến test thành release gate đáng tin.

## 1. Trạng thái bằng chứng

| Nhóm | Kết luận |
|---|---|
| `SOURCE` | Đã đọc trực tiếp FastAPI, chat pipeline, RAG, embedder, ingestor, matcher, admin domains, test runner và 8 workflow local |
| `LOCAL` | Redis container có 65 FAQ ZeO, 19 FAQ CFC, 52 catalog ZeO (49 stock/3 out), vector docs 65/19; snapshot TTL `-1`; catalog Redis mất badge |
| `LOCAL` | Unit discovery chạy 26/26 pass; FastAPI và Ollama không chạy ở lần kiểm tra cuối nên không chạy live integration/eval qua provider |
| `HISTORICAL` | Summary ghi các mốc eval 112/112 và scenario 48/55; các runner có tiêu chí/exit-code yếu nên không phải chứng nhận production |
| `PRODUCTION UNKNOWN` | Workflow local đều `active:false`; production n8n/Messenger/tunnel/Graph API chưa được kiểm tra |

## 2. Chấm điểm hệ thống hiện tại

Thang điểm phản ánh độ trưởng thành có bằng chứng, không chỉ số lượng tính năng.

| Năng lực | Điểm /10 | Giải thích |
|---|---:|---|
| Architecture | 7 | Single decision layer rõ, deterministic-first đúng hướng; trust/security/state boundaries thiếu |
| Code organization | 6 | Admin đã tách domain, matcher/RAG riêng; `chat_pipeline.py` vẫn lớn và order-sensitive |
| Data pipeline | 5 | Có Sheet→Redis→index; schema drift, non-atomic success và partial overwrite risk |
| Knowledge quality | 5 | Có schema/source ID ở FAQ; agent rows, unsupported hardcode và thiếu provenance/freshness |
| Retrieval | 6 | Lexical-first + KNN + filters; chưa benchmark Recall/MRR hoặc rank fusion |
| Vietnamese understanding | 6 | Nhiều alias/typo/slang cases; coverage dựa mạnh vào regex/test đã viết |
| Intent detection | 6 | Deterministic router hữu ích, optional planner; planner live mặc định off/chưa benchmark |
| Context resolution | 6 | Ordinal/pronoun/product context đã có; chưa đủ cross-list/version cases |
| Conversation memory | 4 | Structured state tốt nhưng process-local cache/lock, async write, no TTL/version/CAS |
| Reranking | 4 | Heuristic explainable nhưng chưa learned reranker/hard-negative evaluation |
| Grounding | 3 | Structured tools grounded; LLM/hardcoded answer paths chưa có complete source envelope/validator |
| Hallucination prevention | 3 | Có guardrails nhưng còn absolute unsupported claims và facts-empty generation path |
| Fallback | 5 | Có degraded paths và Telegram; learning queue producer chưa end-to-end |
| Performance | 5 | Historical fast-path rất nhanh; không có current live p50/p95/p99 hay component budget |
| Concurrency | 3 | Per-process lock không bảo vệ multi-worker; no idempotency/CAS/load proof |
| Caching | 4 | FAQ/catalog/session RAM cache có ích; stale/version/invalidation/query embedding gaps |
| Observability | 4 | Có last trace/analytics rời rạc; trace schema, retrieval candidates, validator/timing chưa đồng nhất |
| Evaluation | 4 | Nhiều case/unit; weak assertions, fake planner, nonzero-exit và retrieval/faithfulness metrics thiếu |
| Maintainability | 5 | Documentation tốt và module hóa một phần; duplicated schemas/hardcodes/legacy paths còn nhiều |
| Scalability | 4 | Redis/FastAPI có nền tảng; process-local state, Ollama queue và sync sequential là giới hạn |
| Production readiness | 3 | Admin security/grounding/data publication/state correctness là blockers; production chưa verify |

Điểm không phải KPI tuyệt đối. Sau P0/P1, chấm lại bằng cùng rubric và artifact test.

## 3. Current vs Target

| Area | Current | Target | Điều kiện |
|---|---|---|---|
| Admin access | `/admin/*` không auth, CORS rộng | Auth + RBAC + redacted settings + audit | P0 blocker |
| Factual data | Facts nằm trong Sheet/catalog và một số hardcode | Canonical records + source/version/freshness | P0 |
| Sync | Ghi snapshot/index/cache theo nhiều path | Validate staging → atomic publish → success | P0 |
| Audience | Filter không đồng nhất | `customer` allowlist end-to-end | P0 |
| Generation | Prompt yêu cầu bám facts | FactEnvelope + deterministic validator | P0 |
| Retrieval | Lexical early-return hoặc vector KNN + heuristic | Baseline measured; optional BM25+dense+RRF+reranker | Chỉ khi metric tăng |
| Product facts | Python matcher trên snapshot | Vẫn deterministic, typed schema + freshness | Giữ nguyên nguyên tắc |
| Memory | RAM/Redis async, per-process lock | Redis authority + TTL + turn/version + CAS | P2 |
| Duplicate event | `message_id` không dùng | Idempotency key/outcome cache | P2 |
| Learning | Telegram; exporters pop queue | Producer + durable stream/ack + idempotent review | P3 |
| Ollama | Per-call clients, unknown live capacity | Shared client, semaphore, warm model, measured queue | P4 |
| Tests | Intent/keyword pass counts | Typed facts/docs/forbidden claims + nonzero gates | P5 |
| Production evidence | Local files and historical notes | Canary/E2E/runbook evidence by deployed version | Release gate |

## 4. Năm thay đổi ưu tiên tuyệt đối

### 1. Khóa admin và bỏ general shell capability

Lý do: đây là rủi ro Critical độc lập với độ thông minh của bot. Anonymous access có thể chạm settings, PII và workflow mutations; LLM tool có shell làm tăng blast radius.

Kết quả mong đợi: unauthorized request bị 401/403, secrets redacted, privileged action có scope/audit/human control.

### 2. FactEnvelope + output validator + dọn unsupported claims

Lý do: prompt “không bịa” không đủ. Giá/link/safety claim phải so exact với source trước khi phát.

Kết quả mong đợi: `UnsupportedClaimRate = 0` trên critical set; AI down/invalid output vẫn có grounded template.

### 3. Canonical schema và atomic versioned sync

Lý do: current workflow/admin/fallback không bảo toàn cùng fields; badge/audience/source version có thể mất, partial sheet có thể thay active snapshot.

Kết quả mong đợi: malformed data không ảnh hưởng active version; mọi answer trace được version; audience leak = 0.

### 4. Idempotent Messenger + Redis versioned state

Lý do: “thông minh đa lượt” không ổn nếu duplicate/restart/multi-worker làm sai lượt hoặc stale context.

Kết quả mong đợi: one event → one turn/reply, burst ordered, restart/multi-worker giữ state đúng.

### 5. Evaluation/observability thành release gate

Lý do: 112/112 hiện chứng minh case đã khai báo theo matcher của runner, không đo retrieval/grounding/security đầy đủ.

Kết quả mong đợi: Recall@K/MRR/faithfulness/range/unsupported/security/p95 được đo theo version; runner fail thật khi gate fail.

## 5. Ba câu hỏi quan trọng về “độ thông minh”

### Vì sao có Ollama mà bot vẫn trả lời sai?

Ollama chỉ là một component. Nếu router chọn sai tool, context state stale, catalog mất field, retrieval chọn nhầm fact hoặc prompt không có facts, model không thể tự biết nguồn đúng. Cho model chạy hai lần còn có thể làm tăng latency và tạo thêm cơ hội bịa.

### Có nên để Ollama đi hai lần không?

Không mặc định. Hai pass hợp lý duy nhất là:

1. pass 1 tạo structured plan trong vùng mơ hồ;
2. code/tool lấy facts;
3. pass 2 rewrite facts;
4. deterministic validator kiểm tra.

Nếu query đã rõ hoặc chỉ hỏi giá/link, bỏ cả hai pass và dùng deterministic response.

### Có nên thêm hybrid search/reranker không?

Có thể, nhưng sau golden retrieval baseline. Corpus FAQ customer hiện nhỏ; dữ liệu, grounding và state correctness có impact lớn hơn. Thử BM25+dense+RRF ở shadow, chỉ giữ nếu Recall/MRR tăng mà p95 nằm trong budget.

## 6. Trả lời năm câu bắt buộc

### 1. Ba vấn đề lớn nhất khiến chatbot hiện tại chưa thông minh là gì?

1. **Không có factual contract end-to-end:** một số path lấy facts đúng, path khác dùng hardcode hoặc generation khi facts rỗng; output chưa được validate theo source.
2. **Context/data state chưa đáng tin khi môi trường thay đổi:** schema sync lệch, cache/version thiếu, duplicate event và multi-worker có thể tạo stale context.
3. **Evaluation chưa đo đúng thứ cần tối ưu:** pass intent/keyword chưa cho biết retrieved document có đúng, claims có supported và latency/concurrency có đạt hay không.

Bảo mật admin là blocker Critical cho production, dù không trực tiếp là nguyên nhân NLU “kém thông minh”.

### 2. Ba thay đổi mang lại improvement lớn nhất là gì?

1. Canonical knowledge/product schema + versioned atomic publication.
2. FactEnvelope + deterministic claim validator + no-generation-when-no-facts.
3. Golden multi-turn/retrieval dataset + unified trace, sau đó mới tối ưu exact/hybrid/reranking theo evidence.

### 3. Những công nghệ nào không nên thêm vào?

- GraphRAG/knowledge graph: chưa có multi-hop graph use case hoặc corpus đủ phức tạp.
- Full agentic RAG/customer autonomous agent: tăng nondeterminism và risk, trong khi tools hiện rõ.
- LangChain/LangGraph migration: không giải quyết schema/grounding/state blockers và tạo thêm abstraction.
- Vector DB mới: Redis đã phục vụ state/snapshot/KNN; chưa có benchmark chứng minh giới hạn.
- Embedding/LLM mới: chưa có golden set để chứng minh tốt hơn `bge-m3`/current model.
- LLM judge online trên mọi câu: tăng latency/cost và không thay security validator deterministic.

### 4. Nếu chỉ được làm năm thay đổi thì nên làm gì?

1. Admin auth/RBAC/redaction và loại general shell tool.
2. Gỡ unsupported hardcodes, thêm FactEnvelope/claim validator.
3. Canonical versioned schema + staged atomic sync + audience allowlist.
4. `message_id` idempotency + Redis `turn_seq/session_version/CAS/TTL`.
5. Sửa evaluation/trace/release gates; đo baseline trước hybrid experiment.

### 5. Kiến trúc cuối cùng nên như thế nào?

```text
Messenger
→ n8n ingress validation/idempotent forwarding
→ FastAPI public chat boundary
→ Redis ordered/versioned conversation state
→ Vietnamese normalizer + structured QueryPlan
→ deterministic tool cho price/stock/link/policy/safety
   hoặc measured FAQ/document retrieval
     (exact/lexical + dense KNN; RRF/reranker nếu benchmark thắng)
→ FactEnvelope có source/version/freshness
→ deterministic template hoặc controlled Ollama rewrite
→ deterministic claim/privacy/safety validator
→ response + unified trace + durable learning event
→ n8n gửi Graph API với bounded retry

Sheet/CSV
→ staging validation/dedupe/version
→ build/verify snapshot + index
→ atomic active switch
→ cache invalidation
→ success/audit
```

Admin nằm ở boundary riêng có authentication/RBAC; LLM không nắm quyền admin và không chạy shell chung.

## 7. Go / No-Go

### No-Go cho public rollout rộng nếu còn một trong các điều sau

- admin mutation/settings/customer data truy cập anonymous;
- raw secrets/cookie vẫn được source-control hoặc trả qua API;
- unsupported price/stock/link/safety claims;
- partial sync có thể thay active snapshot;
- customer retrieval chạm `agent/internal` rows;
- duplicate/restart/multi-worker state tests fail;
- critical suite hoặc security suite fail;
- không có rollback theo deployed version.

### Go cho controlled canary khi

- P0 gates pass;
- unit + critical regression + integration dependencies pass;
- current data version/health rõ;
- p95 và overload behavior đã đo trên hardware thật;
- one small traffic segment được theo dõi với rollback trigger;
- production n8n workflow ID/credentials/status được xác minh trực tiếp, không suy từ local `active:false`.

## 8. Hành động kế tiếp đề xuất

1. Review [03_WEAKNESSES.md](03_WEAKNESSES.md) và quyết định owner cho ba P0.
2. Freeze behavior bằng [08_RAG_EVALUATION_PLAN.md](08_RAG_EVALUATION_PLAN.md) trước code change.
3. Triển khai Release A trong [07_IMPLEMENTATION_ROADMAP.md](07_IMPLEMENTATION_ROADMAP.md).
4. Chạy performance baseline theo [09_PERFORMANCE_PLAN.md](09_PERFORMANCE_PLAN.md).
5. Chỉ mở experiment hybrid/reranker sau baseline và P0.

Đây là audit/architecture recommendation; chưa có source behavior nào được thay đổi trong đợt này.
