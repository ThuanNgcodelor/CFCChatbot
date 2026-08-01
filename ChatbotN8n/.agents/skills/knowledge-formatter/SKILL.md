---
name: knowledge-formatter
description: >
  Use this skill when the user provides a raw document (docx, xlsx, csv, text, markdown, PDF text)
  and wants to convert it into a structured knowledge format (CSV + Markdown) that can be
  uploaded to Google Sheets FAQ tab and used by a RAG chatbot workflow (n8n Basic RAG).
  Triggers on phrases like: "chuyển file này thành KB", "format tài liệu để chatbot đọc",
  "convert docx thành FAQ", "tạo knowledge base từ file", "nạp dữ liệu vào chatbot",
  "học từ file này", "ném file vào để AI đọc", "tạo CSV cho Google Sheets FAQ".
---

# Knowledge Formatter Skill

Skill này dùng để **chuyển đổi tài liệu thô** (Word, Excel, CSV, text, Markdown)
thành **2 output file chuẩn** để nạp vào hệ thống RAG n8n của ZeO:

- `output.csv` → Upload thẳng vào Google Sheets tab **FAQ**
- `output_kb.md` → Lưu trữ, review, và dùng làm nguồn tham chiếu

---

## Bước 1 – Đọc và phân tích tài liệu đầu vào

Khi nhận được file hoặc nội dung thô, hãy đọc và trích xuất:

1. **Thông tin metadata** (nếu có): brand, category, nguồn tài liệu
2. **Các cặp Q&A** (câu hỏi – câu trả lời)
3. **Các chính sách, quy trình, thông tin sản phẩm** có thể chuyển thành Q&A
4. **Tone giọng văn** để giữ nguyên khi viết lại

Nếu tài liệu không có Q&A rõ ràng, hãy **tự suy luận** các câu hỏi khách hàng
thường hỏi dựa trên nội dung (xem ví dụ trong `examples/`).

---

## Bước 2 – Xác định metadata bắt buộc

Hỏi người dùng (hoặc suy luận từ file) các thông tin sau:

| Trường | Bắt buộc | Mô tả | Mặc định |
|---|---|---|---|
| `brand` | ✅ | Tên thương hiệu | `ZeO` |
| `category` | ✅ | Loại nội dung | `faq` |
| `source_id` | ✅ | ID nguồn tài liệu | Tên file gốc |
| `priority` | ❌ | Độ ưu tiên 0-100 | `80` |
| `updated_at` | ❌ | Ngày cập nhật | Ngày hôm nay |

**Giá trị hợp lệ cho `brand`:**
```
ZeO | PANO | Oplus | ZeO/PANO/Oplus | CFC
```

**Giá trị hợp lệ cho `category`:**
```
faq | policy | product | shipping | support | brand | operations
```

---

## Bước 3 – Chuẩn hóa từng knowledge entry

Với mỗi Q&A hoặc thông tin cần lưu, tạo 1 entry theo cấu trúc:

```
active          : TRUE (luôn TRUE với entry mới)
brand           : [brand từ metadata]
category        : [loại phù hợp]
intent          : [snake_case, mô tả ngắn gọn intent, ví dụ: opening_hours, cod_payment]
question_examples: [tối thiểu 3-5 câu; ngăn cách bằng dấu ";"; sát cách khách nói thật]
answer          : [câu trả lời đầy đủ, chính xác, không bịa]
priority        : [0-100, intent quan trọng hơn → priority cao hơn]
source_id       : [tên file gốc hoặc ID được cung cấp]
updated_at      : [YYYY-MM-DD]
```

### Quy tắc viết `question_examples` (RẤT QUAN TRỌNG)

```
✅ PHẢI có ít nhất 3 câu hỏi biến thể
✅ Viết như cách người Việt nhắn tin thật (ngắn, bỏ dấu đôi khi, viết tắt)
✅ Bao gồm cả câu hỏi có "?" và không có "?"
✅ Bao gồm cả câu đầy đủ và câu rút gọn
✅ Ngăn cách bằng dấu ";", KHÔNG có dòng mới

Ví dụ TỐT:
"Có COD không?;Trả tiền mặt được không?;Ship rồi thu tiền không?;Giao hàng thu tiền mặt không?;Đặt hàng trả sau được ko?"

❌ TRÁNH:
"COD"                        ← quá ngắn
"Có thanh toán khi nhận hàng hay không?" ← quá văn vẻ
```

### Quy tắc viết `answer`

```
✅ Viết như nhân viên CSKH thật, xưng "mình"/"bạn"
✅ Đầy đủ, chính xác, không bịa thêm
✅ Ngắn gọn, tự nhiên
✅ Với thông tin nhạy cảm (hoàn tiền, khiếu nại): CHỈ ghi nhận, không hứa hẹn

❌ KHÔNG:
- Bịa giá, số lượng, ngày giờ không có trong tài liệu gốc
- Thêm link, SĐT không được nhắc đến
- Cam kết thời gian xử lý khi không có thông tin
```

### Quy tắc đặt `intent`

```
Format: snake_case, tiếng Anh, mô tả rõ
Ví dụ:
  opening_hours       ← giờ mở cửa
  cod_payment         ← thanh toán COD
  return_policy       ← chính sách đổi trả
  product_ingredients ← thành phần sản phẩm
  shipping_fee        ← phí vận chuyển
  wholesale_dealer    ← đại lý/nhập sỉ
  address             ← địa chỉ công ty
  complaint_handling  ← xử lý khiếu nại
```

---

## Bước 4 – Xuất output.csv

Xuất file CSV với **header dòng đầu tiên** và **mỗi entry 1 dòng**:

```csv
active,brand,category,intent,question_examples,answer,priority,source_id,updated_at
TRUE,ZeO,faq,opening_hours,"Shop mở cửa lúc mấy giờ?;Giờ làm việc?;Shop mở đến mấy giờ?","Dạ shop mở cửa từ 8:00 đến 21:00 mỗi ngày nha bạn.",100,zeo_faq_v1,2026-07-31
```

**Lưu ý CSV:**
- Nếu `answer` hoặc `question_examples` chứa dấu phẩy → bọc trong dấu ngoặc kép `"..."`
- Không có dòng trống ở cuối (ngoại trừ dòng cuối cùng)
- Encoding: UTF-8

---

## Bước 5 – Xuất output_kb.md (tài liệu tham chiếu)

Xuất file Markdown với YAML frontmatter chuẩn để lưu trữ và review:

```markdown
---
source_id: [source_id]
brand: [brand]
category: [category]
dung_cho_chatbot: true
updated_at: [YYYY-MM-DD]
tong_so_intent: [N]
---

# [Tên tài liệu]

> Tài liệu được tạo tự động từ: [tên file gốc]  
> Tổng số intent: [N]  
> Cập nhật: [ngày]

---

## [intent_name]

**priority:** [0-100]  
**category:** [category]

**question_examples:**
- Câu hỏi biến thể 1
- Câu hỏi biến thể 2
- Câu hỏi biến thể 3

**answer:**
Câu trả lời đầy đủ, chính xác.

---

## [intent_name_2]
...
```

---

## Bước 6 – Hướng dẫn upload

Sau khi tạo xong 2 file, luôn cung cấp hướng dẫn ngắn gọn:

```
📋 HƯỚNG DẪN UPLOAD:

1. Mở Google Sheets của dự án
2. Vào tab "FAQ"
3. Xóa toàn bộ nội dung cũ (nếu thay thế) hoặc để nguyên (nếu thêm mới)
4. File → Import → Upload → chọn output.csv
5. Chọn: "Replace current sheet" (nếu thay thế) hoặc "Append to current sheet" (nếu thêm)
6. Chọn separator: Comma (,)
7. Bấm Import
8. Vào n8n → Workflow "Zeo Knowledge Sync Basic" → bấm Execute
9. Kiểm tra tab KnowledgeSnapshot: knowledge_count đã tăng chưa
```

---

## Xử lý các trường hợp đặc biệt

### Tài liệu chứa nội dung nhạy cảm (hoàn tiền, khiếu nại)

- Tạo entry với `category: policy`
- `answer` chỉ ghi nhận, KHÔNG hứa hẹn:
  ```
  "Dạ mình đã ghi nhận thông tin của bạn. Admin sẽ liên hệ để hỗ trợ sớm nhất ạ."
  ```
- Đặt `priority: 50` (thấp hơn FAQ thông thường vì chatbot sẽ fallback)

### Tài liệu về nhiều brand cùng lúc

- Tạo **riêng biệt** từng entry cho từng brand
- Không dùng `brand: ZeO/PANO/Oplus` trừ khi thông tin thật sự áp dụng cho cả 3

### Tài liệu quá dài (>50 Q&A)

- Chia thành nhiều file theo category: `output_faq.csv`, `output_policy.csv`, `output_product.csv`
- Mỗi file upload vào cùng 1 tab FAQ (Append mode)

### Tài liệu không có Q&A rõ ràng (ví dụ: Brand Bible, chính sách nội bộ)

- Đọc toàn bộ → tự đặt câu hỏi khách có thể hỏi
- Xem `examples/brand_bible_to_faq.md` để tham khảo cách chuyển đổi
- Ưu tiên thông tin: địa chỉ, liên hệ, sản phẩm, chính sách, giờ mở cửa

---

## Checklist trước khi xuất file

Trước khi xuất `output.csv`, kiểm tra:

- [ ] Mỗi intent có ít nhất **3 question_examples**
- [ ] Không có `answer` nào bịa thêm thông tin không có trong tài liệu gốc
- [ ] `intent` là snake_case, không trùng lặp
- [ ] `brand` đúng với giá trị hợp lệ
- [ ] `active` tất cả là `TRUE` (trừ khi người dùng yêu cầu tắt)
- [ ] CSV encoding UTF-8, không có ký tự lạ
- [ ] File `.md` có YAML frontmatter hợp lệ

---

## Tham khảo thêm

- Schema chi tiết: `references/faq_schema.md`
- Ví dụ mẫu: `examples/zeo_faq_sample.csv` và `examples/zeo_faq_sample.md`
- Quy tắc RAG scoring: `references/rag_scoring_rules.md`
