# Redis Phase 1

## Muc dich

Redis thay Google Sheets trong duong tra loi cua chatbot. Google Sheets van la noi cap nhat FAQ; workflow dong bo doc FAQ dinh ky va ghi snapshot vao Redis. Chatbot chi doc Redis trong moi tin nhan.

## Khoi dong

1. Cai va mo Docker Desktop tren may dang chay n8n/Ollama.
2. Tao `infra/redis/.env` tu `.env.example`, thay `REDIS_PASSWORD` bang mat khau dai va duy nhat.
3. Chay `docker compose --env-file .env -f infra/redis/docker-compose.yml up -d` tu thu muc `ChatbotN8n`.
4. Kiem tra `docker compose --env-file .env -f infra/redis/docker-compose.yml ps` cho den khi container healthy.
5. Tao credential `Redis` tren n8n ten `Zeo Redis (local)`: host `127.0.0.1`, port `6379`, database `0`, password dung voi `.env`.

Redis chi bind vao `127.0.0.1`, khong mo cong 6379 ra Internet. Container su dung AOF va volume Docker `redis-data` de giu du lieu khi khoi dong lai.

## Cac key phase 1

| Key | Noi dung | TTL |
| --- | --- | --- |
| `zeo:kb:basic:active` | Snapshot FAQ dang phuc vu | Khong het han |
| `zeo:sync:faq:basic:last-success` | Metadata lan dong bo thanh cong gan nhat | Khong het han |
| `zeo:session:messenger:{sender_id}` | Ngu canh mot nguoi dung | 30 phut |
| `zeo:learning:queue` | Cac ca chua tu tin, can nguoi duyet | Khong het han |

## Van hanh an toan

- Khong tu dong dua `zeo:learning:queue` vao FAQ. Admin phai xem, soan cau tra loi, sau do them mot dong FAQ co `question_examples` truoc khi dong bo lai.
- Tin nhan ve doi tra, khieu nai, hang loi, lua dao va ngoai pham vi khong dua vao Ollama. Chung vao hang cho duyet va bot gui phan hoi fallback.
- Khong dua gia, ton kho, ma san pham vao prompt RAG. Khi bo sung du lieu nay, can them key cau truc rieng va router truy van truc tiep truoc khi goi Ollama.
- Phase 1 chua dung vector search. Khi FAQ lon hon hoac nguoi dung viet qua tu do, them embeddings va Redis Search sau khi da co tap du lieu/learning queue duoc duyet.
