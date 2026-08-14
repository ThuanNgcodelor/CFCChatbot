# CFC AI Semantic RAG Server

Service Python giúp chatbot ZeO và CFC Cò Bay hiểu ngữ nghĩa tiếng Việt thay vì chỉ đếm từ khoá.

## Kiến trúc

```
n8n Chatbot → POST /search → FastAPI → Ollama (bge-m3 embed) → Redis Vector Search → Trả kết quả
                                      ↓
                            POST /rewrite → Ollama (qwen2.5 rewrite) → Câu trả lời mượt mà
```

## Cài đặt

### Bước 1: Cấu hình Redis password

Mở file `settings.json` và điền password Redis:

```json
{
  "redis": {
    "password": "ĐIỀN_PASSWORD_TỪ_infra/redis/.env"
  }
}
```

### Bước 2: Tạo môi trường Python

```bash
cd ChatbotN8n/javis/server

# Tạo virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Cài packages
pip install -r requirements.txt
```

### Bước 3: Kéo model embedding về Ollama

Model `bge-m3` là mô hình embedding đa ngôn ngữ tốt nhất, hiểu tiếng Việt rất tốt kể cả không dấu.

```bash
ollama pull bge-m3
```

> **Nếu máy yếu RAM:** Dùng model nhẹ hơn `mxbai-embed-large`:
> ```bash
> ollama pull mxbai-embed-large
> ```
> Sau đó sửa `settings.json`: `"embed_model": "mxbai-embed-large"` và `"embed_dim": 1024`

### Bước 4: Chạy server

```bash
cd ChatbotN8n/javis/server
source .venv/bin/activate
python main.py
```

Server chạy tại: `http://localhost:8000`

### Bước 5: Đồng bộ dữ liệu FAQ vào Vector Index

```bash
# Đồng bộ cả ZeO và CFC
curl -X POST "http://localhost:8000/sync?brand=all"

# Hoặc từng brand
curl -X POST "http://localhost:8000/sync?brand=zeo"
curl -X POST "http://localhost:8000/sync?brand=cfc"
```

Quá trình này sẽ tạo embedding cho từng dòng FAQ và lưu vào Redis Vector Index. Chạy mỗi khi cập nhật FAQ mới từ Google Sheets.

---

## Kiểm tra

```bash
# Health check
curl http://localhost:8000/health

# Test tìm kiếm ZeO
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "co ship khong shop", "brand": "zeo"}'

# Test câu không dấu — đây là điểm mạnh chính
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "thom ko ship v", "brand": "zeo"}'

# Test CFC
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "co phan bon npk khong", "brand": "cfc"}'
```

---

## Tích hợp vào n8n

Thêm một node **HTTP Request** vào workflow n8n (sau node Dialogue Manager):

```
Method: POST
URL: http://127.0.0.1:8000/search
Body (JSON):
{
  "query": "{{ $('Loc Dau Vao').first().json.text }}",
  "brand": "zeo",
  "top_k": 5
}
```

Kết quả trả về:
```json
{
  "confidence": "high",
  "score": 0.92,
  "intent": "nationwide_shipping_no_cod",
  "answer": "Dạ ZeO có giao hàng toàn quốc...",
  "answer_mode": "rewrite"
}
```

Nếu `confidence == "high"` hoặc `"medium"` và `answer_mode == "rewrite"` → đẩy qua node `GoiOllamaLocal` để viết lại tự nhiên hơn.

---

## Tóm tắt thay đổi đã làm

### Giai đoạn 1 (đã sửa trong n8n):
- ✅ Fix regex số điện thoại trong `zeo_chatbot.workflow.ts`
- ✅ Fix regex số điện thoại trong `cfc_cobay_chatbot.workflow.ts`
- ✅ Nới lỏng nhận diện địa chỉ (không cần bắt buộc có từ khoá "tỉnh/tp")

### Giai đoạn 2 (Python service này):
- ✅ `embedder.py` — Tạo vector embeddings qua Ollama bge-m3
- ✅ `knowledge_sync.py` — Đọc Redis snapshot → embed → upsert vào Redis Vector Index
- ✅ `rag_search.py` — Semantic search với RediSearch KNN
- ✅ `main.py` — FastAPI với /health, /sync, /search, /rewrite
