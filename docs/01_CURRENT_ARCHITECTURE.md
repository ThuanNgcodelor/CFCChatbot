# Current Architecture - Chatbot ZeO / CFC

Ngày đối chiếu: 2026-08-22  
Phạm vi: source trong workspace `N8n/`, runtime local được ghi nhận trong phiên audit ngày 22/08 và các khoảng trống cần xác minh trước production.

Tài liệu này mô tả trạng thái hiện hành, không phải cam kết production. Khi tài liệu khác source, dữ liệu runtime hoặc n8n server, ưu tiên bằng chứng mới hơn rồi cập nhật lại tài liệu.

## 1. Quy Ước Bằng Chứng

| Nhãn | Ý nghĩa |
|---|---|
| `[SOURCE]` | Đã đọc trực tiếp file trong workspace |
| `[TEST-LOCAL]` | Kết quả kiểm thử local/offline; không đại diện Messenger end-to-end |
| `[RUNTIME-LOCAL]` | Snapshot Redis/FastAPI local tại thời điểm audit; có thể thay đổi sau đó |
| `[HISTORICAL-LOCAL]` | Kết quả local được ghi lại trước lần kiểm tra cuối; không được chạy lại trong trạng thái service hiện thời |
| `[CONFIGURED]` | Có cấu hình trong source nhưng chỉ hoạt động khi dependency, credential và workflow live hợp lệ |
| `[UNVERIFIED-PROD]` | Chưa kiểm tra n8n production, Messenger thật hoặc trạng thái deploy hiện hành |
| `[GAP]` | Hành vi còn thiếu, có rủi ro hoặc mô tả chưa được bảo đảm bởi source |

Không dùng `.n8n-state.json`, `active: false` trong file local, ảnh chụp cũ hoặc kết quả test mocked để kết luận production đang chạy.

## 2. Kiến Trúc Tổng Quan

```text
Khách hàng trên Facebook Messenger
  -> n8n ZeO/CFC Chatbot workflow
       - Facebook Trigger
       - bóc tách text/sender/message ID
       - POST FastAPI /api/chat-pipeline
       - POST Facebook Graph API để trả lời
  -> FastAPI chat_pipeline.py
       - normalize và guardrail
       - customer/session state
       - deterministic router và Shopee matcher
       - optional Ollama NLU planner
       - FAQ lexical/vector RAG
       - grounded rewrite/fallback
  -> Redis
       - FAQ snapshot và vector index
       - Shopee catalog snapshot
       - customer/session/history
       - learning queue, analytics và dedup metadata
  -> n8n hoặc Python notifier cho các luồng quản trị
```

Phân vai hiện hành:

- `[SOURCE]` n8n là gateway nhận/gửi và chạy các workflow đồng bộ.
- `[SOURCE]` FastAPI là decision layer của hội thoại tại `/api/chat-pipeline`.
- `[SOURCE]` Redis là state store/cache/runtime knowledge store.
- `[SOURCE]` Ollama `bge-m3` tạo embedding; chat model chỉ hỗ trợ planner/rewrite khi được bật.
- `[SOURCE]` Giá, link và tồn kho không được lấy từ câu trả lời tự do của LLM; matcher phải đọc catalog.
- `[UNVERIFIED-PROD]` Chưa xác minh lại workflow nào đang active trên n8n production hoặc Messenger webhook hiện tại có trỏ đúng workflow hay không.

## 3. Source Map

| Thành phần | File chính | Vai trò |
|---|---|---|
| FastAPI app | `ChatbotN8n/javis/server/main.py` | `/health`, `/sync`, `/search`, `/rewrite`, `/api/chat-pipeline`, `/api/shopee/refresh-cache` |
| Chat decision layer | `ChatbotN8n/javis/server/chat_pipeline.py` | Router, state, context, guardrail, RAG fallback |
| Shopee product tools | `ChatbotN8n/javis/server/shopee_matcher.py` | Catalog loading, constraint giá, ranking, link và product memory |
| FAQ retrieval | `ChatbotN8n/javis/server/rag_search.py` | Lexical hot cache và Redis Vector KNN |
| Knowledge indexing | `ChatbotN8n/javis/server/knowledge_sync.py` | Snapshot Redis -> embeddings -> vector index |
| Embeddings | `ChatbotN8n/javis/server/embedder.py` | Ollama `bge-m3`, vector 1024 chiều |
| LLM integration | `ChatbotN8n/javis/server/ai_engine.py` | Provider routing, NLU JSON planner, grounded synthesis |
| Telegram Python | `ChatbotN8n/javis/server/telegram_notifier.py` | Lead/complaint notification độc lập với n8n alert workflow |
| Admin facade | `ChatbotN8n/javis/server/admin_routes.py` | Mount các router trong `domains/` dưới prefix `/admin` |
| Unit tests | `ChatbotN8n/javis/server/tests/` | Price, product follow-up, planner và conversation guards |
| Offline eval | `ChatbotN8n/javis/server/eval_test_suite.py` | Single-turn và multi-turn expectation tests |
| Scenario runner | `ChatbotN8n/javis/server/run_test_md_scenarios.py` | Replay kịch bản Markdown |
| n8n workflows | `ChatbotN8n/workflows/local-n8n/*.workflow.ts` | Messenger, knowledge, learning, Shopee sync và alert |
| Runtime scripts | `testing/start_all.sh`, `testing/stop_all.sh` | Khởi động/dừng stack local |

## 4. FastAPI Chat Pipeline

### 4.1 Request Path

```text
POST /api/chat-pipeline
  -> normalize brand/text
  -> per-sender coordination
  -> load profile và conversation state
  -> privacy, complaint, safety và deterministic fast paths
  -> product/category/price/link matcher
  -> optional Ollama NLU plan ở off/shadow/assist
  -> FAQ/RAG khi chưa có route chắc chắn
  -> grounded response hoặc explicit fallback
  -> lưu state/history/trace
```

Các nhánh dữ liệu có tính quyết định:

- Product price, rank, link và `in_stock`: Shopee catalog snapshot.
- FAQ/policy/company information: FAQ snapshot/vector docs đã sync.
- Customer/session memory: Redis, có cache RAM hỗ trợ.
- Facts không có nguồn: thiết kế mong muốn là fallback/learning queue. `[GAP]` Pipeline hiện còn nhánh low-score gọi LLM khi facts rỗng và chưa enqueue learning queue end-to-end.

### 4.2 Context Và State

Conversation state hiện có thể chứa:

- active entity/product/category;
- `last_products_shown` với product ID, rank, price snapshot và URL;
- recent turns và conversation summary;
- active return flow;
- source/trace của lần match gần nhất.

`[GAP]` Cache RAM và lock theo sender là process-local. Khi chạy nhiều worker, chúng không tự đồng bộ lock/cache. Redis session chưa có đầy đủ `turn_seq`, optimistic versioning và TTL có chủ đích cho mọi state quan trọng.

`[GAP]` Workflow truyền `message_id` vào request nhưng `chat_pipeline.py` chưa dùng nó làm idempotency key. Webhook retry có thể tạo câu trả lời trùng.

## 5. Redis Và Cache

Các key chính:

```text
zeo:kb:basic:active
cfc:kb:basic:active
zeo:sync:faq:basic:last-success
cfc:sync:faq:basic:last-success
zeo:vec:faq
cfc:vec:faq
zeo:shopee:catalog:active
zeo:customer:messenger:{sender_id}
cfc:customer:messenger:{sender_id}
zeo:session:messenger:{sender_id}
cfc:session:messenger:{sender_id}
zeo:history:messenger:{sender_id}
cfc:history:messenger:{sender_id}
zeo:learning:queue
cfc:learning:queue
ops:telegram:dedup:{hash}
```

Shopee loader đọc theo thứ tự:

```text
process-local in-memory cache
  -> Redis {brand}:shopee:catalog:active
  -> ZeO CSV fallback local
  -> empty catalog
```

`[GAP]` In-memory Shopee cache không có TTL. Nếu Redis đã đổi nhưng `/api/shopee/refresh-cache` không chạy thành công, process có thể tiếp tục dùng snapshot cũ cho đến khi refresh hoặc restart.

`[GAP]` Chưa có catalog CFC tương đương trong fallback CSV hiện hành.

## 6. Ollama Và RAG

### 6.1 Embedding

- `[SOURCE]` Ollama base URL mặc định: `http://127.0.0.1:11434`.
- `[SOURCE]` Embedding model: `bge-m3`.
- `[SOURCE]` Vector dimension: 1024.
- `[SOURCE]` FAQ sync tạo embedding rồi upsert Redis Vector Index.

### 6.2 NLU Planner Và Rewrite

Planner hỗ trợ ba mode:

- `off`: không gọi planner;
- `shadow`: ghi nhận dự đoán nhưng quyết định vẫn theo luồng cũ;
- `assist`: planner có thể chọn deterministic tool nếu JSON hợp lệ và confidence đạt ngưỡng.

Ollama không phải nguồn sự thật cho giá, link, tồn kho, chính sách hoặc chứng nhận. Nếu timeout, JSON sai hoặc matcher không trả dữ liệu hợp lệ, pipeline phải quay lại deterministic/RAG/fallback.

`[GAP]` Chưa có số đo production cho cold-start, queue wait, token throughput, cache hit hoặc p95/p99 của Ollama.

## 7. Tám Workflow n8n Local

Tất cả file dưới đây đang có `active: false` trong source local. Cờ này không chứng minh trạng thái live.

| Workflow | ID local | Node/connection | Trigger | Đích chính | Trạng thái nguồn |
|---|---|---:|---|---|---|
| Zeo Chatbot | `d7fctbMhVUmhrNG0` | 5/5 | Facebook messages | `/api/chat-pipeline`, Graph API v17.0 | Source đầy đủ; live chưa xác minh |
| CFC Co Bay Chatbot | `uJOo6NQO2mJZhUAr` | 5/5 | Facebook messages | `/api/chat-pipeline`, Graph API v17.0 | Source đầy đủ; live chưa xác minh |
| Zeo Knowledge | `DhrLUsDsldhxtTdX` | 7/6 | Manual + schedule | Redis FAQ + `/sync?brand=zeo` | Schedule interval chưa explicit |
| CFC Co Bay Knowledge | `92I5floRW5MElgu5` | 7/6 | Manual + schedule | Redis FAQ + `/sync?brand=cfc` | Schedule interval chưa explicit |
| Zeo Learning Queue Export | `sUgJYuP1hj75sERu` | 6/5 | Manual + 5 phút | Redis list -> Google Sheet | Có requeue khi append báo lỗi |
| CFC Learning Queue Export | `hPY4cMva4TOCOXee` | 6/5 | Manual + 5 phút | Redis list -> Google Sheet | Có requeue khi append báo lỗi |
| Chatbot Operations Alert | `f2IjxVj9sW3KQRAw` | 8/7 | Execute Workflow + manual | Redis dedup -> Telegram | Scaffold chưa đủ cấu hình |
| Zeo Shopee Catalog Sync | `ivng9UpBOEGTnVvr` | 6/5 | Manual + cron 00:00 | Redis catalog + cache refresh | Chỉ tự chạy khi live active |

### 7.1 Messenger Workflows

Luồng source:

```text
Facebook Trigger
  -> LocDauVao
  -> POST http://127.0.0.1:8000/api/chat-pipeline
  -> PrepareMessengerReply
  -> POST https://graph.facebook.com/v17.0/me/messages
```

Connection thứ năm là error output của FastAPI request quay về `PrepareMessengerReply` để dùng fallback text.

`[GAP]` `LocDauVao` chỉ bóc tách và đánh dấu `emptyInput`, `inputKind`, `isEcho`; nó chưa lọc các item này. Attachment, input rỗng hoặc echo vẫn đi tiếp nếu trigger phát event.

`[GAP]` `fb_name` được đọc trong HTTP body nhưng không được node `LocDauVao` xuất ra, nên giá trị gửi FastAPI hiện thường rỗng.

`[GAP]` Node gửi Graph API không có retry/error branch riêng. Phiên bản Graph API `v17.0` cần được kiểm tra khả dụng trước deploy, không suy từ source rằng nó còn được Meta hỗ trợ.

### 7.2 FAQ Knowledge Workflows

```text
Google Sheet FAQ
  -> normalize, filter active/brand/customer audience
  -> validate minimum rows, duplicate intent, examples
  -> write {brand}:kb:basic:active
  -> write {brand}:sync:faq:basic:last-success
  -> POST /sync?brand=...
```

`[GAP]` Schedule node của ZeO và CFC chỉ có `field: 'minutes'`, chưa đặt `minutesInterval`. Không gọi đây là cron 00:00.

`[GAP]` Metadata `last-success` được ghi trước khi gọi rebuild vector. HTTP rebuild dùng `continueRegularOutput`; rebuild thất bại có thể để metadata mới nhưng vector index cũ và workflow vẫn trông như đã hoàn tất.

### 7.3 Shopee Catalog Workflow

```text
Google Sheet / Shopee_Catalog
  -> normalize active rows có name + link
  -> write zeo:shopee:catalog:active
  -> POST /api/shopee/refresh-cache
```

- Cron source: `0 0 * * *`, timezone `Asia/Ho_Chi_Minh`.
- Redis chỉ lưu mảng `snapshot_json`; workflow không ghi một metadata key riêng.
- Mỗi product được gắn `updated_at` khi normalize.

`[GAP]` Validation chỉ yêu cầu tối thiểu một product. Chưa có expected minimum count, duplicate `item_id`, brand allowlist, URL schema hoặc price sanity check. Một lần đọc Sheet thiếu vẫn có thể ghi đè snapshot đầy đủ.

`[GAP]` Workflow không giữ trường `badge`, nên ranking bestseller/new-arrival có thể mất sau sync.

`[GAP]` Cache refresh xảy ra sau Redis write và HTTP error được cho đi tiếp. Redis có thể mới trong khi FastAPI process vẫn dùng cache cũ.

### 7.4 Learning Queue Workflows

```text
POP {brand}:learning:queue
  -> normalize event
  -> append Google Sheet LearningQueue
  -> nếu append trả error output: PUSH lại Redis list
```

`[GAP]` Đây không phải reliable queue end-to-end. Event đã bị POP trước khi ghi Sheet; process chết giữa POP và append/requeue có thể làm mất event. Retry sau khi Sheet đã ghi nhưng client không nhận ack có thể tạo dòng trùng vì chưa có idempotent upsert theo `event_id`.

### 7.5 Operations Alert Workflow

- Dedup key có TTL 900 giây.
- Local node Telegram đang dùng `chatId: SET_TELEGRAM_CHAT_ID_IN_N8N`.
- Local node Telegram chưa gắn credential.
- Không có workflow nào trong tám file local gọi workflow alert này.

Vì vậy `[CONFIGURED]` đây mới là scaffold nhận event/manual test, không được xem là Telegram alert production đã hoạt động. Python `telegram_notifier.py` là đường thông báo khác.

## 8. Data Sync Và Consistency Boundary

### 8.1 FAQ

```text
Sheet -> n8n validation -> Redis snapshot -> Python vector rebuild
```

Consistency hiện không atomic giữa snapshot và vector index. Consumer có thể thấy FAQ snapshot mới trong khi vector index vẫn cũ nếu rebuild lỗi.

Mục tiêu nâng cấp:

- ghi snapshot vào key staging;
- rebuild index theo `source_version/snapshot_hash`;
- chỉ promote active version khi snapshot và index đều thành công;
- ghi metadata success sau bước promote;
- lưu error state riêng thay vì nuốt lỗi.

### 8.2 Shopee

```text
Sheet -> normalize -> Redis active snapshot -> process-local cache refresh
```

Consistency hiện không atomic giữa Redis và cache của một hoặc nhiều FastAPI process.

Mục tiêu nâng cấp:

- validate count/hash/schema ở staging key;
- atomic promote snapshot;
- publish version/invalidation event;
- mỗi worker xác nhận version đã nạp;
- giữ snapshot trước để rollback.

## 9. Runtime Scripts

### 9.1 `testing/start_all.sh`

| Mode | Thành phần | Public tunnel | Readiness/test |
|---|---|---|---|
| Interactive mặc định | Redis, n8n, Cloudflared, Ollama, FastAPI | Có | Fixed sleep, không readiness đầy đủ |
| `--background` | Redis, n8n, Cloudflared, Ollama, FastAPI | Có | Fixed sleep, ghi `logs/pids.txt` |
| `--test` | Redis, Ollama, FastAPI | Không | Health wait, unit discovery và 3 API smoke requests |

`--test` không chạy `eval_test_suite.py` và không tự dọn các process/container mà nó tạo. PID test được ghi vào `logs/test-pids.txt`, nhưng `testing/stop_all.sh` không đọc file này.

Interactive/background bind Ollama và FastAPI trên `0.0.0.0`; FastAPI chạy `uvicorn --reload`. Đây là launcher development/local, không phải cấu hình production.

`[GAP]` `npx n8n start` không pin version. Interactive/background không kiểm tra đầy đủ service đã sẵn sàng; Redis startup error còn bị `|| true` bỏ qua.

### 9.2 `testing/stop_all.sh`

- Đọc `logs/pids.txt` của background mode.
- Sau đó chạy fallback `pkill -f` cho n8n, cloudflared, Ollama, uvicorn/Python.
- Force-kill mọi listener trên TCP port 8000.
- Không đọc `logs/test-pids.txt` hoặc `logs/python_api.pid`.
- Hardcode đường dẫn `$HOME/Documents/David-nguyen/N8n/logs`.

Đây là script có phạm vi rộng. Phải kiểm tra process target trước khi chạy; không dùng như primitive quản lý process production.

## 10. Runtime Snapshot Gần Nhất

Snapshot dưới đây được chép từ phiên audit local ngày 22/08/2026 và không được coi là trạng thái đang chạy ở thời điểm đọc tài liệu:

| Hạng mục | Snapshot | Nhãn |
|---|---|---|
| FastAPI `:8000` | Health từng pass trong phiên; lần curl cuối không còn listener | `[RUNTIME-LOCAL]` |
| Redis FAQ | ZeO 65 customer records, CFC 19 | `[RUNTIME-LOCAL]` |
| Redis Shopee | ZeO 52 records: 49 stock, 3 out-of-stock | `[RUNTIME-LOCAL]` |
| CFC Shopee | Chưa có catalog runtime/fallback tương đương | `[RUNTIME-LOCAL]` |
| Unit discovery | 26/26 pass | `[TEST-LOCAL]` |
| Offline eval | 112/112 theo expectation runner, trung bình 2,7ms/lượt; không chạy lại sau lần health cuối | `[HISTORICAL-LOCAL]` |
| Markdown scenarios `--all` | 48/55 lượt pass; 4 scenario còn REVIEW; không chạy lại sau lần health cuối | `[HISTORICAL-LOCAL]` |
| n8n production | Không kiểm tra live | `[UNVERIFIED-PROD]` |
| Messenger thật | Không kiểm tra live | `[UNVERIFIED-PROD]` |

Con số 2,7ms là pipeline offline/degraded, không bao gồm Redis/Ollama/Meta/n8n end-to-end và không được dùng làm SLA.

## 11. Production Verification Gate

Trước khi gọi hệ thống là production-ready, cần có bằng chứng cho toàn bộ mục sau:

1. Xác minh đúng environment n8n, workflow ID, project và credential mapping.
2. Pull/compare drift trước khi push; không force overwrite remote change.
3. Validate tám workflow và kiểm tra node credential bắt buộc.
4. Activate đúng workflow live; xác nhận Facebook webhook subscription.
5. Kiểm tra Graph API version và gửi/nhận Messenger thật.
6. Kiểm tra FastAPI URL từ chính network namespace của n8n; `127.0.0.1` chỉ đúng khi hai service cùng host namespace.
7. Chạy FAQ sync và xác nhận snapshot version khớp vector index version.
8. Chạy Shopee sync với guard count/hash, kiểm tra cache của mọi worker.
9. Kiểm tra duplicate webhook, echo, attachment và empty input.
10. Kiểm tra Redis/Ollama/FastAPI restart, timeout và degraded fallback.
11. Chạy unit, offline eval, failure tests, load và soak test theo `docs/09_PERFORMANCE_PLAN.md`.
12. Bảo vệ `/admin/*`, giới hạn CORS và không public dev `--reload` qua tunnel.

Chỉ sau khi gate này có log/execution ID/timestamp mới gắn nhãn `[VERIFIED-PROD]` cho từng thành phần.
