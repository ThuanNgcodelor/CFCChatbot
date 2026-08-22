# Nghiên cứu AI/RAG áp dụng cho chatbot ZeO/CFC

Ngày nghiên cứu: 2026-08-22  
Phạm vi: retrieval, reranking, evaluation, Ollama vận hành cục bộ và an toàn cho FastAPI/admin.  
Mục tiêu: chọn kỹ thuật giải quyết vấn đề đã thấy trong source; không chọn công nghệ vì độ phổ biến.

## 1. Cách đọc tài liệu

Tài liệu tách hai loại nhận định:

- **FACT — nguồn ngoài**: nội dung được paper hoặc tài liệu chính thức mô tả. FACT không tự động chứng minh kỹ thuật sẽ tốt trên dữ liệu tiếng Việt của ZeO/CFC.
- **PROJECT INFERENCE — suy luận cho dự án**: kết luận dựa trên FACT và hiện trạng source/runtime đã audit. Mọi thay đổi chất lượng retrieval vẫn phải qua benchmark local trước khi rollout.

Các mốc hiện trạng dùng để suy luận:

- Pipeline hiện là deterministic-first, lexical-first và Redis KNN fallback; chưa hợp nhất hai rank list bằng RRF: `docs/02_RAG_AUDIT.md`, mục 4–5.
- FAQ runtime local tại ngày audit có 65 record ZeO và 19 record CFC; catalog ZeO có 52 sản phẩm: `01_TONG_HOP_HE_THONG_CHATBOT_ZEO_CFC_HIEN_HANH.md:187-205`.
- Embedding hiện tại là `bge-m3`, dimension 1.024 và gọi qua Ollama: `01_TONG_HOP_HE_THONG_CHATBOT_ZEO_CFC_HIEN_HANH.md:406-425`.
- Ollama planner mặc định `off`; synthesizer chưa có output validator đầy đủ: `01_TONG_HOP_HE_THONG_CHATBOT_ZEO_CFC_HIEN_HANH.md:628-640`.
- `/admin/*` chưa có authentication, CORS cho phép `*`, trong khi assistant có tool shell/workflow: `01_TONG_HOP_HE_THONG_CHATBOT_ZEO_CFC_HIEN_HANH.md:1039-1056`.

## 2. Kết luận nghiên cứu

| Hạng mục | Applicability | Impact kỳ vọng | Effort/tài nguyên | Rủi ro chính | Quyết định |
|---|---|---|---|---|---|
| Giữ `bge-m3` làm dense baseline | Cao | Giữ ổn định, tránh migration chưa có bằng chứng | Thấp; model đã có | Ngộ nhận benchmark công bố đồng nghĩa chất lượng tiếng Việt ZeO/CFC | Giữ; benchmark trước khi thay |
| Metadata filtering + structured lookup | Rất cao | Chặn sai brand/category/price/stock | Trung bình; cần schema/version thống nhất | Filter thiếu field hoặc schema lệch | Ưu tiên trước model mới |
| Lexical + dense + application-side RRF | Cao nhưng có điều kiện | Có thể tăng Recall@K cho exact term và paraphrase | Trung bình; chưa cần thêm dịch vụ | Thêm độ phức tạp mà không tăng metric | Shadow experiment |
| Redis `FT.HYBRID` | Có điều kiện | Đơn giản hóa hybrid query trong Redis | Trung bình; yêu cầu Redis Open Source 8.4+ và client phù hợp | Không tương thích runtime/deploy hiện tại | Chỉ thử sau version gate |
| Cross-encoder reranker | Có điều kiện | Có thể giảm top-k nhiễu cho FAQ/policy gần nghĩa | Trung bình–cao; thêm model và inference mỗi candidate | Tăng p95, RAM/VRAM; rerank nhầm hard constraint | Chỉ thử sau RRF baseline |
| Ragas | Trung bình | Thêm góc nhìn context/faithfulness/relevance | Trung bình; một số metric cần LLM judge | Nondeterminism, chi phí, bias tiếng Việt | Metric phụ, không làm gate duy nhất |
| Ollama keep-alive/backpressure/capacity test | Cao | Giảm cold start và xác định ngưỡng tải an toàn | Thấp–trung bình; cần load test thật | Tăng parallel gây thiếu RAM/VRAM | Đo rồi mới chỉnh |
| Claim validator + security boundary | Rất cao | Giảm unsupported claim, prompt injection và quyền quá mức | Trung bình–cao | False reject; cấu hình auth sai | Bắt buộc trước khi mở rộng agent/tool |
| GraphRAG, full agentic RAG, vector DB mới | Thấp ở quy mô hiện tại | Chưa có lợi ích được benchmark | Cao | Over-engineering, tăng bề mặt lỗi | Chưa cần |

`Impact kỳ vọng` trong bảng là giả thuyết kỹ thuật, không phải kết quả đã đo.

## 3. BGE-M3: baseline phù hợp, chưa có lý do thay model

### FACT — nguồn ngoài

[BGE-M3 paper](https://arxiv.org/abs/2402.03216) mô tả model hỗ trợ hơn 100 ngôn ngữ, ba chế độ dense/sparse/multi-vector và input tới 8.192 token. Kết quả tốt được báo cáo trên các benchmark multilingual, cross-lingual và long-document của paper.

[FlagEmbedding repository](https://github.com/FlagOpen/FlagEmbedding) cũng liệt kê `bge-m3` là model multilingual, có dense, sparse và multi-vector retrieval.

### PROJECT INFERENCE

- Việc paper hỗ trợ nhiều ngôn ngữ không chứng minh Recall@K trên typo, tiếng Việt không dấu, tên ZeO/PANO/Oplus hoặc policy của dự án.
- Project hiện dùng output dense qua Ollama. Khả năng sparse/multi-vector của họ model không đồng nghĩa pipeline hiện đã sử dụng hai chế độ đó.
- Corpus FAQ hiện nhỏ. Chất lượng nhiều khả năng phụ thuộc schema, negative examples, audience filter, entity/brand filter và evaluation nhiều hơn việc đổi model ngay.

### Applicability, impact, resource và risk

- **Applicability:** cao cho semantic FAQ và policy; thấp cho price/stock/SKU vì các field đó phải lookup deterministic.
- **Impact:** giữ model giúp tạo baseline ổn định; chưa thể gán mức tăng accuracy cho model khác khi chưa có A/B test.
- **Resource:** không thêm model mới. Việc kích hoạt sparse/multi-vector qua FlagEmbedding sẽ cần thêm đường inference/index và vận hành ngoài API dense hiện tại.
- **Risk:** thay model làm đổi dimension, phải rebuild index, có thể tăng latency/RAM và làm threshold cũ mất hiệu lực.

### Gate quyết định

Chỉ A/B model khi có tập retrieval có `expected_document_ids`, hard negatives ZeO/CFC, typo/không dấu/SKU và báo cáo ít nhất Recall@1/5, MRR, p95, RAM/VRAM. Model mới phải thắng baseline có ý nghĩa và không làm tăng `unsupported_claim_rate`.

## 4. Redis vector search và metadata filtering

### FACT — nguồn ngoài

[Redis vector search documentation](https://redis.io/docs/latest/develop/ai/search-and-query/vectors/) cho biết vector search có thể kết hợp filter text, numeric, geospatial và tag metadata. Redis hỗ trợ KNN, range query và metadata filter. Tài liệu khuyến nghị `FLAT` cho tập nhỏ dưới một triệu vector hoặc khi ưu tiên độ chính xác tuyệt đối; `HNSW` phù hợp tập lớn hơn hoặc khi scalability/latency quan trọng hơn perfect accuracy.

### PROJECT INFERENCE

- Với dưới 100 FAQ runtime và 52 sản phẩm ở snapshot audit, thay Redis bằng vector database khác không có bằng chứng về scale hay feature gap.
- Typed metadata quan trọng hơn ANN phức tạp: `brand`, `audience`, `category`, `risk_level`, `active`, `source_version`, `in_stock`, `price_current`, `product_id` phải được validate/filter trước khi xếp hạng.
- Current product matcher bằng Python vẫn đúng hướng cho giá, tồn kho, comparator và rank; không nên chuyển những điều kiện này thành semantic text.
- Có thể benchmark `FLAT` với HNSW cho FAQ nhỏ, nhưng không cần migration chỉ vì tài liệu gợi ý FLAT; lợi ích vận hành ở quy mô này có thể không đáng thay đổi index đang chạy.

### Applicability, impact, resource và risk

- **Applicability:** rất cao cho chống lẫn brand/audience/category và range violation.
- **Impact:** filter đúng có thể loại hẳn candidate không hợp lệ, khác với reranker chỉ hạ điểm.
- **Resource:** schema/index migration, validation dữ liệu và rebuild staging index; không cần service mới.
- **Risk:** schema producer/consumer đang lệch thì filter có thể bỏ sạch kết quả hoặc để lọt row không mong muốn.

### Gate quyết định

Trước khi publish index mới: validate schema, minimum-row threshold, duplicate ID/intent, audience allowlist, source version; chạy smoke query; sau đó mới atomic switch active index/cache.

## 5. Hybrid retrieval và Reciprocal Rank Fusion

### FACT — nguồn ngoài

[RRF paper của Cormack, Clarke và Büttcher](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf) đề xuất hợp nhất nhiều danh sách xếp hạng bằng tổng điểm theo hạng, thường biểu diễn là `1 / (k + rank)`. Paper báo cáo RRF cải thiện kết quả trên các collection được thử nghiệm; đó không phải bảo đảm cho mọi corpus.

[Redis `FT.HYBRID` documentation](https://redis.io/docs/latest/commands/ft.hybrid/) cho biết lệnh kết hợp full-text và vector search, hỗ trợ RRF hoặc linear fusion. Lệnh có từ **Redis Open Source 8.4.0**; RRF là mặc định, còn text scorer mặc định là BM25STD.

### PROJECT INFERENCE

- Current lexical và vector search có tín hiệu bổ sung, nhưng pipeline đang lexical early-return hoặc vector + heuristic; chưa có hai rank list độc lập được fusion.
- RRF phù hợp để thử trước weighted sum vì không cần calibrate lexical score và cosine score về cùng thang. Tuy nhiên tham số và top-k vẫn phải benchmark.
- Application-side RRF là thử nghiệm ít phụ thuộc hạ tầng nhất: giữ Redis KNN hiện tại, tạo lexical rank list riêng, fusion trong Python và chạy shadow.
- Không được chạy hybrid retrieval cho exact product ID, price, stock, link hoặc fast-path rõ ràng.

### Applicability, impact, resource và risk

- **Applicability:** cao cho semantic FAQ/policy có paraphrase, entity hoặc từ khóa chính xác; thấp cho dữ liệu cấu trúc.
- **Impact:** có thể tăng Recall@5/MRR khi lexical và dense tìm đúng ở các query khác nhau. Chưa có số tăng thực tế.
- **Resource:** application-side RRF ở mức trung bình; `FT.HYBRID` cần Redis 8.4+, index text/vector đúng schema và client/runtime tương thích.
- **Risk:** fusion kéo candidate lexical nhiễu lên cao, tăng latency và làm fixed threshold cũ không còn ý nghĩa.

### Gate quyết định

1. Xác nhận version bằng runtime thật; không suy ra từ tài liệu hay image tag.
2. Đo lexical-only, dense-only, current pipeline và RRF cùng một golden set.
3. Chỉ rollout nếu Recall@5/MRR tăng, brand/audience violation bằng 0 và p95 nằm trong latency budget.
4. Nếu runtime thấp hơn Redis 8.4, giữ application-side RRF; không nâng Redis chỉ để có một lệnh mới.

## 6. Cross-encoder reranker

### FACT — nguồn ngoài

[FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding) khuyến nghị dùng/fine-tune cross-encoder reranker để rerank top-k document từ embedding retrieval. Repository liệt kê `bge-reranker-v2-m3` là multilingual cross-encoder.

### PROJECT INFERENCE

- Project đã có heuristic rerank nhanh và explainable. Cross-encoder chỉ nên bổ sung relevance cho FAQ/document candidates mà lexical+dense chưa xếp đúng.
- Hard filter `brand`, `audience`, `active`, `category`, price/stock và safety phải chạy trước reranker; model không được “cứu” một candidate bị loại vì business constraint.
- Với corpus nhỏ, reranker có thể chỉ thêm p95 và model memory mà không cải thiện top-1. Cần benchmark trước khi đưa vào request path.

### Applicability, impact, resource và risk

- **Applicability:** trung bình cho FAQ/policy gần nghĩa và hard negatives; không áp dụng cho deterministic tool.
- **Impact:** giả thuyết là Precision@1/nDCG tốt hơn sau retrieval top 10–20.
- **Resource:** thêm model, RAM/VRAM, dependency/serving path và compute theo số candidate. Không nên ghi con số phần cứng trước khi đo model thực tế.
- **Risk:** p95 tăng, contention với model chat/embedding trên Ollama hoặc GPU local, confidence khó calibrate.

### Gate quyết định

Thử shadow với top 10–20, giữ 3–5; so current heuristic, RRF và RRF + reranker. Chỉ bật cho intent retrieval có lợi ích đo được. Có timeout riêng và fallback về rank deterministic/RRF.

## 7. Ragas và chiến lược evaluation

### FACT — nguồn ngoài

[Ragas metrics documentation](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/) liệt kê Context Precision, Context Recall, Context Entities Recall, Noise Sensitivity, Response Relevancy và Faithfulness cho RAG; với tool/agent có Tool Call Accuracy và Tool Call F1. Tài liệu cũng nói metric dựa trên LLM có thể cần một hoặc nhiều LLM call.

### PROJECT INFERENCE

- Ragas hữu ích để phát hiện context nhiễu, answer không bám context hoặc tool selection kém, nhưng không thay được test nghiệp vụ deterministic.
- Giá, link, product ID, brand, stock, source version và “must not say” nên được chấm bằng exact assertions; không giao cho LLM judge.
- Với tiếng Việt, judge model/prompt có thể tạo bias và nondeterminism. Cần pin model/prompt/version, lưu raw judgments và lấy mẫu review tay.

### Applicability, impact, resource và risk

- **Applicability:** trung bình, làm lớp metric phụ cho RAG/generation.
- **Impact:** mở rộng góc nhìn ngoài intent pass/fail; không tự sửa retrieval.
- **Resource:** xây evaluation records có expected docs/facts, chạy judge model và lưu version/cost/latency.
- **Risk:** score biến động, test “đẹp” nhưng bỏ sót lỗi giá/link; phụ thuộc provider/judge.

### Gate quyết định

Evaluation tối thiểu phải có hai tầng:

1. **Deterministic gate:** expected intent/tool/document/fact, range violation, privacy, unsupported price/link/stock, latency.
2. **Semantic review:** context precision/recall, faithfulness, response relevancy bằng Ragas hoặc rubric tương đương; không là gate duy nhất.

## 8. Ollama local: capacity phải đo, không chỉnh theo cảm tính

### FACT — nguồn ngoài

[Ollama FAQ](https://docs.ollama.com/faq) nêu:

- model mặc định được giữ trong memory 5 phút; có thể điều chỉnh bằng `keep_alive` hoặc `OLLAMA_KEEP_ALIVE`;
- khi queue quá tải, server có thể trả HTTP 503; `OLLAMA_MAX_QUEUE` điều chỉnh giới hạn queue;
- `OLLAMA_NUM_PARALLEL` mặc định là 1 và RAM cần thiết tăng theo parallelism nhân context length;
- nếu thiếu memory, request/model mới được xếp hàng cho đến khi có chỗ.

### PROJECT INFERENCE

- Tăng `OLLAMA_NUM_PARALLEL` không mặc định làm hệ thống nhanh hơn; nó có thể làm tăng memory và contention.
- Planner, synthesizer, embedding và reranker dùng chung local inference cần budget riêng. Không nên để một nhánh rewrite chậm chặn deterministic reply đã có fact.
- Model warm-up/keep-alive có thể giảm cold start, nhưng cần đo idle memory và thời gian load model trước khi giữ model vô hạn.

### Applicability, impact, resource và risk

- **Applicability:** cao cho reliability và p95/p99.
- **Impact:** giảm cold-start variance và biến overload thành fallback có kiểm soát.
- **Resource:** load test, metrics queue/503/model-load, timeout/semaphore/backpressure trong app.
- **Risk:** queue quá dài làm response hết giá trị; retry đồng loạt gây thundering herd; keep-alive chiếm memory cho model không dùng.

### Gate quyết định

Chạy load test 1/2/4 concurrent conversations với payload thật; ghi p50/p95/p99, 503, memory, model load time và tỷ lệ deterministic fallback. Chọn concurrency theo dữ liệu, đặt timeout và bounded queue; không retry vô hạn.

## 9. Prompt injection, sensitive data và excessive agency

### FACT — nguồn ngoài

[OWASP LLM01 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) nói RAG và fine-tuning không loại bỏ hoàn toàn prompt injection. Mitigation gồm giới hạn model, validate output bằng code deterministic, filter input/output, least privilege, human approval cho hành động rủi ro, tách untrusted content và adversarial testing.

[OWASP LLM02 Sensitive Information Disclosure](https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/) đề xuất data sanitization, strict input validation, least-privilege access, giới hạn data source, tokenization/redaction và policy retention rõ ràng.

[OWASP LLM06 Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) xác định ba gốc rủi ro là excessive functionality, permissions và autonomy; tài liệu khuyên tránh tool mở như chạy shell, thu hẹp function/permission, thực thi theo scope người dùng và phê duyệt hành động tác động cao.

### PROJECT INFERENCE

- Sheet, CSV, uploaded Markdown và catalog phải được coi là untrusted content. Nội dung “ignore rules” trong knowledge không được trở thành instruction cho model.
- Public chatbot chỉ được đọc data public/customer và state gắn đúng `sender_id`; không được dùng admin/CRM tool.
- Admin assistant hiện có tool shell/workflow trong khi `/admin/*` chưa auth là rủi ro ưu tiên cao hơn việc thêm Agentic RAG.
- System prompt “không bịa” là cần nhưng không đủ; output price/link/stock/safety phải validate với fact envelope/source version.

### Applicability, impact, resource và risk

- **Applicability:** bắt buộc cho cả customer pipeline và admin surface.
- **Impact:** giảm khả năng lộ PII/secret, chạy lệnh hoặc phát unsupported claim khi model bị thao túng.
- **Resource:** auth/RBAC, allowlisted tools, validator, redaction, audit log, adversarial suite.
- **Risk:** guard quá rộng gây false positive; vì vậy enforce theo data/action boundary thay vì chặn câu tự nhiên quá mạnh.

### Gate quyết định

Không public admin/API qua tunnel và không mở rộng autonomous tool trước khi có authentication, authorization, origin allowlist, rate limit, audit log và approval cho mutation. Customer answer có unsupported critical claim phải bị reject/fallback.

## 10. FastAPI authentication, JWT và scopes

### FACT — nguồn ngoài

[FastAPI OAuth2/JWT tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) minh họa Bearer token, password hashing, JWT expiration và dependency lấy current user. Tài liệu cũng chỉ đến OAuth2 scopes để triển khai quyền chi tiết. FastAPI cung cấp primitive; ứng dụng vẫn phải tự chọn identity store, key management, revocation và deployment boundary phù hợp.

### PROJECT INFERENCE

- `/admin/*` cần authentication và authorization. OAuth2/JWT là một lựa chọn phù hợp nếu có nhiều operator/API client; reverse-proxy SSO hoặc session secure có thể đơn giản hơn nếu chỉ có một admin nội bộ.
- Tách scope tối thiểu: `admin:read`, `admin:write`, `knowledge:sync`, `workflow:toggle`, `workflow:deploy`, `assistant:tool`. Read-only token không được gọi mutation.
- JWT không sửa CORS, CSRF, secret storage hoặc downstream privilege. Cần origin allowlist, HTTPS, short expiry/rotation, audit log và server-side authorization từng endpoint.

### Applicability, impact, resource và risk

- **Applicability:** bắt buộc nếu dashboard/API admin có thể được truy cập ngoài localhost.
- **Impact:** đóng bề mặt truy cập CRM, settings, sync và workflow control.
- **Resource:** identity/secret design, dependency bảo vệ route, scope mapping và security tests.
- **Risk:** tự viết auth sai, token sống quá lâu, JWT secret lưu trong source, chỉ ẩn UI nhưng không bảo vệ API.

### Gate quyết định

Test bắt buộc: unauthenticated = 401, wrong scope = 403, expired/invalid token = 401, read-only không mutation, WebSocket/file-watch cũng được bảo vệ, CORS chỉ cho origin đã duyệt.

## 11. GraphRAG và framework agent: kết quả nghiên cứu âm cũng có giá trị

### FACT — nguồn ngoài

[Microsoft GraphRAG repository](https://github.com/microsoft/graphrag) mô tả pipeline trích xuất structured data từ unstructured text bằng LLM, cảnh báo indexing có thể đắt, và hiện ghi dự án ở maintenance mode. Repository cũng nói code là demonstration, không phải Microsoft offering được support chính thức.

[LangGraph documentation](https://docs.langchain.com/oss/python/langgraph/overview) mô tả framework orchestration low-level cho long-running, stateful agent, có durable execution và human-in-the-loop. [LangChain documentation](https://docs.langchain.com/oss/python/langchain/overview) mô tả agent harness kết hợp model, tools, prompt và middleware.

### PROJECT INFERENCE

- FAQ/product/policy hiện là record cấu trúc nhỏ, câu hỏi chủ yếu cần exact lookup, filter, single-hop retrieval và memory theo lượt. Chưa có golden set yêu cầu multi-hop traversal qua đồ thị; GraphRAG không giải quyết lỗi grounding/schema/auth hiện tại.
- Customer pipeline hiện có deterministic router và controlled planner. Di chuyển sang LangChain/LangGraph không tự tăng retrieval accuracy hoặc grounding, nhưng làm tăng dependency và migration surface.
- LangGraph chỉ đáng thử sau này cho admin workflow dài có pause/resume và human approval; không phải lý do rewrite chat pipeline hiện tại.

### Quyết định

- GraphRAG: **không cần ở giai đoạn hiện tại**.
- Full agentic RAG cho public chatbot: **không cần**; giữ planner/tool có allowlist và validator.
- LangChain rewrite: **không cần**.
- LangGraph: **có thể thử giới hạn cho admin approval workflow nếu xuất hiện requirement durable execution**.
- Vector database mới: **không cần khi chưa có benchmark chứng minh Redis thiếu scale, filter, isolation hoặc vận hành**.

## 12. Kế hoạch thử nghiệm theo thứ tự ít rủi ro

### Experiment A — Retrieval baseline

- Tạo golden set từ chat thật: exact FAQ, paraphrase, typo, không dấu, entity/SKU, policy hard negative, ZeO/CFC negative.
- Gắn `expected_document_ids`, `expected_facts`, `must_not_say`.
- Đo lexical-only, dense-only và current routed pipeline: Recall@1/5, MRR, nDCG@5, fallback và p95.

**Exit gate:** có báo cáo per-category và danh sách failure cụ thể; chưa cần đổi production.

### Experiment B — Application-side RRF shadow

- Sinh lexical top-k và dense top-k độc lập.
- Fusion RRF sau hard filters; không thay response production.
- Log candidate ranks, selected source, latency và disagreement với current path.

**Exit gate:** metric tăng có ý nghĩa, không có audience/brand violation, p95 trong budget.

### Experiment C — Reranker shadow

- Chỉ chạy với retrieval intent mà Experiment B còn top-k nhiễu.
- Rerank top 10–20, lấy 3–5; timeout riêng và fallback.
- Đo Precision@1/nDCG, p95, memory và concurrency.

**Exit gate:** lợi ích lớn hơn cost; không bật global.

### Experiment D — Redis `FT.HYBRID`

- Kiểm tra runtime Redis, module và client support.
- So kết quả/latency với application-side RRF trên cùng index/data version.
- Không nâng Redis production chỉ để hoàn thành thử nghiệm.

**Exit gate:** Redis >= 8.4, query semantics đã test và đơn giản hóa vận hành rõ ràng.

### Experiment E — Ollama capacity

- Warm/cold run; concurrency 1/2/4; theo dõi queue/503, memory, p50/p95/p99.
- Test planner/synthesizer timeout và deterministic fallback.

**Exit gate:** cấu hình keep-alive/parallel/queue được chọn từ số đo, không từ mặc định cảm tính.

### Experiment F — Security/grounding

- Adversarial input trực tiếp và injection nằm trong Sheet/Markdown.
- Test PII cross-user, prompt/system disclosure, shell/workflow mutation, unsupported price/link/stock/safety.
- Test auth/scope/CORS và audit event.

**Exit gate:** critical actions fail closed; unsupported critical claim bằng 0 trên security golden set.

## 13. Nguồn chính thức/primary

1. [BGE-M3 paper — arXiv:2402.03216](https://arxiv.org/abs/2402.03216)
2. [FlagEmbedding — official repository](https://github.com/FlagOpen/FlagEmbedding)
3. [Redis vector search concepts](https://redis.io/docs/latest/develop/ai/search-and-query/vectors/)
4. [Redis FT.HYBRID command](https://redis.io/docs/latest/commands/ft.hybrid/)
5. [Reciprocal Rank Fusion paper — SIGIR 2009](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf)
6. [Ragas available metrics](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/)
7. [Ollama FAQ](https://docs.ollama.com/faq)
8. [OWASP LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
9. [OWASP LLM02:2025 Sensitive Information Disclosure](https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/)
10. [OWASP LLM06:2025 Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)
11. [FastAPI OAuth2/JWT tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
12. [Microsoft GraphRAG — official repository](https://github.com/microsoft/graphrag)
13. [LangGraph overview — official documentation](https://docs.langchain.com/oss/python/langgraph/overview)
14. [LangChain overview — official documentation](https://docs.langchain.com/oss/python/langchain/overview)

## 14. Kết luận

Nghiên cứu không cho thấy cần thay model, framework hoặc vector database ngay. Thứ tự có lợi nhất là: sửa trust boundary và grounding contract; chuẩn hóa source/schema/version; tạo retrieval golden set; thử application-side RRF ở shadow; chỉ sau đó mới cân nhắc reranker hoặc `FT.HYBRID`. GraphRAG và full agentic architecture không có problem statement đủ mạnh trong quy mô dữ liệu hiện tại.
