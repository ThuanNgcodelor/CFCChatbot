# Điểm Yếu Và Rủi Ro Ưu Tiên Của Chatbot ZeO/CFC

Ngày lập: 2026-08-22  
Phạm vi: FastAPI, RAG, Redis, Ollama, Shopee catalog, session memory, Admin API và bộ kiểm thử trong workspace `N8n/`.

Tài liệu này là báo cáo rủi ro độc lập. Nó không phải bằng chứng production đã lỗi hoặc đã an toàn. Mọi kết luận đều gắn với một trong bốn mức bằng chứng bên dưới.

## 1. Quy Ước Bằng Chứng

| Nhãn | Ý nghĩa |
|---|---|
| `SOURCE` | Đã đọc trực tiếp source/data trong workspace ngày 22/08/2026. |
| `LOCAL` | Đã quan sát bằng kiểm tra read-only hoặc test local; không đại diện production. |
| `HISTORICAL` | Kết quả được ghi nhận ở lần chạy trước; có thể không phản ánh trạng thái hiện tại. |
| `PRODUCTION UNKNOWN` | Chưa xác minh reverse proxy, auth, workflow active, Redis production, Messenger thật hoặc execution n8n production. |

Line number trong tài liệu là line tại thời điểm audit và có thể dịch chuyển sau khi source thay đổi. Tên file và function là mốc định vị chính.

## 2. Thang Mức Độ

| Mức | Tiêu chí |
|---|---|
| `P0` | Có thể gây lộ bí mật/PII, thực thi lệnh, thay đổi production, hoặc đưa claim an toàn nghiêm trọng tới khách. Phải xử lý trước khi public hoặc demo trên hạ tầng thật. |
| `P1` | Có thể làm sai dữ liệu, sai câu trả lời, sai ngữ cảnh hoặc tạo tín hiệu test xanh giả. Cần xử lý trước rollout rộng. |
| `P2` | Rủi ro vận hành, freshness, provenance hoặc khả năng tái lập. Cần có kế hoạch và SLO rõ ràng. |

## 3. Bảng Ưu Tiên

| ID | Severity | Vấn đề | Trạng thái |
|---|---|---|---|
| W-001 | P0 | Admin API chưa có auth, có thể lộ secrets/PII và mở đường tới shell/deploy | Mở |
| W-002 | P0 | Claim an toàn/hiệu quả không grounded và chưa có output validator | Mở |
| W-003 | P1 | Contract Shopee catalog lệch giữa CSV, workflow, admin sync và matcher | Mở |
| W-004 | P1 | Audience isolation không được bảo đảm trên mọi đường ingest/retrieval | Mở |
| W-005 | P1 | Conversation state chưa an toàn cho follow-up nhanh, restart và multi-worker | Mở |
| W-006 | P1 | Regression runner có thể trả exit code thành công dù chất lượng chưa đạt | Mở |
| W-007 | P2 | Freshness và provenance của catalog/knowledge chưa đủ để gọi là realtime | Mở |

## 4. W-001 — Admin API Chưa Có Auth, Có Thể Lộ Secrets/PII Và Mở Đường Tới Shell/Deploy

**Severity:** `Critical (P0)`

### Hiện trạng

Admin routes được mount mà không có lớp authentication/authorization chung; cùng bề mặt này có settings, customer data, workflow mutation và assistant tool có thể chạy shell.

### Evidence (Bằng chứng)

**SOURCE — đã xác minh**

- `ChatbotN8n/javis/server/main.py:92-97`, cấu hình `CORSMiddleware` cho phép mọi origin, method và header.
- `ChatbotN8n/javis/server/admin_routes.py:29-39`, toàn bộ domain router được include dưới `/admin` nhưng không có dependency xác thực/ủy quyền ở facade.
- `ChatbotN8n/javis/server/domains/system/routes.py:19-49`, `GET /admin/settings` trả cấu hình hiện tại và `POST /admin/settings` có thể ghi cấu hình.
- `ChatbotN8n/javis/server/domains/common/config.py:19-51`, `get_cfg()` có thể tự nạp Redis password từ `.env` và trả object cấu hình nguyên trạng.
- `ChatbotN8n/javis/server/domains/customers/routes.py:23-72`, API có thể list/export profile, đọc session/history, sửa và xóa dữ liệu khách.
- `ChatbotN8n/javis/server/domains/assistant/routes.py:12-23`, endpoint assistant nhận nội dung tự do và gọi agent.
- `ChatbotN8n/javis/server/ai_agent_tools.py:174-191`, schema công cụ khai báo `execute_system_command` nhận câu lệnh shell tự do.
- `ChatbotN8n/javis/server/ai_agent_tools.py:620-660`, lệnh được chạy bằng `asyncio.create_subprocess_shell`; denylist chỉ chặn một số chuỗi hủy diệt cụ thể.
- `ChatbotN8n/javis/server/ai_agent_tools.py:705-749`, dispatcher cho phép model gọi công cụ shell.
- `ChatbotN8n/javis/server/domains/n8n/routes.py:28-34,80-86`, API có thể toggle và deploy workflow n8n.
- `ChatbotN8n/javis/server/scripts/shopee_auth.json` đang được Git theo dõi và là file không rỗng. Audit không đọc hoặc sao chép nội dung bí mật của file.

**LOCAL — đã xác minh**

- Chỉ xác minh source và trạng thái Git của file auth; không gọi endpoint settings, customer, shell, toggle hoặc deploy để tránh lộ dữ liệu và thay đổi runtime.

**HISTORICAL**

- Ảnh/log vận hành trước đây cho thấy dashboard từng được truy cập qua tunnel. Đây không phải bằng chứng route production hiện vẫn public.

**PRODUCTION UNKNOWN**

- Chưa xác minh reverse proxy có lớp SSO, Access Policy, IP allowlist hoặc mTLS ở phía trước FastAPI hay không.
- Chưa xác minh domain production hiện route toàn bộ `/admin/*` hay chỉ route một phần.

### Root cause

- Admin dashboard và API được thiết kế theo mô hình trusted-localhost nhưng có khả năng được đưa qua public tunnel.
- Authentication, authorization, secret redaction và tool permissions chưa được đặt ở boundary chung.
- Tool shell dùng denylist chuỗi thay vì allowlist hành động cố định hoặc sandbox tách biệt.

### Tác động

- Lộ API key, token, Redis password, lịch sử chat, số điện thoại hoặc ghi chú CRM.
- Kẻ tấn công có thể sửa cấu hình, xóa session, toggle/deploy workflow hoặc điều khiển shell thông qua agent.
- Prompt injection vào assistant có thể chuyển từ lỗi nội dung thành lỗi hạ tầng.

### Giải pháp

1. Không public `/admin` cho tới khi có auth ở FastAPI hoặc reverse proxy đã được xác minh.
2. Thêm authentication ở facade router và RBAC tối thiểu: `viewer`, `operator`, `deployer`, `security-admin`.
3. `GET /admin/settings` chỉ trả cấu hình đã redact; không bao giờ trả password/token/key.
4. Xóa `execute_system_command` khỏi tool schema production. Nếu thật sự cần, thay bằng các tool read-only có tham số typed và allowlist cố định.
5. Yêu cầu xác nhận ngoài mô hình cho mọi thao tác thay đổi workflow, settings hoặc dữ liệu khách.
6. Giới hạn CORS theo origin quản trị đã cấu hình; thêm CSRF protection nếu dùng cookie session.
7. Revoke/rotate browser session liên quan, bỏ file auth khỏi Git index/history và chỉ lưu secret ở runtime secret store. Giữ một file mẫu không chứa credential.
8. Ghi audit log bất biến cho login, settings change, data export, workflow deploy và tool call.

### Expected improvement

- Unauthenticated admin access giảm về `0`.
- Secret/PII exposure qua API giảm về `0`.
- Unauthorized shell/tool/deploy execution giảm về `0`.
- Có khả năng truy vết đầy đủ ai đã thay đổi gì và khi nào.

### Acceptance gate

- Tất cả request không auth tới `/admin/*` trả `401/403`, ngoại trừ endpoint public được liệt kê rõ.
- Secret scanner xác nhận response/settings/docs/log không chứa credential thật.
- Prompt-injection suite không thể gọi shell, deploy, toggle hoặc export PII khi thiếu đúng role và explicit approval.

## 5. W-002 — Claim An Toàn/Hiệu Quả Không Grounded Và Chưa Có Output Validator

**Severity:** `Critical (P0)`

### Hiện trạng

Một số matcher và prompt tự bổ sung claim safety/efficacy/marketing ngoài fact đã truy xuất, trong khi output chưa được kiểm chứng từng claim trước khi trả khách.

### Evidence (Bằng chứng)

**SOURCE — đã xác minh**

- `ChatbotN8n/javis/server/shopee_matcher.py:1189-1194`, `match_skin_care_dishwashing()` khẳng định sản phẩm “hoàn toàn không ăn da tay”.
- `ChatbotN8n/javis/server/shopee_matcher.py:1234-1243`, `match_baby_or_sensitive_laundry()` thêm claim không kích ứng và đã kiểm nghiệm an toàn da liễu, kể cả nhánh fallback hardcode.
- `ChatbotN8n/javis/server/shopee_matcher.py:1287-1291`, `match_front_load_washer()` thêm claim liên quan tắc nghẽn/hỏng vi mạch.
- `ChatbotN8n/javis/server/shopee_matcher.py:1329-1337`, `match_stain_removal_or_efficacy()` khẳng định “hoàn toàn” tẩy được vết máu và mẹo sạch `100%`, đồng thời gợi ý Javen.
- `ChatbotN8n/javis/server/ai_engine.py:626-650`, `reason_and_answer_cskh()` hardcode website, hotline, Shopee, Freeship và chính sách chiết khấu vào system prompt thay vì nhận toàn bộ từ facts.
- `ChatbotN8n/javis/server/ai_engine.py:656-657`, khi không có fact, model vẫn được phép trả lời bằng “thông tin chung của thương hiệu”.
- `ChatbotN8n/javis/server/ai_engine.py:694-709`, output chỉ được kiểm tra thành công, độ dài và một số emoji; chưa có validator đối chiếu từng claim với `source_id`, `product_id`, giá, tồn kho hoặc URL.

**LOCAL — đã xác minh**

- Offline eval từng trả các claim tuyệt đối nêu trên nhưng vẫn được runner tính PASS vì expectation tập trung vào intent hoặc từ khóa.

**HISTORICAL**

- Mốc `112/112` ngày 21/08/2026 và lần offline/degraded ngày 22/08/2026 không phải chứng nhận zero-hallucination.

**PRODUCTION UNKNOWN**

- Chưa replay transcript Messenger production để đo tỷ lệ claim không được nguồn hỗ trợ.
- Chưa xác minh model/provider nào đang thực sự synthesize ở production.

### Root cause

- Product matching và fact generation bị trộn trong cùng function; sau khi tìm tên/giá/link, function tự bổ sung kiến thức marketing/safety.
- Prompt “không bịa” được xem như validator, trong khi LLM không bảo đảm tuân thủ tuyệt đối.
- Golden set hiện chưa mô hình hóa `expected_facts` và `must_not_say` ở mức claim.

### Tác động

- Có thể tư vấn sai về da nhạy cảm, trẻ em, hóa chất hoặc cách dùng Javen.
- Tăng rủi ro khiếu nại, mất uy tín và rủi ro tuân thủ quảng cáo/sản phẩm.
- Một câu trả lời đúng intent vẫn có thể chứa fact sai hoặc nguy hiểm.

### Giải pháp

1. Tách `retrieval/tool result` khỏi `response template`; matcher chỉ trả structured facts và provenance.
2. Chuyển mọi claim thành record được duyệt trong Sheet/knowledge store với `fact_id`, `source_id`, `risk_level`, `valid_from`, `reviewed_by` và `expires_at` khi cần.
3. Bỏ ngôn ngữ tuyệt đối như “100%”, “hoàn toàn”, “không kích ứng” nếu không có tài liệu được duyệt hỗ trợ trực tiếp.
4. Với safety/chemical questions, dùng template thận trọng, yêu cầu đọc nhãn và chuyển admin khi thiếu dữ liệu.
5. Thêm output validator: trích claim có số, URL, tồn kho, chứng nhận, hiệu quả và safety; mỗi claim phải map được về fact nguồn.
6. Nếu validator fail, trả deterministic fallback và ghi learning/review event; không để LLM tự sửa fact.
7. Thêm golden cases có `expected_facts` và `must_not_say` theo kế hoạch tại `08_RAG_EVALUATION_PLAN.md`.

### Expected improvement

- `UnsupportedCriticalClaimRate = 0` cho giá, link, tồn kho, safety, chứng nhận và hướng dẫn hóa chất.
- Giảm khiếu nại do lời hứa tuyệt đối và tăng khả năng audit từng câu trả lời.
- Intent accuracy không còn che lấp lỗi factuality.

### Acceptance gate

- Mọi claim critical trong output có `fact_id/source_id` hợp lệ hoặc bị fallback.
- Không case nào vi phạm `must_not_say` trong safety/adversarial golden set.
- Test bằng dữ liệu trống không được sinh tên sản phẩm, giá, link, chứng nhận hoặc claim hiệu quả mới.

## 6. W-003 — Contract Shopee Catalog Lệch Giữa CSV, Workflow, Admin Sync Và Matcher

**Severity:** `High (P1)`

### Hiện trạng

CSV, workflow Shopee, admin direct sync và matcher không dùng cùng một product schema; snapshot Redis local đã mất toàn bộ badge dù CSV có badge.

### Evidence (Bằng chứng)

**SOURCE — đã xác minh**

- `ChatbotN8n/javis/server/shopee_matcher.py:88-172`, runtime ưu tiên Redis, sau đó fallback CSV; cache RAM không tự kiểm schema.
- `ChatbotN8n/javis/server/shopee_matcher.py:113-127`, CSV fallback giữ `item_id`, `category`, `badge`, `link_shopee`, `in_stock`.
- `ChatbotN8n/workflows/local-n8n/zeo_shopee_sync.workflow.ts:128-142`, workflow Redis không ghi trường `badge` và thay `updated_at` bằng giờ sync.
- `ChatbotN8n/javis/server/shopee_matcher.py:631-661`, bestseller phụ thuộc `badge`; nếu badge thiếu thì fallback lấy các item còn hàng đầu tiên nhưng vẫn gọi là bán chạy nhất.
- `ChatbotN8n/javis/server/shopee_matcher.py:698-728`, new-arrival có cùng lỗi fallback theo thứ tự item.
- `ChatbotN8n/javis/server/domains/knowledge/service.py:259-299,369-409`, admin direct sync/upload ghi schema `variant`, `promotion`, `link`, thiếu nhiều field matcher cần.
- Cùng service gọi `reload_catalog()` ở line `298-299` và `408-409`, nhưng `shopee_matcher.py` chỉ định nghĩa `refresh_shopee_cache()` ở line `177`; exception bị nuốt.

**LOCAL — đã xác minh**

- Redis local có 52 sản phẩm ZeO, gồm 49 còn hàng và 3 hết hàng.
- Snapshot Redis local không có `badge` trong bất kỳ record nào.
- CSV local có 52 record và có badge, nên hành vi Redis-first khác hành vi CSV fallback.

**HISTORICAL**

- Các câu demo cũ từng gắn “Top 1/Bestseller/New Arrival” theo snapshot trước; không dùng làm bằng chứng ranking hiện tại.

**PRODUCTION UNKNOWN**

- Chưa đọc Redis catalog production và chưa kiểm tra workflow Shopee production đã deploy phiên bản nào.
- Chưa xác minh Sheet production có badge/rank đầy đủ hay không.

### Root cause

- Không có một schema typed/canonical dùng chung cho CSV parser, n8n normalization, admin direct sync và matcher.
- Sync ghi thẳng key active trước khi validate contract đầy đủ.
- Cache refresh lỗi nhưng exception bị bỏ qua, làm trạng thái Redis và RAM có thể khác nhau.

### Tác động

- Sai hoặc thiếu link, category, stock, price metadata và rank.
- Bot có thể gọi sản phẩm đầu tiên là “bán chạy nhất/mới ra mắt” mà không có bằng chứng.
- Admin một-click sync có thể ghi snapshot hợp lệ về JSON nhưng không hợp lệ về nghiệp vụ.

### Giải pháp

1. Định nghĩa một `CatalogProduct` schema bắt buộc: `product_id`, `brand`, `name`, `category`, `price_current`, `price_original`, `discount`, `in_stock`, `url`, `badge/rank`, `source_updated_at`, `source_version`.
2. Mọi producer phải normalize về schema này; cấm schema riêng cho admin direct sync.
3. Validate toàn snapshot trước khi atomic swap từ staging key sang active key.
4. Reject snapshot nếu thiếu field critical, duplicate `product_id`, URL không hợp lệ, giá âm hoặc `in_stock` không parse được.
5. Thay lời gọi cache bằng đúng `refresh_shopee_cache()` và không nuốt exception quan trọng.
6. Khi không có badge/rank đáng tin cậy, trả “gợi ý” thay vì “bán chạy nhất/mới nhất”.
7. Thêm contract tests cho CSV, workflow payload, admin upload, Redis snapshot và matcher.

### Expected improvement

- `CatalogSchemaViolationRate = 0` trên snapshot active.
- `RankingUnsupportedClaimRate = 0`.
- Redis-first và CSV-fallback cho cùng kết quả trên cùng fixture.
- Admin sync thất bại an toàn, không làm hỏng snapshot đang chạy.

### Acceptance gate

- Snapshot thiếu badge không được sinh ngôn ngữ “Top/Bán chạy nhất/Mới nhất”.
- Malformed upload trả lỗi và active key giữ nguyên.
- Contract test xác nhận mọi producer/consumer dùng cùng field và type.

## 7. W-004 — Audience Isolation Không Được Bảo Đảm Trên Mọi Đường Ingest/Retrieval

**Severity:** `High (P1)`

### Hiện trạng

Đường sync chuẩn có lọc customer audience, nhưng Python sync, CSV fallback và một số admin sync path chưa thực thi cùng một allowlist end-to-end.

### Evidence (Bằng chứng)

**SOURCE — đã xác minh**

- `ChatbotN8n/javis/server/rag_search.py:136-172`, CSV fallback nạp mọi row active, không chỉ `audience=customer`.
- `ChatbotN8n/javis/server/rag_search.py:175-223`, các row này được đưa vào intent/phrase cache.
- `ChatbotN8n/javis/server/rag_search.py:399-401,454-457`, rerank chỉ trừ điểm `audience=agent`, không loại bỏ chắc chắn.
- `ChatbotN8n/javis/server/knowledge_sync.py:167-178`, vector sync chỉ loại `audience=internal`, không loại `agent`.
- `ChatbotN8n/workflows/local-n8n/zeo_knowledge_sync_basic.workflow.ts:200-206`, đường n8n chuẩn có lọc chính xác `audience === 'customer'`.
- `ChatbotN8n/javis/server/domains/knowledge/service.py:232-241,342-351`, admin direct FAQ sync bỏ trường `audience`; downstream có thể mặc định thành customer.
- ZeO FAQ CSV có 81 record: 65 customer và 16 agent.

**LOCAL — đã xác minh**

- Redis local hiện có 65 FAQ ZeO customer và 19 FAQ CFC customer, phù hợp đường workflow chuẩn.
- Lỗ hổng nằm ở fallback CSV, vector sync độc lập và admin direct sync; không khẳng định local Redis hiện đã chứa agent row.

**HISTORICAL**

- Không có artifact chứng minh agent content đã được gửi cho khách; đây là rủi ro có đường thực thi trong source.

**PRODUCTION UNKNOWN**

- Chưa kiểm tra vector docs production hoặc replay query nhằm vào 16 agent row.

### Root cause

- Audience được xử lý như tín hiệu rerank thay vì security boundary.
- Các producer có quy tắc lọc khác nhau.
- Thiếu allowlist query-time để phòng trường hợp snapshot/index bị nhiễm.

### Tác động

- Bot khách hàng có thể trả template nội bộ, hướng dẫn giọng điệu, nội dung marketing hoặc thông tin không dành cho khách.
- Direct sync có thể vô tình nâng nội dung agent thành customer.
- Vi phạm nguyên tắc single source of truth và tách dữ liệu theo audience.

### Giải pháp

1. Dùng allowlist duy nhất: customer pipeline chỉ ingest và retrieve `audience == customer`.
2. Áp dụng filter tại bốn lớp: producer, snapshot validation, vector/lexical index và query-time.
3. Admin/agent knowledge dùng index/namespace riêng và endpoint riêng có auth.
4. Preserve `audience` ở mọi đường sync; từ chối row thiếu audience thay vì mặc định customer.
5. Thêm negative retrieval tests cho toàn bộ 16 agent intent.

### Expected improvement

- `AudienceLeakRate = 0` ở retrieval và final answer.
- Admin sync không thể thay đổi audience ngầm.
- Customer và internal assistant có nguồn dữ liệu, quyền và audit trail rõ ràng.

### Acceptance gate

- Mọi agent/internal document có rank “không xuất hiện” đối với customer query.
- Fixture cố ý nhiễm agent row vào Redis vẫn bị query-time filter loại.
- Missing/unknown audience làm sync fail trước atomic swap.

## 8. W-005 — Conversation State Chưa An Toàn Cho Follow-up Nhanh, Restart Và Multi-worker

**Severity:** `High (P1)`

### Hiện trạng

Structured state đã có nhưng coordination/cache nằm trong process và Redis write chưa có turn sequence, version/CAS hoặc TTL; duplicate `message_id` chưa bị loại.

### Evidence (Bằng chứng)

**SOURCE — đã xác minh**

- `ChatbotN8n/javis/server/chat_pipeline.py:62-68`, per-sender lock và local session/customer cache chỉ tồn tại trong process.
- `ChatbotN8n/javis/server/chat_pipeline.py:106-110`, lock không phân phối giữa nhiều worker/instance.
- `ChatbotN8n/javis/server/chat_pipeline.py:307-329`, state chưa có `session_version`, `turn_seq` hoặc TTL policy.
- `ChatbotN8n/javis/server/chat_pipeline.py:1458-1503`, pipeline ưu tiên cache process trước Redis khi load context.
- `ChatbotN8n/javis/server/chat_pipeline.py:1561-1581`, phần lớn fast path cập nhật RAM rồi tạo background task ghi Redis.
- `ChatbotN8n/javis/server/chat_pipeline.py:2840-2882`, final RAG path tạo background save nhưng không cập nhật local cache tương ứng trước khi trả response.
- `ChatbotN8n/javis/server/chat_pipeline.py:2932-2987`, session dùng plain `SET`, history `RPUSH/LTRIM`, không CAS/version check/TTL.

**LOCAL — đã xác minh**

- Các unit/multi-turn test hiện chủ yếu chạy một process, một event loop; không kiểm tra restart hoặc hai worker cạnh tranh.

**HISTORICAL**

- Các lỗi “sản phẩm đó”, “cái số 2” và stale product context từng xuất hiện trong transcript trước; một số case đã được sửa cho single-process flow.

**PRODUCTION UNKNOWN**

- Chưa xác minh số worker FastAPI production, sticky session, Redis latency hoặc thứ tự message thực tế từ Messenger/n8n.

### Root cause

- Tối ưu latency bằng cache RAM/background write được triển khai trước khi có protocol versioning cho critical state.
- Lock không dùng Redis/distributed primitive.
- Không có idempotency key/turn sequence ở session update.

### Tác động

- Follow-up có thể đọc context cũ và trả sai sản phẩm, giá hoặc link.
- Task cũ có thể ghi đè state mới khi nhiều worker xử lý hoặc khi message đến dồn dập.
- Restart có thể làm mất state chưa kịp ghi; session không TTL có thể giữ context quá lâu.

### Giải pháp

1. Thêm `session_version`, `turn_seq`, `message_id`, `updated_at` và TTL có chủ đích.
2. Ghi write-through cho critical state trước khi trả response; analytics/transcript có thể tiếp tục async.
3. Dùng CAS/Lua transaction hoặc distributed per-sender lock khi chạy nhiều worker.
4. Chỉ chấp nhận update có `turn_seq` mới hơn; duplicate message phải idempotent.
5. Xác định cache invalidation khi Redis snapshot/catalog version đổi.
6. Test burst, out-of-order, duplicate, restart giữa hai turn và multi-worker.

### Expected improvement

- `ReferenceResolutionAccuracy` ổn định sau restart và khi nhiều worker.
- `StaleContextRate = 0` cho explicit new entity và product-link/price follow-up critical.
- Không mất critical session state sau response thành công.

### Acceptance gate

- Bộ test hai worker và 20 message burst không đảo thứ tự state.
- Restart sau mỗi turn vẫn resolve đúng `product_id` ở turn kế.
- Duplicate `message_id` không tạo hai history event hoặc hai notification.

## 9. W-006 — Regression Runner Có Thể Trả Exit Code Thành Công Dù Chất Lượng Chưa Đạt

**Severity:** `High (P1)`

### Hiện trạng

Các runner hiện có nhiều case hữu ích nhưng assertion/exit-code chưa đủ để biến kết quả thành release gate cho factuality, retrieval và scenario quality.

### Evidence (Bằng chứng)

**SOURCE — đã xác minh**

- `ChatbotN8n/javis/server/eval_test_suite.py:310-325`, single-turn chủ yếu so intent và chấp nhận nhiều nhóm synonym rộng.
- `ChatbotN8n/javis/server/eval_test_suite.py:354-370`, chỉ một số multi-turn case kiểm tra link hoặc substring; chưa kiểm tra toàn bộ facts.
- `ChatbotN8n/javis/server/eval_test_suite.py:387-409`, runner in tổng kết nhưng không `sys.exit(1)` khi có failure.
- `ChatbotN8n/javis/server/run_test_md_scenarios.py:304-309`, một turn chỉ cần bất kỳ `expect_words` nào xuất hiện.
- `ChatbotN8n/javis/server/run_test_md_scenarios.py:321-369`, REVIEW không làm process thất bại.
- `testing/start_all.sh:55-90`, `--test` chạy unit discovery và ba API price/link smoke, không chạy toàn bộ eval/scenario.
- `testing/run_test_md_scenarios.py:11`, wrapper dựng sai `SERVER_DIR` dưới thư mục `testing/`.

**LOCAL — đã xác minh**

- Unit discovery: `26/26 PASS`.
- `eval_test_suite.py`: `112/112 PASS` trong chế độ offline/degraded; đây là 98 single-turn + 14 scenario, tổng 131 lượt pipeline.
- `run_test_md_scenarios.py --all`: `48/55` lượt, tương đương `87,3%`; scenario 04, 05, 09 và 16 còn REVIEW.

**HISTORICAL**

- Mốc 21/08/2026 từng báo `112/112` và một tập con scenario pass. Không thể suy ra toàn bộ hệ thống hoặc production pass.

**PRODUCTION UNKNOWN**

- Chưa có CI artifact, JUnit/JSON report, dataset hash, model version và production replay report để đối chiếu.

### Root cause

- Eval được xây như script quan sát thủ công, chưa phải quality gate cho CI.
- Expected intent được ưu tiên hơn document/fact/forbidden-claim.
- Degraded mode và live dependency mode không được tách thành hai loại kết quả bắt buộc.

### Tác động

- Pipeline/CI có thể xanh dù test fail hoặc answer chứa claim sai.
- “100% PASS” dễ bị hiểu thành production readiness.
- Regression factuality, safety và context có thể lọt qua nếu intent vẫn đúng.

### Giải pháp

1. Chuẩn hóa golden set theo `08_RAG_EVALUATION_PLAN.md` với `expected_documents`, `expected_facts`, `must_not_say`.
2. Runner trả nonzero khi bất kỳ P0/P1 gate fail; xuất JSON + JUnit artifact.
3. Tách `offline-fixture`, `local-integration`, `live-shadow` và `production-canary` thành report riêng.
4. Ghi dependency health, model/embedder version, source version và dataset hash trong mỗi run.
5. Sửa wrapper hoặc xóa wrapper legacy; `start_all --test` phải gọi đúng bộ regression bắt buộc.
6. Không cho synonym intent che lỗi document, numeric constraint, URL hoặc forbidden claim.

### Expected improvement

- CI status phản ánh đúng pass/fail.
- Có thể so sánh regression giữa commit/model/data version.
- Giảm khả năng phát hành câu trả lời đúng intent nhưng sai fact.

### Acceptance gate

- Một case fail làm command exit khác `0`.
- Scenario critical đạt `100%`; toàn bộ golden set đạt threshold đã định.
- Report chỉ được gắn nhãn live khi Redis/Ollama/index health và source version đã được ghi nhận.

## 10. W-007 — Freshness Và Provenance Chưa Đủ Để Gọi Catalog/Knowledge Là Realtime

**Severity:** `Medium (P2)`

### Hiện trạng

Catalog/knowledge là snapshot không TTL/source-version SLA đầy đủ; một số câu trả lời và tài liệu lịch sử dùng từ “realtime” dù không truy vấn trực tiếp Shopee tại thời điểm khách hỏi.

### Evidence (Bằng chứng)

**SOURCE — đã xác minh**

- `ChatbotN8n/javis/server/shopee_matcher.py:136-172`, cache catalog giữ trong RAM và không có TTL/freshness check.
- `ChatbotN8n/workflows/local-n8n/zeo_shopee_sync.workflow.ts:128-155`, `updated_at` được đặt bằng thời điểm workflow sync, không phải thời điểm nguồn Shopee/Sheet thay đổi.
- Cùng workflow có cron `0 0 * * *` tại line `60-69`, nhưng file local khai báo `active: false` tại line `32-37`.
- `ChatbotN8n/javis/server/main.py:45-56`, background sync 10 phút chỉ chạy khi `shopee.sheet_url` được cấu hình.
- `ChatbotN8n/javis/server/scripts/format_crawled_shopee_catalog.py:170-171` và `build_exact_shopee_catalog.py:334-338` phụ thuộc hai CSV crawl không có trong checkout hiện tại.
- Product memory chỉ preserve `source_version` khi nguồn đã cung cấp; schema không bắt buộc field này.

**LOCAL — đã xác minh**

- Catalog local có 52 record và là snapshot, không phải truy vấn Shopee live tại thời điểm khách hỏi.
- Hai file crawl đầu vào dùng để tái tạo snapshot 52 sản phẩm không có trong workspace.

**HISTORICAL**

- Snapshot và giá từng được sync ở các mốc trước; không được dùng như bằng chứng giá hiện tại nếu thiếu source timestamp/version.

**PRODUCTION UNKNOWN**

- Chưa xác minh workflow production active, lần execution thành công cuối, catalog age, Sheet version hoặc deep-link còn hoạt động.

### Root cause

- Metadata mô tả thời điểm ingest thay cho thời điểm dữ liệu nguồn.
- Không có freshness SLO, stale threshold và immutable source version/hash.
- Source crawl provenance chưa được lưu đầy đủ cùng artifact có thể tái lập.

### Tác động

- Bot có thể nói “hiện tại/realtime” với giá, tồn kho hoặc ranking đã cũ.
- Khó điều tra vì không biết câu trả lời dùng snapshot nguồn nào.
- Không thể tái tạo chắc chắn catalog từ workspace hiện tại.

### Giải pháp

1. Phân biệt `source_updated_at`, `ingested_at`, `validated_at` và `source_version`.
2. Đặt freshness SLO theo loại dữ liệu; ví dụ giá/tồn kho nghiêm hơn FAQ thương hiệu.
3. Nếu snapshot quá hạn, không dùng từ “hiện tại/realtime”; fallback và chuyển admin khi fact critical.
4. Lưu hash/version của Sheet export hoặc crawl artifact; giữ manifest nguồn nhưng không lưu credential/cookie.
5. Theo dõi execution success, record count, schema version, snapshot age và cache version.
6. Chỉ swap active key khi sync + validation + cache refresh đều thành công.

### Expected improvement

- Mỗi câu trả lời critical truy được về đúng snapshot/version.
- `StaleFactRate` giảm về `0` theo SLO đã chọn.
- Catalog có thể tái lập và rollback mà không dựa vào file nguồn thất lạc.

### Acceptance gate

- Fixture stale bắt buộc trả disclosure/fallback theo policy.
- Production dashboard hiển thị source age, last successful sync, record count và version.
- Không phát claim “realtime/hiện tại” nếu chưa có nguồn đủ mới.

## 11. Thứ Tự Khắc Phục Đề Xuất

1. Chặn public Admin API, rotate/revoke secret liên quan và vô hiệu hóa shell tool production.
2. Loại bỏ claim safety/efficacy không có nguồn; thêm critical-claim validator.
3. Chuẩn hóa catalog schema và atomic sync; sửa cache refresh.
4. Cô lập audience bằng allowlist ở mọi lớp.
5. Nâng session state lên versioned/write-through và test multi-worker.
6. Biến eval thành CI gate nonzero theo fact, document và forbidden claim.
7. Bổ sung freshness/provenance/SLO và shadow telemetry trước rollout.

## 12. Điều Kiện Được Gọi Là “Sẵn Sàng Production”

Không dùng cụm từ “production ready”, “zero hallucination”, “realtime” hoặc “100% an toàn” chỉ dựa trên unit/offline eval. Tối thiểu phải có:

- P0 gate bằng `0` violation.
- P1 regression đạt threshold và runner exit đúng.
- Production auth/reverse proxy được kiểm tra độc lập.
- Workflow active và execution gần nhất được xác minh trên n8n production.
- Redis/index/catalog production có version/freshness hợp lệ.
- Shadow replay không gửi câu trả lời thử nghiệm tới khách.
- Canary có rollback rule rõ ràng và không có critical incident.
