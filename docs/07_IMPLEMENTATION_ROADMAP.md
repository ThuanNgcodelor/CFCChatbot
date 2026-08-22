# Roadmap triển khai

Ngày lập: 2026-08-22  
Nguyên tắc: sửa theo risk và evidence, giữ behavior đã có bằng regression, không triển khai framework/model mới chỉ vì xu hướng.

## Cách đọc roadmap

- `P0` là blocker trước khi public/production rollout rộng.
- Mỗi phase có deliverable, acceptance gate và rollback boundary.
- Ước lượng effort tương đối: `S` (≤2 ngày kỹ thuật), `M` (3–7 ngày), `L` (1–3 tuần), cần điều chỉnh theo người triển khai và môi trường thật.
- Không gộp security, data migration và model experiment thành một release.

## P0 — Critical safety và production boundary

### P0.1 Bảo vệ Admin API

Effort: `M`  
Impact: Critical

Việc làm:

1. Tách public chat routes và `/admin/*`.
2. Thêm authentication chuẩn; RBAC scopes cho read customer, knowledge write, n8n deploy.
3. Redact secret khỏi `GET /admin/settings` và logs.
4. CORS allowlist, request-size limits và audit log cho mutation.
5. Xóa/disable general shell tool; nếu thật sự cần thì thay bằng allowlisted operations có typed arguments và human approval.
6. Rotate/revoke browser auth state trong `scripts/shopee_auth.json`, đưa secret vào runtime store và xử lý Git history theo quy trình được duyệt.

Gate:

- mọi `/admin/*` nhạy cảm trả 401/403 khi thiếu/sai quyền;
- settings response không chứa raw token/password/cookie;
- customer export/deploy/toggle không thể gọi bằng anonymous request;
- security tests cho prompt injection không thể kích hoạt shell/tool đặc quyền.

### P0.2 Gỡ unsupported claims và thêm grounding contract

Effort: `M`  
Impact: Critical

Việc làm:

1. Inventory mọi answer producer và hardcoded claim.
2. Chuyển claim đã được duyệt về Sheet/catalog với `source_id`, risk và version.
3. Loại hoặc đổi giọng thận trọng cho claim không có nguồn, đặc biệt `100%`, `hoàn toàn`, an toàn da liễu, vi mạch, vết máu.
4. Chuẩn hóa `FactEnvelope` cho deterministic tool/RAG.
5. Validator số tiền, %, URL, product ID/name, stock wording, hotline và safety absolutes.
6. Không gọi synthesizer khi facts rỗng; fallback/clarify/transfer admin.

Gate:

- `UnsupportedClaimRate = 0` trên high-risk golden set;
- mọi price/link/stock claim map được về source version;
- output bị validator reject không được gửi khách;
- deterministic fallback vẫn hoạt động khi tất cả AI provider down.

### P0.3 Sửa data publication và audience isolation

Effort: `M`  
Impact: Critical/High

Việc làm:

1. Canonical schema dùng chung cho n8n, admin sync, CSV fallback và matcher.
2. `audience=customer` allowlist tại ingest, index, cache và response.
3. Validate required fields, types, duplicate intent/product ID, URL host, price, stock và abnormal row-count delta.
4. Giữ badge/rank, `source_version`, `as_of`, content hash.
5. Staging snapshot/index, smoke check, rồi atomic active pointer.
6. Chỉ ghi sync success sau vector rebuild + cache invalidation pass.
7. Sửa hoặc vô hiệu admin direct-sync path cho đến khi tương đương validator chuẩn.

Gate:

- toàn bộ 16 dòng ZeO `audience=agent` không thể tới customer retrieval;
- malformed/partial Sheet bị reject và active snapshot cũ giữ nguyên;
- 52-row catalog round-trip không mất badge/item ID/link/stock;
- bestseller/new-arrival không dùng row order để giả ranking.

## P1 — Retrieval quality có benchmark

Effort tổng: `M–L`

### P1.1 Xây golden retrieval baseline

- Chọn transcript thật đã ẩn danh, typo, không dấu, SKU, policy, negative/cross-brand.
- Annotate `expected_documents`, `expected_facts`, `must_not_retrieve`.
- Đo riêng exact/lexical, dense KNN và routed pipeline: Recall@1/3/5, MRR, nDCG@5, brand/audience violation.

### P1.2 Cải thiện metadata/exact lookup

- Typed brand/category/audience/risk/product filters.
- Entity aliases/negative keywords trong Sheet thay vì tăng regex vô hạn.
- Exact SKU/item ID/size lookup trước semantic retrieval.
- Product lookup vẫn deterministic.

### P1.3 A/B hybrid retrieval

- Prototype BM25/FTS + dense KNN, RRF ở application layer.
- Nếu runtime Redis >=8.4, benchmark thêm `FT.HYBRID`; không nâng Redis chỉ để dùng lệnh này nếu application fusion đủ.
- Chỉ thử multilingual cross-encoder trên top 10–20 nếu fusion vẫn có precision thấp.

Gate:

- Recall@5 ≥ 95% trên critical FAQ hoặc tăng ≥5 điểm phần trăm so baseline;
- MRR/nDCG tăng có ý nghĩa trên hard set;
- `must_not_retrieve`/audience violation = 0;
- p95 retrieval không vượt budget;
- nếu không có improvement, bỏ prototype và giữ baseline đơn giản.

## P2 — Conversation intelligence và state correctness

Effort tổng: `L`

### P2.1 Messenger idempotency

- Dùng `message_id` làm Redis idempotency key có TTL.
- Cache request outcome đủ để retry không tạo thêm turn/reply.
- n8n bỏ echo/empty/unsupported event trước FastAPI hoặc FastAPI reject rõ.

### P2.2 Versioned conversation state

- Thêm `session_version`, `turn_seq`, `last_query`, `updated_at`, TTL.
- Redis là authority; write critical state trước response.
- CAS/transaction/Lua ngăn stale write.
- Distributed ordering hoặc queue theo sender cho multi-worker.
- RAM cache chỉ là read optimization theo version, không là source of truth.

### P2.3 Reference resolver contract

- Chuẩn hóa reference theo `product_id`, list version và rank.
- Re-read current catalog by ID trước price/link/stock response.
- Test `cái số N/nó/loại đó` qua budget, bestseller, product category và flow interruption.
- Explicit new entity phải thắng stale context.

Gate:

- duplicate event không nhân đôi turn/reply;
- 5 message burst cùng sender giữ đúng order;
- restart và 2 worker không mất/ghi đè state;
- reference resolution ≥ 95% trên golden multi-turn set;
- stale price/link test = 0 lỗi.

## P3 — Answer quality, fallback và learning loop

Effort tổng: `M`

### P3.1 Controlled generation

- Deterministic template cho critical facts.
- Ollama chỉ nhận redacted FactEnvelope, temperature thấp và structured constraints.
- Query planner schema/allowlist; `off → shadow → assist` theo metric.
- Không gửi data/prompt ra cloud provider nếu chưa có data policy/explicit configuration.

### P3.2 Granular fallback

- Chuẩn hóa `NO_MATCH`, `AMBIGUOUS`, `DEPENDENCY_DOWN`, `VALIDATION_FAILED`, `STALE_SOURCE`, `PRIVACY_OR_SAFETY`, `CONFLICTING_FACTS`.
- Mỗi reason có customer wording, admin action và retry policy riêng.
- Không nâng confidence từ low lên medium chỉ vì LLM tạo được một đoạn text.

### P3.3 Durable learning queue

- Producer trong chat pipeline tạo event đã redacted, có `event_id`.
- Dùng Redis Stream/consumer group hoặc pending/ack pattern.
- Export Sheet idempotent; retry không tạo duplicate, crash không mất event.
- Admin approval tạo version mới, không sửa active knowledge trực tiếp.

Gate:

- fallback trace coverage 100%; không generic unknown reason;
- validation fail sinh learning event đúng một lần;
- crash giữa read và append không mất event;
- approved answer chỉ active sau sync validation.

## P4 — Performance và resilience

Effort tổng: `M`

### P4.1 Instrument trước tối ưu

- Timing normalize/state/router/lexical/embed/KNN/rerank/generate/validate/n8n/Graph.
- p50/p95/p99, error/timeout/queue depth, Ollama load/eval duration.
- Tách fast-path, RAG path và LLM path.

### P4.2 Cheap optimizations

- Shared `httpx.AsyncClient` và connection pooling.
- Embedding hash/query cache bounded theo model version.
- Batch changed embeddings trong sync.
- Ollama warm-up/`keep_alive`, bounded semaphores và queue.
- Cache invalidation theo source version.

### P4.3 Failure/load tests

- 1/2/5/10 concurrent conversations;
- same-sender burst và many-sender load;
- Redis/Ollama/Sheet/n8n/Graph slow/down;
- malformed LLM JSON, stale cache, partial sync;
- 30–60 phút soak theo capacity thật.

Gate:

- deterministic p95 ≤ 150 ms local brain;
- RAG no-generation p95 ≤ 700 ms;
- LLM-assisted brain p95 ≤ 4 s trên hardware mục tiêu;
- zero unbounded queue/memory growth;
- overload trả bounded fallback/503 thay vì treo.

Các con số là target ban đầu, phải hiệu chỉnh từ benchmark thật; không phải SLA đã đạt.

## P5 — Evaluation và release gates

Effort tổng: `M`

1. Sửa mọi runner trả exit code khác 0 khi có FAIL/REVIEW vượt threshold.
2. Không dùng “ANY expected word” làm tiêu chí duy nhất.
3. Assertions typed cho intent, selected source/product, price constraint, URL, required facts, forbidden claims và fallback reason.
4. Tách unit/mocked, offline with fixtures, local integration, live dependency và Messenger E2E.
5. Snapshot current behavior trước mỗi refactor; review intentional changes.
6. Dashboard trends theo version, không chỉ một con số pass.

Gate release tối thiểu:

- unit 100%;
- critical regression 100%;
- all scenario không còn REVIEW không được duyệt;
- RangeViolationRate/UnsupportedClaimRate/audience leak = 0;
- retrieval/latency gates pass;
- security tests pass;
- production canary có rollback trigger.

## P6 — Advanced features, chỉ khi evidence yêu cầu

Các experiment có điều kiện:

- query rewrite cho ambiguous semantic FAQ;
- multi-query tối đa 2–3 biến thể;
- cross-encoder multilingual reranker;
- parent-child retrieval cho tài liệu dài;
- Redis native hybrid nếu version/benchmark phù hợp;
- LLM offline evaluator bổ sung human review.

Không nằm trong kế hoạch mặc định:

- GraphRAG;
- full agentic RAG cho customer chat;
- new vector database;
- LangChain/LangGraph migration;
- fine-tune LLM/embedding;
- knowledge graph;
- microservices split.

## Impact / Effort matrix

| Improvement | Impact | Effort | Risk khi làm | Priority |
|---|---|---|---|---|
| Admin auth/RBAC + bỏ shell tool | Critical | M | Medium | P0 |
| Remove unsupported claims + validator | Critical | M | Medium | P0 |
| Canonical schema + atomic sync + audience allowlist | Critical | M | Medium | P0 |
| Message idempotency | High | S–M | Low | P2 |
| Versioned Redis state/CAS/TTL | High | L | Medium | P2 |
| Evaluation runner nonzero + typed assertions | High | M | Low | P5, bắt đầu sớm |
| Unified trace/timing | High | M | Low | P4, bắt đầu sớm |
| Exact SKU/entity metadata lookup | High | S–M | Low | P1 |
| Durable learning stream | Medium–High | M | Medium | P3 |
| HTTP pooling + embedding cache/batch | Medium | M | Low | P4 |
| BM25 + RRF | Chưa biết, đo trước | M | Medium | P1 experiment |
| Cross-encoder reranker | Chưa biết | M–L | Medium/latency | P6 |
| Query rewrite/multi-query | Chưa biết | M | Hallucinated constraints | P6 |
| GraphRAG/new vector DB | Low với scope hiện tại | L | High | Không làm |

## Thứ tự release đề xuất

### Release A — Safe boundary

Admin auth/redaction, disable shell, unsupported claim cleanup, customer audience allowlist. Không thay retrieval ranking.

### Release B — Trusted data

Canonical schema, staged/atomic sync, source version/freshness, catalog badge preservation. Có migration + rollback về active snapshot cũ.

### Release C — Correct state

Idempotency, turn sequence, CAS/write-through, TTL; chạy restart/multi-worker/burst test.

### Release D — Measured quality

Golden set, trace, fixed runners và baseline report. Chỉ sau đó quyết định hybrid/reranker.

### Release E — Retrieval experiment

Shadow BM25/RRF/reranker, progressive rollout nếu vượt quality/latency gates.

## Definition of done toàn chương trình

- Mọi customer fact quan trọng truy được `source_id` + `source_version`.
- Không còn public unauthenticated admin mutation/secret exposure.
- Không còn unsupported price/stock/link/safety claim trong critical set.
- Sync fail không làm hỏng active data và không báo success giả.
- Duplicate/burst/restart/multi-worker tests pass.
- Evaluation có retrieval, grounding, conversation, security và latency metrics.
- Production state được kiểm chứng riêng; file local `active:false` không bị diễn giải thành production status.
