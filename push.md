# Push workflow an toàn, giữ cấu hình trên n8n UI

Các workflow đã được pull từ n8n trước khi sửa nên file local hiện có App ID, credential ID, Page credential, project và workflow ID mới nhất tại thời điểm chỉnh sửa. File giữ nguyên trạng thái `active` theo bản remote để khi bạn push không vô tình unpublish workflow đang chạy.

## Nguyên tắc

- Repo đúng: `/Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n`.
- Không dùng thư mục `/Users/hyden/Documents/N8n/ChatbotN8n`; đó chỉ là bản kiểm thử tạm.
- Không mở và sửa cùng một workflow trên n8n UI trong lúc chuẩn bị push.
- `keep-current` nghĩa là **bản local ghi đè bản UI**.
- `keep-incoming` nghĩa là **lấy bản UI và bỏ thay đổi local**.
- Không dùng lại quy trình `git diff > patch` rồi `git apply --3way` khi index đang khác; đây là nguyên nhân lỗi `does not match index` trước đây.

## 1. Kiểm tra trước khi push

```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n

git status --short
git diff --check

npx --yes n8nac skills validate workflows/local-n8n/zeo_knowledge_sync_basic.workflow.ts
npx --yes n8nac skills validate workflows/local-n8n/cfc_knowledge_sync_basic.workflow.ts
npx --yes n8nac skills validate workflows/local-n8n/zeo_chatbot.workflow.ts
npx --yes n8nac skills validate workflows/local-n8n/cfc_cobay_chatbot.workflow.ts
```

## 2. Đẩy Knowledge trước

```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n

npx --yes n8nac push workflows/local-n8n/zeo_knowledge_sync_basic.workflow.ts --verify
npx --yes n8nac push workflows/local-n8n/cfc_knowledge_sync_basic.workflow.ts --verify
npx --yes n8nac push workflows/local-n8n/zeo_shopee_sync.workflow.ts --verify
```

Nếu CLI báo conflict nhưng từ lúc Codex hoàn tất bạn **không sửa hai workflow này trên UI**, giữ bản local đã kiểm thử:

```bash
npx --yes n8nac resolve DhrLUsDsldhxtTdX --mode keep-current
npx --yes n8nac resolve 92I5floRW5MElgu5 --mode keep-current
```

Sau đó chạy lại hai lệnh `push --verify` ở trên.

Tiếp theo, vào n8n chạy tay `Zeo Knowledge` và `CFC Co Bay Knowledge` một lần. Chỉ tiếp tục khi cả hai execution thành công.

## 3. Kiểm tra Redis đã warm

```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/infra/redis
docker compose exec redis redis-cli -a "$REDIS_PASSWORD"
```

Trong `redis-cli`:

```text
GET zeo:sync:faq:basic:last-success
GET cfc:sync:faq:basic:last-success
STRLEN zeo:kb:basic:active
STRLEN cfc:kb:basic:active
```

Kỳ vọng `knowledge_count` hiện tại: ZeO `47`, CFC `7`. Không cần `FLUSHALL`.

## 4. Đẩy hai Chatbot

```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n

npx --yes n8nac push workflows/local-n8n/zeo_chatbot.workflow.ts --verify
npx --yes n8nac push workflows/local-n8n/cfc_cobay_chatbot.workflow.ts --verify
```

Nếu CLI báo conflict nhưng từ lúc Codex hoàn tất bạn **không sửa hai chatbot trên UI**, giữ bản local đã có credential:

```bash
npx --yes n8nac resolve d7fctbMhVUmhrNG0 --mode keep-current
npx --yes n8nac resolve uJOo6NQO2mJZhUAr --mode keep-current
```

Sau đó chạy lại hai lệnh `push --verify`.

## 5. Khi đã sửa workflow trên UI sau lần Codex hoàn tất

Không dùng `keep-current` ngay. Dừng lại và pull/merge lại thay đổi UI trước; nếu không, credential hoặc node vừa cấu hình trên UI có thể bị ghi đè.

Không dùng `keep-incoming` nếu còn muốn giữ phần code local, vì lệnh đó bỏ thay đổi local của workflow tương ứng.

## 6. Sau khi push

1. Mở từng workflow và kiểm tra credential không có cảnh báo đỏ.
2. Chạy tay hai Knowledge workflow, kiểm tra Redis như bước 3.
3. Publish hai chatbot.
4. Test bằng tài khoản Facebook cá nhân, không dùng chính Page để nhắn.
5. Xem `Executions` để xác nhận đúng workflow nhận đúng Page.

Telegram Operations Alert không thay đổi trong đợt này nên không cần push lại.
