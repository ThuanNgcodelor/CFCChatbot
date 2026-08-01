# Kế Hoạch Cơ Bản: ZeO Chatbot Dùng Google Drive Và Google Sheets

## Mục Tiêu

Triển khai bản cơ bản trước khi dùng vector DB/RAG nâng cao:

- Lấy tri thức từ 4 file Google Docs/Docx trên Google Drive.
- Lấy Q&A/FAQ từ Google Sheets.
- Gom tất cả thành một Knowledge Base nội bộ.
- Chatbot chỉ trả lời dựa trên Knowledge Base này, không lấy thông tin từ bên ngoài.
- Giữ workflow Messenger hiện tại ổn định, thay phần `Doc Knowledge Base` hardcoded bằng nguồn sync từ Google.

## Nguồn Dữ Liệu Hiện Có

Thư mục local `docx/` chỉ là bản tải về để đọc mẫu và hiểu cấu trúc nội dung. Runtime sau này không đọc file trong thư mục này.

4 file mẫu đang có:

- `Auto reply test.docx`: Q&A ZeO cơ bản như giờ mở cửa, giao hàng, mua hàng, nhập hàng, địa chỉ.
- `CFC Reply.docx`: Q&A CFC/Cò Bay, có nội dung phân bón. Cần tách brand/ngữ cảnh để tránh bot ZeO trả lời nhầm.
- `01_Chính Sách Đổi Trả - CSKH - Xử Lý Khiếu Nại.docx`: chính sách đổi trả, mẫu chăm sóc khách hàng, quy trình khiếu nại.
- `03_Brand Bible - Tone of Voice - Thông Tin Sản Phẩm - USP.docx`: brand bible, tone of voice, thông tin công ty/sản phẩm/USP.

Khi triển khai thật, n8n sẽ lấy trực tiếp 4 file trên Google Drive. Nếu file là Google Docs native, Google Drive node có thể download/export thành `txt`. Nếu file là `.docx`, có thể download binary rồi dùng `Extract from File`, nhưng khuyến nghị convert sang Google Docs native để extract text ổn định hơn.

## Google Sheet Nên Có

Tạo một Google Sheet làm FAQ chính, vì sheet dễ để admin sửa nhanh hơn tài liệu dài.

| active | brand | category | intent | question_examples | answer | priority | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TRUE | ZeO | faq | opening_hours | Shop mở cửa lúc mấy giờ?; Giờ làm việc? | Shop mở cửa từ 8:00 đến 21:00 mỗi ngày. | 100 | 2026-07-30 |

Quy ước:

- `active`: chỉ lấy row TRUE.
- `brand`: `ZeO`, `PANO`, `Oplus`, `CFC`. Chatbot ZeO ưu tiên `ZeO`, `PANO`, `Oplus`; không lấy `CFC` nếu đang trả lời page ZeO.
- `question_examples`: nhiều câu hỏi mẫu, ngăn cách bằng dấu `;`.
- `answer`: câu trả lời chuẩn. Ollama có thể viết lại tự nhiên hơn nhưng không được thêm fact mới.
- `priority`: số càng cao càng ưu tiên khi match trùng nhau.

## Workflow 1: Sync Knowledge Basic

Tên đề xuất: `Zeo Knowledge Sync Basic`

Chạy theo lịch mỗi 15-30 phút hoặc manual khi cần.

Node nên dùng:

1. `Schedule Trigger`
   - Type: `n8n-nodes-base.scheduleTrigger`
   - Version: `1.3`
   - Chạy mỗi 15-30 phút trong giai đoạn đầu.

2. `Google Drive - Download Docs`
   - Type: `n8n-nodes-base.googleDrive`
   - Version: `3`
   - Resource: `file`
   - Operation: `download`
   - Mỗi file Google Docs/Docx có thể dùng một node download, hoặc dùng một Code node tạo danh sách fileId rồi loop.
   - Nếu là Google Docs native: export sang `Text (txt)`.
   - Output binary field: `data`.

3. `Extract from File`
   - Type: `n8n-nodes-base.extractFromFile`
   - Version: `1.1`
   - Operation: `text`
   - Binary property: `data`
   - Destination key: `text`

4. `Google Sheets - Read FAQ`
   - Type: `n8n-nodes-base.googleSheets`
   - Version: `4.7`
   - Resource: `sheet`
   - Operation: `read`
   - Range: ví dụ `FAQ!A:H`

5. `Code - Normalize Knowledge`
   - Parse Q&A trong docs theo mẫu `Q:` / `A:`.
   - Cắt tài liệu dài thành section theo `PHẦN`, heading, hoặc độ dài khoảng 800-1500 ký tự.
   - Gắn metadata:
     - `sourceType`: `sheet` hoặc `doc`
     - `sourceName`
     - `brand`
     - `category`
     - `intent`
     - `priority`
   - Tạo một array JSON `knowledgeItems`.

6. `Redis - Set KB Snapshot` hoặc static data n8n
   - Giai đoạn cơ bản nên dùng Redis nếu đã có sẵn.
   - Key: `zeo:kb:basic:v1`
   - Value: JSON string của `knowledgeItems`.
   - Nếu chưa có Redis, có thể tạm thời đọc Sheets/Docs trực tiếp mỗi request, nhưng sẽ chậm hơn.

## Workflow 2: Messenger Chatbot Basic RAG

Sửa workflow hiện tại `workflows/local-n8n/zeo_chatbot.workflow.ts` theo từng bước, không thay đổi các Facebook send nodes đang ổn.

Routing mới:

1. `Messenger Trigger`
2. `Lọc Đầu Vào`
3. `Redis - Get KB Snapshot`
4. `Code - Basic Retriever`
5. `If - Has Trusted Context`
6. `Gọi Ollama Local`
7. `Kiểm Chứng`
8. `Router Guardrail`
9. `Nhắn Khách Auto` hoặc `Nhắn Khách Fallback`

`Code - Basic Retriever` giai đoạn đầu làm keyword/semantic-lite:

- Normalize tiếng Việt: bỏ dấu, lowercase.
- Tokenize đúng bằng regex whitespace: `/\s+/`.
- Match theo:
  - exact intent/question_examples trước;
  - keyword overlap sau;
  - ưu tiên `brand = ZeO/PANO/Oplus`;
  - loại `CFC` nếu chatbot đang ở page ZeO.
- Lấy top 3-5 items làm context.
- Nếu score thấp thì fallback admin, không gọi Ollama.

## Prompt Để Output Giống Người Thật Hơn

Dùng prompt chat ngắn gọn, grounded:

```text
Bạn là nhân viên CSKH của ZeO Vietnam.

LUẬT BẮT BUỘC:
- Chỉ dùng thông tin trong [DỮ LIỆU NỘI BỘ].
- Không lấy thông tin ngoài, không bịa giá, chính sách, khuyến mãi, địa chỉ, tồn kho.
- Nếu dữ liệu không đủ để trả lời, hãy nói nhẹ nhàng rằng mình sẽ chuyển admin hỗ trợ.
- Trả lời như người thật: ngắn, tự nhiên, thân thiện.
- Xưng hô: "mình" và "bạn".
- Nếu câu hỏi đơn giản, trả lời 1-2 câu. Không liệt kê dài nếu không cần.
- Nếu khách khiếu nại/hoàn tiền/lừa đảo/sản phẩm lỗi, ưu tiên ghi nhận và chuyển admin.

[DỮ LIỆU NỘI BỘ]
{{context}}

[CÂU HỎI KHÁCH]
{{userMessage}}

[TRẢ LỜI]
```

Ví dụ:

- Context: `Shop mở cửa từ 8:00 đến 21:00 mỗi ngày.`
- Output tốt: `Dạ shop mở cửa từ 8:00 đến 21:00 mỗi ngày nha bạn.`
- Output xấu: `Theo thông tin tôi được cung cấp...`

## Guardrail Cần Có

Sau Ollama:

- Xóa `<think>...</think>`.
- Giới hạn 1000 ký tự.
- Fail nếu:
  - output rỗng/quá ngắn;
  - có câu `tôi không có dữ liệu nhưng...` rồi vẫn bịa;
  - có URL/số điện thoại không nằm trong context;
  - câu hỏi sensitive mà bot tự hứa xử lý hoàn tiền/đổi trả.

Nếu fail: dùng fallback admin.

## Cách Connect Google Drive/Docs

Cần làm trong n8n UI:

1. Tạo credential Google OAuth2 hoặc Service Account.
2. Cấp quyền Drive/Docs/Sheets cho credential đó.
3. Lấy link 4 file Google Docs/Docx trên Drive.
4. Trong Google Drive node, chọn file bằng URL hoặc ID.
5. Nếu file là Google Docs native, chọn export `Text (txt)`.
6. Nếu file là `.docx`, download binary rồi dùng `Extract from File` operation `text`. Nếu n8n không extract docx tốt, nên convert thành Google Docs native trên Drive.

## Cách Connect Google Sheets

Cần làm trong n8n UI:

1. Tạo sheet theo schema đề xuất.
2. Share sheet cho credential Google của n8n.
3. Trong Google Sheets node:
   - Authentication: OAuth2 hoặc Service Account.
   - Resource: `sheet`.
   - Operation: `read`.
   - Document: chọn URL/ID.
   - Sheet: chọn tab FAQ.
   - Range: `A:H`.

## Verification Plan

Test bằng các câu:

- `Shop mở cửa mấy giờ?` -> trả giờ mở cửa từ sheet/doc.
- `Địa chỉ công ty ở đâu?` -> trả địa chỉ trong docs.
- `Đổi trả hàng bị lỗi thế nào?` -> trả đúng điều kiện/chuyển admin nếu cần hồ sơ.
- `Có phân bón nào?` -> với page ZeO, không nên trả CFC nếu không được phép.
- `Cho xin giá khuyến mãi mới nhất` -> nếu sheet/doc không có, fallback admin.

## Bước Tiếp Theo Để Implement Workflow

Cần anh cung cấp/chọn trong n8n UI:

- Google credential đã tạo hay chưa.
- 4 Google Drive file URL/ID.
- Google Sheet URL/ID và tên tab.
- Redis đã có hay chưa. Nếu chưa, giai đoạn đầu có thể đọc Sheets/Docs trực tiếp mỗi request, nhưng sẽ chậm hơn.

Sau khi có các thông tin trên, sửa `zeo_chatbot.workflow.ts` theo basic RAG và tạo workflow sync mới trong `workflows/local-n8n/`.
