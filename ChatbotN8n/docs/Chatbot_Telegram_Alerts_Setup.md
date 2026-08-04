# Chatbot Telegram Alerts Setup

## Muc dich

Workflow `Chatbot Operations Alert` nhan canh bao tu ZeO va CFC/Cò Bay. No khong gui tat ca cuoc hoi thoai; chi gui cac case chatbot khong the tu tra loi an toan hoac khong qua guardrail.

Redis chong trung trong 15 phut theo brand, loai event, PSID va noi dung cau hoi. Loi Telegram khong duoc phep chan chatbot tra loi khach.

## Tao Telegram bot va group

1. Mo Telegram, chat voi `@BotFather`, dung lenh `/newbot` va luu Bot Token.
2. Tao mot group noi bo, vi du `Chatbot Alerts`.
3. Them bot vao group va cap quyen gui tin nhan.
4. Gui mot tin nhan bat ky trong group.
5. Lay `chat_id` cua group bang mot trong cac cach: dung node Telegram Trigger tam thoi trong n8n, hoac goi Bot API `getUpdates` sau khi gui tin nhan.

## Cau hinh trong n8n

1. Tao credential `Telegram account` trong n8n bang Bot Token, khong dan token vao workflow source.
2. Mo workflow **Chatbot Operations Alert**.
3. Node `Send Telegram Alert`: chon credential `Telegram account`, dien `chat_id` cua group vao truong Chat ID.
4. Chay `Manual Trigger` trong workflow de gui mot alert TEST.
5. Khi group nhan duoc tin, luu/publish workflow.

## Event duoc gui

- `REVIEW`: RAG khong co nguon hoac Ollama khong qua guardrail.
- `URGENT`: fallback co danh dau nhay cam, vi du khieu nai, hang loi, hoan tien.

Noi dung alert chi co brand, loai event, muc uu tien, cau hoi, ly do, diem RAG va thoi gian. PSID khach khong duoc gui day du.
