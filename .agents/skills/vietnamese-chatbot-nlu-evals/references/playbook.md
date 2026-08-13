# Vietnamese Chatbot NLU Playbook

## 1. Artifact Checklist

Read these before making recommendations:

- FAQ CSVs in `ChatbotN8n/google_upload/`
- Chatbot workflows in `ChatbotN8n/workflows/local-n8n/*chatbot.workflow.ts`
- Knowledge sync workflows in `ChatbotN8n/workflows/local-n8n/*knowledge_sync*.workflow.ts`
- Learning queue or alert workflows if fallback/admin review is involved

Capture the current values for:

- `normalizeForSearch` aliases
- stop words
- intent/example scoring formula
- high/medium/low confidence thresholds
- fallback reasons
- direct/rewrite/review route indexes
- guardrail checks after Ollama

## 2. Input Normalization Targets

Cover these Vietnamese chat patterns:

- No accents: `shop mo cua may gio`, `co ship khong`
- Abbreviations: `k`, `ko`, `kh`, `dc`, `dk`, `sp`, `sdt`, `dt`, `npp`, `cod`
- Chat particles: `v`, `z`, `nha`, `nhe`, `ak`, `ạ`, `shop oi`, `ad oi`
- Short questions: `gia sao`, `ship k`, `mua dau`, `co cod`, `con hang k`
- Typos and spacing: `giaohang`, `webside`, `wed`, `phan bonn`
- Follow-ups: `loai do sao`, `con cai nay`, `vay ship sao`, `co mui nao`
- Lead info: bare phone number, location, province/district, phone plus area

Add aliases only when they improve multiple cases. Avoid aliases that collapse different intents into one token.

## 3. FAQ Coverage Rules

Each public FAQ row should have at least:

- 1 formal Vietnamese question with accents
- 1 no-accent version
- 1 short Messenger-style version
- 1 abbreviation version
- 1 customer-need phrasing
- 1 negative/edge phrasing when relevant

Example for shipping:

`Có giao hàng không?;co ship k;shop co ship ko;giao tan noi duoc khong;ship ve tinh dc k;nhan hang sao`

Keep `answer` canonical and factual. Do not hide uncertain data in `answer`; uncertain cases should route to review or clarification.

## 4. Retrieval And Routing Policy

Use a layered decision:

1. Deterministic guardrails: echo, duplicate, empty, prompt injection, foreign script, sensitive complaint, out-of-scope.
2. Lead capture: phone/location/dealer requests.
3. Forced high-signal intents: website, COD, opening hours, product catalog, dealer request.
4. RAG match with confidence and ambiguity margin.
5. Clarification when intent family is likely but exact intent is ambiguous.
6. Review queue only when the bot lacks safe evidence or the case is risky.

Do not make fallback the default for medium-confidence low-risk questions. A one-question clarification is usually better UX than a generic admin handoff.

## 5. Ollama Rewrite Policy

Use Ollama as a style layer, not a knowledge source.

Safe rewrite conditions:

- A canonical answer exists.
- The matched intent is high confidence or low-risk medium confidence.
- The row has `answer_mode=rewrite` or the workflow explicitly allows rewrite for the category.
- Guardrail compares output against canonical answer and falls back to canonical on fact drift.

Do not rewrite:

- Complaints, refund/return disputes, legal/safety claims
- Missing data cases
- Questions about price, dosage, distributor, warranty, or policy unless the canonical answer explicitly contains the fact

## 6. Eval Metrics

Track at least:

- intent accuracy
- false fallback rate
- wrong-direct-answer rate
- correct escalation rate for risky cases
- clarification quality for ambiguous cases
- brand leakage
- fact drift after rewrite

Prefer improving eval pass rate over subjective tone changes.
