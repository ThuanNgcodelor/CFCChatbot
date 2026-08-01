# FAQ Schema – Google Sheets Tab FAQ

Đây là schema chuẩn cho tab **FAQ** trong Google Sheets,
dùng bởi workflow `Zeo Knowledge Sync Basic`.

---

## Cấu trúc cột (A đến I)

| Cột | Header | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|---|
| A | `active` | Boolean | ✅ | `TRUE` = bật, `FALSE` = tắt |
| B | `brand` | Text | ✅ | Tên thương hiệu |
| C | `category` | Text | ✅ | Loại nội dung |
| D | `intent` | Text | ✅ | Tên intent (snake_case) |
| E | `question_examples` | Text | ✅ | Các câu hỏi mẫu, cách nhau bằng `;` |
| F | `answer` | Text | ✅ | Câu trả lời |
| G | `priority` | Number | ❌ | 0-100, mặc định 80 |
| H | `source_id` | Text | ❌ | ID nguồn tài liệu |
| I | `updated_at` | Date | ❌ | YYYY-MM-DD |

---

## Giá trị hợp lệ

### `brand` (phải khớp chính xác để RAG filter đúng)

```
ZeO
PANO
Oplus
ZeO/PANO/Oplus   ← dùng khi thông tin áp dụng cho cả 3 brand
CFC              ← thường bị filter out trong workflow ZeO
```

### `category`

```
faq          ← câu hỏi thường gặp chung
shipping     ← vận chuyển, giao hàng, phí ship
payment      ← thanh toán, COD, chuyển khoản
product      ← thông tin sản phẩm, thành phần, công dụng
policy       ← chính sách đổi trả, bảo hành, khiếu nại
support      ← hỗ trợ, liên hệ, hotline
brand        ← thông tin thương hiệu, USP, xuất xứ
operations   ← địa chỉ, giờ mở cửa, thông tin công ty
wholesale    ← đại lý, nhập sỉ, phân phối
```

### `priority` (quy tắc đặt)

```
100  ← FAQ cốt lõi, hỏi nhiều nhất (giờ mở cửa, giao hàng, mua ở đâu)
90   ← FAQ quan trọng (hỗ trợ, tư vấn, đại lý)
80   ← FAQ thông thường
50   ← Chính sách, thông tin phụ
10   ← Thông tin ít dùng, dễ thay đổi
```

---

## RAG Scoring – Hiểu để viết `question_examples` tốt hơn

Workflow `RAG Tim Kiem` tính điểm theo công thức:

```
Exact substring match (câu hỏi ≈ example)  → +50 điểm
Intent keyword có trong câu hỏi            → +12 điểm
Token overlap với question_examples        → +4 điểm/token
Token overlap với answer                   → +1 điểm/token
Priority bonus                             → +0..1 điểm
```

**Ngưỡng:** `bestScore >= 12` mới gọi AI. Nếu thấp hơn → fallback.

**Kết luận thực hành:**
- 1 question_example khớp gần exact với câu hỏi khách → +50 → đủ gọi AI ngay
- Nhiều token chung nhau → cộng dồn → đủ ngưỡng
- Viết `question_examples` sát cách khách nói thật = tăng điểm nhiều nhất

---

## Workflow connection

```
Tab FAQ (nguồn gốc, người edit)
    ↓ đọc bởi ReadFaqRows (mỗi 30 phút)
NormalizeKnowledge (lọc active, brand, normalize)
    ↓
Tab KnowledgeSnapshot (1 row JSON, được cache)
    ↓ đọc bởi GetKnowledgeSnapshot (mỗi request)
RAG Tim Kiem (tìm top-3)
    ↓
Ollama (generate)
    ↓
Khách hàng nhận trả lời
```
