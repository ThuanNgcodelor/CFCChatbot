# Kỹ thuật và quyết định áp dụng

Ngày đánh giá: 2026-08-22  
Nguyên tắc: mỗi kỹ thuật phải giải quyết một failure mode đã quan sát và vượt acceptance gate; không thêm framework chỉ vì phổ biến.

## Bảng quyết định nhanh

| Kỹ thuật | Phân loại | Khi thực hiện |
|---|---|---|
| Canonical schema + staged atomic publish | MUST | P0 |
| Audience/brand/risk metadata allowlist | MUST | P0 |
| Deterministic structured product/policy tools | MUST | Giữ và chuẩn hóa |
| FactEnvelope + deterministic answer validator | MUST | P0 |
| Admin auth/RBAC + least privilege | MUST | P0 |
| Messenger idempotency + versioned Redis state | MUST | P2 |
| Exact/lexical + dense retrieval baseline | MUST | P1 measurement |
| BM25/FTS + dense + RRF | SHOULD, có điều kiện | Khi baseline chứng minh retrieval gap |
| Multilingual cross-encoder reranker | LATER | Khi RRF top-k còn nhiễu |
| Parent-child retrieval cho tài liệu dài | SHOULD, có điều kiện | Khi document RAG được nối vào chat |
| Controlled query rewrite | LATER | Chỉ cho ambiguous semantic query |
| Multi-query retrieval | LATER | Chỉ nếu single-query recall thấp |
| Ragas/LLM judge | SHOULD như metric phụ | Offline/shadow evaluation |
| Ollama keep-alive/backpressure/pooling | MUST đo và cấu hình | P4 |
| Durable Redis Stream learning loop | SHOULD | P3 |
| GraphRAG | NOT NEEDED | Chưa có multi-hop graph use case |
| Full agentic RAG | NOT NEEDED | Customer chat cần deterministic boundary |
| LangChain/LangGraph migration | NOT NEEDED hiện tại | Chỉ xét workflow dài có pause/resume |
| Vector database mới | NOT NEEDED | Redis chưa chứng minh là bottleneck |
| Embedding/LLM swap | LATER | Sau golden benchmark |

## 1. Canonical schema và staged atomic publication

**Tên:** Canonical Knowledge/Product Contract + Staging/Atomic Active Version  
**Nguồn:** Kỹ thuật database/versioned deployment phổ quát; Redis hỗ trợ index/metadata và application có thể dùng versioned keys/aliases. [Redis vector search](https://redis.io/docs/latest/develop/ai/search-and-query/vectors/).  
**Giải quyết:** schema drift, partial Sheet overwrite, badge/audience/source version bị mất, success metadata xanh giả.  
**Áp dụng vào module:** n8n knowledge/Shopee workflows, `knowledge_sync.py`, admin Sheet service, `rag_search.py`, `shopee_matcher.py`.  
**Current problem:** nhiều producer tạo field khác nhau và ghi thẳng active key/index/cache.  
**Expected benefit:** một snapshot chỉ active sau validation/index/cache smoke pass; rollback được; answer trace được version.  
**Complexity:** Medium.  
**Resource requirement:** schema models, staging keys/index, migration/contract tests; không cần dịch vụ mới.  
**Recommended:** **YES — MUST/P0**.

## 2. Metadata allowlist và hard filtering

**Tên:** Typed Metadata Filtering  
**Nguồn:** Redis cho phép kết hợp vector query với text, numeric và tag filters: [Redis vector search](https://redis.io/docs/latest/develop/ai/search-and-query/vectors/).  
**Giải quyết:** lẫn ZeO/CFC, customer nhận nội dung `agent/internal`, sản phẩm sai category/stock/price.  
**Áp dụng vào module:** `knowledge_sync.py`, `rag_search.py`, `shopee_matcher.py`, sync validators.  
**Current problem:** một số path chỉ phạt audience bằng score hoặc lọc chính xác `internal`, thay vì allowlist `customer`.  
**Expected benefit:** invalid candidates bị loại trước ranking; violation rate có thể buộc bằng 0.  
**Complexity:** Low–Medium.  
**Resource requirement:** typed fields và migration/reindex.  
**Recommended:** **YES — MUST/P0**.

## 3. Deterministic structured lookup

**Tên:** Product/Policy Tools thay cho semantic guessing  
**Nguồn:** Nguyên tắc hệ thống hiện có và target architecture; structured facts không cần LLM.  
**Giải quyết:** giá, stock, SKU, link, ranking, comparator và policy risk cần exactness.  
**Áp dụng vào module:** `shopee_matcher.py`, price parser, privacy/safety/complaint routes.  
**Current problem:** phần lookup đúng hướng nhưng một số matcher trộn structured result với claim marketing/safety hardcode.  
**Expected benefit:** constraint violation bằng 0, explainable trace, latency thấp.  
**Complexity:** Low để giữ, Medium để tách result/template.  
**Resource requirement:** canonical record + tool result schema.  
**Recommended:** **YES — MUST; không thay bằng RAG/LLM**.

## 4. FactEnvelope và deterministic answer validator

**Tên:** Source-grounded Claim Validation  
**Nguồn:** OWASP khuyên xác định/validate output format, filter output và giữ controls ngoài LLM: [Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/), [Improper Output Handling](https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/).  
**Giải quyết:** output LLM/hardcode thêm giá, URL, stock, chứng nhận hoặc absolute safety claim không có nguồn.  
**Áp dụng vào module:** mọi answer producer trong `chat_pipeline.py`, `ai_engine.py`, `shopee_matcher.py`.  
**Current problem:** prompt bám facts nhưng facts có thể rỗng; post-check hiện chủ yếu length/emoji.  
**Expected benefit:** `UnsupportedCriticalClaimRate = 0` trên critical set; fail closed về template/clarification.  
**Complexity:** Medium–High.  
**Resource requirement:** fact schema, typed claim extractor, policies, golden `must_not_say`.  
**Recommended:** **YES — MUST/P0**.

## 5. FastAPI authentication, RBAC và least privilege

**Tên:** Authenticated Admin Boundary  
**Nguồn:** FastAPI hỗ trợ OAuth2/JWT và scopes: [OAuth2/JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [OAuth2 scopes](https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/); OWASP yêu cầu least privilege/human approval cho high-risk tools: [Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/).  
**Giải quyết:** anonymous settings/PII/workflow access và shell tool blast radius.  
**Áp dụng vào module:** `admin_routes.py`, domain routers, settings/customer/n8n/assistant routes, reverse proxy.  
**Current problem:** không có shared auth dependency, CORS rộng, tool shell chung.  
**Expected benefit:** unauthorized access/tool execution bằng 0; audit được actor/action.  
**Complexity:** Medium–High.  
**Resource requirement:** identity choice, roles/scopes, key/session lifecycle, audit tests.  
**Recommended:** **YES — MUST/P0**.

## 6. Messenger idempotency và versioned Redis state

**Tên:** Idempotent Event Handling + Optimistic State Concurrency  
**Nguồn:** Distributed-system pattern; áp dụng trực tiếp vì `message_id` đã có nhưng chưa sử dụng.  
**Giải quyết:** duplicate webhook, stale async write, multi-worker lock gap và sai ordinal follow-up.  
**Áp dụng vào module:** n8n ingress, `ChatPipelineRequest`, session load/save, Redis keys.  
**Current problem:** process-local lock/cache; plain background `SET`; không TTL/CAS/turn sequence.  
**Expected benefit:** one event → one turn/reply; burst ordered; restart/multi-worker giữ state.  
**Complexity:** High.  
**Resource requirement:** idempotency key TTL, `turn_seq/session_version`, transaction/Lua/CAS tests.  
**Recommended:** **YES — MUST/P2**.

## 7. Exact/lexical + dense baseline

**Tên:** Measured Multi-Retriever Baseline  
**Nguồn:** BGE-M3 cung cấp multilingual dense retrieval foundation: [BGE-M3 paper](https://arxiv.org/abs/2402.03216); Redis hỗ trợ KNN + metadata filtering.  
**Giải quyết:** chưa biết query nào lexical thắng, query nào dense thắng; không có Recall@K/MRR.  
**Áp dụng vào module:** `rag_search.py`, golden evaluation harness.  
**Current problem:** lexical có thể early-return, nên không lưu hai rank lists để so sánh.  
**Expected benefit:** evidence để biết có cần hybrid/reranker; tối ưu đúng failure cluster.  
**Complexity:** Medium.  
**Resource requirement:** expected document IDs, trace candidates, offline runner.  
**Recommended:** **YES — MUST trước mọi retrieval upgrade**.

## 8. BM25/FTS + dense + Reciprocal Rank Fusion

**Tên:** Hybrid Retrieval with RRF  
**Nguồn:** [RRF paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf); Redis `FT.HYBRID` kết hợp full-text/vector bằng RRF hoặc linear từ Redis 8.4: [FT.HYBRID](https://redis.io/docs/latest/commands/ft.hybrid/).  
**Giải quyết:** exact keywords/SKU/entity và semantic paraphrase cung cấp tín hiệu bổ sung.  
**Áp dụng vào module:** FAQ/document retrieval, không dùng cho price/stock deterministic tools.  
**Current problem:** current path chọn lexical sớm hoặc vector rồi heuristic, chưa rank fusion.  
**Expected benefit:** giả thuyết Recall@5/MRR cao hơn mà không cần calibrate hai score bằng RRF.  
**Complexity:** Medium.  
**Resource requirement:** application-side fusion; hoặc Redis >=8.4 cho `FT.HYBRID`; benchmark/trace.  
**Recommended:** **YES — SHOULD/SHADOW**, chỉ giữ khi metric tăng và p95 đạt.

## 9. Multilingual cross-encoder reranker

**Tên:** `bge-reranker-v2-m3` hoặc reranker multilingual tương đương  
**Nguồn:** FlagEmbedding mô tả reranker nhận query+document và cho relevance score, đồng thời liệt kê model multilingual: [FlagEmbedding reranker](https://github.com/FlagOpen/FlagEmbedding/tree/master/examples/inference/reranker).  
**Giải quyết:** top-k FAQ/policy gần nghĩa còn xếp sai sau hybrid retrieval.  
**Áp dụng vào module:** top 10–20 FAQ/document candidates sau hard filters/RRF.  
**Current problem:** heuristic rerank nhanh nhưng khó xử lý hard negatives semantic.  
**Expected benefit:** có thể tăng Precision@1/nDCG@5.  
**Complexity:** Medium–High.  
**Resource requirement:** thêm model serving, RAM/VRAM, semaphore, timeout/fallback.  
**Recommended:** **LATER**, chỉ khi RRF baseline chưa đạt; không chạy mọi request.

## 10. Parent-child retrieval

**Tên:** Heading-aware Child Retrieval + Parent Context  
**Nguồn:** Information-retrieval pattern; project đã có heading-aware chunks nhưng chưa giữ parent envelope.  
**Giải quyết:** chunk nhỏ retrieve đúng câu nhưng thiếu điều kiện/phần policy cha.  
**Áp dụng vào module:** `document_ingestor.py`, `*:vec:docs`, future document search integration.  
**Current problem:** fixed max chars/overlap, không `parent_id/heading_path/doc_version`; docs search chưa nối chat.  
**Expected benefit:** context đầy đủ hơn, giảm policy answer bị cắt nghĩa.  
**Complexity:** Medium.  
**Resource requirement:** schema/reindex + document golden set.  
**Recommended:** **YES — SHOULD**, sau khi xác nhận document RAG use case.

## 11. Controlled query rewrite

**Tên:** Schema-constrained Query Rewrite  
**Nguồn:** Retrieval technique phổ biến; không có nguồn nào bảo đảm rewrite luôn cải thiện project này.  
**Giải quyết:** typo/slang/elliptical semantic question mà aliases hiện không cover.  
**Áp dụng vào module:** optional NLU planner trước FAQ retrieval.  
**Current problem:** regex/aliases lớn nhưng query rewrite chưa có contract/budget; rewrite có thể làm mất số/phủ định/brand.  
**Expected benefit:** có thể tăng recall cho ambiguous wording.  
**Complexity:** Medium.  
**Resource requirement:** JSON schema, preserve constraints test, cache, timeout.  
**Recommended:** **LATER**, chỉ cho low-confidence semantic query; không rewrite price/SKU constraints.

## 12. Multi-query retrieval

**Tên:** Bounded Multi-query Expansion  
**Nguồn:** Retrieval expansion pattern; applicability phải đo trên golden set.  
**Giải quyết:** một query formulation bỏ sót relevant FAQ.  
**Áp dụng vào module:** semantic FAQ/document path sau query planner.  
**Current problem:** chưa có evidence single-query Recall@K thấp; thêm nhiều query tăng Ollama/embedding/search cost.  
**Expected benefit:** có thể tăng recall cho câu dài/mơ hồ.  
**Complexity:** Medium–High.  
**Resource requirement:** tối đa 2–3 variants, dedupe/fusion, latency budget.  
**Recommended:** **LATER**, không bật mặc định.

## 13. Ragas hoặc semantic evaluator

**Tên:** RAG Quality Metrics as Secondary Evaluation  
**Nguồn:** Ragas liệt kê Context Precision/Recall, Noise Sensitivity, Response Relevancy, Faithfulness và tool accuracy metrics: [Ragas metrics](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/).  
**Giải quyết:** current tests thiên về intent/keywords, chưa đo context relevance/faithfulness.  
**Áp dụng vào module:** offline evaluation/reporting, không nằm trong critical production path.  
**Current problem:** LLM judge có nondeterminism/bias tiếng Việt và không kiểm exact price/URL tốt bằng code.  
**Expected benefit:** bổ sung signal semantic và review failure clusters.  
**Complexity:** Medium.  
**Resource requirement:** pinned judge/prompt/version, stored raw judgments, human sample review.  
**Recommended:** **YES — SHOULD như metric phụ**, không làm gate duy nhất.

## 14. Ollama keep-alive, pooling và backpressure

**Tên:** Bounded Local Inference Serving  
**Nguồn:** Ollama mô tả `keep_alive`, `OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_QUEUE` và 503 khi queue quá tải: [Ollama FAQ](https://docs.ollama.com/faq).  
**Giải quyết:** cold start, new HTTP client mỗi embed, unmeasured concurrency và request queue.  
**Áp dụng vào module:** `embedder.py`, `ai_engine.py`, FastAPI lifecycle/startup, runtime config.  
**Current problem:** shared hardware cho embedding/generation; parallelism tăng theo context memory; chưa p95/load data.  
**Expected benefit:** giảm connection/cold-start overhead, overload có kiểm soát.  
**Complexity:** Medium.  
**Resource requirement:** shared `httpx.AsyncClient`, separate semaphore, warm-up, load/soak test.  
**Recommended:** **YES — MUST đo rồi cấu hình**, không tăng parallel theo cảm tính.

## 15. Durable learning stream

**Tên:** Redis Stream/Consumer Group với Ack + Idempotent Export  
**Nguồn:** Reliable queue pattern; thay cho pop-before-write hiện tại.  
**Giải quyết:** chatbot chưa enqueue end-to-end; exporter crash có thể mất event, retry có thể duplicate Sheet row.  
**Áp dụng vào module:** chat fallback/validator, n8n learning exporters, review Sheet.  
**Current problem:** Redis list `POP → append → requeue on explicit error` không giữ pending ownership.  
**Expected benefit:** zero lost event trong failure test, retry/approval trace được.  
**Complexity:** Medium.  
**Resource requirement:** event ID, consumer group/pending reclaim, Sheet idempotent key.  
**Recommended:** **YES — SHOULD/P3**.

## 16. GraphRAG

**Tên:** Knowledge Graph-based RAG  
**Nguồn:** [Microsoft GraphRAG](https://github.com/microsoft/graphrag) tập trung trích xuất structured graph từ unstructured text và cảnh báo indexing có thể tốn tài nguyên.  
**Giải quyết:** multi-hop/global questions trên corpus lớn có quan hệ phong phú.  
**Áp dụng vào module:** không có module phù hợp được chứng minh trong scope hiện tại.  
**Current problem:** FAQ/product/policy nhỏ, single-hop; blockers là grounding/schema/auth/state, không phải graph reasoning.  
**Expected benefit:** chưa có measurable benefit cho ZeO/CFC hiện tại.  
**Complexity:** High.  
**Resource requirement:** entity/relation extraction, graph store, index cost, evaluation mới.  
**Recommended:** **NO — NOT NEEDED**.

## 17. Full agentic RAG

**Tên:** Autonomous plan/retrieve/retry/tool loop  
**Nguồn:** OWASP cảnh báo excessive functionality/permissions/autonomy làm tăng excessive agency risk: [Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/).  
**Giải quyết:** complex open-ended multi-step task.  
**Áp dụng vào module:** không áp dụng cho customer reply; optional admin task chỉ sau auth/human approval.  
**Current problem:** customer intents/tools đã rõ, trong khi admin tool surface đang quá mạnh.  
**Expected benefit:** thấp cho FAQ/product CSKH; tăng nondeterminism và latency.  
**Complexity:** High.  
**Resource requirement:** policy engine, sandbox, approvals, durable state, extensive red-team tests.  
**Recommended:** **NO cho customer pipeline; LATER cho một số admin workflow đã khóa quyền**.

## 18. LangChain/LangGraph migration

**Tên:** Agent orchestration framework migration  
**Nguồn:** [LangChain](https://docs.langchain.com/oss/python/langchain/overview) cung cấp agent harness; [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) cung cấp stateful/durable orchestration.  
**Giải quyết:** workflow dài, pause/resume, human-in-loop phức tạp.  
**Áp dụng vào module:** có thể thử cho future admin workflow, không phải chat pipeline hiện tại.  
**Current problem:** framework không tự sửa source provenance, claim validation, catalog schema hay Redis races.  
**Expected benefit:** không rõ và migration cost cao cho current request path.  
**Complexity:** High.  
**Resource requirement:** dependency/migration/observability/retraining team.  
**Recommended:** **NO hiện tại**.

## 19. Vector database mới

**Tên:** Qdrant/Milvus/Weaviate hoặc dịch vụ vector khác  
**Nguồn:** Không có benchmark/source-project evidence cho thấy Redis hiện thiếu capacity cần thiết.  
**Giải quyết:** scale/feature gap rất lớn nếu thực sự xuất hiện.  
**Áp dụng vào module:** không đề xuất.  
**Current problem:** corpus FAQ dưới 100 records và Redis đang phục vụ state/snapshot/search; lỗi hiện tại thuộc schema/grounding/evaluation.  
**Expected benefit:** gần như không có ở quy mô hiện tại; tăng vận hành/consistency boundary.  
**Complexity:** High.  
**Resource requirement:** service mới, migration, backup, monitoring và dual-write.  
**Recommended:** **NO — NOT NEEDED**.

## 20. Đổi embedding hoặc chat model

**Tên:** Model A/B Migration  
**Nguồn:** BGE-M3 đã là multilingual dense baseline có cơ sở paper; model mới phải được so trên data nội bộ.  
**Giải quyết:** chỉ khi benchmark chứng minh retrieval/NLU hiện tại là bottleneck model-specific.  
**Áp dụng vào module:** `embedder.py`, index rebuild, planner/synthesizer.  
**Current problem:** chưa có Recall/MRR/faithfulness/p95 baseline đủ mạnh để kết luận model yếu.  
**Expected benefit:** chưa biết.  
**Complexity:** Medium–High.  
**Resource requirement:** pinned model, rebuild index, threshold calibration, A/B hardware benchmark.  
**Recommended:** **LATER; không thay trước golden set**.

## Thứ tự áp dụng

```text
1. Auth/RBAC + least privilege
2. Canonical schema + audience filters + atomic publication
3. FactEnvelope + deterministic validator
4. Idempotency/versioned state
5. Golden retrieval/grounding/performance baseline
6. Application-side RRF shadow experiment
7. Reranker/query rewrite/parent-child chỉ theo failure evidence
```

Nếu một kỹ thuật không vượt quality gate hoặc làm p95/resource vượt budget, loại khỏi target architecture thay vì giữ vì đã đầu tư prototype.
