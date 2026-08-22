# Tổng Hợp Hệ Thống Chatbot ZeO / CFC Hiện Hành

Ngày cập nhật: 2026-08-22 (đối chiếu trực tiếp source, workflow, dữ liệu và test hiện có)
Phạm vi: `ChatbotN8n/javis/`, `ChatbotN8n/workflows/local-n8n/`, dữ liệu Google Sheet/CSV, Redis, Ollama, RAG và các file vận hành liên quan.

Đây là tài liệu sống của dự án. Khi nội dung tài liệu khác source/runtime thì ưu tiên source và trạng thái runtime thực tế, sau đó cập nhật lại tài liệu này. Lần rà soát này chỉ xác nhận source trong workspace; không tự suy ra trạng thái production từ file local.

Lưu ý bảo mật: không đưa password Redis, token n8n, API key, Facebook token, Telegram token, cookie hoặc browser auth-state thật vào tài liệu/ChatGPT/GPT bên ngoài. File `ChatbotN8n/javis/server/scripts/shopee_auth.json` hiện đang được Git theo dõi và chứa trạng thái đăng nhập trình duyệt; cần revoke/rotate phiên liên quan, bỏ file khỏi Git history/index và thay bằng file mẫu hoặc secret runtime.

### Trạng thái kiểm chứng của tài liệu

| Phạm vi | Trạng thái ngày 22/08/2026 |
|---|---|
| Source FastAPI, router, matcher, RAG | Đã đối chiếu trực tiếp file hiện có |
| 8 workflow `.workflow.ts` local | Đã đối chiếu cấu trúc, node, connection, schedule và endpoint; tất cả file local đang `active: false` |
| CSV/JSONL trong workspace | Đã đếm bằng parser; số liệu được ghi tại mục 4 và 15 |
| FastAPI local `:8000` | Health từng pass trong phiên audit ngày 22/08, nhưng lần kiểm tra cuối cùng không kết nối được port 8000; không coi service đang chạy ở thời điểm bàn giao |
| Redis runtime local | ZeO FAQ 65 customer records, CFC FAQ 19; ZeO catalog 52 records (49 stock/3 out), chưa có CFC catalog |
| Test code hiện có | Unit 26/26 và offline eval 112/112 đã chạy ngày 22/08; scenario `--all` chỉ đạt 48/55 lượt, xem mục 15 |
| n8n production và Messenger thật | Chưa xác minh lại trong lần cập nhật tài liệu này |
| `.n8n-state.json` | Chỉ là metadata đồng bộ lịch sử, không dùng để kết luận workflow production đang active |

## 1. Mục Tiêu Hệ Thống

Hệ thống dùng để trả lời khách hàng tự động cho 2 nhóm thương hiệu:

- ZeO / PANO / Oplus: nhóm chất tẩy rửa, chăm sóc gia đình.
- CFC Cò Bay: nhóm phân bón nông nghiệp.

Nguyên tắc vận hành:

- Google Sheet/CSV là nguồn biên soạn chính cho FAQ và catalog; runtime đọc Redis snapshot/cache, còn catalog có fallback CSV local.
- Nếu dữ liệu không có trong nguồn đã kiểm chứng thì bot phải fallback/hỏi rõ/chuyển admin, không được tự tạo fact.
- Không tự bịa giá, tồn kho, liều lượng, chứng nhận, địa chỉ đại lý, link kênh bán hàng.
- Câu không chắc phải fallback rõ ràng (`FallbackReason`), hỏi rõ hơn hoặc chuyển admin. Enqueue learning queue là yêu cầu còn thiếu trong implementation hiện tại.
- Trong hai workflow chatbot local hiện tại, Python FastAPI là lớp quyết định chính; n8n làm I/O gateway nhận/gửi Messenger và trigger webhook.
- Mốc offline regression ngày 21/08/2026 đạt trung bình **2,9ms/câu** trong môi trường fallback local. Đây không phải latency end-to-end Messenger và không phải SLA production.

## 2. Kiến Trúc Tổng Quan

```text
Facebook Messenger
→ n8n chatbot workflow (I/O Gateway)
→ Python FastAPI /api/chat-pipeline (Single Brain)
  ├── Per-Sender Lock (Tuần tự hóa tin nhắn, chống race condition)
  ├── Redis/RAM Conversation State + Structured Product Memory
  ├── Deterministic Router/Tools (giá, link, tồn kho, safety, CRM)
  ├── Ollama NLU Planner tùy chọn (chỉ trả JSON intent/tool)
  ├── Lexical & Hybrid Semantic RAG khi chưa có fast-path phù hợp
  ├── CSKH Synthesizer (được prompt bám facts; chưa có output validator đầy đủ)
  ├── Covered Fact Exclusion (Loại trừ fact cũ khi khách hỏi follow-up)
  └── Guardrails & Granular Fallback Classification
→ ChatPipelineResponse có answer/intent/score/shopee_url/fallback_reason/latency
→ Trả answer về n8n → Messenger
```

Trace chi tiết được lưu vào Redis session/history; `ChatPipelineResponse` hiện không trả field `trace` ra API.

Sơ đồ báo cáo và prompt tạo hình dùng ngay được đặt tại `SO_DO_WORKFLOW_CHATBOT_ZEO_CFC_CHO_BAO_CAO.md`.

Luồng đồng bộ kiến thức:

```text
Google Sheet
→ n8n knowledge sync workflow
→ Normalize row
→ Redis snapshot: zeo:kb:basic:active hoặc cfc:kb:basic:active
→ POST http://127.0.0.1:8000/sync?brand=...
→ knowledge_sync.py
→ Ollama bge-m3 tạo embedding
→ Redis Vector Index: zeo:vec:faq hoặc cfc:vec:faq
```

Hạ tầng learning queue dự kiến:

```text
Bot không chắc / guardrail fail
→ Redis learning queue: zeo:learning:queue hoặc cfc:learning:queue
→ n8n learning queue export
→ append vào Google Sheet review
→ admin duyệt / bổ sung FAQ
→ sync lại knowledge
```

Khoảng trống hiện tại: `chat_pipeline.py` mới gửi Telegram qua `notify_admin_unanswered`; source không thấy thao tác push event vào `zeo:learning:queue`/`cfc:learning:queue`, và hai workflow chatbot 5 node cũng không enqueue. Hai workflow export chỉ pop/requeue dữ liệu đã có. Vì vậy vòng học tự động từ chatbot đến Sheet chưa được nối end-to-end.

## 3. Cây Thư Mục Quan Trọng

```text
.
├── ChatbotN8n/
│   ├── google_upload/
│   │   ├── zeo_faq_google_sheet_from_ZeoN8n_2026_08_13.csv
│   │   ├── cfc_faq_google_sheet_from_CfcCoBayN8n_2026_08_13.csv
│   │   ├── *.bak
│   │   └── các file docx/md nguồn FAQ
│   ├── evals/
│   │   ├── vietnamese_chatbot_eval_cases.jsonl
│   │   └── zeo_benchmark_1000_cases.jsonl
│   ├── testing/
│   │   ├── zeo_chatbot_test_cases.jsonl
│   │   ├── cfc_chatbot_test_cases.jsonl
│   │   └── facebook_live_test_*.md
│   ├── javis/
│   │   ├── README.md
│   │   ├── knowledge/
│   │   │   └── shopee_catalog.json
│   │   ├── server/
│   │   │   ├── domains/                 # 📂 9 Domain Packages theo chuẩn DDD
│   │   │   │   ├── common/              # Shared Kernel (Redis connection pool, settings I/O)
│   │   │   │   ├── system/              # Status, Health check, Cài đặt & Analytics
│   │   │   │   ├── assistant/           # Trợ lý điều hành AI & Autonomous Tools
│   │   │   │   ├── customers/           # Quản lý khách hàng, hội thoại, Leads CRM & Export CSV
│   │   │   │   ├── n8n/                 # Quản trị Workflow n8n, Executions & File Watching
│   │   │   │   ├── reports/             # Báo cáo điều hành kinh doanh AI Insights
│   │   │   │   ├── learning/            # Hàng đợi học (Learning Queue) & AI gợi ý FAQ
│   │   │   │   ├── knowledge/           # Kho kiến thức Markdown & Google Sheets Live Hub
│   │   │   │   └── rag_test/            # Kiểm thử Semantic Search RAG & NLU
│   │   │   ├── scripts/                 # 📂 Scripts cào Shopee & tiện ích tiền xử lý CSV
│   │   │   ├── main.py                  # Server FastAPI chính (port 8000)
│   │   │   ├── admin_routes.py          # Facade Gateway Router (~55 dòng)
│   │   │   ├── chat_pipeline.py         # Não bộ xử lý hội thoại & NLU
│   │   │   ├── rag_search.py            # Lexical hot cache + Redis Vector KNN fallback
│   │   │   ├── knowledge_sync.py        # Đồng bộ Redis Vector Index
│   │   │   ├── embedder.py              # Vector embedding Ollama (bge-m3)
│   │   │   ├── ai_engine.py             # Kết nối LLMs (Groq, Gemini, OpenRouter, Ollama)
│   │   │   ├── ai_agent_tools.py        # Autonomous Tool Execution cho Trợ lý AI
│   │   │   ├── ai_reporter.py           # Báo cáo kinh doanh AI Briefing
│   │   │   ├── document_ingestor.py     # Nạp tài liệu MD vào Vector Index
│   │   │   ├── shopee_matcher.py        # Khớp link Shopee Mall khi chat
│   │   │   ├── telegram_notifier.py     # Bắn thông báo Telegram
│   │   │   ├── eval_test_suite.py       # 98 single-turn + 14 multi-turn cases trong source hiện tại
│   │   │   ├── eval_sheet_grounding_cases.jsonl
│   │   │   ├── tests/                   # 4 file unit test hiện có
│   │   │   ├── settings.example.json    # Cấu hình mẫu không chứa secret
│   │   │   ├── settings.json            # Cấu hình local/private, không đưa vào tài liệu
│   │   │   ├── requirements.txt         # Thư viện Python
│   │   │   └── static/                  # Frontend Web Admin (HTML/CSS/JS)
│   │   └── skills/
│   ├── workflows/
│   │   └── local-n8n/
│   │       ├── zeo_chatbot.workflow.ts
│   │       ├── cfc_cobay_chatbot.workflow.ts
│   │       ├── zeo_knowledge_sync_basic.workflow.ts
│   │       ├── cfc_knowledge_sync_basic.workflow.ts
│   │       ├── zeo_learning_queue_export.workflow.ts
│   │       ├── cfc_learning_queue_export.workflow.ts
│   │       ├── chatbot_operations_alert.workflow.ts
│   │       ├── zeo_shopee_sync.workflow.ts
│   │       ├── n8n-workflows.d.ts
│   │       ├── tsconfig.json
│   │       ├── .n8n-state.json
│   │       └── .n8n-sync-events.jsonl
│   └── infra/
│       └── redis/
├── logs/
│   ├── python_api.log
│   ├── python_api.pid
│   └── test-pids.txt
├── testing/
│   ├── start_all.sh
│   ├── stop_all.sh
│   ├── run.md
│   ├── push.md
│   ├── test.md
│   ├── run_test_md_scenarios.py
│   └── KICH_BAN_TEST_SEP_KHO_TINH_ZEO.md
├── SO_DO_WORKFLOW_CHATBOT_ZEO_CFC_CHO_BAO_CAO.md
└── TONG_HOP_HE_THONG_CHATBOT_ZEO_CFC_HIEN_HANH.md
```

Ghi chú:

- Không có thư mục `ChatbotN8n/javis-test/` trong workspace được kiểm tra ngày 22/08/2026.
- `.codegraph/` là index code cục bộ, không thuộc runtime chatbot.

## 4. Dữ Liệu Kiến Thức Google Sheet / CSV

File chính:

```text
ChatbotN8n/google_upload/zeo_faq_google_sheet_from_ZeoN8n_2026_08_13.csv
ChatbotN8n/google_upload/cfc_faq_google_sheet_from_CfcCoBayN8n_2026_08_13.csv
ChatbotN8n/google_upload/zeo_shopee_catalog_template.csv
```

Số record hiện tại, đếm bằng CSV parser và không tính header:

- ZeO FAQ: **81 record**, tất cả đang `active`; gồm 65 `audience=customer` và 16 `audience=agent`.
- CFC FAQ: **19 record**, tất cả đang `active` và `audience=customer`.
- ZeO Shopee catalog: **52 record**, gồm 49 `in_stock` và 3 hết hàng.

Snapshot Redis local ngày 22/08/2026 có 65 FAQ ZeO và 19 FAQ CFC, khớp với đường sync chuẩn đã lọc `audience=customer`. Nếu Redis rỗng, `rag_search.py` fallback CSV hiện nạp cả 16 dòng ZeO `audience=agent`; rerank chỉ phạt `audience=agent` chứ không loại bỏ chắc chắn. `knowledge_sync.py` cũng chỉ loại đúng `audience=internal`, nên producer khác ghi snapshot có thể đưa agent content vào index. Đây là grounding gap cần sửa.

Các bộ dữ liệu kiểm thử JSONL hiện có:

| File | Số record JSON hợp lệ |
|---|---:|
| `ChatbotN8n/evals/vietnamese_chatbot_eval_cases.jsonl` | 172 |
| `ChatbotN8n/evals/zeo_benchmark_1000_cases.jsonl` | 1.000 |
| `ChatbotN8n/javis/server/eval_sheet_grounding_cases.jsonl` | 40 |
| `ChatbotN8n/testing/zeo_chatbot_test_cases.jsonl` | 109 |
| `ChatbotN8n/testing/cfc_chatbot_test_cases.jsonl` | 63 |

Các con số trên mô tả file trong workspace, không đồng nghĩa tất cả bộ JSONL đều được chạy bởi `eval_test_suite.py` hoặc `testing/start_all.sh --test`.

Schema hiện tại:

```csv
active,brand,category,intent,question_examples,answer,priority,source_id,updated_at,audience,answer_mode,risk_level,learning_tags,profile_slots,escalation_policy
```

Ý nghĩa các cột:

| Cột | Vai trò |
|---|---|
| `active` | TRUE/FALSE, quyết định dòng có được dùng không |
| `brand` | ZeO, PANO, Oplus, CFC hoặc nhóm brand |
| `category` | Nhóm kiến thức: product, sales, shipping, policy, support, operations... |
| `intent` | Mã ý định ổn định để code/RAG gọi đúng câu trả lời |
| `question_examples` | Các cách khách có thể hỏi, phân tách bằng dấu `;` |
| `answer` | Câu trả lời chuẩn, là nguồn sự thật |
| `priority` | Ưu tiên khi nhiều câu gần nhau |
| `source_id` | Nguồn tài liệu hoặc batch sinh ra dòng |
| `updated_at` | Ngày cập nhật |
| `audience` | `customer` hoặc `agent/internal`; dòng internal không nên trả trực tiếp |
| `answer_mode` | `direct` hoặc `rewrite` |
| `risk_level` | low/medium/high, dùng để guardrail |
| `learning_tags` | Tag phục vụ phân tích/lọc lỗi |
| `profile_slots` | Thông tin cần thu từ khách như phone/area |
| `escalation_policy` | Gợi ý chuyển admin/nhân sự |

Các nhóm dữ liệu ZeO đáng chú ý:

- Giờ mở cửa, giao hàng, website, hotline.
- Chính sách đổi trả/hoàn tiền/khiếu nại.
- Tổng quan công ty, slogan, USP.
- Dòng sản phẩm giặt giũ, rửa chén, lau sàn, tẩy rửa vệ sinh.
- ZeO, PANO, Oplus: công nghệ, mùi hương, quy cách, sản phẩm chưa xác minh.
- FAQ giá chỉ có câu trả lời chung; giá sản phẩm cụ thể nằm trong Shopee catalog snapshot, không nằm trong FAQ CSV.

Các nhóm dữ liệu CFC đáng chú ý:

- Giờ mở cửa, thông tin công ty, website.
- Dòng phân bón: NPK, hữu cơ, dinh dưỡng cây trồng.
- Giá/đại lý/phân phối: yêu cầu khách gửi số điện thoại, khu vực, cây trồng.
- Liều lượng/cách dùng: không tự bịa, cần kỹ sư/admin tư vấn.

## 5. Python FastAPI Server

Thư mục:

```text
ChatbotN8n/javis/server/
```

Chạy server:

```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/javis/server
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Dependencies chính:

```text
fastapi
uvicorn
redis
numpy
httpx
python-dotenv
pydantic
python-multipart
```

### 5.1 `main.py`

Vai trò:

- Khởi tạo FastAPI app phiên bản khai báo `2.1.0`.
- Mount admin dashboard tại `/admin` và `/`.
- Đăng ký `admin_routes`.
- Cung cấp API chính cho n8n và RAG.
- Chạy background task:
  - sync Shopee catalog mỗi 10 phút nếu `settings.json` có cấu hình `shopee.sheet_url` hợp lệ.
  - lưu analytics snapshot mỗi 1 giờ.

Endpoint chính:

| Endpoint | Vai trò |
|---|---|
| `GET /health` | Kiểm tra FastAPI, Ollama, Redis, vector index |
| `POST /sync?brand=zeo` | Sync ZeO snapshot Redis sang vector index |
| `POST /sync?brand=cfc` | Sync CFC snapshot Redis sang vector index |
| `POST /sync?brand=all` | Sync cả ZeO và CFC |
| `POST /search` | Search RAG semantic trực tiếp |
| `POST /rewrite` | Prompt Ollama viết lại và yêu cầu giữ fact; chưa có output validator, lỗi thì trả answer gốc |
| `POST /api/chat-pipeline` | API chính n8n gọi để trả lời Messenger |
| `POST /api/shopee/refresh-cache` | Xóa cache catalog trong RAM để lần đọc sau nạp snapshot mới |
| `GET /admin` | Dashboard quản trị |

### 5.2 `chat_pipeline.py`

Đây là não trả lời chính hiện tại.

Vai trò:

- Nhận request từ `/api/chat-pipeline`.
- Normalize tiếng Việt có dấu/không dấu, viết tắt, typo.
- Đọc customer profile/session từ Redis.
- Nhớ số điện thoại/khu vực khách đã gửi.
- Nhớ ngữ cảnh hội thoại: sản phẩm đang nói, danh sách vừa liệt kê, intent gần nhất.
- Fast-path cho chào hỏi, cảm ơn, số điện thoại, hotline, website, catalog, sản phẩm, giá, ship, khiếu nại.
- Intent-first router trước RAG để chống vector search bắt nhầm.
- RAG fallback nếu không route được.
- Guardrail chống trả nhầm policy/contact/address/internal content.
- Lưu session/history/trace vào Redis.
- Gửi Telegram cho admin khi câu không chắc. Enqueue tự động vào Redis learning queue chưa được nối trong pipeline hiện tại.

Các khối quan trọng:

| Khối | Chức năng |
|---|---|
| `VIETNAMESE_ALIASES` | Chuẩn hóa `ko`, `k`, `sp`, `sdt`, `cty`, `oplis -> oplus`... |
| `PRODUCT_MEMORY_BY_INTENT` | Map intent sang sản phẩm/danh sách sản phẩm để nhớ ngữ cảnh |
| `TECH_CONTEXT_INTENTS` | Nhớ ngữ cảnh công nghệ ZeO/Oplus/PANO |
| `_normalize_vn()` | Bỏ dấu, lowercase, thay alias |
| `_extract_phone_and_area()` | Tách số điện thoại và khu vực |
| `_load_conversation_state()` | Đọc state cũ từ Redis session |
| `_resolve_reference()` | Hiểu `cái đầu tiên`, `cái thứ 2`, `nó`, `loại đó` |
| `_detect_out_of_scope_general_question()` | Chặn câu như `hôm nay thứ mấy`, `Soạn`, `Viết cho ZeO VietNam` khỏi RAG |
| `_detect_contextual_dosage_followup()` | Giữ ngữ cảnh liều lượng kiểu `vậy 2 bộ thì sao` |
| `_detect_specific_product_intent()` | Bắt ZIF, PANO, Oplus, Javen, nước tẩy... |
| `_build_contextual_more_info_answer()` | Trả thêm thông tin cùng sản phẩm khi khách hỏi `còn gì nữa` |
| `process_chat_pipeline()` | Pipeline tổng |
| `_async_save_session()` | Lưu session, state, trace, history |

Các lỗi đã được chặn gần đây:

| Câu khách hỏi | Hành vi đúng hiện tại |
|---|---|
| `hôm nay thứ mấy` | Không RAG, trả ngoài phạm vi |
| `Soạn` | Không RAG, trả ngoài phạm vi |
| `Viết cho ZeO VietNam` | Không RAG, trả ngoài phạm vi |
| `tôi muốn mua oplis` | Hiểu `oplis` là `Oplus`, hỏi rõ loại Oplus |
| `nước tẩy` | Route thẳng `zeo_javen_bleach` |
| `vậy 2 bộ thì sao` sau câu liều lượng | Vẫn giữ guardrail liều lượng, không nhảy đổi trả |
| `còn công nghệ nào khác ko` | Giữ ngữ cảnh sản phẩm công nghệ đang hỏi |
| `cái thứ 2 còn không` | Hiểu danh sách vừa trả lời, không bịa tồn kho |
| `cái đầu tiên giá nhiu` | Hiểu mục thứ nhất, không bịa giá |

### 5.3 `rag_search.py`

Vai trò:

- Kết nối Redis.
- Normalize query tiếng Việt.
- Thử lexical search trên FAQ hot cache trong RAM trước; kết quả đủ cao có thể trả ngay.
- Nếu lexical chưa đủ chắc, tạo embedding query qua `embedder.py` và search RediSearch KNN trong index `zeo:vec:faq` hoặc `cfc:vec:faq`.
- Khi Ollama/Redis lỗi, có degraded lexical fallback.
- Rerank kết quả bằng rule lexical/entity.
- Trả kết quả tốt nhất kèm score/confidence/source.
- `get_faq_by_intent()` lấy đúng câu trả lời theo intent từ Redis vector docs.

Điểm quan trọng:

- Vector search dùng cosine distance.
- Query được mở rộng bằng bản có dấu + không dấu + hint nhóm sản phẩm.
- Rerank boost entity như ZIF, PANO, Oplus, NPK.
- Rerank phạt catalog tổng nếu khách hỏi sản phẩm cụ thể.
- Rerank phạt nội dung `agent/internal` nếu khách không hỏi tạo nội dung.

### 5.4 `knowledge_sync.py`

Vai trò:

- Đọc Redis snapshot:
  - `zeo:kb:basic:active`
  - `cfc:kb:basic:active`
- Parse JSON snapshot từ n8n.
- Lọc dòng:
  - không active.
  - thiếu answer/intent.
  - audience internal.
- Build embedding text từ intent + examples + answer + bản không dấu.
- Gọi Ollama bge-m3 để tạo vector.
- Upsert HASH vào Redis Vector Index.
- Xóa stale docs không còn trong snapshot.
- Làm mới FAQ hot cache sau khi sync thành công.

Index:

```text
zeo:vec:faq
cfc:vec:faq
```

Doc key dạng:

```text
{index_name}:doc:{source_id}:{intent}
```

### 5.5 `embedder.py`

Vai trò:

- Gọi Ollama local để tạo embedding.
- Model chính: `bge-m3`.
- Dimension: `1024`.
- Chuyển vector float thành bytes để ghi Redis.
- Có hàm cosine similarity phụ trợ.

Cấu hình mẫu:

```json
{
  "ollama": {
    "base_url": "http://127.0.0.1:11434",
    "embed_model": "bge-m3",
    "embed_dim": 1024
  }
}
```

### 5.6 `shopee_matcher.py`

Vai trò:

- Đọc catalog Shopee từ Redis `{brand}:shopee:catalog:active`.
- Fallback về `ChatbotN8n/google_upload/zeo_shopee_catalog_template.csv` khi Redis chưa có snapshot.
- Nhận diện câu hỏi Shopee/link mua hàng.
- Match sản phẩm theo keyword/alias.
- Trả suggested reply kèm link Shopee nếu có.
- Nhận diện promotion/deal/voucher.
- Parse giá thành `PriceConstraint` có operator `LT/LTE/GT/GTE/BETWEEN/EXACT/APPROX`.
- Áp dụng category, tồn kho và price comparator như hard constraints trước khi xếp hạng.

Nếu không có link chính thức trong catalog/Sheet thì bot không nên tự bịa link.

### 5.7 `admin_routes.py` & Kiến Trúc `domains/` (DDD)

Vai trò:

- `admin_routes.py`: Facade Gateway Router tinh gọn (~55 dòng) nạp 8 sub-router nghiệp vụ.
- `domains/`: Có 9 package gồm `common` và 8 package có router:
  - `domains.common`: Shared Kernel (Redis pool, settings I/O, config).
  - `domains.system`: Settings, Status, Health check & Analytics weekly.
  - `domains.assistant`: Trợ lý điều hành AI & Autonomous tool calling.
  - `domains.customers`: Quản lý khách hàng, hội thoại, Leads CRM & Export CSV.
  - `domains.n8n`: Điều khiển Workflow n8n, Executions & Real-time File Watching.
  - `domains.reports`: Báo cáo điều hành kinh doanh AI Insights.
  - `domains.learning`: Hàng đợi học (Learning Queue) & AI gợi ý FAQ.
  - `domains.knowledge`: Kho kiến thức, Tài liệu Markdown & Google Sheets Live Hub.
  - `domains.rag_test`: Kiểm thử Semantic Search RAG & NLU evaluation.

Nhóm endpoint tiêu biểu:

| Nhóm Domain | Endpoint tiêu biểu | Chức năng chính |
|---|---|---|
| **System & Settings** | `/admin/settings`, `/admin/status`, `/admin/stats/today`, `/admin/analytics/weekly` | Quản trị kết nối, cấu hình và theo dõi sức khỏe hệ thống |
| **AI Assistant** | `/admin/assistant/chat`, `/admin/assistant/quick-prompts` | Trợ lý điều hành có thể thực thi tool và tra cứu số liệu CRM/n8n |
| **Customers CRM** | `/admin/customers`, `/admin/customers/{brand}/{id}/session`, `/admin/customers/export` | Quản lý profile, số điện thoại lead, lịch sử chat và xuất CSV |
| **n8n Automation** | `/admin/n8n/workflows`, `/admin/n8n/deploy`, `/admin/n8n/executions`, `/admin/n8n/ws/file-watch` | Bật/tắt workflow, deploy file `.ts` và theo dõi file |
| **AI Reports** | `/admin/reports/latest`, `/admin/reports/generate` | Sinh bản tin báo cáo điều hành với provider được cấu hình |
| **Learning Queue** | `/admin/learning-queue`, `/admin/learning-queue/approve`, `/admin/learning/ai-suggest` | Duyệt câu hỏi chưa chắc và gợi ý FAQ |
| **Knowledge Hub** | `/admin/sheets/get-tabs`, `/admin/sheets/preview`, `/admin/sheets/sync-direct`, `/admin/documents/upload` | Xem/sync Sheet và nạp tài liệu Markdown |
| **Shopee API** | `/admin/shopee/catalog`, `/admin/shopee/sync-sheet` | Đọc catalog và gọi đồng bộ Sheet |
| **RAG Test** | `/admin/test/query` | Thử Semantic Search và câu trả lời bot |

### 5.8 `document_ingestor.py`

Vai trò:

- Chia Markdown/document thành chunk.
- Tạo document vector index riêng.
- Ingest thư mục knowledge.
- Search tài liệu bổ sung.
- Dùng AI để extract FAQ từ tài liệu thô.

Đây là lớp hỗ trợ tài liệu dài, khác với FAQ CSV chính.

### 5.9 `ai_engine.py` và `ai_agent_tools.py`

`ai_engine.py`:

- Gọi Gemini/OpenRouter/Groq/Ollama tùy cấu hình.
- Sinh text cho admin assistant.
- Chạy assistant chat có thể dùng tool.

`ai_agent_tools.py`:

- Tool để assistant/admin kiểm tra hệ thống.
- Gọi n8n API, xem workflows/executions.
- Xem business stats, learning queue, Shopee catalog.
- Search FAQ knowledge.
- Kiểm tra Redis/Ollama/n8n.
- Có tool chạy system command, cần cẩn trọng quyền.

### 5.10 `telegram_notifier.py`

Vai trò:

- Gửi Telegram alert.
- Báo lead mới khi khách gửi số điện thoại.
- Báo câu chưa trả lời/chưa chắc cho admin.
- Test Telegram config.

### 5.11 `eval_test_suite.py`

Vai trò:

- Bộ regression inline gồm 98 single-turn case và 14 multi-turn scenario; tổng cộng 131 lượt gọi pipeline nhưng báo cáo 112 case.
- Kiểm tra intent, context memory, out-of-scope, no-hallucination guardrails.

Chạy test:

```bash
cd /Users/hyden/Documents/David-nguyen/N8n
ChatbotN8n/javis/server/.venv/bin/python ChatbotN8n/javis/server/eval_test_suite.py
```

Lưu ý:

- Cần Redis/Ollama/knowledge đã sync để test live đầy đủ; khi dependency không truy cập được, nhiều nhánh có thể chạy degraded/local fallback.
- Runner chấp nhận một số nhóm intent tương đương và hiện chỉ in tổng kết, không `sys.exit(1)` khi có case fail. Vì vậy phải đọc số PASS/FAIL trong output, không chỉ nhìn exit code.
- Hai unit test planner dùng fake planner, nên 2/2 unit pass không chứng minh Ollama live đã hiểu câu hỏi.

## 6. Redis

Redis đang được dùng cho nhiều nhóm dữ liệu:

1. Snapshot kiến thức từ n8n.
2. Vector index RAG.
3. Customer profile.
4. Session/history/context memory.
5. Learning queue/admin review.
6. Shopee catalog snapshot/cache metadata.
7. Analytics/report, Telegram dedup và deploy log của admin.

Key chính:

```text
zeo:kb:basic:active
cfc:kb:basic:active

zeo:sync:faq:basic:last-success
cfc:sync:faq:basic:last-success

zeo:vec:faq
cfc:vec:faq

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

Session hiện lưu thêm:

```json
{
  "last_user_message": "...",
  "last_bot_reply": "...",
  "last_intent": "...",
  "lead_stage": "...",
  "conversation_state": {
    "active_entities": {
      "product": "...",
      "product_intent": "...",
      "category": "...",
      "product_id": "...",
      "shopee_url": "...",
      "price": null,
      "rank": null
    },
    "last_products_shown": [],
    "customer_constraints": {},
    "active_flow": {"name": "", "stage": ""},
    "covered_fact_ids": [],
    "recent_turns": [],
    "conversation_summary": "...",
    "last_source_id": "...",
    "updated_at": "..."
  },
  "last_trace": {
    "normalized_text": "...",
    "matched_intent": "...",
    "score": 0.0,
    "source_id": "...",
    "reference": {}
  }
}
```

`last_trace` thay đổi theo nhánh xử lý; không phải fast-path nào cũng có đủ `matched_intent`, `score` hoặc `source_id` như ví dụ trên.

## 7. Ollama / Model

Ollama chạy local:

```text
http://127.0.0.1:11434
```

Model embedding chính:

```text
bge-m3
```

Vai trò:

- Tạo embedding cho FAQ khi sync knowledge.
- Tạo embedding cho câu hỏi khi RAG search.

Model rewrite fallback trong cấu hình:

```text
qwen2.5:7b-instruct
```

Vai trò của model chat:

- `plan_chat_intent_with_ollama()` có thể phân loại câu khó thành JSON intent/tool. `shadow` chỉ ghi nhận dự đoán để đối chiếu; `assist` mới được phép chọn deterministic tool. Mặc định vẫn `off` để không đổi hành vi cũ.
- `settings.json` local được kiểm tra không có block `llm_nlu`; vì vậy planner rơi về mặc định `off` nếu không có biến môi trường ghi đè.
- Planner không được trả giá, link hay tên sản phẩm trực tiếp; matcher deterministic phải đọc catalog thật rồi mới tạo kết quả.
- Synthesizer được prompt bám facts đã truy xuất, nhưng chưa có output validator đầy đủ và vẫn có nhánh gọi khi facts rỗng.
- Nếu Ollama timeout, JSON lỗi, confidence thấp hoặc tool không tìm được dữ liệu, pipeline tiếp tục deterministic/RAG/fallback hiện hành.

## 8. n8n Workflows Trong `local-n8n`

Thư mục:

```text
ChatbotN8n/workflows/local-n8n/
```

Có 8 workflow `.ts` được viết theo `@n8n-as-code/transformer`. Tất cả file local đang có `active: false`; trạng thái production chỉ được kết luận sau khi kiểm tra n8n server. `.n8n-state.json` là metadata lịch sử và còn chứa mapping cũ, không phải bằng chứng workflow đang chạy.

### 8.1 `zeo_chatbot.workflow.ts`

Tên workflow:

```text
Zeo Chatbot
```

Số node:

```text
5 nodes, 5 connections (Streamlined Single-Brain I/O Gateway)
```

Vai trò:

- Nhận tin nhắn Messenger cho ZeO.
- Bóc tách payload đầu vào (`LocDauVao`).
- Chuyển tiếp sang não xử lý Python `/api/chat-pipeline` (`GoiFastApiChatPipeline`).
- Chuẩn bị tin nhắn phản hồi (`PrepareMessengerReply`).
- Gửi tin nhắn trả lời trực tiếp cho khách qua Facebook Graph API (`NhanKhachAuto`).
- Đã loại bỏ hoàn toàn các node rìa/tàn dư cũ để tối ưu hóa hiệu năng và độ ổn định.

Node chính:

| Node | Loại | Vai trò |
|---|---|---|
| `MessengerTrigger` | facebookTrigger | Nhận tin Messenger |
| `LocDauVao` | code | Lọc/chuẩn hóa input, bóc tách text/senderId/messageId |
| `GoiFastApiChatPipeline` | httpRequest | Gọi `http://127.0.0.1:8000/api/chat-pipeline` (Single Brain) |
| `PrepareMessengerReply` | code | Chuẩn bị final reply trả về từ Python |
| `NhanKhachAuto` | httpRequest | Gửi reply về khách hàng qua Graph API Facebook |

Route chính:

```text
MessengerTrigger
→ LocDauVao
→ GoiFastApiChatPipeline
→ PrepareMessengerReply
→ NhanKhachAuto
```

Connection thứ năm là nhánh error output từ `GoiFastApiChatPipeline` về `PrepareMessengerReply`, để n8n vẫn tạo phản hồi fallback khi API lỗi.

### 8.2 `cfc_cobay_chatbot.workflow.ts`

Tên workflow:

```text
CFC Co Bay Chatbot
```

Số node:

```text
5 nodes, 5 connections (Streamlined Single-Brain I/O Gateway)
```

Vai trò giống `zeo_chatbot.workflow.ts` nhưng dùng cho thương hiệu CFC Cò Bay:

```text
brand: "cfc"
Facebook Page ID: 946909570780806
cfc:kb:basic:active
cfc:learning:queue
```

Khác biệt nghiệp vụ:

- Brand là CFC Cò Bay.
- Dữ liệu là phân bón.
- Guardrail nghiêm hơn với liều lượng, công dụng nông nghiệp, đại lý, giá.
- Không được lẫn sản phẩm tẩy rửa ZeO/PANO/Oplus vào CFC.

### 8.3 `zeo_knowledge_sync_basic.workflow.ts`

Tên workflow:

```text
Zeo Knowledge
```

Số node:

```text
7 nodes, 6 connections
```

Vai trò:

- Đọc FAQ ZeO từ Google Sheet.
- Normalize row theo schema.
- Lọc internal/agent.
- Ghi snapshot vào Redis.
- Ghi metadata lần sync.
- Gọi Python rebuild vector index.

Route:

```text
ManualTrigger
→ ReadFaqRows
→ NormalizeKnowledge
→ WriteRedisSnapshot
→ WriteRedisSyncMetadata
→ RebuildZeoVectorIndex

ScheduleTrigger
→ ReadFaqRows
```

Lưu ý lịch chạy: source local chỉ khai báo `field: 'minutes'` nhưng chưa đặt `minutesInterval`. Vì vậy không ghi nhận đây là cron 00:00; cần cấu hình interval rõ ràng và activate workflow trên n8n trước khi kỳ vọng chạy tự động.

Redis key:

```text
zeo:kb:basic:active
zeo:sync:faq:basic:last-success
```

HTTP gọi Python:

```text
POST http://127.0.0.1:8000/sync?brand=zeo
```

### 8.4 `cfc_knowledge_sync_basic.workflow.ts`

Tên workflow:

```text
CFC Co Bay Knowledge
```

Số node:

```text
7 nodes, 6 connections
```

Vai trò:

- Đọc FAQ CFC từ Google Sheet.
- Normalize row.
- Ghi snapshot vào Redis.
- Ghi metadata sync.
- Gọi Python rebuild vector index.

Redis key:

```text
cfc:kb:basic:active
cfc:sync:faq:basic:last-success
```

HTTP gọi Python:

```text
POST http://127.0.0.1:8000/sync?brand=cfc
```

Workflow CFC có cùng lưu ý schedule với ZeO: file local chưa khai báo `minutesInterval` cụ thể.

### 8.5 `zeo_learning_queue_export.workflow.ts`

Tên workflow:

```text
Zeo Learning Queue Export
```

Số node:

```text
6 nodes, 5 connections
```

Vai trò:

- Mỗi 5 phút pop một event từ `zeo:learning:queue`.
- Chuẩn hóa event thành row review.
- Append vào Google Sheet learning/review.
- Nếu append lỗi thì push lại queue.

Route:

```text
ManualTrigger hoặc ScheduleTrigger
→ PopLearningEvent
→ PrepareReviewRow
→ AppendLearningQueue
→ nếu lỗi: RequeueFailedEvent
```

Redis list:

```text
zeo:learning:queue
```

### 8.6 `cfc_learning_queue_export.workflow.ts`

Tên workflow:

```text
CFC Learning Queue Export
```

Vai trò giống ZeO nhưng dùng:

```text
cfc:learning:queue
```

Mỗi 5 phút pop event, append vào Google Sheet review, lỗi thì requeue.

### 8.7 `chatbot_operations_alert.workflow.ts`

Tên workflow:

```text
Chatbot Operations Alert
```

Số node:

```text
8 nodes, 7 connections
```

Vai trò:

- Nhận alert từ workflow khác.
- Normalize alert.
- Deduplicate bằng Redis để tránh spam Telegram.
- Gửi Telegram alert.
- Lưu key dedup.

Route:

```text
WhenExecutedByAnotherWorkflow
→ NormalizeAlert
→ GetRecentDuplicate
→ SkipRecentDuplicate
→ SendTelegramAlert
→ RememberTelegramAlert
```

Redis key:

```text
ops:telegram:dedup:{hash}
```

Dedup alert được cấu hình TTL 900 giây trong workflow local.

### 8.8 `zeo_shopee_sync.workflow.ts`

Tên workflow:

```text
Zeo Shopee Catalog Sync
```

Số node:

```text
6 nodes, 5 connections
```

Vai trò:

- Đọc catalog ZeO từ Google Sheet.
- Normalize row và ghi snapshot `zeo:shopee:catalog:active` vào Redis.
- Ghi metadata lần sync.
- Gọi `POST http://127.0.0.1:8000/api/shopee/refresh-cache`.
- Có cron `0 0 * * *` theo timezone `Asia/Ho_Chi_Minh`.

File local đang `active: false`, nên cron 00:00 chỉ có hiệu lực sau khi workflow tương ứng được deploy và activate trên n8n.

## 9. Luồng Trả Lời Messenger Hiện Hành

### 9.1 Luồng chuẩn nhanh

```text
Messenger
→ n8n LocDauVao
→ FastAPI /api/chat-pipeline
→ chat_pipeline đọc Redis profile/session
→ resolve context/reference
→ deterministic tool hoặc Ollama NLU planner tùy chọn
→ RAG chỉ khi chưa có route chắc chắn
→ guardrail/grounding
→ trả ChatPipelineResponse
→ n8n PrepareMessengerReply
→ Facebook Send Message
```

### 9.2 Luồng trong `chat_pipeline.py`

```text
1. Nhận text, brand, sender_id
2. Normalize tiếng Việt
3. Extract phone/area
4. Đọc Redis customer + session
5. Load conversation_state
6. Resolve reference: "nó", "cái thứ 2", "loại đó"
7. Multi-intent + fast path:
   - số điện thoại
   - hỏi lại thông tin đã lưu
   - chào/cảm ơn/ok
   - complaint
8. Nếu bật `assist`, Ollama NLU planner chỉ đề xuất JSON intent/tool cho câu bán hàng khó; confidence thấp thì bỏ qua
9. Intent-first deterministic router:
   - out-of-scope
   - company/address/contact
   - website/social
   - product/catalog
   - budget/specific price/price ranking
   - product link và follow-up `sản phẩm đó`
   - shipping
   - usage/dosage safety
   - contextual follow-up
10. Shopee matcher/catalog tool trả product_id, giá, link và trạng thái tồn kho theo snapshot hiện hành
11. RAG lexical/semantic search nếu chưa bắt được intent chắc chắn
12. CSKH synthesizer (nếu cần) được prompt bám facts; output chưa được validator kiểm chứng đầy đủ
13. Guardrail theo intent/category/risk
14. Fallback trung thực nếu score thấp
15. Lưu session/history/trace và `last_products_shown`
16. Trả answer
```

### 9.3 Response model

`ChatPipelineResponse` gồm:

```json
{
  "ok": true,
  "answer": "...",
  "intent": "...",
  "confidence": "high|medium|low",
  "score": 1.0,
  "brand": "ZEO|CFC",
  "has_phone": false,
  "phone": "",
  "area": "",
  "lead_stage": "new|browsing_catalog|collecting_contact|lead_ready|escalated",
  "shopee_url": null,
  "fallback_reason": "",
  "latency_ms": 0.0
}
```

## 10. Guardrail Chống Bịa

Các nhóm không được tự bịa:

- Giá cụ thể.
- Tồn kho/còn hàng.
- Liều lượng phân bón.
- Liều lượng hóa chất/giặt giũ.
- Chứng nhận/kiểm định.
- Link TikTok/Zalo/Shopee nếu chưa có.
- Địa chỉ đại lý theo tỉnh nếu Sheet không có.
- Sản phẩm mới nhất/mới ra mắt.
- Sản phẩm đối thủ hoặc sản phẩm ngoài brand.

Ví dụ hành vi đúng:

| Câu hỏi | Hành vi đúng |
|---|---|
| `ZIF giá bao nhiêu` | Không báo giá cụ thể, xin quy cách/SĐT/khu vực |
| `cái thứ 2 còn không` | Không bịa tồn kho, admin kiểm tra |
| `bón bao nhiêu kg cho 1 công lúa` | Không tự tư vấn liều lượng |
| `hôm nay thứ mấy` | Không RAG vào FAQ, báo ngoài phạm vi |
| `Soạn` | Không RAG vào FAQ |
| `Có bột giặt Omo không` | Không nhận vơ là ZeO |
| `CFC có nước giặt không` | Không lẫn CFC với ZeO |

## 11. Admin Dashboard

URL local:

```text
http://127.0.0.1:8000/admin
```

Chức năng chính:

- Xem trạng thái Redis/Ollama/n8n.
- Xem customer/session/history.
- Xem learning queue.
- Test query.
- Sync documents/FAQ.
- Xem Shopee catalog và mở Google Sheets Live Hub để sync.
- Gửi test Telegram.
- Xem analytics/report.
- Chat với assistant nội bộ.

Giao diện hiện không có trang/menu Shopee CRUD riêng. File `static/js/pages/shopee.js` cũ vẫn được load nhưng gọi một số CRUD endpoint không còn tồn tại; đây là mã legacy cần dọn hoặc nối lại trước khi mô tả là chức năng quản lý catalog hoàn chỉnh.

Lưu ý an toàn: các route `/admin/*` hiện chưa có lớp xác thực trong FastAPI, CORS đang cho phép `*`, trong khi assistant có tool chạy shell và bật/tắt workflow. Không nên public trực tiếp dashboard/API admin qua tunnel nếu chưa thêm authentication, authorization và giới hạn origin.

File giao diện:

```text
ChatbotN8n/javis/server/static/admin.html
```

Backend:

```text
ChatbotN8n/javis/server/admin_routes.py
```

## 12. Shopee / Kênh Mua Hàng

Nguồn catalog mà matcher đang đọc:

```text
Redis: zeo:shopee:catalog:active
Fallback: ChatbotN8n/google_upload/zeo_shopee_catalog_template.csv
```

`ChatbotN8n/javis/knowledge/shopee_catalog.json` vẫn tồn tại nhưng không được `shopee_matcher.py` dùng trong luồng runtime hiện tại.

Code xử lý:

```text
ChatbotN8n/javis/server/shopee_matcher.py
```

Nguyên tắc:

- Nếu có link trong catalog thì match và trả link.
- Nếu không có link chính thức thì không tự bịa.
- Các kênh TikTok/Zalo/Facebook nếu Sheet chưa có link chính thức thì trả `official_channel_unverified`.
- Giá, badge và `in_stock` là dữ liệu của snapshot gần nhất, không phải truy vấn live Shopee tại thời điểm khách hỏi.
- Luồng `/admin/sheets/sync-direct` và upload CSV hiện ghi schema Shopee rút gọn (`variant`, `promotion`, `link`), trong khi matcher ưu tiên schema (`variants`, `discount`, `link_shopee`, `item_id`, `in_stock`). Ngoài ra service đang gọi tên hàm cache cũ `reload_catalog()` rồi nuốt exception. Vì vậy chưa nên coi admin 1-click sync là tương đương workflow `zeo_shopee_sync` hoặc là refresh cache đáng tin cậy cho production.

## 13. Telegram Alert

Có 2 lớp:

- Python `telegram_notifier.py`.
- n8n `chatbot_operations_alert.workflow.ts`.

Khi dùng:

- Có lead mới: khách gửi số điện thoại.
- Bot không chắc/câu ngoài dữ liệu.
- Guardrail fail.
- Learning queue cần review.

Redis dedup key:

```text
ops:telegram:dedup:{hash}
```

## 14. File Vận Hành

| File | Vai trò |
|---|---|
| `testing/start_all.sh` | Khởi động service local; hỗ trợ interactive, `--background`, `--test` |
| `testing/stop_all.sh` | Dừng service local bằng PID và các fallback process pattern rộng |
| `logs/python_api.log` | Log Python API |
| `logs/python_api.pid` | PID Python API |
| `logs/test-pids.txt` | PID được ghi trong chế độ test |
| `testing/run.md` | Ghi chú/lệnh chạy |
| `testing/push.md` | Ghi chú deploy/push |
| `testing/test.md` | Bộ test thủ công lớn |
| `testing/run_test_md_scenarios.py` | Wrapper legacy đang dựng sai đường dẫn và hiện exit 1 |
| `ChatbotN8n/javis/server/run_test_md_scenarios.py` | Runner scenario thực tế |
| `testing/KICH_BAN_TEST_SEP_KHO_TINH_ZEO.md` | Kịch bản demo/stress test thủ công |
| `SO_DO_WORKFLOW_CHATBOT_ZEO_CFC_CHO_BAO_CAO.md` | Sơ đồ và prompt tạo hình báo cáo |
| `TONG_HOP_HE_THONG_CHATBOT_ZEO_CFC_HIEN_HANH.md` | Tài liệu hiện hành này |

`testing/start_all.sh --test` không mở n8n hoặc public tunnel; nó chạy unit discovery và 3 API smoke request, nhưng không tự chạy `eval_test_suite.py`. Chế độ interactive/`--background` có mở n8n và named Cloudflare tunnel, nên cần kiểm soát việc public dashboard.

`testing/stop_all.sh` có fallback `pkill -f` cho n8n, cloudflared, Ollama, uvicorn và `kill -9` mọi listener trên port 8000. Script cũng không đọc `logs/test-pids.txt`; hãy kiểm tra target trước khi chạy để tránh dừng process không thuộc phiên hiện tại.

## 15. Cách Kiểm Tra Hệ Thống

### 15.1 Kiểm tra server

```bash
curl http://127.0.0.1:8000/health
```

Kỳ vọng:

- `service: ok`
- `redis: ok`
- `ollama: ok`
- có index `zeo:vec:faq`, `cfc:vec:faq` sau khi sync.

### 15.2 Sync knowledge

```bash
curl -X POST "http://127.0.0.1:8000/sync?brand=zeo"
curl -X POST "http://127.0.0.1:8000/sync?brand=cfc"
curl -X POST "http://127.0.0.1:8000/sync?brand=all"
```

### 15.3 Test chat pipeline trực tiếp

```bash
curl -X POST "http://127.0.0.1:8000/api/chat-pipeline" \
  -H "Content-Type: application/json" \
  -d '{
    "brand": "zeo",
    "sender_id": "manual_test_001",
    "text": "Tôi muốn xem về nước rửa chén"
  }'
```

### 15.4 Chạy eval tự động

```bash
cd /Users/hyden/Documents/David-nguyen/N8n
ChatbotN8n/javis/server/.venv/bin/python ChatbotN8n/javis/server/eval_test_suite.py
```

Chạy scenario runner đúng:

```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/javis/server
.venv/bin/python run_test_md_scenarios.py --all
```

Không dùng wrapper `N8n/testing/run_test_md_scenarios.py` cho đến khi sửa phép dựng `SERVER_DIR`.

### 15.5 Kết quả xác minh gần nhất

| Bộ kiểm tra | Kết quả ngày 22/08/2026 | Ý nghĩa |
|---|---:|---|
| Unit discovery `tests/test_*.py` | **26/26 PASS** | Chủ yếu local/mocked; 2 planner tests dùng fake planner |
| `eval_test_suite.py` | **112/112 PASS**, 2,7ms/lượt trung bình | Offline/degraded trong lần chạy này; 98 single + 14 scenario, tổng 131 lượt; runner chưa fail exit code |
| `run_test_md_scenarios.py --all` | **48/55 lượt PASS (87,3%)** | Offline/degraded; 11 scenario; scenario 04, 05, 09, 16 còn REVIEW |
| `GET /health` local | Từng PASS trong phiên audit; lần curl cuối port 8000 không lắng nghe | Khi pass đã thấy `bge-m3` và hai FAQ vector index; cần start lại FastAPI để kiểm tra hiện thời |

Scenario runner chỉ yêu cầu một trong các `expect_words` xuất hiện và cũng không trả exit code lỗi khi có REVIEW. Do đó chưa được dùng 112/112 hay 48/55 như một chứng nhận zero-hallucination hoặc production readiness.

### 15.6 Kịch bản Test Hội Thoại Đa Lượt Chuẩn Thực Tế (9 Lượt CSKH)

Kịch bản dưới đây kiểm tra hành vi, không đóng đinh giá/tên sản phẩm. Giá và link phải đối chiếu snapshot catalog đang active ở thời điểm test.

```text
1. [Khách]: "Xin chào"
   → [Bot]: Chào hỏi thân thiện, giới thiệu các dòng sản phẩm ZeO Vietnam.

2. [Khách]: "Có sản phẩm nào giá tầm dưới 100k ko nhỉ"
   → [Bot]: Chỉ trả sản phẩm đang bán có giá < 100.000đ trong snapshot; không vi phạm khoảng giá.

3. [Khách]: "có bột giặt ko"
   → [Bot]: Giới thiệu 3 nhóm bột giặt (ZeO Enzyme, Oplus 4in1, PANO VEILEX) và hỏi nhu cầu sạch sâu / thơm lâu / tiết kiệm.

4. [Khách]: "nhu cầu tiết kiệm đi"
   → [Bot]: Tư vấn đúng nhóm tiết kiệm từ catalog/FAQ hiện hành, không kéo nhầm sản phẩm ngoài ngữ cảnh.

5. [Khách]: "có link shopee ko"
   → [Bot]: Gửi link gian hàng hoặc deep-link phù hợp; chỉ nói Freeship Extra nếu snapshot/Sheet hiện hành có fact đó.

6. [Khách]: "nước rửa chén nào bán chạy nhỉ"
   → [Bot]: Chỉ gọi là “bán chạy” khi snapshot có badge/ranking đáng tin cậy; nếu badge thiếu thì không giả định item đầu tiên là Top 1.

7. [Khách]: "cái số 2 là sao nhỉ"
   → [Bot]: Giải thích USP 4in1 của Bột giặt Oplus theo đúng ngữ cảnh hội thoại.

8. [Khách]: "xin giá nước rửa chén vitamin e"
   → [Bot]: Báo đúng giá snapshot và deep-link của sản phẩm đích danh; không dùng sản phẩm cũ trong context.

9. [Khách]: "cho xin link web của công ty"
   → [Bot]: Trả về website chính thức https://zeo.vn/ từ Google Sheet.
```

## 16. Điểm Mạnh Hiện Tại

- **Dữ liệu có nguồn quản trị tập trung**: FAQ và catalog được biên soạn từ Sheet/CSV, sau đó dùng Redis snapshot/cache ở runtime.
- **Có pipeline đồng bộ rõ ràng**: FAQ workflow ghi Redis rồi rebuild vector index; Shopee workflow được cấu hình cron 00:00. Tự động chạy hay không còn phụ thuộc workflow đã được activate trên n8n.
- **Shopee Dynamic Catalog Engine**: Matcher đọc snapshot 52 sản phẩm (49 `in_stock`, 3 hết hàng) từ Redis hoặc fallback CSV; đây không phải dữ liệu live trực tiếp từ Shopee.
- **Smart CS AI Agent Intelligence**:
  - Tự động parse và lọc sản phẩm theo ngân sách / tầm giá (`match_products_by_budget`).
  - Nhận diện và tư vấn đa lượt theo nhu cầu thực tế (`match_need_preference`: tiết kiệm, thơm lâu, sạch sâu, dịu nhẹ).
  - Báo giá theo snapshot catalog và dẫn deep-link cho sản phẩm đích danh (`match_specific_product_price`).
  - Có lớp **Ollama NLU Planner** tùy chọn (`off`/`shadow`/`assist`): Ollama chỉ phân loại ý định JSON, sau đó code deterministic mới chọn catalog/giá/link để tránh bịa.
  - Có matcher cho Bán Chạy / Mới Ra Mắt, nhưng badge đang bị mất ở Redis sync và route new-arrival còn xung đột; chưa xem là ổn định.
- **Hiệu năng**: Fast-path deterministic thường ở mức vài ms; lần offline regression gần nhất ngày 21/08/2026 trung bình 2,9ms/câu trong điều kiện fallback local.
- **Có guardrail chống bịa cho các fact trọng yếu**: Giá, tồn kho, liều lượng và link được ưu tiên lấy từ matcher/Sheet/Redis hoặc fallback rõ ràng. Đây là mục tiêu thiết kế, không phải bảo đảm tuyệt đối cho mọi câu.
- **Có regression suite hữu ích**: Mốc chạy ngày 21/08/2026 đạt **112/112** eval và 26/26 unit tests; kết quả chỉ chứng minh các case đã định nghĩa trong môi trường chạy đó.

## 17. Điểm Yếu / Rủi Ro & Trạng Thái Xử Lý

- **Dữ liệu giá & link Shopee**: Đã chuyển sang catalog động qua `shopee_matcher.py` và Redis `zeo:shopee:catalog:active`; vẫn cần freshness/source-version guard ở các phase tiếp theo.
- **Badge ranking bị mất khi sync**: Redis catalog ngày 22/08 có 52 record nhưng không record nào có `badge`, vì workflow Shopee chưa ghi trường này. `match_best_sellers()`/`match_new_arrivals()` vì vậy có thể fallback theo thứ tự item còn hàng thay vì ranking thật.
- **Một số câu trả lời Shopee chưa grounded**: `shopee_matcher.py` còn hardcode các khẳng định tuyệt đối như “hoàn toàn không ăn da tay”, “tẩy vết máu 100%”, không phai/mục vải hoặc ảnh hưởng vi mạch. Các fact này chưa được truy vết trong FAQ/catalog và cần bỏ hoặc đưa về Sheet kèm nguồn duyệt trước khi dùng production.
- **Admin sync Shopee lệch schema/cache**: Direct sync/upload ghi schema rút gọn và gọi nhầm `reload_catalog()`; có thể làm matcher thiếu `item_id`, `in_stock`, badge, link hoặc tiếp tục dùng cache cũ.
- **Bề mặt admin chưa được bảo vệ**: `/admin/*` chưa có auth, CORS `*`, assistant có shell/workflow tool; public tunnel tạo rủi ro quyền truy cập nghiêm trọng.
- **Phình mã nguồn regex**: Đã tách matcher Shopee và phân tầng fast-path/RAG, nhưng `chat_pipeline.py` vẫn lớn và cần tiếp tục modular hóa cùng regression test.
- **Redis snapshot rỗng khi mới khởi động**: Matcher fallback về CSV ZeO nếu Redis chưa có key và có endpoint `/api/shopee/refresh-cache`; không có catalog CFC tương đương trong fallback CSV hiện tại.
- **RAG Semantic Search**: Hiện sử dụng Redis Vector Search KNN kết hợp Ollama `bge-m3` embedding tiếng Việt. Cần đảm bảo container Redis và Ollama luôn hoạt động ổn định.
- **Session RAM là process-local**: Cache RAM giảm round-trip nhưng không loại bỏ hoàn toàn race/cross-worker inconsistency; session Redis hiện chưa có TTL/versioning đầy đủ.
- **Script dừng service có phạm vi rộng**: `testing/stop_all.sh` có thể dừng process khác cùng pattern hoặc port 8000.

## 18. Hướng Nâng Cấp Nên Làm Tiếp

### Phase 1: Ổn định dữ liệu

- Chuẩn hóa thêm `keywords`, `negative_keywords`, `entity_aliases` trong Google Sheet.
- Tách rõ `customer` và `agent/internal`.
- Bổ sung nhiều question examples từ chat thật.
- Thêm cột `product_entity` hoặc `entity_scope` để giảm hardcode trong Python.

### Phase 2: Hybrid Retrieval

```text
Query
→ normalize
→ intent/entity classifier
→ keyword/BM25 search
→ vector search bge-m3
→ merge candidates
→ rerank
→ guardrail
→ grounded answer
```

### Phase 3: Controlled LLM

LLM chỉ nên dùng để:

- Classify intent theo JSON schema.
- Rewrite answer đã có trong Sheet.
- Tóm tắt lịch sử hội thoại.
- Gợi ý câu hỏi làm rõ.

LLM không được dùng để tạo fact mới.

### Phase 4: Observability

Mỗi câu nên log:

```json
{
  "brand": "zeo",
  "raw_text": "...",
  "normalized_text": "...",
  "detected_intent": "...",
  "matched_intent": "...",
  "score": 0.82,
  "source_id": "...",
  "fallback_reason": "...",
  "conversation_state": {}
}
```

Dashboard nên xem được:

- Top câu fallback.
- Top intent bị nhầm.
- Top câu bị guardrail.
- Top câu khách hỏi nhưng Sheet chưa có.
- Learning queue theo brand/category.

## 19. Checklist Khi Deploy / Restart

1. Bật Redis container.
2. Bật Ollama.
3. Đảm bảo model `bge-m3` đã có.
4. Chạy Python FastAPI.
5. Chạy n8n.
6. Chạy knowledge sync ZeO/CFC.
7. Kiểm tra `/health`.
8. Test `/api/chat-pipeline`.
9. Test Messenger thật.
10. Kiểm tra Redis keys:

```text
zeo:kb:basic:active
cfc:kb:basic:active
zeo:vec:faq
cfc:vec:faq
```

## 20. Lệnh Chạy Nhanh

Start Python:

```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/javis/server
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Health:

```bash
curl http://127.0.0.1:8000/health
```

Sync all:

```bash
curl -X POST "http://127.0.0.1:8000/sync?brand=all"
```

Eval:

```bash
cd /Users/hyden/Documents/David-nguyen/N8n
ChatbotN8n/javis/server/.venv/bin/python ChatbotN8n/javis/server/eval_test_suite.py
```

## 21. Quy Ước Giảm Token Cho Lần Làm Việc Sau

File này là project memory chính của hệ thống. Khi bắt đầu một phiên làm việc mới, chỉ cần đọc:

```text
AGENTS.md
TONG_HOP_HE_THONG_CHATBOT_ZEO_CFC_HIEN_HANH.md
```

Sau đó mới đọc thêm đúng file đang cần sửa. Không cần đọc lại toàn bộ dự án nếu yêu cầu chỉ liên quan một phần nhỏ.

Quy tắc sử dụng:

- `AGENTS.md` nói cho agent biết phải ưu tiên file tổng hợp này.
- File tổng hợp này mô tả kiến trúc, luồng dữ liệu, file quan trọng, Redis keys, workflow, RAG, guardrail và test hiện hành.
- Khi code thực tế khác với file này, phải tin code thực tế trước, rồi cập nhật lại file này.
- Khi sửa phần quan trọng của hệ thống, phải cập nhật lại file này trước khi kết thúc.

Những thay đổi cần cập nhật vào file này:

- Kiến trúc hệ thống hoặc data flow.
- n8n workflow, webhook, knowledge sync.
- Schema Google Sheet/CSV, intent, category, answer mode.
- Redis keys, vector index, session, profile, learning queue.
- RAG search, rerank, intent router, context memory, guardrail, fallback.
- Endpoint API, lệnh restart, deploy, eval/test.
- Case lỗi lớn đã fix hoặc case mới cần theo dõi.

Những thay đổi không cần cập nhật:

- Sửa typo nhỏ.
- Format code không đổi hành vi.
- Thử nghiệm tạm thời rồi bỏ.

CodeGraph dùng để giảm việc đọc code thủ công. Khi cần hiểu code, ưu tiên hỏi CodeGraph trước:

```bash
codegraph explore "chat_pipeline.py context memory"
codegraph explore "rag_search.py rerank hybrid search"
codegraph explore "knowledge_sync.py Redis vector index"
codegraph explore "zeo_chatbot.workflow.ts Messenger flow"
```

CodeGraph giúp tìm symbol, file liên quan, caller/callee và phạm vi ảnh hưởng nhanh hơn việc mở nhiều file. Sau khi sửa code, index có thể trễ khoảng 1 giây; nếu báo stale thì đọc trực tiếp file vừa sửa.

## 22. Kết Luận

Hệ thống hiện tại đã chuyển từ chatbot FAQ đơn giản sang kiến trúc có:

- n8n nhận/gửi Messenger và sync Google Sheet.
- Python FastAPI làm não xử lý chính.
- Redis lưu knowledge/session/vector/learning queue.
- Ollama bge-m3 cho embedding tiếng Việt.
- RAG + intent router + context memory + guardrail.
- Admin dashboard và eval test.

Mục tiêu đúng của hệ thống không phải là trả lời mọi thứ. Mục tiêu đúng là:

- Có dữ liệu thì trả đúng.
- Không có dữ liệu thì không bịa.
- Câu rủi ro thì hỏi thêm hoặc chuyển admin.
- Lỗi nên được đưa vào learning queue để cập nhật Sheet; kết nối enqueue tự động từ chatbot hiện còn thiếu.
- Google Sheet cập nhật thì Redis/RAG phải sync lại để bot phản ánh đúng dữ liệu mới.

## 23. Module Danh Mục Shopee Động & Đồng Bộ Tự Động (Shopee Dynamic Catalog)

Các mục 23–30 lưu lịch sử các đợt nâng cấp. Khi một mô tả lịch sử khác phần trạng thái hiện hành ở mục 1–17 hoặc bảng xác minh mục 15.5, dùng phần trạng thái hiện hành. Các caveat được bổ sung trực tiếp bên dưới để tránh biến changelog thành cam kết production.

### 23.1. Mục Tiêu & Nguyên Tắc
- **Catalog snapshot là nguồn runtime chính**: Giá, sản phẩm và các metadata có mặt được đọc từ Redis; khi Redis rỗng matcher fallback CSV local. Snapshot hiện thiếu badge, và một số URL/hotline/fallback text/claim tư vấn vẫn đang hardcode.
- **Cấu hình sync 00:00**: `zeo_shopee_sync.workflow.ts` có cron `0 0 * * *`, ghi Redis rồi gọi `POST /api/shopee/refresh-cache`. File local đang `active: false`, nên chỉ tự chạy sau khi deploy/activate trên n8n.

### 23.2. Cấu Trúc Dữ Liệu Shopee Catalog
1. **File CSV Danh mục**: `ChatbotN8n/google_upload/zeo_shopee_catalog_template.csv` gồm **52 record**. Một số script build tham chiếu hai file crawl nguồn nhưng hai file đó không có trong checkout hiện tại, nên provenance không tái lập được chỉ từ workspace này:
   - **49 sản phẩm đang bán** (`in_stock: TRUE`).
   - **3 sản phẩm hết hàng** (`in_stock: FALSE` gồm: Nước tẩy toilet Pano 960g, Nước tẩy quần áo màu ZeO 400ml, Bộ 4 Tinh dầu thơm phòng ZeO).
   - **0 sản phẩm CFC** trong gian hàng ZeO Shopee Mall.
   - Cả 52 record trong snapshot CSV có URL dạng `https://shopee.vn/<slug>-i.20523065.<item_id>`; khả năng truy cập về sau vẫn phụ thuộc Shopee và item còn tồn tại.
   - CSV có đủ `BEST_SELLER_TOP_1..10`; nhóm new-arrival chỉ có rank 1, 4, 5, 6, 7, 9 cùng các badge `NEW_ARRIVAL` không rank, không đủ `TOP_1..10`.
   - Snapshot Redis đang chạy không có trường `badge` vì workflow sync bỏ cột này.
2. **Khớp sản phẩm thông minh (`shopee_matcher.py`)**:
   - Khớp ưu tiên: Top Bán Chạy / Mới Ra Mắt $\rightarrow$ Khớp theo Danh mục chính xác (+5 điểm) $\rightarrow$ Từ khóa sản phẩm (+4 điểm) $\rightarrow$ Biến thể / SKU $\rightarrow$ Fallback gian hàng.
   - `match_best_sellers()` và `match_new_arrivals()` duyệt catalog đã nạp từ cache/Redis/CSV để sinh câu trả lời. Tuy nhiên detector `sản phẩm mới nhất/mới ra mắt` ở `chat_pipeline.py` hiện chạy sớm và có thể trả `new_product_unverified` trước khi tới matcher new-arrival; nhánh này cần thống nhất lại.
3. **Endpoint hỗ trợ**: `POST /api/shopee/refresh-cache` làm mới cache tức thì mà không cần restart server.

### 23.3. Trí Tuệ Tư Vấn Khách Hàng Thông Minh (Smart CS AI Agent)
Để đóng vai trò một chuyên viên chăm sóc khách hàng (CSKH) xuất sắc, hệ thống đã nâng cấp toàn diện các luồng nghiệp vụ trong `chat_pipeline.py` và `shopee_matcher.py`:

1. **Lọc theo Tầm Giá / Ngân Sách (`match_products_by_budget`)**:
   - Nhận diện linh hoạt câu hỏi ngân sách: *"dưới 100k", "không quá 100k", "tầm/khoảng/quanh/gần 200k", "50k - 150k", "0.2 triệu"*.
   - Phân biệt chính xác `dưới` (`<`) với `không quá` (`<=`), `trên` (`>`) với `từ ... trở lên` (`>=`).
   - Với `APPROX`, tìm trong biên ±15%; chỉ khi rỗng mới mở rộng một lần đến ±25% và nói rõ với khách.
   - Quét Redis Shopee Catalog, chọn lọc 3-4 sản phẩm tiêu biểu thuộc các nhóm ngành khác nhau (giặt giũ, rửa chén, tẩy rửa) phù hợp tầm giá.
   - Category/tồn kho là hard filter; nếu không có kết quả thì trả no-result grounded, không lấy sản phẩm sai nhóm và không rơi sang semantic RAG.
   - Định dạng giá ưu đãi, % giảm giá (`6%`, `53%`) và link Shopee Mall kèm câu hỏi gợi mở tiếp tục tư vấn.

2. **Tư Vấn Đa Lượt Theo Lựa Chọn Nhu Cầu (`match_need_preference`)**:
   - Khi bot giới thiệu các nhóm và hỏi khách: *"Bạn muốn tư vấn theo nhu cầu sạch sâu, thơm lâu hay dịu nhẹ tiết kiệm?"*
   - Khách trả lời: *"nhu cầu tiết kiệm đi"*, *"loại nào thơm lâu"*, *"sạch sâu"*, *"dịu nhẹ da tay"*.
   - Bot lập tức tư vấn sâu đúng dòng tương ứng (vd: Tiết kiệm $\rightarrow$ Bột giặt Oplus 4in1, Bột giặt Pano bao lớn; Thơm lâu $\rightarrow$ PANO Veilex; Sạch sâu $\rightarrow$ ZeO Enzyme Thụy Điển; Dịu nhẹ $\rightarrow$ Pano Vitamin E / ZeO Nha Đam).

3. **Báo Giá Trực Tiếp Sản Phẩm Đích Danh & Tự Động Ghép Ngữ Cảnh (`match_specific_product_price` + `_resolve_reference`)**:
   - Khi khách hỏi giá sản phẩm cụ thể (vd: *"xin giá nước rửa chén vitamin e"*, *"bột giặt pano bao nhiêu"*).
   - Khi khách hỏi tắt theo quy cách/dung tích nối tiếp (vd: lượt 1 giới thiệu can lớn $\rightarrow$ lượt 2 hỏi *"Can 3.8kg giá bao nhiêu tiền?"* hoặc *"Giá bao nhiêu 1 chai?"*): Bot tự động lấy thực thể từ lượt trước trong `conversation_state`, ghép nối và tra cứu chính xác sản phẩm tương ứng trong Redis Shopee Catalog để báo giá ưu đãi và gửi link Shopee trực tiếp.
   - Nếu khách chỉ hỏi danh mục chung (vd: *"nước giặt giá bao nhiêu tiền 1 can"*), hệ thống tự chuyển sang bảng giá chung (`zeo_price_inquiry_general`) từ Google Sheet.

4. **Tư Vấn Can Lớn & Quán Ăn / Nhà Hàng (`match_bulk_or_restaurant_need`)**:
   - Khách hỏi can lớn thì matcher lọc catalog đã nạp từ cache/Redis/CSV. Tên, giá và link phải lấy từ snapshot hiện hành, không đóng đinh theo ví dụ lịch sử.

5. **Tư Vấn Chăm Sóc Da Tay (`match_skin_care_dishwashing`)**:
   - Matcher có thể gợi ý sản phẩm từ catalog, nhưng phần khẳng định pH/an toàn da tay hiện là text hardcode chưa có fact nguồn tương ứng. Cần thay bằng answer đã duyệt trong Sheet hoặc lời khuyên thận trọng trước khi dùng production.

6. **Bổ Sung Kiến Thức Hóa Đơn Đỏ VAT & Hướng Dẫn Sử Dụng Tẩy Rửa**:
   - `corporate_invoice_support`: Hỗ trợ xuất hóa đơn GTGT điện tử cho doanh nghiệp/hộ kinh doanh khi mua hàng.
   - `cleaning_usage_instruction`: Hướng dẫn các bước ngâm và cọ rửa bồn cầu / tẩy vệ sinh an toàn, hiệu quả.

7. **Bán Chạy & Mới Ra Mắt Theo Danh Mục**:
   - Câu bán chạy có thể dùng badge catalog. Câu “mới nhất/mới ra mắt” còn xung đột routing như lưu ý tại mục 23.2.

8. **Phân Tách Rõ Ràng Các Kênh Thông Tin (Website vs Mua Hàng Online vs Shopee Mall)**:
   - Hỏi **Website** $\rightarrow$ Sheet hiện ghi `https://zeo.vn/` cho ZeO và `https://cfccobay.com` cho CFC. `ai_engine.py` còn hardcode sai CFC thành `.vn`, cần sửa để không mâu thuẫn nguồn.
   - Hỏi **Link Shopee / Đặt Online** $\rightarrow$ Trả về gian hàng Shopee Mall chính hãng hoặc link mua hàng từ Sheet.

9. **Chuẩn Hóa Link Shopee Mall**:
   - Catalog snapshot lưu deep-link cho từng item. Hệ thống có thể kiểm tra định dạng/không rỗng, nhưng không thể bảo đảm link không 404 nếu Shopee đổi slug, gỡ item hoặc thay chính sách định tuyến.

10. **Bộ Lọc Câu Hỏi Cá Nhân & Phản Hồi Lịch Sự (Polite Dismiss & Clarification)**:
   - Khách hỏi cá nhân / ngoài lề (*"có biết anh Thuận là anh nào không"*, *"ai tạo ra bot"*): Bot phản hồi lịch sự xác định vai trò trợ lý CSKH và hỏi lại nhu cầu sản phẩm.
   - Khách từ chối / không quan tâm (*"ko quan tâm"*, *"ko cần biết"*, *"thôi khỏi"*): Bot chào lịch sự, không spam khuyến mãi.
   - Khách xác nhận ngắn (*"z ok"*, *"vậy ok"*, *"ok nha"*): Bot ghi nhận và cảm ơn thay vì tìm kiếm nhầm sang sản phẩm khác.
   - Khách gửi dấu hỏi (*"???"*, *"là sao"*): Bot hỏi lại khách cần giải thích phần nào để hỗ trợ.
   - Khách hỏi tẩy sàn / lau sàn (*"có cái nào mà tẩy sàn nhà ko"*, *"xin ít sản phẩm để tẩy sàn nhà đi"*): Bắt đúng nhóm Nước lau sàn ZeO & Oplus đậm đặc 2X.

11. **Kết Quả Đánh Giá NLU Regression Suite**:
   - Mốc ngày 21/08/2026: **112/112 regression PASS** và **26/26 unit PASS**. Kết quả cập nhật ngày 22/08 nằm tại mục 15.5.

---

## 24. Cập Nhật Web Admin: Google Sheets Live Hub & Trợ Lý Điều Hành AI

Ngày cập nhật: **18/08/2026**

### 24.1 Google Sheets Live Hub (Xem Trước & Direct Sync)
- **Tự động tải danh sách Tab (From List)**:
  - Endpoint `POST /admin/sheets/get-tabs`: Kết nối Google Sheets API v4 metadata, tự động đọc toàn bộ danh sách các Tab (Sheet Name) trong bảng tính và nạp vào Dropdown cho người dùng chọn trước khi xem trước/đồng bộ.
- **Tích hợp xem trước bảng tính trực tiếp**:
  - Hỗ trợ cả Sheet công khai và Sheet riêng tư (thông qua Google Cloud API Key / OAuth Bearer Token).
  - Endpoint `POST /admin/sheets/preview`: Bóc tách cấu trúc cột, số dòng theo đúng Sheet Tab đã chọn.
- **Đồng bộ trực tiếp vào Redis (1-Click Sync)**:
  - Endpoint `POST /admin/sheets/sync-direct` có thể ghi Redis và sync vector cho FAQ, nhưng đây là đường giản lược: nó bỏ `audience`, `answer_mode`, `source_id`, `profile_slots`, `escalation_policy`, ép `active=True` và không có các validation/min-row/duplicate-intent như workflow n8n. Không dùng thay đường sync chuẩn cho production cho đến khi bổ sung validation.
- **Tải lên File CSV trực tiếp (Offline / No Key)**:
  - Endpoint `POST /admin/sheets/upload-csv`: Cho phép kéo thả file CSV xuất từ Google Sheet trực tiếp mà không cần cấp quyền Google Drive.
  - Source chỉ decode/parse CSV; chưa hỗ trợ `.xlsx`/Excel. Với target Shopee, direct sync/upload còn lệch schema và chưa refresh đúng hot cache như nêu tại mục 12.

### 24.2 Trợ Lý Điều Hành AI & Tự Động Thực Thi Công Cụ (Autonomous Tool Execution)
- Có cơ chế `_match_autonomous_tool` trong `ai_engine.py` để một số câu hỏi gọi tool thật thay vì chỉ sinh text.
- Khi người dùng hỏi về:
  - Tình hình khách hàng/leads hôm nay $\rightarrow$ Tự động chạy `get_business_stats` đọc Redis CRM.
  - Danh mục Shopee $\rightarrow$ Tự động chạy `get_shopee_catalog_summary` đọc snapshot/cache hiện hành.
  - Danh sách / Lỗi n8n $\rightarrow$ Tự động chạy `list_n8n_workflows` hoặc `get_n8n_executions`.
  - Hàng đợi học $\rightarrow$ Tự động chạy `get_learning_queue_summary`.

Các tool có thể chạy shell hoặc thay đổi trạng thái workflow; chỉ mở cho admin đã xác thực và phải log/audit hành động.

### 24.3 Tinh Gọn Giao Diện Web Admin
- **Loại bỏ Menu & Tab Shopee Catalog**: Đã gỡ bỏ mục Shopee Catalog khỏi thanh Sidebar điều hướng, gỡ trang Shopee và gỡ bỏ thẻ cấu hình Shopee trong mục Cài đặt (Settings) theo yêu cầu, giữ giao diện Web Admin gọn gàng, tập trung vào Quản trị Chatbot, CRM Lead, n8n Console và Kho Kiến Thức FAQ RAG.

### 24.4 Nâng Cấp Báo Cáo AI Briefing (AI Insights)
- **Model Routing**: `call_groq()` generic vẫn thử default `llama-3.3-70b-versatile` trước; sau đó mới thử `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.6-27b`, `groq/compound`. Cấu hình chỉ có hiệu lực ở call site truyền model hoặc khi default không che mất config.
- **Dự phòng tổng hợp số liệu**: Khi AI provider lỗi, hệ thống có template fallback từ số liệu Redis. Cơ chế này giảm lỗi hiển thị nhưng không bảo đảm giao diện không bao giờ lỗi.
- **Render Markdown trực quan**: Định dạng bảng biểu, tiêu đề và gạch đầu dòng rõ ràng trên giao diện web.

### 24.5 SPA URL Hash Routing & Đồng Bộ Thanh Điều Hướng (Deep Linking)
- **Đồng bộ URL Hash khi chuyển Tab**: Mỗi khi chuyển tab (vd: Trợ lý AI, Hội thoại Lead, Báo cáo AI, n8n Control, Cài đặt), URL trình duyệt tự động cập nhật hash tương ứng (`/#assistant`, `/#customers`, `/#reports`, `/#n8n`, `/#learning`, `/#documents`, `/#test`, `/#settings`).
- **Giữ nguyên vị trí khi Reload (F5)**: Khi người dùng reload trang hoặc truy cập trực tiếp bằng đường link có hash, hệ thống tự động nhận diện và mở đúng trang đó mà không bị nhảy về Dashboard.
- **Hỗ trợ Nút Back/Forward của trình duyệt**: Bắt sự kiện `popstate` và `hashchange` để người dùng có thể điều hướng tới lui mượt mà như một ứng dụng web đa trang hiện đại.

### 24.6 Tái Cấu Trúc Toàn Diện Theo Mô Hình DDD & Modular Architecture
- **Bóc tách tệp nguyên khối `admin_routes.py` (2,377 dòng)** thành các Bounded Contexts / Domain Folders riêng biệt tại `domains/`:
  - `domains/common/`: Shared Kernel (Redis connection pool, settings I/O, config helpers).
  - `domains/system/`: Trạng thái hệ thống, Settings, Health check & Analytics.
  - `domains/assistant/`: Trợ lý điều hành AI & Autonomous tool agent.
  - `domains/customers/`: Quản lý khách hàng, hội thoại, Leads CRM & Export CSV.
  - `domains/n8n/`: Điều khiển Workflow n8n, Executions & Real-time File Watching.
  - `domains/reports/`: Báo cáo điều hành kinh doanh & AI Insights.
  - `domains/learning/`: Hàng đợi học (Learning Queue) & AI gợi ý FAQ.
  - `domains/knowledge/`: Kho kiến thức, Tài liệu Markdown & Google Sheets Live Hub.
  - `domains/rag_test/`: Kiểm thử Semantic Search RAG & NLU evaluation.
- **Facade Gateway Router**: `admin_routes.py` trở thành Facade Router tinh gọn (~55 dòng), nạp 8 sub-router và giữ các re-export đang được `main.py`/module khác dùng. Chưa có test chứng minh backward compatibility tuyệt đối cho mọi client.
- **Tổ chức thư mục `scripts/`**: Toàn bộ các script cào dữ liệu Shopee (`crawl_shopee_*.py`), tiền xử lý CSV (`clean_*.py`, `format_*.py`) và sinh tài liệu (`generate_doc.py`) được quy hoạch vào thư mục `scripts/`, giữ thư mục gốc server sạch sẽ và đúng chuẩn Enterprise codebase.

---

## 25. Nâng Cấp Trí Tuệ Hội Thoại Chuyên Sâu, Tư Vấn Đa Ý Định & Xử Lý Sự Cố Khẩn Cấp (CSKH 5 Sao)

Ngày cập nhật: **19/08/2026**

### 25.1 Grounded CSKH Synthesizer (`synthesize_cskh_answer`)
- **Tận dụng Ollama Local (`qwen2.5:7b-instruct`) / Groq / Gemini Flash**:
  - Khi tra cứu được dữ liệu thực tế (Facts từ Google Sheet / Redis Catalog), module `synthesize_cskh_answer` trong `ai_engine.py` chuyển thể Fact khô khan thành câu trả lời CSKH ngọt ngào, lễ phép, xưng "mình/dạ em", gọi "bạn/anh/chị".
  - **Grounding instruction**: Prompt yêu cầu model chỉ viết lại facts và có timeout/fallback template. Đây là lớp giảm rủi ro, không phải bảo đảm zero-hallucination.
  - **Clean Styling**: Bộ lọc loại một danh sách emoji cụ thể; không phải whitelist tuyệt đối cho mọi ký tự/emoji.

### 25.2 Multi-Intent Disambiguation (Bóc Tách Câu Hỏi Ghép Nhiều Ý)
- Khi khách hỏi câu ghép có liên từ (`và`, `với lại`, `còn`, `kèm theo`, `tiện thể`):
  - Hệ thống tự động phân tách câu hỏi thành 2 vế độc lập (Sub-queries).
  - Xử lý tuần tự tối đa 2 vế qua Shopee matcher/RAG rồi hợp nhất facts.
  - Ví dụ giá + giao hàng chỉ được bổ sung ưu đãi/Freeship khi fact đó có trong nguồn đã duyệt.

### 25.3 Tư Vấn Nỗi Đau & Nhu Cầu Chuyên Biệt (Consultative Sales Matching)
- Bổ sung các bộ matcher thông minh theo insight thực tế của người tiêu dùng:
  1. **Quần áo trẻ nhỏ / Da nhạy cảm (`match_baby_or_sensitive_laundry`)**: Có route tư vấn và chọn item từ catalog, nhưng claim “an toàn da liễu/không hóa chất tẩy gắt” hiện chưa có fact nguồn tương ứng.
  2. **Máy giặt cửa trước ít bọt (`match_front_load_washer`)**: Có route chọn sản phẩm, nhưng claim bảo vệ vi mạch/lồng giặt cần nguồn duyệt trước khi trả khách.
  3. **Da tay mỏng / Tróc da tay (`match_skin_care_dishwashing`)**: Có route gợi ý sản phẩm; claim pH trung tính/hoàn toàn không ăn da tay hiện là hardcode chưa grounded.
  4. **Can lớn tiết kiệm cho quán ăn / nhà hàng (`match_bulk_or_restaurant_need`)**: Tư vấn Can lớn 3.8kg / 9kg tối ưu chi phí và hỗ trợ số liên hệ sỉ B2B.

Giá trong các câu trả lời này phải lấy từ snapshot hiện hành; các con số ghi trong lịch sử thay đổi không phải giá cố định.

### 25.4 Phân Luồng & Cảnh Báo Khiếu Nại Hàng Lỗi Khẩn Cấp (`notify_urgent_complaint`)
- Nhận diện các phản ánh hàng bể nắp, nứt vỡ, rách bao, chảy nước (`URGENT_DAMAGE_TRIGGERS`):
  - Bot xin lỗi, hướng dẫn gửi ảnh/video và số điện thoại, đồng thời nêu phương án đổi/hoàn theo chính sách. Source hiện không cam kết hoàn tất đổi/hoàn trong 24 giờ; không được diễn giải thời hạn phản hồi thành thời hạn xử lý xong.
  - Tự động dispatch cảnh báo khẩn cấp `notify_urgent_complaint` về nhóm Telegram Admin kèm tên khách, số điện thoại, nội dung phản ánh và Sender ID để CSKH xử lý ngay.

### 25.5 In-Memory Local Session Cache
- Bổ sung `_local_session_cache` trong `chat_pipeline.py`:
  - Giúp lượt chat kế tiếp có thể đọc state từ RAM và giảm round-trip Redis. Không bảo đảm 0ms, không chia sẻ giữa worker/process và không loại bỏ hoàn toàn race condition.
  - Pipeline lập background task để lưu Redis (`session:messenger:*`). Nếu process chết trước khi task hoàn tất thì state có thể mất; chưa có write-through/versioning đầy đủ.

### 25.6 Khắc Phục Bắt Sai Ý Định Giá & Nâng Cấp Tư Vấn Vết Máu / Vết Ố / Hiệu Quả Làm Sạch
- **Khắc phục xung đột tiền tố `[GIÁ RẺ]`**: Khi `_resolve_reference` giải quyết tham chiếu (ví dụ *"Cái số 2 dùng ổn không, liệu có tẩy được vết máu không"* -> `[GIÁ RẺ] Bột giặt Pano...`), tiền tố `[GIÁ RẺ]` trong tên sản phẩm từng khiến bộ lọc giá hiểu lầm khách đang hỏi giá. Hệ thống đã tách biệt câu hỏi gốc của khách, loại bỏ tiền tố và chặn câu hỏi giá khi khách đang hỏi tính năng (`dùng ổn không`, `tẩy vết máu`, `tẩy ố`, `có sạch không`).
- **Module `match_stain_removal_or_efficacy`**: Có route cho câu hỏi vết máu/vết ố, nhưng text hiện chứa claim “tẩy vết máu 100%”, không phai/mục vải chưa được nguồn FAQ/catalog xác nhận. Đây là lỗi grounding cần sửa, không phải tính năng đã duyệt.
- **Bóc tách câu ghép đa mệnh đề theo dấu câu (`_detect_and_process_multi_intent`)**: Xử lý mượt mà các câu hỏi kép phân tách bởi dấu phẩy, dấu chấm hỏi hoặc liên từ (ví dụ: *"có sản phẩm nào dưới 200k ko nhỉ, có giao về rạch giá đc ko"* -> giải đáp đồng thời cả Phân khúc giá dưới 200k và Chính sách giao hàng về Rạch Giá).

### 25.7 Mốc Regression Ngày 21/08/2026
- **112/112 case theo expectation của runner**:
  - 98 câu đơn lẻ + 14 kịch bản hội thoại đa lượt (Multi-turn Context Memory).
  - Case mới xác minh `khoảng 200k -> xin link sản phẩm đó` trả URL sản phẩm trực tiếp, không phải link gian hàng chung.
- **PriceConstraint/price-ranking unit suite: 11/11 PASS**:
  - Comparator, `APPROX`, khoảng giá, triệu/thập phân, strict boundary, hard category, out-of-stock và range widening.
  - Câu `mắc nhất/đắt nhất/cao nhất` đọc catalog, sort theo giá hiện hành, bỏ hàng hết và không bị context cũ kéo sai.
- **Product/context follow-up unit suite: 6/6 PASS**:
  - Giữ `product_id`, rank, price snapshot và URL trong `last_products_shown`.
  - Resolve `sản phẩm đó` về đúng record; lookup catalog hiện hành theo `product_id` và fallback exact product name cho session cũ.
  - Câu hỏi explicit như `Giá nước xả vải ZeO shop ơi` không được dùng nhầm sản phẩm cũ trong context.
  - Câu nhu cầu `cái nào giặt đồ thơm thơm` được route sang tư vấn thơm lâu thay vì catalog chung.
- **Ollama NLU planner unit suite: 2/2 PASS**:
  - Test dùng fake planner để kiểm integration JSON/tool, không gọi Ollama live.
  - Ollama không sinh câu trả lời khách; giá/link vẫn lấy từ Shopee catalog và matcher deterministic.

Mốc cập nhật ngày 22/08/2026 nằm ở mục 15.5; scenario `--all` hiện chưa pass toàn bộ.

---

## 26. Kiến Trúc Hybrid Agentic RAG Có Kiểm Soát

Ngày cập nhật: **21/08/2026**

### 26.1 Nguyên Tắc Vận Hành Mới
- **Trạng thái thực tế 21/08/2026**: Pipeline là kiến trúc hybrid có kiểm soát, không phải LLM-only. Numeric constraint, an toàn, complaint, CRM và các intent rõ ràng tiếp tục dùng deterministic router; LLM chỉ tổng hợp facts hoặc hỗ trợ nhánh confidence thấp.
- **Phân định ranh giới rõ ràng**:
  1. **Data Layer (Code/Redis/Sheet)**: Cung cấp FAQ và catalog snapshot. FAQ được vector hóa bằng `bge-m3`; catalog giá hiện vẫn lọc bằng Python, chưa phải product vector index typed.
  2. **Decision Layer (`chat_pipeline.py`)**: Điều phối deterministic router, reference resolution, structured product memory, catalog matcher, optional Ollama NLU planner và RAG theo độ chắc chắn.
  3. **Language Layer (`ai_engine.py`)**: Ollama có thể phân loại intent dạng JSON hoặc viết lại facts thành câu CSKH; không được tự quyết định giá/link/tồn kho ngoài tool result.
  4. **Guardrail Layer**: Chặn một số unsupported facts, xử lý SĐT/địa chỉ CRM Lead, khiếu nại khẩn cấp và fallback/Telegram alert. Auto-enqueue learning queue chưa nối.
- **Lợi ích vận hành**: Cập nhật dữ liệu trong schema hiện có có thể phản ánh qua sync mà không sửa code; operator, policy hoặc hành vi nghiệp vụ mới vẫn phải qua test và có thể cần thay đổi parser/router.

### 26.2 Khắc Phục Lỗi Phản Hồi Câu Ngắn & Nhớ Ngữ Cảnh Chọn Nhóm (Short-Query & Slot-Filling Context)
- **Vấn đề đã xử lý**: Khi Bot hỏi *"Bạn đang quan tâm nhóm nào?"*, khách hàng nhắn ngắn gọn (`nước giặt`, `rửa chén`, `lau sàn`, `nhóm 1`, `số 2`), bot trước đây bị bẫy `_has_product_view_action` và văng vào vòng lặp fallback.
- **Giải pháp**:
  1. Nới lỏng `_has_product_view_action`: Tự động nhận diện tên danh mục sản phẩm độc lập ngắn gọn ($\le 4$ từ) mà không cần từ khóa phụ (*"muốn xem"*, *"cho xem"*).
  2. Bổ sung `_ordinal_reference_index` hỗ trợ các mẫu `nhóm 1`, `nhóm 2`, `nhóm 3`, `nhóm 4` để mở bung chi tiết nhóm ngành khi khách chọn theo số thứ tự sau khi xem catalog tổng quan.
  3. Cố định thứ tự ưu tiên: Nhận diện chi tiết sản phẩm cụ thể (`_detect_specific_product_intent`) chạy trước tổng quan nhóm (`_detect_product_group_intent`) để các câu hỏi đặc thù (mùi hương lau sàn, chứng nhận Pasteur, VEILEX) không bị đè bởi nhóm chung.

### 26.3 Xử Lý Chuyên Sâu Ý Định Nhập Hàng / Mua Sỉ (Wholesale & B2B Inquiries)
- **Vấn đề đã xử lý**: Khi khách dùng cụm từ *"cần nhập"*, *"muốn nhập"*, *"nhập nước rửa chén oplus loại 400g"*, hệ thống cũ bỏ sót từ khóa và bị nhảy sang Bột giặt Oplus.
- **Giải pháp triển khai**:
  1. Mở rộng từ khóa nhận diện sỉ/đại lý trong PATH 3.7: Bổ sung `can nhap`, `muon nhap`, `nhap lo`, `nhap ve`, `nhap dai ly`.
  2. Bổ sung điều kiện loại trừ từ khóa sỉ (`nhap`, `si`, `dai ly`) tại các nhánh catalog thông thường để không bị bắt nhầm thành hỏi thông tin sản phẩm.
  3. Cá nhân hóa câu trả lời B2B: Tự động trích xuất tên sản phẩm khách muốn nhập, xin số điện thoại + khu vực để chuyên viên liên hệ. Không khẳng định mức/chính sách chiết khấu nếu Sheet hoặc admin chưa cung cấp fact đã duyệt.

### 26.4 Kết Quả Kiểm Thử Theo Từng Mốc
- `eval_test_suite.py`: mốc 21/08 và lần offline/degraded 22/08 đều báo **112/112** theo expectation của runner.
- Tập con `--scenario user`, `user_slot`, `01`, `02`, `03`, `26`, `27` từng pass ở mốc 21/08; không suy ra toàn bộ scenario pass.
- Lần chạy offline/degraded `--all` ngày 22/08: **48/55 lượt (87,3%)**; scenario 04, 05, 09, 16 còn REVIEW.

### 26.5 Kết Hợp Redis State + Ollama Hỗ Trợ Suy Luận
- **Trạng thái**: Structured product memory đã triển khai lát cắt đầu tiên cho danh sách theo giá và follow-up xin link; write-through/versioning đầy đủ vẫn thuộc phần còn lại của Phase 2.
- **Cơ chế hoạt động thực tế trong mã nguồn**:
  1. **Redis (Long-Term Memory & State Store)**:
     - Lưu trữ snapshot kiến thức FAQ từ Google Sheet và Danh mục Shopee Catalog.
     - Lưu trạng thái phiên chat `f"{brand}:session:messenger:{sender_id}"` và `recent_turns` tối đa 6 lượt. Hiện key chưa đặt TTL.
     - Kết quả budget hiện lưu `product_id`, rank, category, price snapshot, URL và `shown_at` trong `last_products_shown`; `source_version` được giữ khi nguồn có cung cấp.
     - Follow-up `xin link sản phẩm đó` resolve theo `product_id`, lookup catalog hiện hành và fallback exact product name cho session cũ chỉ có name/category/intent.
  2. **Python resolver + Ollama tùy chọn**:
     - Pipeline hiện truyền `conversation_summary` cho CSKH synthesizer; tham số full `chat_history`/`catalog_products` có trong engine nhưng chưa được cấp ở mọi call site.
     - Giải mã đại từ (*"cái số 2"*, *"loại đó"*), chọn danh mục và phần lớn route mua sỉ do Python deterministic xử lý, không phải Ollama tự nhớ.
     - Lớp NLU planner tùy chọn hỗ trợ `off`, `shadow`, `assist`. Ollama local chỉ trả JSON intent/tool; pipeline chỉ áp dụng kế hoạch ở `assist`, khi confidence đạt ngưỡng và matcher deterministic trả được kết quả.
     - Có thể viết lại facts theo văn phong CSKH và lọc một số icon; output vẫn phải qua grounding/validation vì LLM không bảo đảm đúng tuyệt đối.
  3. **Cơ chế Fallback thông minh đa tầng**:
     - CSKH synthesizer ưu tiên `Ollama Local`, sau đó theo provider list của `generate_ai_text`; deterministic facts/fallback vẫn là lớp bảo vệ cuối.

---

## 27. Kế Hoạch Triển Khai RAG Giá & Structured Memory (21/08/2026)

### Phase 1 — PriceConstraint & Constraint-First Retrieval — ĐÃ HOÀN THÀNH

- `parse_price_constraint()` chuẩn hóa `LT/LTE/GT/GTE/BETWEEN/EXACT/APPROX` và tiền Việt (`k/nghìn/ngàn/tr/triệu`).
- `APPROX` dùng ±15%, mở rộng tối đa một lần tới ±25% khi không có candidate.
- Tồn kho, category và price comparator là hard constraints.
- `APPROX` xếp theo khoảng cách tuyệt đối tới target; các operator khác giữ business badge ordering.
- No-result trả deterministic answer, không semantic fallback sang sản phẩm sai điều kiện.
- `last_trace` lưu constraint, `range_widened`, `no_results` và `selected_product_ids`.
- Đã sửa false split multi-intent cho `còn không/còn hàng` và câu mô tả vết bẩn/da tay có dấu phẩy.

Acceptance đã xác minh:

```text
Price/ranking unit tests:       11/11 PASS
Product/context follow-up tests: 6/6 PASS
Ollama NLU planner tests:        2/2 PASS
Conversation guard tests:       7/7 PASS
NLU regression suite:          112/112 PASS
GET /health:                Redis OK, Ollama OK, bge-m3 available
API khoảng 200k:            grounded result + widened disclosure
API dưới 200k + nước giặt:  đúng category, mọi giá < 200.000đ
Redis trace:                APPROX target=200000 + product IDs
```

### Phase 2 — Structured Product Memory & Critical State — ĐANG TRIỂN KHAI

- **Đã hoàn thành lát cắt product-link**: `last_products_shown` lưu `product_id`, rank, category, price snapshot, URL và timestamp cho kết quả budget.
- **Đã hoàn thành lát cắt product-link**: resolve `sản phẩm đó` về `product_id`, lookup catalog mới nhất trước khi trả link; session cũ fallback exact product name.
- **Đã sửa stale-context pricing**: câu mới có category rõ ràng như `nước xả vải` trở thành hard filter trong báo giá, không cho `active_entities`/`last_products_shown` cũ làm lệch sang sản phẩm trước đó.
- **Đã sửa short need detection**: câu kiểu `cái nào giặt đồ thơm thơm` được hiểu là nhu cầu `thơm lâu`.
- **Đã thêm price-ranking intent**: câu kiểu `sản phẩm nào mắc nhất`, `giá cái nào mắc nhất`, `đắt nhất/cao nhất` trả top sản phẩm theo giá từ Shopee catalog, không rơi về catalog overview hoặc sản phẩm đầu tiên trong context.
- **Đã thêm Ollama NLU planner tùy chọn**: câu wording khó có thể được Ollama phân loại JSON. Mặc định `off`; `shadow` dùng để quan sát không đổi quyết định, `assist` mới cho phép chuyển sang tool deterministic.
- **Đã thêm return-flow state**: các lượt `Trả hàng` -> `Liên hệ sao để trả hàng` -> câu typo `Điện có tốn phí không` tiếp tục bám chính sách đổi trả, không trôi sang phí giao hàng.
- **Đã sửa catalog nước xả**: câu `Mua nước xả`, `Có nước xả ko`, `Xả vải ZeO` ưu tiên Shopee catalog thật và trả đúng Nano Clean ZeO cùng link sản phẩm; FAQ cũ nói chưa có đã được thay thế.
- **Đã thêm privacy guard**: không tra cứu/cung cấp thông tin khách hàng khác theo tên qua chatbot công khai.
- **Đã sửa availability false-positive**: `có sản phẩm` không còn bị hiểu thành `có sẵn`; vì vậy `Cái số 3 có sản phẩm nào thế` mở đúng nhóm lau sàn.
- Tiếp theo: mở rộng cùng cơ chế cho `cái số N/nó/loại đó` ở giá, tồn kho và các danh sách catalog khác; bổ sung source version bắt buộc.
- Thêm `last_query.price_constraint`, `turn_seq` và `session_version`.
- Critical conversational state dùng write-through/versioned update; transcript/analytics tiếp tục async.
- Đặt TTL có chủ đích và test restart/multi-worker, không dựa riêng vào RAM cache.

Gate: `ReferenceResolutionAccuracy`, không stale price, không mất state khi restart.

### Phase 3 — Product Search Schema & True Hybrid Retrieval

- Chỉ triển khai khi benchmark cho thấy Python filtering hiện tại không đủ.
- Index catalog theo typed fields: `product_id`, `brand`, `category`, `price_current NUMERIC`, `in_stock`, `updated_at`, text aliases và vector.
- Numeric/tag pre-filter trước lexical/vector; hợp nhất candidate bằng RRF hoặc score calibration.
- Không thay Redis ở phase này; chưa A/B embedding khi chưa có golden-set retrieval.

Gate: `RangeViolationRate = 0`, Recall@K/MRR tăng và p95 không suy giảm đáng kể.

### Phase 4 — Ollama Structured Fallback & Grounding Validator

- **Đã có lát cắt đầu tiên**: `plan_chat_intent_with_ollama()` trả JSON schema cho price/budget/link, product search/availability, chọn nhóm catalog, tư vấn nhu cầu, đổi trả, privacy, clarification và unknown; pipeline không cho planner trả text trực tiếp.
- Rule parser xử lý comparator/số; Ollama JSON Schema chỉ fallback cho câu khó hoặc confidence thấp.
- **Chưa triển khai đầy đủ** validator đối chiếu `product_id`, price, stock, URL và source version trước khi phát câu trả lời.
- **TODO** khi validation fail: deterministic fallback + enqueue learning queue. Hiện pipeline chủ yếu gửi Telegram alert và lưu session/history.

Gate: `UnsupportedClaimRate = 0` cho giá/tồn kho/link và clarification rate hợp lý.

### Phase 5 — Observability, Shadow & Rollout

- Golden set theo operator, typo, không dấu, multi-intent, reference, catalog update và no-result.
- Offline replay → shadow mode → progressive rollout.
- Dashboard theo dõi parse accuracy, range violations, reference resolution, stale price, fallback và p95.

### Lệnh Khởi Động/Test An Toàn

`testing/start_all.sh` hỗ trợ:

```bash
./testing/start_all.sh --test
```

Chế độ này không mở public tunnel, không `pkill`; chỉ khởi động/tái sử dụng Redis, Ollama và FastAPI local, chờ readiness rồi chạy unit + API price smoke tests. Chế độ `--background` không còn tự dừng process cũ theo pattern rộng; chỉ ghi PID của process do lần chạy hiện tại tạo.

---

## 28. Sơ Đồ Workflow Dùng Cho Báo Cáo Và Tạo Hình

File nguồn:

```text
SO_DO_WORKFLOW_CHATBOT_ZEO_CFC_CHO_BAO_CAO.md
```

File này gồm:

- Mermaid flowchart của luồng tin nhắn Messenger từ khách đến n8n, Python FastAPI, Redis/Ollama/RAG rồi trả về khách.
- Mermaid flowchart của luồng đồng bộ Google Sheet/Shopee Catalog vào Redis snapshot và vector index.
- Mermaid flowchart của learning queue khi bot thiếu dữ liệu hoặc guardrail fail.
- Prompt tiếng Việt đầy đủ và prompt rút gọn để đưa trực tiếp vào ChatGPT/Image Generator tạo infographic 16:9 cho báo cáo.
- Checklist kiểm tra hình để tránh mô tả sai vai trò của n8n, Python, Ollama và RAG.

Luồng một dòng dùng trong slide:

```text
Khách nhắn Messenger
→ n8n nhận/lọc tin
→ Python FastAPI đọc memory và chọn deterministic tool / Ollama NLU / RAG
→ grounding + guardrail
→ n8n gửi Facebook Graph API
→ khách nhận câu trả lời
```

Trạng thái xác minh ngày 21/08/2026:

```text
Unit tests:       26/26 PASS
Regression eval: 112/112 PASS, trung bình 2,9ms/câu trong offline test
FastAPI /health: service OK, Redis OK, Ollama OK, bge-m3 available (isolated worker :8001)
Vector indexes:   zeo:vec:faq, cfc:vec:faq
```

Lưu ý: số `2,9ms/câu` chỉ đo phần pipeline trong bộ offline regression; không đại diện tổng thời gian Messenger → n8n → Facebook Graph API ngoài thực tế.

---

## 29. Regression Guard Cho Hội Thoại Thực Tế (21/08/2026)

Các lỗi từ transcript thực tế đã được khóa bằng code và test:

| Tình huống | Hành vi mới | Nguồn quyết định |
|---|---|---|
| `Mua nước xả` / `Xả vải ZeO` | Trả đúng Nano Clean ZeO, giá và deep-link hiện hành | Shopee catalog trong Redis |
| `Trả hàng` -> `Liên hệ sao` -> `Điện có tốn phí không` | Giữ active return flow; không nhảy sang shipping | Structured session state + Sheet policy |
| `Cái số 3 có sản phẩm nào thế` | Mở chi tiết nhóm lau sàn | Catalog context + ordinal resolver |
| `Thông tin khách hàng <tên>` | Từ chối cung cấp dữ liệu người khác | Privacy guard deterministic |
| `sản phẩm mắc nhất` | Sắp xếp toàn catalog theo giá, không dùng item cũ trong context | Shopee price matcher |

Ollama được đặt đúng vai trò **NLU planner**, không phải nguồn sự thật. Kết quả planner phải đi qua deterministic matcher/Sheet/Redis trước khi trả khách. Nếu Ollama timeout, JSON sai hoặc confidence thấp, luồng cũ tiếp tục hoạt động.

Theo ghi nhận ngày 21/08/2026, một worker tạm `127.0.0.1:8001` từng pass health và 7 lượt smoke với Redis/Ollama. Không có artifact log độc lập trong checkout để tái lập claim này, và audit ngày 22/08 không chạy lại bộ 7 lượt; dùng bảng mục 15.5 làm trạng thái kiểm thử hiện tại.

---

## 30. Bộ Case Trình Diễn Cho Quản Lý Khó Tính

File kiểm thử thủ công:

```text
testing/KICH_BAN_TEST_SEP_KHO_TINH_ZEO.md
```

Bộ test được chia thành:

- Nhóm A gồm 8 kịch bản nên pass trước khi demo: ràng buộc giá/deep-link, mắc nhất toàn catalog, nước xả không stale context, chọn nhóm số 3, đổi trả có typo, privacy, multi-intent và chống bịa khi thiếu dữ liệu.
- Nhóm B gồm 5 stress test cần chạy trước khi trình diễn: prompt injection, ép tồn kho realtime, điều kiện mâu thuẫn, an toàn hóa chất và phục hồi sau khi khách công kích.
- Có tiêu chí PASS/FAIL, lỗi nghiêm trọng, bảng ghi kết quả và ngưỡng go/no-go trước buổi demo.

Giá, sản phẩm và link trong bộ test không đóng đinh theo snapshot cũ; người test phải đối chiếu catalog hiện hành tại thời điểm chạy.

---

## 31. Cập Nhật Intelligence QueryPlan & Grounded Routing (22/08/2026)

Mục tiêu đợt này không audit lại toàn hệ thống mà tập trung vào khả năng hiểu tiếng Việt tự nhiên, giữ ngữ cảnh, truy xuất đúng và trả lời không bịa.

### 31.1 Tài liệu mới

Đã bổ sung bộ tài liệu intelligence trong `docs/`:

- `11A_INTELLIGENCE_BASELINE.md`: baseline trước/sau, 30 case đại diện và lỗi quan sát.
- `11B_QUERYPLAN_DESIGN.md`: contract QueryPlan deterministic.
- `11C_REFERENCE_RESOLUTION_DESIGN.md`: thiết kế giữ/ngắt ngữ cảnh tham chiếu.
- `11D_RETRIEVAL_BENCHMARK.md`: benchmark trước/sau và hai case còn REVIEW do alias intent.
- `11E_INTELLIGENCE_IMPLEMENTATION_REPORT.md`: báo cáo implementation, guardrail và test.

### 31.2 Source thay đổi

| File | Vai trò |
|---|---|
| `ChatbotN8n/javis/server/query_understanding.py` | Module mới tạo `QueryPlan` deterministic từ câu tiếng Việt đã normalize |
| `ChatbotN8n/javis/server/chat_pipeline.py` | Tích hợp QueryPlan vào trace/router; thêm route an toàn cho toilet, brand ecosystem, compatibility và CFC lúa |
| `ChatbotN8n/javis/server/shopee_matcher.py` | Giảm các claim tuyệt đối chưa có nguồn như “100%”, “hoàn toàn không ăn da tay”, “hỏng vi mạch” |
| `ChatbotN8n/javis/server/ai_engine.py` | Không gọi CSKH LLM khi không có retrieved facts/catalog products |
| `ChatbotN8n/javis/server/tests/test_query_understanding.py` | Thêm 8 unit test QueryPlan |

### 31.3 Hành vi mới đáng chú ý

- `Bồn cầu bị cặn vôi ố vàng...` được route về nhóm tẩy rửa vệ sinh, không còn bị hiểu là vết bẩn quần áo.
- `Có bị nồng nặc mùi hôi như mấy loại tẩy con vịt ko?` dùng fact từ `zeo_toilet_cleaner`, không kéo sang gửi link sản phẩm.
- `ZeO, PANO với Oplus là 3 hãng khác nhau hay sao?` trả overview hệ thương hiệu từ `company_overview`.
- `Nước giặt PANO 3.5kg có bị trào bọt không?` trả lời thận trọng theo hướng compatibility, không bịa cam kết kỹ thuật.
- `Tôi chuẩn bị xuống giống 3 hecta lúa...` được nhận diện là CFC agriculture advisory, trả lời an toàn và xin thông tin cho kỹ sư/đại lý, không tự đưa liều lượng.
- Tin nhắn có số điện thoại vẫn ưu tiên lead capture trước mọi route advisory/context.
- Câu CFC hỏi giá rõ sản phẩm như `Bao 25kg NPK... giá bao nhiêu?` không bị context lúa trước đó kéo sai sang contextual price.

### 31.4 Kết quả test sau cập nhật

Điều kiện test ngày 22/08/2026: sandbox degraded, Redis/Ollama/Groq không truy cập được; Shopee catalog dùng fallback CSV local.

```text
Unit tests:                 34/34 PASS
eval_test_suite.py:        112/112 PASS, ~2.6–2.8ms/câu
run_test_md_scenarios.py:   53/55 PASS (96.4%)
```

Hai lượt scenario còn REVIEW là khác tên intent nhưng nội dung đúng nguồn:

- `cleaning_usage_instruction` vs expected alias `usage_instructions`.
- `pano_laundry_fragrance_options` vs expected alias `pano_fragrance_options`.

Không đổi source intent chỉ để ăn điểm test; nếu muốn báo cáo 55/55 thì nên thêm alias tương đương trong scenario runner.
