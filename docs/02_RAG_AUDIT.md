# Audit RAG hiện hành

Ngày audit: 2026-08-22  
Phạm vi: `ChatbotN8n/javis/server/`, dữ liệu FAQ/catalog, Redis local và các test hiện có.  
Nguyên tắc bằng chứng: `SOURCE` là đọc trực tiếp mã; `LOCAL` là chạy/đọc runtime máy này; `HISTORICAL` là kết quả được ghi lại từ lần trước; `PRODUCTION UNKNOWN` là chưa kiểm tra n8n/Messenger thật.

## Kết luận ngắn

Hệ thống hiện tại là một pipeline **deterministic-first + lexical-first + vector fallback**, không phải một RAG thuần LLM và cũng chưa phải hybrid retrieval đúng nghĩa. Cách này phù hợp với giá, link, tồn kho và policy vì dữ liệu cấu trúc nên do code tra cứu. Điểm yếu lớn nhất không nằm ở việc thiếu thêm model, mà ở bốn chỗ: dữ liệu chưa có hợp đồng/version thống nhất, retrieval chưa được đo bằng golden set, output LLM chưa có claim validator, và session/sync chưa đủ an toàn cho nhiều worker.

Khuyến nghị giữ `bge-m3` làm baseline. Chỉ thêm BM25/RRF hoặc reranker sau khi bộ evaluation chứng minh Recall@K/MRR hiện tại chưa đạt. Không thay Redis, không thêm GraphRAG và không biến toàn pipeline thành agentic RAG ở giai đoạn này.

## 1. Data ingestion và nguồn sự thật

### Hiện trạng

| Nguồn | Đường nạp hiện tại | Dữ liệu runtime | Đánh giá |
|---|---|---|---|
| FAQ ZeO/CFC | Google Sheet → n8n normalize → Redis snapshot → `/sync` | FAQ HASH + RediSearch index | Luồng chính hợp lý, nhưng success marker và rebuild chưa atomic |
| Catalog Shopee | Google Sheet → workflow Shopee → Redis snapshot → refresh RAM cache | Python lọc typed price/category/stock | Đúng hướng deterministic, nhưng schema giữa workflow/admin/matcher bị lệch |
| CSV local | Fallback khi Redis FAQ/catalog chưa sẵn sàng | Hot cache/matcher | Hữu ích để degraded mode, nhưng có nguy cơ nạp `audience=agent` |
| Markdown/text | `document_ingestor.py` → `*:vec:docs` | Document vector index riêng | Đã có ingestion/search nhưng chưa nối vào chat pipeline chính |

Evidence:

- `SOURCE` — `knowledge_sync.py:128-221` đọc snapshot, tạo embedding và upsert từng FAQ.
- `SOURCE` — `rag_search.py:552-769` phục vụ FAQ retrieval.
- `SOURCE` — `document_ingestor.py:53-126` chunk heading-aware; `:139-233` ingest/search document.
- `LOCAL` — Redis ngày audit có 65 FAQ ZeO, 19 FAQ CFC, 52 sản phẩm ZeO; các key snapshot không có TTL. Không có catalog CFC.

### Khoảng trống

1. Không có `schema_version`, `source_version`, checksum và thời điểm hiệu lực bắt buộc trên mọi row.
2. Sync ghi từng document vào index đang phục vụ; không có staging index + verify + atomic alias swap.
3. `active_doc_keys` được ghi nhận trước khi embedding thành công, nên một embedding lỗi có thể giữ lại document cũ mà lần sync vẫn khó nhận biết.
4. Lọc audience không đồng nhất: đường chuẩn n8n lọc `agent/internal`, nhưng Python sync chỉ loại giá trị chính xác `internal`; CSV fallback có thể nạp cả dòng `agent`.
5. Chưa có kiểm tra duplicate intent/product ID, conflict answer, empty critical fields, min-row threshold hoặc tỷ lệ giảm dữ liệu bất thường trước khi publish.

### Đích đề xuất

`Sheet/CSV → staging → schema validation → duplicate/conflict checks → version/hash → build index mới → smoke queries → atomic active pointer → cache invalidation → success metadata`.

Không đánh dấu `last-success` trước khi vector rebuild và cache refresh hoàn tất.

## 2. Chunking strategy

### FAQ và product

- FAQ đang dùng **một row = một retrieval unit**. Đây là lựa chọn đúng cho dữ liệu hỏi/đáp ngắn; không nên cắt tiếp theo số ký tự.
- Product là dữ liệu cấu trúc và đang được lọc trực tiếp bằng Python. Không nên biến giá, tồn kho, SKU, dung tích thành text chunks để LLM đoán.
- Nên enrich retrieval text của FAQ bằng `intent`, examples, entity aliases, category và bản không dấu, nhưng metadata phải còn ở typed fields để filter/trace.

### Tài liệu dài

`document_ingestor.split_markdown()` tách theo heading/paragraph, giới hạn 1.500 ký tự và overlap 150 ký tự. Đây là baseline tốt hơn fixed-size mù, nhưng còn thiếu:

- `parent_id`/section breadcrumb để trả lại context cha;
- loại tài liệu và policy version;
- chunk token count thay vì chỉ character count;
- kiểm tra một bảng/list bị tách làm mất nghĩa;
- benchmark kích thước/overlap theo tập câu hỏi thật;
- kết nối document retrieval vào chat pipeline.

Khuyến nghị: giữ FAQ row-based; product lookup typed; policy/document dùng heading-aware child chunks và trả kèm parent section. Không dùng một chunker duy nhất cho mọi loại dữ liệu.

## 3. Embedding

### Hiện trạng

- `embedder.py` gọi Ollama `/api/embed`, model cấu hình chính là `bge-m3`, dimension 1.024.
- Mỗi call tạo một `httpx.AsyncClient` mới, timeout 30 giây.
- Không có connection pool dùng chung, batch embedding, hash cache, retry có backoff, semaphore hoặc dimension validation trước `vec_to_bytes()`.
- Khi model chính trả 404, code thử `fallback_embed_model`; cấu hình có thể trỏ tới chat model. Không có bằng chứng mọi fallback là embedding model tương thích 1.024 chiều.

### Đánh giá model

`bge-m3` là baseline hợp lý cho tiếng Việt/multilingual. Paper gốc mô tả hỗ trợ dense, sparse và multi-vector, hơn 100 ngôn ngữ và input dài; nhưng project hiện chỉ dùng dense embedding qua Ollama. Việc model có các khả năng khác không có nghĩa hệ thống hiện đã dùng chúng.

Không thay model trước khi có benchmark riêng cho:

- có dấu/không dấu, typo và slang Việt;
- tên sản phẩm/SKU/quy cách;
- câu rất ngắn;
- policy gần nghĩa nhưng khác điều kiện;
- negative pairs dễ nhầm ZeO/CFC.

Gate cho model mới: tăng Recall@5 và MRR có ý nghĩa, `unsupported_claim_rate` không tăng, p95/VRAM nằm trong ngân sách.

Nguồn nghiên cứu: [BGE-M3 paper](https://arxiv.org/abs/2402.03216).

## 4. Retrieval hiện tại

### Luồng thực tế

```text
query
→ normalize + alias/rule router
→ fast lexical search trên FAQ hot cache
   ├─ score >= 0,75: trả lexical ngay
   └─ chưa chắc: embed query bằng bge-m3
       → Redis KNN cosine, có category filter tùy chọn
       → heuristic rerank theo entity/lexical/priority
       → confidence theo fixed threshold + score margin
→ nếu Ollama/Redis lỗi: degraded lexical fallback
```

Evidence: `rag_search.py:236-433`, `:435-550`, `:552-769`.

### Điểm tốt

- Lexical-first giảm gọi embedding cho câu rõ ràng và giúp tên riêng/SKU.
- Category filter được áp trước KNN khi caller cung cấp.
- Có score margin và degraded behavior thay vì làm toàn API chết.
- `exclude_fact_ids` hỗ trợ tránh lặp fact trong follow-up.
- Giá/category/stock được xử lý ở matcher deterministic, không giao cho vector search.

### Chưa phải hybrid search đúng nghĩa

Kết quả lexical và vector không được hợp nhất thành hai rank list độc lập. Lexical hoặc trả sớm, hoặc vector thắng rồi heuristic điều chỉnh. Chưa có BM25, score calibration, RRF hay learned cross-encoder. Vì corpus FAQ nhỏ, đây chưa chắc là lỗi cần thêm hạ tầng ngay; phải đo retrieval failures trước.

### Failure patterns có khả năng xảy ra

| Query type | Rủi ro hiện tại | Cách đo/khắc phục |
|---|---|---|
| SKU, tên/size chính xác | tokenize/normalize làm mất exactness | exact/tag lookup trước lexical/vector |
| Câu ngắn `cái số 2` | retrieval không đủ ngữ cảnh | structured state + reference resolver, không embed riêng câu |
| Policy gần nhau | vector similarity cao dù điều kiện khác | metadata filter + hard negative + reranker/validator |
| Typo/không dấu | rule alias không bao phủ hết | golden set; char/trigram hoặc controlled rewrite nếu cần |
| Câu ghép | một embedding có thể nghiêng về một vế | split tối đa có kiểm soát, trace từng sub-query |
| Câu phủ định | overlap cao nhưng nghĩa ngược | intent/constraint parser và hard negatives |
| ZeO/CFC lẫn brand | shared wording | brand filter bắt buộc ở mọi data path |

## 5. Hybrid retrieval, RRF và reranker

### Khi nào nên thêm

Chỉ thêm nếu golden set cho thấy lexical-only và vector-only bổ sung cho nhau, ví dụ exact product/SKU tốt ở lexical nhưng paraphrase policy tốt ở dense retrieval.

Thứ tự thử nghiệm ít rủi ro:

1. Đo current lexical, current vector và current routed pipeline riêng biệt.
2. Thêm application-side BM25/FTS + dense KNN, hợp nhất bằng RRF.
3. So sánh Recall@5/MRR/nDCG@5 và p95.
4. Chỉ khi top-k còn nhiễu, thử `bge-reranker-v2-m3` trên top 10–20.
5. Không rerank các fast-path deterministic hoặc exact lookup.

Redis có metadata-filtered KNN; `FT.HYBRID` hỗ trợ text + vector và RRF/linear từ Redis 8.4. Phải kiểm tra phiên bản Redis runtime trước khi chọn lệnh này. Nếu phiên bản thấp hơn, hợp nhất rank ở application layer là đủ. Nguồn: [Redis vector search](https://redis.io/docs/latest/develop/ai/search-and-query/vectors/), [Redis FT.HYBRID](https://redis.io/docs/latest/commands/ft.hybrid/), [RRF paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf), [FlagEmbedding reranker](https://github.com/FlagOpen/FlagEmbedding).

## 6. Query understanding và routing

### Hiện trạng

`chat_pipeline.py` có normalization tiếng Việt, aliases, regex intent, price parser, product matcher, multi-intent split, out-of-scope/privacy/safety rules, conversation state và optional Ollama planner. Đây là tài sản nghiệp vụ quan trọng; không nên thay toàn bộ bằng một LLM call.

Planner mặc định `off` khi không có `llm_nlu` trong settings/environment. `shadow` chỉ log/so sánh; `assist` mới được dùng và vẫn phải gọi tool deterministic. Hai unit test planner dùng fake planner, không chứng minh Ollama live phân loại tốt.

### Vấn đề

- Router regex lớn, thứ tự branch là một phần behavior nhưng chưa có decision trace thống nhất.
- Một số intent mới được giải quyết bằng hardcode answer thay vì source fact.
- Câu mơ hồ score thấp có thể đi vào `reason_and_answer_cskh()` với facts rỗng, làm tăng nguy cơ LLM tạo thông tin chung.
- Query rewrite/multi-query hiện không phải một module có contract, budget và validation độc lập.

### Đề xuất

- Giữ deterministic parser cho price/stock/link/SKU/policy risk.
- Chuẩn hóa `QueryPlan` JSON: `intent`, `entities`, `constraints`, `references`, `subqueries`, `required_tools`, `confidence`.
- Chỉ gọi Ollama planner cho vùng uncertainty rõ; cache theo normalized query + schema/model version.
- Không dùng multi-query mặc định. Chỉ kích hoạt cho ambiguous semantic FAQ sau khi single-query Recall@K thấp; giới hạn 2–3 rewrite và cấm rewrite numeric constraints.

## 7. Reranking

Heuristic reranker hiện boost/phạt theo entity, catalog và intent. Ưu điểm là nhanh, explainable; nhược điểm là rule interaction khó hiệu chỉnh và không học được hard negatives.

Đề xuất giữ heuristic cho business constraints. Cross-encoder chỉ làm **relevance reranking** cho top-k FAQ/document candidates, không được ghi đè brand/category/audience/risk filters. Benchmark local multilingual reranker trước; không để reranker vào mọi request.

## 8. Conversation memory và reference resolution

### Hiện trạng

- State giữ active entities, `last_products_shown`, constraints, active flow, covered facts, recent turns và summary.
- `_resolve_reference()` hiểu ordinal và đại từ từ structured product memory.
- Có process-local lock và RAM session cache; Redis lưu session/history bằng background task.
- `message_id` có trong request model nhưng không được dùng để deduplicate.

### Đánh giá

Thiết kế structured state đúng hơn việc nhét toàn transcript vào prompt. Tuy nhiên RAM cache/lock chỉ bảo vệ trong một process. Plain `SET` không `turn_seq/session_version/CAS`, không TTL và background write có thể tạo stale overwrite hoặc mất lượt khi restart/multi-worker.

Đích:

- Redis là authoritative conversational state.
- `message_id` idempotency key có TTL.
- State update có `turn_seq` + optimistic compare-and-set hoặc Redis transaction/Lua.
- Critical product/reference state write-through trước response; transcript/analytics có thể async.
- TTL có chủ đích và chính sách privacy/retention.

## 9. Grounded generation và answer verification

### Hiện trạng

- Deterministic template trả lời được nhiều price/link/product/policy case.
- `synthesize_cskh_answer()` prompt model bám facts và có fallback.
- Chưa có output validator đầy đủ để đối chiếu mọi claim với source envelope.
- Một số matcher/synthesizer chứa absolute claims hardcode; low-score branch có thể gọi model khi raw facts rỗng.

### Grounding contract cần có

Mọi answer producer phải trả một `FactEnvelope`:

```json
{
  "facts": [
    {"fact_id": "...", "field": "price", "value": 123000, "source_id": "...", "source_version": "..."}
  ],
  "allowed_claims": ["..."],
  "prohibited_claim_types": ["medical", "absolute_safety", "unverified_stock"],
  "freshness": {"as_of": "...", "stale": false}
}
```

Sau generation, validator phải:

1. parse URL, số tiền, phần trăm, hotline, dung tích và tên sản phẩm;
2. đối chiếu exact với facts/source version;
3. chặn từ tuyệt đối `100%`, `hoàn toàn an toàn`, `không bao giờ` nếu source không cho phép;
4. kiểm tra brand/audience/privacy;
5. fail closed về deterministic template/clarification và ghi learning event.

Prompt không phải security boundary và không thay validator.

## 10. Fallback và learning loop

Fallback hiện có nhiều lý do (`OLLAMA_TIMEOUT`, `REDIS_FAILED`, no knowledge...) và Telegram notification, nhưng chat pipeline chưa push sự kiện vào `zeo:learning:queue`/`cfc:learning:queue`. Hai n8n exporter chỉ tiêu thụ event đã có, nên vòng học chưa end-to-end.

Fallback cần phân biệt:

- `NO_MATCH`: knowledge thiếu;
- `AMBIGUOUS`: cần hỏi rõ;
- `DEPENDENCY_DOWN`: degraded mode;
- `VALIDATION_FAILED`: model tạo claim không được phép;
- `STALE_SOURCE`: có dữ liệu nhưng quá freshness SLA;
- `PRIVACY_OR_SAFETY`: từ chối/chuyển người;
- `CONFLICTING_FACTS`: nguồn mâu thuẫn.

Learning event nên dùng Redis Stream hoặc queue có ack/idempotent `event_id`; mô hình `LPOP → append Sheet` hiện có khe mất event khi worker crash.

## 11. Cache

| Cache/state | Hiện tại | Rủi ro | Đề xuất |
|---|---|---|---|
| FAQ hot cache | RAM per-process | stale/cross-worker | versioned cache, active pointer, broadcast invalidation |
| Catalog cache | RAM per-process + Redis/CSV | refresh không đồng đều | cache key theo `source_version`, TTL/freshness |
| Embedding query | Không có | lặp Ollama call | bounded LRU/Redis hash theo model+normalized query |
| Exact response | Không rõ contract | stale price/policy nếu cache thô | chỉ cache source-independent response hoặc include source version |
| Session | RAM + Redis | race/no TTL | Redis authoritative, CAS/TTL |

Không cache final answer chứa price/stock nếu không gắn source version và freshness.

## 12. Ollama performance

Hiện tại chưa có benchmark p50/p95/p99 trên hardware thật. `embedder.py` tạo client mới mỗi request; chat model calls và embedding có thể tranh RAM/VRAM. Ollama hỗ trợ `keep_alive`, queue và parallelism, nhưng tăng `OLLAMA_NUM_PARALLEL` làm tăng memory theo context; cần load test thay vì tăng tùy ý. Nguồn: [Ollama FAQ](https://docs.ollama.com/faq).

Action:

- shared `httpx.AsyncClient` với connection limits;
- separate semaphore cho embed và generation;
- warm model + explicit `keep_alive` phù hợp;
- bounded queue, timeout budget và circuit breaker;
- batch embedding khi sync;
- log load/prompt/eval duration từ Ollama response;
- benchmark 1, 2, 5 và 10 concurrent conversations trên máy thật.

## 13. Observability

Session có `last_trace`, nhưng schema thay đổi theo branch và API không trả full trace. Cần một event schema thống nhất:

```json
{
  "request_id": "...",
  "message_id_hash": "...",
  "brand": "zeo",
  "route": "deterministic|lexical|vector|planner|fallback",
  "query_plan": {},
  "retrieved": [{"id": "...", "rank": 1, "score": 0.82}],
  "source_version": "...",
  "validation": {"passed": true, "violations": []},
  "fallback_reason": "",
  "timings_ms": {},
  "result": "answered|clarified|escalated"
}
```

Không log raw token, Redis password, PII nguyên văn hoặc full customer transcript vào telemetry chung.

## 14. Security liên quan RAG/LLM

- Treat Sheet/document text là untrusted data; không cho nội dung retrieved trở thành instruction.
- Audience allowlist `customer` ở mọi producer và index.
- Không để LLM quyết định permission hoặc gọi general shell.
- Redact settings, PII và credentials trước prompt/log/output.
- Admin APIs cần authentication/RBAC trước khi public tunnel.
- `shopee_auth.json` đang được Git theo dõi là credential artifact risk; rotate/revoke và loại khỏi index/history theo quy trình có phê duyệt.

OWASP lưu ý RAG/fine-tuning không tự loại prompt injection; access control và output validation phải nằm ngoài LLM: [Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/), [Sensitive Information Disclosure](https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/), [Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/).

## 15. Chấm điểm RAG-specific

| Năng lực | Điểm /10 | Lý do |
|---|---:|---|
| Ingestion | 5 | Có Sheet→Redis→index, nhưng validation/version/atomic publish yếu |
| Chunking | 6 | FAQ row đúng; Markdown heading-aware; chưa benchmark/parent context |
| Embedding | 6 | `bge-m3` phù hợp baseline; client/cache/batch/fallback validation thiếu |
| Retrieval | 6 | lexical-first + KNN + filters; chưa fusion/benchmark retrieval |
| Query understanding | 6 | Nhiều rule nghiệp vụ hữu ích; router lớn và planner live chưa chứng minh |
| Reranking | 4 | Chỉ heuristic; chưa hard-negative benchmark/cross-encoder |
| Memory/reference | 6 | Structured product memory tốt; persistence/concurrency chưa chắc |
| Grounding | 3 | Deterministic facts có, nhưng absolute hardcode và no validator |
| Fallback | 5 | Có degraded behavior/Telegram; learning queue chưa nối |
| Evaluation | 4 | Nhiều regression case, nhưng không đo Recall/MRR/faithfulness và runner không fail chắc |
| Performance evidence | 4 | Fast-path nhanh theo historical test; chưa có live p95/p99/load data |

## 16. Acceptance criteria trước nâng cấp retrieval

Không thêm BM25/RRF/reranker cho đến khi:

1. Golden set có expected docs/facts và hard negatives cho ZeO/CFC.
2. Baseline ghi riêng lexical, vector và routed pipeline.
3. `RangeViolationRate = 0` và `UnsupportedClaimRate = 0` cho price/stock/link/safety.
4. Audience leak test chứng minh mọi dòng `agent/internal` không thể tới customer.
5. Các runner trả exit code khác 0 khi fail.
6. Có p50/p95/p99 và memory footprint trên hardware thật.

Nếu hybrid không tăng retrieval metrics đủ để bù latency/complexity, giữ kiến trúc hiện tại và tập trung chất lượng dữ liệu/grounding.
