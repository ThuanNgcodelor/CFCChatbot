# Push workflow an toan, giu config tren n8n UI

Dung file nay khi muon day code workflow len n8n ma van giu cac config da gan truc tiep tren UI nhu credential, App credential, Page credential, Telegram chat ID, verify token, webhook subscription.

Luu y quan trong:
- Luon dung repo that: `/Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n`
- Khong dung `/Users/hyden/Documents/N8n/ChatbotN8n` vi thu muc do khong phai repo workflow that.
- Neu muon giu config UI, KHONG tu dong chay `resolve --mode keep-current`.
- `keep-current` = lay file local ghi de UI. Neu local thieu credential/config thi UI se mat config.
- Cach an toan la: luu patch code local -> pull ban moi nhat tu n8n UI -> apply lai patch code -> validate -> push.

## 1. Kiem tra trang thai chung

```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n
npx --yes n8nac list
git status --short
```

## 2. Push ZeO Chatbot, giu config UI

```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n

npx --yes n8nac resolve d7fctbMhVUmhrNG0 --mode keep-current
npx --yes n8nac skills validate workflows/local-n8n/zeo_chatbot.workflow.ts
npx --yes n8nac push workflows/local-n8n/zeo_chatbot.workflow.ts --verify
```

## 3. Push CFC Co Bay Chatbot, giu config UI

```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n

npx --yes n8nac resolve uJOo6NQO2mJZhUAr --mode keep-current
npx --yes n8nac skills validate workflows/local-n8n/cfc_cobay_chatbot.workflow.ts
npx --yes n8nac push workflows/local-n8n/cfc_cobay_chatbot.workflow.ts --verify
```

## 4. Push Telegram Operations Alert, giu config UI

```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n

WF="workflows/local-n8n/chatbot_operations_alert.workflow.ts"
ID="f2IjxVj9sW3KQRAw"
PATCH="/tmp/chatbot_operations_alert.patch"

git diff -- "$WF" > "$PATCH"
npx --yes n8nac pull "$ID"

if [ -s "$PATCH" ]; then
  git apply --3way "$PATCH"
fi

git diff -- "$WF" | rg -n "credentials|facebookGraph|telegram|chatId|webhookId|appId|verify|Verify|SET_TELEGRAM" || true
npx --yes n8nac skills validate "$WF"
npx --yes n8nac push "$WF" --verify
```

## 5. Neu van bi conflict

Neu push bao conflict, uu tien chay lai dung block an toan ben tren cho workflow do.

Chi dung lenh nay khi ban CHAC CHAN muon giu ban tren UI va bo qua local:

```bash
npx --yes n8nac resolve <WORKFLOW_ID> --mode keep-incoming
```

Chi dung lenh nay khi ban CHAC CHAN muon local ghi de UI, ke ca credential/config UI:

```bash
npx --yes n8nac resolve <WORKFLOW_ID> --mode keep-current
```

## 6. Kiem tra sau khi push

```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n
npx --yes n8nac verify d7fctbMhVUmhrNG0
npx --yes n8nac verify uJOo6NQO2mJZhUAr
npx --yes n8nac verify f2IjxVj9sW3KQRAw
```
