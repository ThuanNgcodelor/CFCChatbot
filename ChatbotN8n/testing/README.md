# Chatbot Test Cases

Brand-specific JSONL test files split from `../evals/vietnamese_chatbot_eval_cases.jsonl`.

- `zeo_chatbot_test_cases.jsonl`: ZeO cases, including FAQ, lead capture, profile memory, and guardrail cases.
- `cfc_chatbot_test_cases.jsonl`: CFC cases, including FAQ, dealer/lead capture, profile memory, and guardrail cases.
- `facebook_live_test_zeo.md`: Manual Facebook Page test script for ZeO after deployment.
- `facebook_live_test_cfc.md`: Manual Facebook Page test script for CFC after deployment.

Validate with:

```bash
python3 ../../.agents/skills/vietnamese-chatbot-nlu-evals/scripts/check_eval_cases.py zeo_chatbot_test_cases.jsonl
python3 ../../.agents/skills/vietnamese-chatbot-nlu-evals/scripts/check_eval_cases.py cfc_chatbot_test_cases.jsonl
```
