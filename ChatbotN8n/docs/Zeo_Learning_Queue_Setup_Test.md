# ZeO Learning Queue: Setup va Test

## Muc dich

`LearningQueue` la noi de chatbot ghi lai nhung tin nhan chua the tra loi an toan hoac tu nhien. Admin xem lai, viet cau tra loi chuan, sau do dua cac cau hoi va cau tra loi da duyet vao tab `FAQ` de chatbot co them kien thuc.

Khong sua hay xoa tab `FAQ` va `KnowledgeSnapshot` hien co.

## Setup Google Sheets

Trong cung file Google Sheets dang co hai tab `FAQ` va `KnowledgeSnapshot`:

1. Bam dau `+` o goc duoi ben trai de tao mot tab moi.
2. Doi ten tab thanh chinh xac: `LearningQueue`.
3. Tai o `A1`, dan dong header sau. Day la 19 cot va ten cot phai giu nguyen.

```tsv
event_id	status	channel	sender_id	message_id	user_message	fallback_reason	rag_score	created_at	admin_answer	question_examples	intent	category	brand	priority	source_id	reviewed_at	notes	queue_payload_raw
```

4. Khong can nhap du lieu mau. Workflow se tu dong them moi dong vao duoi header.

## Y nghia cac cot chinh

| Cot | Su dung |
| --- | --- |
| `status` | Bat dau la `pending`; doi thanh `approved`, `rejected`, hoac `needs_info` khi review. |
| `user_message` | Cau khach da gui. |
| `fallback_reason` | Ly do chatbot khong tu tin tra loi, vi du `ollama_guardrail_failed` hoac `low_confidence`. |
| `rag_score` | Diem tim thay trong FAQ; diem thap thuong can bo sung cau hoi mau. |
| `admin_answer` | Cau tra loi da duyet, viet tu nhien va dung chinh sach. |
| `question_examples` | 4-6 cach khach co the hoi cung mot y, cach nhau bang dau `;`. |
| `intent` | Ten y dinh, vi du `contact_hotline`. |
| `category`, `brand`, `priority` | Metadata de chuyen thanh mot dong FAQ. Mac dinh la `faq`, `ZeO`, `50`. |
| `reviewed_at`, `notes` | Ngay review va ghi chu noi bo. |
| `queue_payload_raw` | Ban ghi goc tu Redis; khong can sua. |

## Test workflow

1. Mo workflow **Zeo Learning Queue Export** trong n8n.
2. Bam **Execute workflow** tu `Manual Trigger`.
3. Neu Redis co event dang cho, node `Append Learning Queue` phai chay mau xanh o nhanh `Success`.
4. Mo tab `LearningQueue`: se co mot dong moi duoi hang header.

Neu Google Sheets gap loi, event se duoc dua lai Redis boi node `Requeue Failed Event`; khong bi mat du lieu.

## Quy trinh hoc du lieu

1. Admin review dong co `status = pending`.
2. Dien `admin_answer`, `question_examples`, `intent` va cac metadata can thiet.
3. Doi `status` thanh `approved`, dien `reviewed_at`.
4. Copy noi dung da duyet thanh mot dong trong tab `FAQ` theo dung 9 cot chuan.
5. Chay workflow **Zeo Knowledge Sync Basic** de cap nhat snapshot Redis.
6. Chatbot se dung FAQ moi o cac tin nhan tiep theo.

Chatbot khong tu dong tu hoc truc tiep tu tin nhan cua khach. Buoc admin duyet giup tranh dua cau tra loi sai, thong tin rieng tu, hoac chinh sach chua duoc xac nhan vao knowledge base.
