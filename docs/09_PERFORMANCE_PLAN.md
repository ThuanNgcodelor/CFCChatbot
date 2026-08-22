# Performance And Reliability Plan - Chatbot ZeO / CFC

Ngày lập kế hoạch: 2026-08-22  
Liên quan: `docs/01_CURRENT_ARCHITECTURE.md`

Đây là kế hoạch đo và tối ưu. Các con số trong cột target là SLO đề xuất, chưa phải kết quả production đã đạt.

## 1. Mục Tiêu

Tối ưu hệ thống theo thứ tự:

1. đúng dữ liệu và không trả lời trùng;
2. ổn định khi dependency chậm/lỗi;
3. latency có phân vị p50/p95/p99 theo từng loại request;
4. throughput có kiểm soát, không làm nghẽn Ollama hoặc Redis;
5. có thể giải thích thời gian đã tiêu ở đâu qua trace;
6. rollout có gate, rollback và bằng chứng rõ ràng.

Không đánh đổi grounding, hard price constraint, privacy hoặc safety để lấy latency thấp hơn.

## 2. Baseline Hiện Có Và Khoảng Trống

### 2.1 Số Liệu Đang Có

| Số liệu | Giá trị gần nhất | Giới hạn |
|---|---:|---|
| Offline eval | 112/112 expectation pass, trung bình 2,7ms/lượt | Chạy degraded/offline; không đại diện Redis/Ollama/n8n/Meta |
| Unit tests | 26/26 pass | Chủ yếu isolated/mocked |
| Markdown scenario | 48/55 lượt pass | Runner không phải load test và còn REVIEW |
| FastAPI health | Từng pass trong audit, lần cuối port 8000 không lắng nghe | Không phải availability history |

### 2.2 Baseline Gaps

Chưa có:

- histogram p50/p95/p99 theo route và intent class;
- latency end-to-end Messenger -> n8n -> FastAPI -> Graph API;
- tách queue wait, Redis wait, embedding, vector search, Ollama inference và network time;
- cold-start so với warm-cache;
- cache hit ratio cho FAQ, catalog, embedding và session;
- Ollama tokens/second, load duration, prompt eval duration và queue depth;
- Redis pool saturation, command latency và reconnect count;
- event-loop lag, active requests, per-sender lock wait và task backlog;
- error/timeout/fallback rate theo dependency;
- load, spike, soak và recovery test;
- production concurrency profile hoặc traffic mix thật.

Vì vậy không dùng giá trị trung bình 2,7ms làm baseline production.

## 3. Request Classes

Mọi benchmark phải gắn request vào một class:

| Class | Ví dụ | Dependency chính |
|---|---|---|
| A - deterministic | chào, hotline, privacy, price filter đã cache | Python + state/catalog cache |
| B - Redis/catalog | báo giá, link, ranking cần Redis/catalog load | Redis + matcher |
| C - FAQ lexical | FAQ có lexical hit | FAQ hot cache/Redis |
| D - vector RAG | FAQ cần query embedding + KNN | Ollama embedding + Redis Vector |
| E - Ollama planner | wording khó ở `shadow/assist` | Ollama chat model + deterministic tool |
| F - grounded synthesis | rewrite facts bằng model | Ollama/provider + validator |
| G - external end-to-end | Messenger thật | n8n + FastAPI + Meta Graph + dependencies |
| H - background | FAQ/Shopee sync, document embedding | Sheet + Redis + Ollama batch |

Không gộp tất cả class thành một số trung bình duy nhất.

## 4. Latency SLO Đề Xuất

### 4.1 FastAPI Server-Side

Đo từ lúc FastAPI nhận request đến lúc trả response, không gồm n8n/Meta:

| Class | p50 | p95 | p99 | Hard deadline đề xuất |
|---|---:|---:|---:|---:|
| A - deterministic warm | <= 35ms | <= 100ms | <= 200ms | 500ms |
| B - Redis/catalog warm | <= 60ms | <= 180ms | <= 350ms | 750ms |
| C - FAQ lexical warm | <= 75ms | <= 220ms | <= 450ms | 900ms |
| D - vector RAG warm | <= 250ms | <= 700ms | <= 1.2s | 2.0s |
| E - Ollama planner warm | <= 700ms | <= 1.8s | <= 3.0s | 3.5s |
| F - grounded synthesis warm | <= 1.0s | <= 2.5s | <= 4.0s | 4.5s |

Cold model load phải được báo cáo riêng, không trộn vào warm percentile.

### 4.2 End-To-End Messenger

Đo từ webhook receive timestamp đến Graph API send acknowledgement:

| Traffic | p50 | p95 | p99 | Timeout/fallback |
|---|---:|---:|---:|---:|
| Không gọi chat LLM | <= 800ms | <= 2.0s | <= 3.5s | 5s |
| Có Ollama planner/synthesis | <= 1.5s | <= 3.5s | <= 5.5s | 7s |

Current n8n -> FastAPI timeout là 8 giây. Tổng inner deadline phải nhỏ hơn 8 giây và chừa thời gian để tạo fallback; không để model chiếm toàn bộ timeout.

### 4.3 Reliability SLO Đề Xuất

| Chỉ số | Target trước production |
|---|---:|
| HTTP success từ FastAPI với input hợp lệ | >= 99,9% trong load test |
| Duplicate customer reply do cùng `message_id` | 0 |
| Unsupported price/link/stock claim | 0 trong golden set |
| Price range violation | 0 |
| Lost learning event trong failure test | 0 |
| Stale snapshot được promote sau validation failure | 0 |
| FastAPI timeout ở steady-state target load | < 0,1% |
| Recovery sau Redis/Ollama restart | <= 60s, không cần restart toàn stack |

## 5. Per-Component Budget

Budget p95 cho một request vector RAG có target tổng 700ms:

| Thành phần | p95 budget | Ghi chú |
|---|---:|---|
| n8n -> FastAPI local HTTP | 20ms | Cùng host; đo riêng nếu qua container/network |
| Parse/normalize/request validation | 10ms | Không gọi network |
| Per-sender lock wait | 25ms | Báo riêng wait time; không tính inference |
| Profile/session Redis read | 25ms | Pipeline/MGET khi phù hợp |
| Deterministic routing/matcher | 25ms | Catalog warm |
| Embedding cache lookup | 10ms | RAM/Redis |
| Ollama query embedding, warm | 350ms | Nếu cache miss |
| Redis Vector KNN + rerank | 60ms | Gồm deserialize/rerank |
| Response guard/serialize | 20ms | Không LLM synthesis |
| State/trace critical write | 40ms | Critical state sync; analytics async |
| Reserve/jitter | 115ms | GC, scheduler, minor network variance |

Với deterministic request, bỏ embedding/KNN và đặt budget p95 tổng 100ms.

Mỗi trace phải ghi `elapsed_ms` cho component thay vì chỉ tổng latency.

## 6. Instrumentation Trước Khi Tối Ưu

### 6.1 Trace Fields

Mỗi request cần có:

```json
{
  "request_id": "generated-id",
  "message_id_hash": "hash-only",
  "brand": "zeo",
  "request_class": "D_vector_rag",
  "intent": "...",
  "source_version": "...",
  "cache": {
    "session_hit": true,
    "catalog_hit": true,
    "embedding_hit": false
  },
  "timing_ms": {
    "lock_wait": 0,
    "redis_read": 0,
    "router": 0,
    "ollama_queue": 0,
    "embedding": 0,
    "vector_search": 0,
    "llm": 0,
    "redis_write": 0,
    "total": 0
  },
  "fallback_reason": "",
  "dependency_error": ""
}
```

Không log raw token, password, cookie, full phone, full sender ID hoặc nội dung nhạy cảm. Dùng hash/mask và retention có thời hạn.

### 6.2 Metrics

Tối thiểu cần histogram/counter/gauge:

- `chat_request_duration_seconds{class,brand,intent}`;
- `component_duration_seconds{component}`;
- `chat_requests_total{status,fallback_reason}`;
- `ollama_queue_wait_seconds{model}`;
- `ollama_requests_inflight{model}`;
- `redis_command_duration_seconds{operation}`;
- `redis_pool_in_use` và reconnect/error count;
- `cache_hit_total{cache}` / `cache_miss_total{cache}`;
- `sender_lock_wait_seconds`;
- `duplicate_message_total`;
- `learning_queue_depth` và oldest-event age;
- `snapshot_version{brand,type}` và cache/index version mismatch;
- process RSS, CPU, open file descriptors và event-loop lag.

## 7. Ollama Plan

### 7.1 Keep-Alive Và Warm-Up

Đề xuất thử nghiệm, không áp thẳng production:

- gọi warm-up embedding `bge-m3` sau startup và health-ready;
- warm-up chat model chỉ khi `LLM_NLU_MODE` là `shadow/assist` hoặc synthesis được bật;
- thử `keep_alive: "30m"` cho chat model và `keep_alive: "15m"` cho embedding;
- nếu memory pressure hoặc model eviction cao, giảm keep-alive theo số đo, không giữ vô hạn;
- ghi riêng model load time và inference time.

Acceptance:

- warm request đạt target p95;
- không swap/thrashing;
- sau idle, cold load không làm toàn queue vượt deadline;
- health phân biệt daemon up với model actually ready.

### 7.2 Concurrency Và Queue

Current local launcher đặt `OLLAMA_NUM_PARALLEL=1`. Kế hoạch:

1. Giữ `NUM_PARALLEL=1` làm baseline an toàn trên máy hiện tại.
2. Tạo semaphore ở application theo model/task, không bắn request Ollama không giới hạn.
3. Ưu tiên interactive chat hơn background bulk embedding.
4. Tách queue metrics: enqueue time, dequeue time, inference time.
5. Giới hạn queue; khi đầy, dùng deterministic/RAG fallback thay vì đợi quá deadline.
6. Chỉ thử parallel 2 sau khi đo VRAM/RAM, throughput và p99; rollback nếu model reload, OOM hoặc tail latency tăng.

Queue policy đề xuất:

| Workload | Max in-flight ban đầu | Max wait | Khi quá tải |
|---|---:|---:|---|
| Chat planner | 1 | 750ms | Bỏ planner, dùng deterministic/RAG |
| Grounded synthesis | 1 | 1.5s | Trả template grounded |
| Query embedding | 1 | 500ms | Dùng lexical fallback nếu an toàn |
| Background document embedding | 1 batch | Không tranh interactive | Pause/backoff |

Không chạy hai lượt Ollama trên customer path nếu lượt thứ hai không tạo giá trị đo được.

### 7.3 Circuit Breaker

- mở circuit sau chuỗi timeout/connection failure theo cửa sổ ngắn;
- half-open bằng một probe, không thả toàn bộ traffic;
- fallback phải deterministic và có `fallback_reason`;
- không retry model request trong cùng customer deadline trừ khi lỗi xảy ra trước khi inference bắt đầu;
- reset circuit dựa trên health và successful probe.

## 8. HTTP Connection Pooling

### 8.1 FastAPI Outbound

Tạo một `httpx.AsyncClient` theo application lifespan thay vì tạo client mỗi request:

- keep-alive pool;
- explicit `Limits(max_connections, max_keepalive_connections)`;
- timeout tách `connect`, `read`, `write`, `pool`;
- đóng client khi application shutdown;
- metrics cho pool wait và connection reuse.

Giá trị pilot:

```text
max_connections = 50
max_keepalive_connections = 20
keepalive_expiry = 30s
connect timeout = 0.5s local / 2s external
pool timeout = 0.25s
```

Read timeout đặt theo dependency: Ollama khác Redis/Telegram/Graph. Các giá trị phải tune bằng load test.

### 8.2 Retry Policy

- Redis read: reconnect/backoff giới hạn, không spin loop.
- Ollama: không blind retry trong request deadline.
- Google Sheet sync: retry có jitter và run ID.
- Graph send: chỉ retry khi đã có idempotency/delivery strategy; nếu không có, retry có thể gửi trùng.
- Cache refresh và vector rebuild: lỗi phải làm sync run fail, không `continueRegularOutput` rồi ghi success.

## 9. Embedding Cache Và Vector Sync

### 9.1 Query Embedding Cache

Cache key:

```text
sha256(embed_model + model_digest_or_version + normalize_version + normalized_query)
```

Hai tầng:

- process LRU nhỏ cho hot query;
- Redis shared cache với TTL pilot 6-24 giờ.

Yêu cầu:

- không dùng raw customer text làm Redis key;
- giới hạn size và eviction;
- cache version đổi khi model hoặc normalization đổi;
- đo hit ratio và p95 saved;
- không cache query chứa dữ liệu nhạy cảm nếu không hash/retention phù hợp.

### 9.2 Document Embedding

- dùng `snapshot_hash/source_version` để bỏ qua document không đổi;
- batch embedding ở background;
- lưu model version cùng vector;
- build index staging;
- chỉ promote index khi count/hash/validation đạt;
- giữ index trước để rollback;
- background embedding không chiếm queue của customer query.

## 10. Redis, Cache Và State Concurrency

### 10.1 Connection Pool

- một pool sync/async phù hợp theo process, không mở connection mới mỗi request;
- dùng pipeline/MGET cho các field đọc cùng lượt;
- giới hạn pool và đo pool wait;
- timeout ngắn cho interactive read;
- degraded fallback rõ ràng khi Redis unavailable.

### 10.2 Conversation State

Critical state phải write-through trước response hoặc dùng versioned write:

```text
session_version
turn_seq
last_processed_message_id
last_products_shown.source_version
```

Khi multi-worker:

- thay process-local lock bằng Redis lock có lease hoặc optimistic compare-and-set;
- fencing token/turn sequence để request cũ không overwrite state mới;
- session TTL có chủ đích và refresh policy;
- transcript/analytics có thể async, product reference và idempotency không được async mù.

### 10.3 Catalog/FAQ Consistency

- write staging key;
- validate expected schema/count/hash;
- atomic `RENAME` hoặc version pointer promote;
- publish invalidation/version event;
- worker cache kiểm tra version trước khi trả;
- metadata success chỉ ghi sau promote và index/cache confirmation;
- giữ `last-known-good` để rollback.

## 11. Idempotency Và Duplicate Control

### 11.1 Messenger

Tại n8n ingress:

- drop `is_echo=true`;
- drop empty text nếu attachment chưa được hỗ trợ;
- reject empty sender ID;
- truyền `message_id` bắt buộc.

Tại FastAPI:

```text
SET chat:idempotency:{brand}:{message_id_hash} processing NX EX <ttl>
```

- nếu key đã `done`, trả cached response hoặc acknowledgement, không xử lý lại;
- nếu `processing` quá lease, cho phép recovery có fencing token;
- sau khi tạo response, lưu `done + response hash`;
- TTL pilot 24-72 giờ theo webhook retry window;
- không lưu raw message ID nếu không cần.

Tại outbound Graph:

- lưu send-attempt state;
- phân biệt lỗi chắc chắn chưa gửi với timeout không biết đã gửi;
- không blind retry ambiguous timeout;
- reconcile bằng execution log/Meta response khi có thể.

### 11.2 Sync Và Learning Queue

- mỗi sync có `run_id`, source version và snapshot hash;
- cùng run/version không promote hai lần;
- learning event có stable `event_id` và Sheet upsert/dedup;
- thay destructive POP bằng processing queue/stream/consumer group hoặc atomic move sang in-flight list;
- ack sau khi Sheet ghi thành công;
- dead-letter queue sau số lần retry giới hạn.

## 12. Test Plan

### 12.1 Functional Gate Trước Performance

Trước mỗi benchmark:

1. unit tests pass;
2. offline eval pass theo expectation;
3. các scenario REVIEW đã được phân loại;
4. no-hallucination golden set pass;
5. duplicate/echo/attachment tests pass;
6. snapshot/index version consistency pass.

Nếu correctness fail, không dùng performance result làm lý do rollout.

### 12.2 Cold/Warm Microbenchmarks

Đo từng component tối thiểu 1.000 mẫu warm và 30 cold cycles:

- normalize/router;
- catalog match theo price/rank/link;
- Redis profile/session read-write;
- lexical retrieval;
- query embedding;
- vector KNN + rerank;
- Ollama planner;
- grounded synthesis;
- cache refresh và vector sync.

Báo p50/p95/p99, min/max, error rate, CPU/RSS và cache hit.

### 12.3 Load Test

Workload pilot, điều chỉnh sau khi có traffic thật:

```text
45% deterministic
20% catalog/price/link
15% lexical FAQ
10% vector RAG
5% Ollama planner
5% context follow-up/multi-turn
```

Các stage:

| Stage | Concurrency | Thời gian | Mục đích |
|---|---:|---:|---|
| Warm-up | 1 | 5 phút | Nạp model/cache |
| Baseline | 1 | 10 phút | Latency không contention |
| Normal | 5 | 15 phút | Target traffic ban đầu |
| High | 10 | 15 phút | Pool/queue pressure |
| Stress | 20 rồi tăng dần | 10 phút/stage | Tìm knee point, không rollout |
| Recovery | 1 | 10 phút | Kiểm tra trở về baseline |

Tách hai profile:

- nhiều sender độc lập;
- cùng sender gửi burst để đo lock/order/state.

Không load test trực tiếp Facebook production nếu chưa có phê duyệt và rate-limit plan. Đo FastAPI/n8n test environment trước.

### 12.4 Failure Injection

| Failure | Expected behavior |
|---|---|
| Redis unavailable | Fast fail/degraded response; không treo event loop |
| Redis latency 50/200/500ms | Pool timeout hoạt động, p99 được giới hạn |
| Ollama down | Deterministic/RAG/template fallback |
| Ollama timeout/malformed JSON | Không phát fact model tự tạo |
| Model cold load | Queue bounded, không vượt customer deadline hàng loạt |
| Vector index missing | Lexical/fallback và explicit reason |
| FAQ rebuild lỗi sau snapshot write | Không ghi success/promote version mới |
| Shopee Sheet trả 1-5 rows | Validation chặn overwrite active snapshot |
| Cache refresh lỗi | Version mismatch visible, run fail/retry |
| Duplicate `message_id` | Chỉ một xử lý và một reply |
| Echo/attachment/empty input | Drop hoặc route hỗ trợ explicit |
| Graph 429/5xx | Backoff theo policy, không spam duplicate |
| FastAPI restart giữa hai turn | State Redis giữ đúng reference |
| Worker chết sau learning POP | Event vẫn recoverable |
| n8n restart giữa execution | Idempotency ngăn duplicate reply |

### 12.5 Spike Test

- từ 1 lên 20 concurrent trong 10 giây;
- giữ 2 phút rồi hạ về 1;
- queue phải bounded;
- deterministic request không bị background embedding starve;
- p99 phải hồi về baseline trong 2 phút;
- không OOM, không model reload loop.

### 12.6 Soak Test

Chạy tối thiểu 4 giờ ở normal load, sau đó một lần 8-12 giờ trước production:

- RSS growth < 10% sau warm-up hoặc giải thích được bằng bounded cache;
- file descriptor không tăng tuyến tính;
- Redis connection count ổn định;
- event-loop lag không tăng dần;
- catalog/embedding/session cache có giới hạn;
- Ollama không eviction/reload liên tục;
- learning queue age không tăng khi consumer khỏe;
- không tăng duplicate/fallback bất thường.

## 13. Rollout Gate

### Phase 0 - Instrument

- thêm trace/component timing;
- thêm request class và cache/version fields;
- chưa thay routing.

### Phase 1 - Local Baseline

- microbenchmark cold/warm;
- load concurrency 1/5/10;
- chốt bottleneck dựa trên p95/p99.

### Phase 2 - Safe Optimizations

- HTTP/Redis pooling;
- embedding cache có version;
- critical state write-through/versioning;
- ingress/idempotency;
- không thay business answer.

### Phase 3 - Ollama Queue Control

- keep-alive pilot;
- semaphore/priority queue/circuit breaker;
- shadow traffic trước assist.

### Phase 4 - Failure And Soak

- hoàn tất failure matrix;
- 4 giờ rồi 8-12 giờ soak;
- kiểm tra recovery và memory.

### Phase 5 - Progressive Production Rollout

Chỉ khi có quyền deploy và production đã được xác minh:

- 5% traffic hoặc một Page/test audience;
- 25%;
- 50%;
- 100%.

Mỗi bước cần ít nhất một cửa sổ ổn định có đủ sample; rollback nếu:

- correctness/grounding violation > 0 cho critical facts;
- p95 hoặc p99 vượt SLO liên tiếp;
- timeout/fallback tăng gấp đôi baseline;
- duplicate reply > 0;
- Redis/Ollama saturation hoặc memory leak;
- snapshot/index/cache version mismatch.

## 14. Báo Cáo Kết Quả Chuẩn

Mỗi lần benchmark phải ghi:

```text
commit/source hash:
date/timezone:
machine CPU/RAM/GPU:
Python/n8n/Redis/Ollama version:
models and digest:
config: workers, NUM_PARALLEL, keep_alive, pool limits:
data size: FAQ/catalog/vector docs:
workload mix:
concurrency and duration:
cache state: cold/warm:
p50/p95/p99 by request class:
component timings:
throughput:
error/timeout/fallback/duplicate rate:
CPU/RSS/FD/Redis connections:
correctness gate result:
known deviations:
```

Không ghi “production pass” nếu chỉ chạy local/offline. Không so sánh hai lần test khi model, data size, cache state hoặc concurrency khác mà không nêu rõ.

## 15. Definition Of Done

Performance phase chỉ hoàn thành khi:

- có p50/p95/p99 thật cho từng request class;
- component timing giải thích được phần lớn tổng latency;
- idempotency và state ordering pass multi-worker tests;
- FAQ/catalog promote có version và failure-safe behavior;
- Ollama queue bounded, có fallback và không starve interactive traffic;
- load/spike/failure/soak đều đạt gate;
- không regression correctness;
- có runbook rollback và runtime dashboard;
- production status được xác minh riêng bằng execution/log evidence.
