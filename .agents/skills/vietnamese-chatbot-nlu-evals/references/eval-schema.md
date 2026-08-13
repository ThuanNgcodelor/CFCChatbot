# Chatbot Eval Case Schema

Use JSONL: one JSON object per line.

Required fields:

- `id`: stable unique id
- `brand`: `ZeO` or `CFC`
- `message`: raw user message
- `expected_intent`: expected matched intent, or `""` if no intent should be matched
- `expected_mode`: `direct`, `rewrite`, `review`, `clarify`, or `ignore`
- `risk`: `low`, `medium`, or `high`

Recommended fields:

- `expected_category`
- `expected_fallback_reason`
- `context`: previous user/bot text when testing follow-ups
- `notes`: why this case matters

Grading expectations:

- `direct`: bot may answer immediately from canonical knowledge.
- `rewrite`: bot may call Ollama to restyle a canonical answer, then guardrail the result.
- `clarify`: bot should ask one focused question instead of generic fallback.
- `review`: bot should queue/admin handoff or safely acknowledge without inventing facts.
- `ignore`: bot should not send a customer-facing answer.

Minimum coverage targets:

- 20 no-accent cases
- 20 abbreviation/short chat cases
- 10 follow-up/session cases
- 10 lead capture cases
- 10 out-of-scope or cross-brand cases
- 10 sensitive/complaint cases
- 5 prompt-injection or foreign-script cases
