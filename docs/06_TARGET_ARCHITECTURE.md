# Kiến trúc mục tiêu

Ngày thiết kế: 2026-08-22  
Mục tiêu: tăng độ đúng, khả năng giải thích và độ ổn định mà không rewrite toàn bộ project.

## 1. Quyết định kiến trúc

Giữ các nền tảng hiện tại:

- n8n làm Messenger I/O gateway và job đồng bộ;
- FastAPI làm decision layer;
- Redis lưu snapshot, search index và conversation state;
- `bge-m3` là embedding baseline;
- deterministic tools xử lý giá, link, stock, SKU, ranking và policy rủi ro;
- Ollama chỉ hiểu câu khó/diễn đạt facts, không là nguồn sự thật.

Thêm các boundary còn thiếu:

1. authentication/RBAC cho admin;
2. ingress validation + Messenger idempotency;
3. versioned, validated, atomic knowledge publication;
4. structured query plan và fact envelope;
5. deterministic answer validator;
6. Redis-authoritative session update có sequence/version;
7. unified trace và evaluation gates;
8. hybrid retrieval/reranker chỉ bật sau benchmark.

## 2. Sơ đồ request path mục tiêu

```text
Facebook Messenger
        │
        ▼
n8n I/O Gateway
  - verify/normalize event shape
  - ignore echo/unsupported attachment/empty input
  - preserve message_id + request_id
  - retry policy cho FastAPI/Graph API
        │
        ▼
FastAPI Public Chat API
  - input limits, brand allowlist
  - idempotency(message_id)
  - rate limit / overload response
        │
        ▼
Redis Conversation Coordinator
  - distributed sender lock hoặc ordered sequence
  - versioned state + TTL
  - active entities, last products, active flow
        │
        ▼
Message Normalizer + QueryPlan
  - Vietnamese normalize/typo aliases
  - intent/entities/constraints/reference
  - split tối đa 2 subqueries có kiểm soát
        │
        ├───────────────┐
        ▼               ▼
Deterministic Tools     Retrieval Layer
price/product/link      exact/FTS lexical
stock/policy/privacy    + dense KNN
safety/CRM              + optional RRF
                        + optional reranker
        └───────────────┬───────────────┘
                        ▼
                  FactEnvelope
            source_id + source_version
            typed facts + freshness
            allowed/prohibited claims
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
      Deterministic template   Ollama synthesizer
      (ưu tiên facts nhạy cảm) (chỉ rewrite facts)
              └─────────┬─────────┘
                        ▼
              Deterministic Validator
          number/URL/product/brand/safety/PII
              ├─ pass → response
              └─ fail → safe template/clarify/escalate
                        │
                        ▼
             Trace + durable learning event
                        │
                        ▼
                n8n → Facebook Graph API
```

## 3. Kiến trúc ba tầng

### Layer 1 — Deterministic

Áp dụng cho:

- greeting/acknowledgement đơn giản;
- exact product/SKU/item ID;
- price constraint/ranking;
- stock snapshot và freshness;
- product URL/official channel;
- privacy, complaint, chemical/agricultural safety;
- customer contact collection;
- schema validation và output validation.

Lý do: các tác vụ này có đáp án typed, cần boundary rõ và không chấp nhận model suy đoán.

### Layer 2 — Retrieval

Áp dụng cho:

- FAQ;
- chính sách và thông tin công ty;
- giải thích công nghệ/sản phẩm có source;
- tài liệu Markdown dài;
- câu semantic chưa có deterministic tool.

Pipeline mặc định:

```text
metadata filter
→ exact/lexical candidate
→ dense KNN candidate
→ merge khi benchmark chứng minh có lợi
→ optional cross-encoder trên top-k
→ FactEnvelope
```

Business filters (`brand`, `audience`, `active`, `risk`, `category`) luôn chạy trước hoặc độc lập với relevance score; reranker không được vượt qua filter.

### Layer 3 — LLM

Áp dụng có giới hạn:

- JSON intent planning cho câu khó;
- controlled query rewrite;
- tóm tắt state dài;
- viết lại facts theo văn phong CSKH;
- tạo clarification question.

Không áp dụng cho:

- tạo price/stock/link/SKU;
- quyết định quyền admin;
- chạy command chung;
- tạo safety/efficacy claim;
- lựa chọn nguồn ngoài allowlist;
- tự sửa validation failure.

## 4. Hợp đồng dữ liệu mục tiêu

### 4.1 `KnowledgeRecord`

```json
{
  "record_id": "zeo:return_policy:v3",
  "schema_version": 1,
  "source_id": "sheet-zeo-faq",
  "source_version": "2026-08-22T10:30:00+07:00",
  "brand": "zeo",
  "audience": "customer",
  "active": true,
  "category": "policy",
  "intent": "return_policy",
  "question_examples": ["..."],
  "answer": "...",
  "risk_level": "medium",
  "valid_from": "...",
  "valid_to": null,
  "content_hash": "sha256:..."
}
```

Rules:

- allowlist `audience=customer` cho customer index;
- unique `(brand, intent, source_version)` hoặc explicit conflict rule;
- `source_id`, version, hash và updated time bắt buộc;
- không publish nếu mất quá ngưỡng record so với active snapshot;
- policy/high-risk row cần approval metadata.

### 4.2 `ProductRecord`

```json
{
  "product_id": "43672853910",
  "schema_version": 1,
  "source_version": "...",
  "brand": "zeo",
  "name": "...",
  "category": "laundry",
  "variant": "...",
  "price_current": 239343,
  "price_original": 460275,
  "currency": "VND",
  "in_stock": true,
  "url": "https://shopee.vn/...",
  "badges": ["BEST_SELLER_TOP_2"],
  "as_of": "..."
}
```

Rules:

- price numeric, URL host allowlist, product ID unique;
- badge/rank không được tự suy ra từ row order;
- stock là snapshot có `as_of`, không gọi là realtime;
- publish atomic và reject partial snapshot bất thường.

### 4.3 `QueryPlan`

```json
{
  "intent": "product_search",
  "confidence": 0.91,
  "entities": {"category": "laundry"},
  "constraints": {"price": {"operator": "LT", "value": 200000}},
  "reference": {"type": "ordinal", "rank": 2},
  "required_tools": ["catalog_search"],
  "subqueries": []
}
```

Deterministic parser sở hữu numeric constraints. Ollama planner chỉ bổ sung trường còn mơ hồ; JSON phải qua schema/allowlist.

### 4.4 `FactEnvelope`

```json
{
  "facts": [
    {
      "fact_id": "product:43672853910:price",
      "field": "price_current",
      "value": 239343,
      "source_id": "shopee-sheet",
      "source_version": "...",
      "as_of": "..."
    }
  ],
  "allowed_claims": ["name", "price_current", "url"],
  "prohibited_claim_types": ["absolute_safety", "unverified_stock"],
  "citation_ids": ["product:43672853910"]
}
```

LLM nhận envelope đã redacted thay vì nhận settings/profile/raw stores.

### 4.5 `ConversationState`

```json
{
  "session_version": 14,
  "turn_seq": 21,
  "updated_at": "...",
  "expires_at": "...",
  "active_entities": {},
  "last_products_shown": [],
  "last_query": {},
  "active_flow": {},
  "covered_fact_ids": [],
  "summary": "..."
}
```

State critical phải write-through/CAS. History/analytics có thể append async.

## 5. Sync architecture mục tiêu

```text
Google Sheet / reviewed CSV
        │
        ▼
Fetch raw rows + source revision
        │
        ▼
Normalize to canonical schema
        │
        ▼
Validation gate
  - required fields/types
  - audience/brand allowlists
  - duplicates/conflicts
  - URL/price/stock constraints
  - min rows + abnormal delta
        │
        ▼
Write versioned staging snapshot
        │
        ├─ FAQ: batch embed changed hashes only
        └─ Product: typed index/snapshot
        │
        ▼
Smoke queries + record/hash counts
        │
        ▼
Atomic active pointer/alias swap
        │
        ▼
Cache invalidation by source_version
        │
        ▼
Write success metadata + audit event
```

Nếu bất kỳ bước nào fail, active version cũ tiếp tục phục vụ và job báo `failed`; không ghi green metadata sớm.

## 6. Retrieval architecture mục tiêu

### Baseline bắt buộc

- exact intent/entity/SKU lookup;
- current lexical hot cache;
- current dense KNN;
- metadata filter;
- metrics theo từng retriever.

### Candidate target sau benchmark

```text
Lexical/BM25 top 20 ─┐
                     ├─ RRF top 20 ─ optional multilingual reranker ─ top 5
Dense KNN top 20 ────┘
```

`FT.HYBRID` chỉ dùng nếu Redis runtime >= 8.4 và benchmark đơn giản hơn application-side fusion. Với 65 + 19 FAQ customer records hiện tại, application-side implementation có thể dễ kiểm thử hơn; chưa có lý do thay vector DB.

Document index nên hỗ trợ `parent_id`, `heading_path`, `doc_version`, `audience`, `risk_level`, và lấy child hit kèm parent context. FAQ và document results cần cùng `RetrievedFact` schema trước generation.

## 7. Answer validator

Validator không phải một LLM judge duy nhất. Nó gồm rule deterministic:

1. Extract typed claims: giá, %, số lượng, dung tích, hotline, URL, product name, stock wording.
2. Match từng claim với `FactEnvelope` và source version.
3. Enforce brand/audience/privacy/risk policy.
4. Detect unsupported absolutes và prohibited phrases.
5. Kiểm tra link host/item ID và price constraint.
6. Nếu fail: template grounded → clarification → human escalation.

LLM-based faithfulness judge chỉ dùng offline/shadow evaluation, không là security control duy nhất trên production path.

## 8. Admin/security boundary

Tách route public chat và admin:

```text
/api/chat-pipeline       public service credential + rate limit
/admin/*                 authenticated user + RBAC scopes
```

Scopes tối thiểu:

- `admin:read` — status/metrics đã redacted;
- `customers:read` — PII có audit log;
- `knowledge:write` — staging/sync;
- `n8n:deploy` — explicit human action;
- không có scope cho arbitrary shell từ chat assistant.

CORS dùng allowlist. Settings GET trả status/redacted fields, không trả secret. Mọi mutation có actor, request ID, before/after metadata và audit record.

## 9. Failure behavior mục tiêu

| Failure | Hành vi mục tiêu |
|---|---|
| Redis down | Không xác nhận price/state không kiểm chứng; trả safe service fallback và alert |
| Ollama embed down | Exact/lexical degraded mode; trace dependency failure |
| Ollama generation down | Deterministic grounded template |
| Sheet down | Giữ active version cũ; ghi stale status, không xóa snapshot |
| Partial/malformed Sheet | Reject staging; active version không đổi |
| Duplicate Messenger event | Trả/reuse cached result theo `message_id`; không tạo turn thứ hai |
| 5 tin liên tiếp cùng sender | Ordered by `turn_seq`; không stale overwrite |
| Validator fail | Không phát output LLM; fallback + learning event |
| Learning exporter crash | Event còn pending/claimable, không mất do pop trước ack |
| Graph API failure | bounded retry + dead-letter/alert; không gọi lại brain vô hạn |

## 10. Observability và rollout

Mỗi turn có `request_id`, hashed sender/message ID, route, query plan, candidate ranks, selected sources/version, validation outcome, fallback reason và component timing. Không log secrets/PII raw.

Rollout:

1. offline golden set;
2. replay sanitized transcripts;
3. shadow planner/hybrid/validator;
4. compare current vs target;
5. progressive enable theo brand/traffic segment;
6. automatic rollback khi unsupported claims, range violations hoặc p95 vượt gate.

## 11. Những gì cố ý không thêm

- GraphRAG khi corpus chủ yếu là FAQ/catalog nhỏ và không có multi-hop graph use case.
- Full agentic loop cho customer replies.
- LangChain/LangGraph rewrite chỉ để bọc các hàm đang rõ ràng.
- Vector database mới khi Redis đáp ứng snapshot/state/vector hiện tại.
- Embedding/model mới trước benchmark tiếng Việt nội bộ.
- LLM thứ hai trên mọi request chỉ để “kiểm tra” LLM thứ nhất.

Kiến trúc mục tiêu ưu tiên simple, observable, testable và fail-closed cho factual claims.
