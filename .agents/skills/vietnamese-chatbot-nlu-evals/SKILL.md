---
name: vietnamese-chatbot-nlu-evals
description: Improve Vietnamese automated chatbot systems for ZeO/CFC/n8n workflows by auditing FAQ CSVs, natural-language input normalization, no-accent and abbreviation handling, intent routing, RAG thresholds, Ollama rewrite behavior, fallbacks, admin review queues, and eval datasets. Use when the user mentions Vietnamese chatbot quality, Messenger auto replies, ZeO/CFC FAQ CSVs, không dấu, viết tắt, fallback, Ollama, RAG, intent recognition, natural language understanding, or chatbot eval/testing.
---

# Vietnamese Chatbot NLU Evals

Use this skill to make Vietnamese Messenger-style chatbots more robust without losing factual control. Favor measured improvements: expand examples, normalize real chat text, tune routing, and prove changes with eval cases before changing production workflows.

## Core Workflow

1. Map the current bot path before recommending changes.
   - In indexed repos, use CodeGraph first for workflow source.
   - Read the relevant FAQ CSV, knowledge sync workflow, chatbot workflow, and learning queue/export workflow when present.
   - Identify the chain: input filter -> session/context -> knowledge snapshot -> RAG/scoring -> route mode -> rewrite/Ollama -> guardrail -> save/send/review.

2. Build a failure table from real or likely customer messages.
   - Include no-accent text, abbreviations, short fragments, typo variants, follow-ups, phone/location replies, out-of-scope messages, complaints, and prompt-injection attempts.
   - For each case, record expected brand, intent, response mode, escalation behavior, and whether the answer may be rewritten.

3. Diagnose failures in this order.
   - FAQ coverage: missing intent, thin `question_examples`, canonical answer too broad.
   - Normalization: missing aliases/slang, token cleanup, no-accent handling, brand/product synonyms.
   - Retrieval/routing: score thresholds, ambiguity margin, low-risk direct-answer rule, follow-up/session handling.
   - Response shaping: `answer_mode`, Ollama rewrite prompt, guardrail strictness, fallback wording.
   - Observability: learning queue payload, fallback reason, rag score, matched intent, normalized query.

4. Recommend or implement the smallest safe layer.
   - If the user asks for review/planning, do not edit workflow files.
   - If the user asks to implement, start with data/eval changes before broad workflow rewrites.
   - Keep brand knowledge separated: ZeO/PANO/Oplus answers must not leak into CFC, and CFC answers must not leak into ZeO.

5. Validate with eval cases.
   - Use `references/eval-schema.md` for required fields.
   - Seed from `references/seed-cases.jsonl`, then add real failed messages from logs or learning queue.
   - Run `python3 scripts/check_eval_cases.py <cases.jsonl>` to catch malformed cases and coverage gaps.

## Change Guidelines

- Prefer adding realistic `question_examples` over lowering thresholds blindly.
- Treat one-word or two-word messages as ambiguous unless session context makes them clear.
- Use clarification responses for medium confidence when the wrong answer would be costly.
- Let Ollama rewrite only grounded canonical answers; never let it invent product facts, prices, policies, addresses, dosage, distributor data, or medical/agricultural claims.
- Keep fallback messages conversational, not robotic: ask one specific clarifying question when possible.
- Store low-confidence and guardrail-failed examples for review, with enough fields to reproduce the routing decision.

## Resources

- `references/playbook.md`: Detailed NLU/RAG/fallback design checklist for ZeO/CFC.
- `references/eval-schema.md`: JSONL schema and grading expectations.
- `references/seed-cases.jsonl`: Starter Vietnamese chatbot eval cases.
- `scripts/check_eval_cases.py`: Validate eval case shape and print coverage summaries.
