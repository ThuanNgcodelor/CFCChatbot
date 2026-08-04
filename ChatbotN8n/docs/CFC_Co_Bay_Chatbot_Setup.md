# CFC Co Bay Chatbot Setup

## Thanh phan da tao

- `cfc_knowledge_sync_basic.workflow.ts`: doc FAQ CFC trong Google Sheet va ghi snapshot Redis `cfc:kb:basic:active`.
- `cfc_cobay_chatbot.workflow.ts`: Messenger chatbot CFC/Cò Bay, RAG tren snapshot CFC va khong dung Learning Queue.
- `google_upload/cfc_faq_google_sheet_to_append.csv`: 7 FAQ dau tien tu tai lieu `CFC Reply.docx`.

Tat ca Redis key cua CFC bat dau bang `cfc:`. Du lieu session va FAQ cua CFC khong dung chung voi ZeO.

## 1. Import FAQ CFC vao Google Sheet

Mo file CSV `cfc_faq_google_sheet_to_append.csv` bang Google Sheets va import thanh mot tab moi trong cung spreadsheet dang dung cho ZeO.

- Trong Google Sheets: **File -> Import -> Upload** -> chon file CSV -> chon **Insert new sheet(s)**.
- Doi ten tab vua tao thanh chinh xac `CFC_FAQ`.
- Giu dong header `active,brand,category,intent,question_examples,answer,priority,source_id,updated_at`.
- Khong sua tab `FAQ` cua ZeO/PANO/Oplus.

Workflow CFC chi doc tab `CFC_FAQ`; du lieu hai brand khong bi tron.

## 2. Warm CFC snapshot

1. Mo workflow **CFC Co Bay Knowledge Sync Basic** trong n8n.
2. Chay `Manual Trigger` mot lan sau khi da them CSV.
3. Kiem tra Redis co hai key:

```redis
GET cfc:sync:faq:basic:last-success
STRLEN cfc:kb:basic:active
```

4. Publish workflow de no sync lai moi 15 phut.

## 3. Tao credential Facebook rieng cho Co Bay

Khong su dung credential `Facebook Graph account` cua ZeO.

Can hai credential moi trong n8n:

1. `Facebook Graph (App) Co Bay`: Meta App ID va App Secret cua app phuc vu Page Co Bay.
2. `Facebook Graph Co Bay`: Page Access Token cua dung Fanpage Co Bay, co quyen gui tin nhan.

Nen dung Meta App rieng cho Co Bay. Meta Webhooks cua mot App co callback chung; tach App tranh viec workflow ZeO va CFC nhan nham su kien Messenger.

## 4. Cau hinh va publish chatbot

Trong workflow **CFC Co Bay Messenger Chatbot Basic RAG**:

1. Node `Messenger Trigger`: chon credential `Facebook Graph (App) Co Bay`, nhap App ID that, giu event `messages`, va dat Verify Token theo Meta App Cò Bay.
2. Node `Nhan Khach Auto`: chon credential `Facebook Graph Co Bay`.
3. Node `Nhan Khach Fallback`: chon credential `Facebook Graph Co Bay`.
4. Trong Meta Developers, dang ky callback URL cua workflow va subscribe Page Co Bay vao event `messages`.
5. Publish workflow, roi gui mot tin Messenger tu Page Co Bay de test.

## Hanh vi chatbot

- Cau hoi khop FAQ CFC: Ollama viet lai cau tra loi dua tren FAQ CFC.
- Cau hoi trong, nhay cam, ngoai pham vi, khong co FAQ, hoac Ollama tra loi khong dat: chatbot gui fallback lich su ngay.
- Khong co Learning Queue va khong tu dong hoc tu tin nhan khach.
- Session CFC ton tai 30 phut o key `cfc:session:messenger:<PSID>`.
