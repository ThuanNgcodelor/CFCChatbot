# Project Agent Instructions

## Project Memory First

For ZeO/CFC chatbot, n8n workflow, Python RAG, Redis, Google Sheet, Ollama, or eval/test tasks, read this file first:

`TONG_HOP_HE_THONG_CHATBOT_ZEO_CFC_HIEN_HANH.md`

Use it as the current project memory to avoid re-reading the whole repository. If the summary conflicts with live code, CSV, workflow files, or Redis behavior, trust the live source and update the summary after the change.

## CodeGraph

This repository has CodeGraph indexes. For code-level exploration, use CodeGraph before broad grep/read loops when available:

- Use `codegraph_explore` through MCP if it is exposed.
- Or use shell: `codegraph explore "<question, symbol, or file>"`

Good queries include:

- `chat_pipeline.py process_chat_pipeline context memory`
- `rag_search.py rerank hybrid search`
- `knowledge_sync.py Redis vector index`
- `zeo_chatbot.workflow.ts webhook flow`

After edits, CodeGraph may lag by about one second. If a stale warning appears, read the edited files directly.

## Living Documentation Update Rule

After any material change, update `TONG_HOP_HE_THONG_CHATBOT_ZEO_CFC_HIEN_HANH.md` before finishing.

Update it when changing:

- System architecture or data flow.
- n8n workflows or webhook behavior.
- Google Sheet/CSV schema, columns, intent conventions, or knowledge sync.
- Redis keys, vector index fields, session/profile/learning queue behavior.
- RAG retrieval, rerank, guardrails, fallback, context memory, or no-hallucination rules.
- Important endpoints, startup/restart commands, or deployment steps.
- Eval/test coverage or known failure cases.

No need to update it for tiny typo fixes, formatting-only edits, or experiments that are not kept.

## Secrets

Never copy real secrets into docs, prompts, commits, or summaries. This includes Redis passwords, n8n tokens, API keys, webhook secrets, and provider credentials. Use placeholders only.

## n8n-As-Code

For files under `ChatbotN8n/`, also follow `ChatbotN8n/AGENTS.md`. In particular, do not hand-edit generated n8n-as-code configuration or secret files.
