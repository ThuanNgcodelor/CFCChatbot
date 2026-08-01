# 📚 Tài Liệu Kiến Trúc Basic RAG – ZeO Chatbot

> **Phiên bản:** Basic RAG v1  
> **Cập nhật:** 2026-07-31  
> **Stack:** n8n · Google Sheets · Ollama (LLM local) · Facebook Messenger API

---

## Mục lục

1. [RAG là gì? Nguyên lý hoạt động](#1-rag-là-gì-nguyên-lý-hoạt-động)
2. [Kiến trúc tổng quan – 2 luồng](#2-kiến-trúc-tổng-quan--2-luồng)
3. [Luồng 1 – Knowledge Sync (chuẩn bị dữ liệu)](#3-luồng-1--knowledge-sync-chuẩn-bị-dữ-liệu)
4. [Luồng 2 – Chatbot RAG (xử lý câu hỏi)](#4-luồng-2--chatbot-rag-xử-lý-câu-hỏi)
5. [Cơ chế Scoring (chấm điểm liên quan)](#5-cơ-chế-scoring-chấm-điểm-liên-quan)
6. [Guardrail – Tầng kiểm tra an toàn](#6-guardrail--tầng-kiểm-tra-an-toàn)
7. [Cách "train" / cập nhật dữ liệu đầu vào](#7-cách-train--cập-nhật-dữ-liệu-đầu-vào)
8. [Cấu trúc dữ liệu Google Sheets](#8-cấu-trúc-dữ-liệu-google-sheets)
9. [Prompt Engineering cho Ollama](#9-prompt-engineering-cho-ollama)
10. [Checklist triển khai](#10-checklist-triển-khai)
11. [Lộ trình nâng cấp](#11-lộ-trình-nâng-cấp)

---

## 1. RAG là gì? Nguyên lý hoạt động

**RAG = Retrieval-Augmented Generation** (Tạo sinh có Truy xuất tăng cường)

Thay vì để AI "tự bịa" câu trả lời từ dữ liệu huấn luyện chung, RAG **bắt buộc AI chỉ được dùng dữ liệu bạn cung cấp**. Luồng hoạt động gồm 3 bước:

```
[Câu hỏi khách] → [RETRIEVE: tìm đoạn văn liên quan] → [AUGMENT: nhét vào prompt] → [GENERATE: AI trả lời]
      ↑                         ↑                                ↑                          ↑
  Messenger              Google Sheets                    Context window               Ollama LLM
```

### So sánh RAG vs Fine-tuning

| Tiêu chí | Fine-tuning (train lại model) | Basic RAG (hệ thống này) |
|---|---|---|
| Cập nhật dữ liệu | Phải train lại → tốn GPU/thời gian | Sửa Google Sheets → cập nhật ngay sau 30 phút |
| Chi phí | Rất cao | Gần như 0 (chỉ tốn thời gian chỉnh sửa sheet) |
| Kiểm soát nội dung | Khó | Dễ – bạn thấy rõ từng dòng dữ liệu |
| Độ chính xác | Cao hơn cho domain hẹp | Tốt nếu viết ví dụ câu hỏi tốt |
| Phù hợp | Hệ thống lớn, ổn định | **Hệ thống vừa, cần cập nhật linh hoạt** |

---

## 2. Kiến trúc tổng quan – 2 luồng

```
╔══════════════════════════════════════════════════════════════╗
║  LUỒNG 1: KNOWLEDGE SYNC (offline / background)              ║
║                                                              ║
║  [Manual / Mỗi 30 phút]                                     ║
║       ↓                                                      ║
║  [Google Sheets - tab FAQ]                                   ║
║       ↓ (đọc toàn bộ dữ liệu thô)                           ║
║  [NormalizeKnowledge - Code node]                            ║
║       ↓ (lọc active, đúng brand, normalize text)             ║
║  [Google Sheets - tab KnowledgeSnapshot]                     ║
║       (ghi 1 row duy nhất: key = zeo_kb_basic_v1)           ║
╚══════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════╗
║  LUỒNG 2: CHATBOT RAG (online / real-time)                   ║
║                                                              ║
║  [Messenger Trigger - khách nhắn tin]                        ║
║       ↓                                                      ║
║  [Loc Dau Vao] – làm sạch input, phát hiện nhạy cảm         ║
║       ↓                                                      ║
║  [Get Knowledge Snapshot] – đọc snapshot từ Sheets           ║
║       ↓                                                      ║
║  [RAG Tim Kiem] – tìm top-3 entries phù hợp nhất            ║
║       ↓                                                      ║
║  [Router Co Nguon]                                           ║
║    ├─ hasContext=TRUE  → [Goi Ollama] → [Kiem Chung]        ║
║    │                          ↓                              ║
║    │                 [Router Guardrail]                      ║
║    │                   ├─ passed → [Nhan Khach Auto]         ║
║    │                   └─ failed → [Nhan Khach Fallback]     ║
║    └─ hasContext=FALSE → [Nhan Khach Fallback]               ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 3. Luồng 1 – Knowledge Sync (chuẩn bị dữ liệu)

> **File:** `zeo_knowledge_sync_basic.workflow.ts`

Đây là bước **"train" / chuẩn bị dữ liệu** cho hệ thống RAG. Chạy nền, không phụ thuộc vào khách hàng.

### Node 1: Trigger (Kích hoạt)

```
ManualTrigger ──┐
                ├──→ ReadFaqRows
ScheduleTrigger─┘  (mỗi 30 phút)
```

- `ManualTrigger`: Chạy ngay khi bấm nút trong n8n (dùng để test thủ công).
- `ScheduleTrigger`: Tự động chạy **mỗi 30 phút** — đảm bảo chatbot luôn có knowledge mới nhất.

---

### Node 2: Read FAQ Rows (Đọc dữ liệu thô)

```typescript
ReadFaqRows = {
  resource: 'sheet',
  operation: 'read',
  sheetName: 'FAQ',    // tab FAQ trong Google Sheets
  range: 'A:H',        // đọc cột A đến H
}
```

Đọc **toàn bộ** tab FAQ từ Google Sheets. Dữ liệu thô có thể chứa:
- Các dòng chưa active
- Brand không thuộc scope ZeO
- Ký tự dư thừa, whitespace lộn xộn

---

### Node 3: Normalize Knowledge (Chuẩn hóa dữ liệu) ⭐ Quan trọng nhất

Đây là trái tim của bước chuẩn bị dữ liệu. Code node này làm 5 việc:

#### 3.1 – Normalize text
```javascript
function normalizeText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}
// "  Có  COD không?  " → "Có COD không?"
```

#### 3.2 – Parse boolean từ sheet
```javascript
function asBool(value) {
  return ['true', '1', 'yes', 'y'].includes(String(value).toLowerCase());
}
// "TRUE", "1", "yes" → true
// "FALSE", "0", ""   → false
```

#### 3.3 – Tách question examples
```javascript
function splitExamples(value) {
  return String(value).split(';').map(s => s.trim()).filter(Boolean);
}
// "Ship không?;Giao hàng không?" → ["Ship không?", "Giao hàng không?"]
```

#### 3.4 – Lọc dữ liệu theo 3 tiêu chí
```javascript
const allowedBrands = new Set(['zeo', 'pano', 'oplus', 'zeo/pano/oplus']);

knowledgeItems
  .filter(item => item.active)                              // 1. Chỉ lấy dòng active=TRUE
  .filter(item => allowedBrands.has(brandKey(item.brand))) // 2. Đúng brand
  .filter(item => item.answer && item.intent);             // 3. Có đủ nội dung
```

#### 3.5 – Sắp xếp theo priority
```javascript
knowledgeItems.sort((a, b) => b.priority - a.priority || a.intent.localeCompare(b.intent));
// Priority cao → được xét trước khi tìm kiếm
```

**Kết quả đầu ra:**
```json
{
  "snapshot_key": "zeo_kb_basic_v1",
  "brand_scope": "ZeO/PANO/Oplus",
  "knowledge_count": 42,
  "updated_at": "2026-07-31T03:00:00Z",
  "snapshot_json": "[{...},{...},...]"
}
```

---

### Node 4: Write Knowledge Snapshot (Ghi snapshot)

```typescript
WriteKnowledgeSnapshot = {
  operation: 'appendOrUpdate',
  sheetName: 'KnowledgeSnapshot',
  columnToMatchOn: 'snapshot_key',  // upsert theo key này
}
```

**Kết quả ghi vào Sheets:**

| snapshot_key | brand_scope | knowledge_count | updated_at | snapshot_json |
|---|---|---|---|---|
| zeo_kb_basic_v1 | ZeO/PANO/Oplus | 42 | 2026-07-31T... | `[{"intent":"opening_hours",...},...]` |

> **Tại sao dùng 1 row duy nhất?** Chatbot chỉ cần đọc 1 lần, toàn bộ knowledge được nén vào `snapshot_json` dạng JSON string. Tránh đọc hàng trăm row mỗi lần có khách nhắn tin → tối ưu performance.

---

## 4. Luồng 2 – Chatbot RAG (xử lý câu hỏi)

> **File:** `zeo_chatbot.workflow.ts`

### Node 1: Messenger Trigger

Lắng nghe webhook từ **Facebook Messenger**. Khi có tin nhắn mới, n8n nhận payload:
```json
{
  "messaging": [{
    "sender": { "id": "123456789" },
    "message": { "text": "Shop mở cửa mấy giờ?" }
  }]
}
```

---

### Node 2: Loc Dau Vao (Lọc đầu vào)

Node này làm **bộ lọc tiền xử lý** trước khi đụng đến AI:

```javascript
// 1. Trích xuất text và senderId từ nhiều format webhook khác nhau
const text = data.messaging[0].message?.text || '';
const senderId = data.messaging[0].sender?.id || '';

// 2. Nếu không có chữ → dừng lại (tránh tốn tài nguyên)
if (!text || !text.trim()) return [];

// 3. Normalize tiếng Việt (loại bỏ dấu để matching)
function normalize(str) {
  return str
    .normalize('NFD')                // tách dấu ra khỏi ký tự
    .replace(/[\u0300-\u036f]/g, '') // xóa dấu thanh
    .replace(/đ/g, 'd')              // xử lý đặc biệt chữ đ
    .toLowerCase();
}

// 4. Phát hiện câu nhạy cảm
const sensitiveWords = ['hoan tien', 'doi tra', 'khieu nai', 'lua dao', ...];
// isSensitive = true → KHÔNG gọi AI, thẳng fallback

// 5. Phát hiện câu ngoài phạm vi
const outOfScopeWords = ['phan bon', 'co bay', 'npk', 'phan huu co'];
// isOutOfScope = true → KHÔNG gọi AI, thẳng fallback
```

**Output của node:**
```json
{
  "text": "Shop mở cửa mấy giờ?",
  "senderId": "123456789",
  "isSensitive": false,
  "isOutOfScope": false
}
```

---

### Node 3: Get Knowledge Snapshot (Tải knowledge)

```typescript
GetKnowledgeSnapshot = {
  operation: 'read',
  sheetName: 'KnowledgeSnapshot',
  range: 'A:E',
  onError: 'continueRegularOutput',  // nếu lỗi vẫn tiếp tục (không crash)
  alwaysOutputData: true,
}
```

Đọc row `zeo_kb_basic_v1` — kết quả đã được chuẩn bị sẵn từ Luồng 1.

---

### Node 4: RAG Tim Kiem (Retrieve – Bước cốt lõi RAG) ⭐

Đây là **bước RETRIEVE** trong RAG. Thay vì dùng vector embedding (phức tạp, cần GPU), hệ thống dùng **keyword scoring** thuần JavaScript:

```
Câu hỏi: "Shop mở cửa mấy giờ?"
    ↓ normalize → "shop mo cua may gio"
    ↓ tokenize  → ["shop", "mo", "cua", "may", "gio"]
    ↓
Với mỗi knowledge entry:
    - Exact match với question_examples? → +50 điểm
    - intent có trong câu hỏi?           → +12 điểm
    - Overlap token với examples?         → +4 điểm/token
    - Overlap token với answer?           → +1 điểm/token
    - priority bonus                      → +0..1 điểm
    ↓
Sắp xếp → lấy top-3 entries có score cao nhất
```

#### Quy tắc quyết định `hasContext`:

```javascript
const hasContext = !isSensitive && !isOutOfScope && bestScore >= 12;
//                 không nhạy cảm  không out-scope   score đủ cao
```

| Điều kiện | Kết quả |
|---|---|
| `isSensitive = true` | → Fallback (không gọi AI) |
| `isOutOfScope = true` | → Fallback (không gọi AI) |
| `bestScore < 12` | → Fallback (không đủ ngữ cảnh) |
| Tất cả đều thỏa | → Gọi Ollama với context |

---

### Node 5: Router Co Nguon (Phân luồng)

```
hasContext = TRUE  → Goi Ollama Local (out[0])
hasContext = FALSE → Nhan Khach Fallback (out[1])
```

Đây là **cửa kiểm soát** quan trọng: Ollama chỉ được gọi khi **đã có ngữ cảnh đáng tin**. Tránh AI bịa câu trả lời khi không có dữ liệu.

---

### Node 6: Goi Ollama Local (Generate – Bước AI)

```
POST http://100.77.47.82:11434/api/generate
{
  "model": "minimax-m3:cloud",
  "stream": false,
  "prompt": "..."
}
```

Prompt được xây dựng động, bao gồm:
1. **Role**: Nhân viên CSKH ZeO
2. **Rules**: Luật bắt buộc (chỉ dùng dữ liệu nội bộ)
3. **Context**: Top-3 knowledge entries từ RAG
4. **Question**: Câu hỏi của khách
5. **Output placeholder**: `[TRẢ LỜI]` để AI điền vào

> **Nguyên tắc cốt lõi:** AI **không được phép** suy luận ra ngoài `[DỮ LIỆU NỘI BỘ]`. Đây là sự khác biệt cơ bản giữa RAG và prompt thông thường.

---

### Node 7: Kiem Chung (Guardrail sau AI)

Sau khi AI trả lời, node này **kiểm tra lần 2** trước khi gửi cho khách:

```javascript
const tooShort     = aiText.length < 5;       // quá ngắn, vô nghĩa
const tooLong      = aiText.length > 1000;    // quá dài
const hasRefusal   = /khong biet|xin loi|i don't know/i.test(aiText); // AI từ chối
const inventedUrl  = extractUrls(aiText).some(url => !context.includes(url));   // link không có trong KB
const inventedPhone= extractPhones(aiText).some(p => !context.includes(p));    // SĐT bịa
const mentionsCfc  = /\bCFC\b|co bay|phan bon/i.test(aiText);           // sai brand
const sensitivePromise = ragData.isSensitive && /hoan tien|doi tra/i.test(aiText); // hứa hẹn sai

const passed = !tooShort && !tooLong && !hasRefusal
             && !inventedUrl && !inventedPhone && !mentionsCfc && !sensitivePromise;
```

---

### Node 8 & 9: Router Guardrail → Gửi tin

```
passed = TRUE  → NhanKhachAuto    → gửi reply của AI cho khách qua Messenger
passed = FALSE → NhanKhachFallback → gửi "Admin sẽ hỗ trợ bạn sớm nhất nha"
```

---

## 5. Cơ chế Scoring (chấm điểm liên quan)

Hệ thống **KHÔNG dùng vector embedding** mà dùng keyword-based scoring. Đây là **Basic RAG**.

```
Câu hỏi người dùng (đã normalize)
        ↓
  ┌─────────────────────────────────────────┐
  │  Với mỗi knowledge entry:               │
  │                                         │
  │  Exact substring match    → +50 pts     │ ← câu hỏi ≈ example
  │  Intent match             → +12 pts     │ ← intent keyword trong câu
  │  Token overlap (examples) → +4/token    │ ← từ chung với examples
  │  Token overlap (answer)   → +1/token    │ ← từ chung trong answer
  │  Priority bonus           → +0..1 pts   │ ← ưu tiên entry quan trọng
  └─────────────────────────────────────────┘
        ↓
  Sort descending → Top 3 entries
        ↓
  bestScore >= 12? → hasContext = TRUE → Gọi AI
```

### Ví dụ tính điểm:

**Câu hỏi:** "Shop mở cửa mấy giờ?"  
**Normalize:** "shop mo cua may gio"  
**Tokens:** `["shop", "mo", "cua", "may", "gio"]`

| Entry | question_examples | Điểm |
|---|---|---|
| `opening_hours` | "Mấy giờ mở cửa?;Shop mở cửa lúc nào?" | +50 (exact) + 4×3 tokens = **62** |
| `cod_payment` | "Có COD không?" | 0 → bị loại |

→ `bestScore = 62 >= 12` → `hasContext = TRUE` → Gọi Ollama ✅

---

## 6. Guardrail – Tầng kiểm tra an toàn

Hệ thống có **2 tầng guardrail** (rào cản bảo vệ):

```
Tầng 1 (TRƯỚC AI):   Loc Dau Vao + Router Co Nguon
                      → Phát hiện nhạy cảm / out-of-scope / score thấp
                      → Chặn TRƯỚC khi gọi AI (tiết kiệm tài nguyên)

Tầng 2 (SAU AI):     Kiem Chung + Router Guardrail
                      → Phát hiện AI bịa link, SĐT, sai brand
                      → Chặn TRƯỚC khi gửi cho khách
```

### Tất cả tình huống Fallback:

| Tình huống | Tầng | Hành động |
|---|---|---|
| Không có chữ trong tin nhắn | 1 | `return []` – dừng workflow |
| Câu nhạy cảm (hoàn tiền, khiếu nại...) | 1 | Fallback ngay |
| Câu ngoài scope (phân bón, NPK...) | 1 | Fallback ngay |
| Score RAG < 12 | 1 | Fallback ngay |
| AI trả lời quá ngắn (<5 ký tự) | 2 | Fallback |
| AI trả lời quá dài (>1000 ký tự) | 2 | Fallback |
| AI bịa URL không có trong KB | 2 | Fallback |
| AI bịa số điện thoại | 2 | Fallback |
| AI nhắc đến CFC/Cò Bay/phân bón | 2 | Fallback |
| AI hứa hẹn hoàn tiền cho câu nhạy cảm | 2 | Fallback |

---

## 7. Cách "train" / cập nhật dữ liệu đầu vào

> Với Basic RAG, "train" **không phải là train model AI**. Đây là **cập nhật Knowledge Base** — dữ liệu mà AI sẽ được phép dùng.

### Bước 1: Mở tab FAQ trong Google Sheets

Thêm/sửa các dòng với cấu trúc sau:

| Cột | Mô tả | Ví dụ |
|---|---|---|
| `active` | Bật/tắt dòng này | `TRUE` |
| `brand` | Nhãn hàng | `ZeO` |
| `category` | Loại câu hỏi | `shipping` |
| `intent` | Tên ngắn gọn ý định | `cod_payment` |
| `question_examples` | Các câu hỏi khách thường hỏi (cách nhau `;`) | `Có COD không?;Trả tiền mặt được không?` |
| `answer` | Câu trả lời chính xác | `Dạ ZeO hỗ trợ COD toàn quốc...` |
| `priority` | Mức ưu tiên (0-100) | `80` |
| `source_id` | ID nguồn dữ liệu | `zeo_faq_v1` |
| `updated_at` | Ngày cập nhật | `2026-07-31` |

### Bước 2: Chạy Knowledge Sync

- **Tự động:** Chờ tối đa 30 phút (ScheduleTrigger).
- **Thủ công:** Vào n8n → Workflow **"Zeo Knowledge Sync Basic"** → bấm **Execute** trên node ManualTrigger.

### Bước 3: Kiểm tra KnowledgeSnapshot

Mở tab `KnowledgeSnapshot` trong Sheets → xem `knowledge_count` đã tăng chưa và `updated_at` đã mới chưa.

### Bước 4: Test câu hỏi

Gửi tin nhắn test qua Messenger hoặc dùng mock data trong n8n.

---

### Mẹo viết `question_examples` hiệu quả

```
✅ TỐT – nhiều biến thể, sát cách khách nói:
"Có COD không?;Trả tiền mặt được không?;Giao hàng thu tiền mặt không?;Đặt hàng trả sau được không?"

❌ KHÔNG TỐT:
"COD"      ← quá ngắn, không đủ ngữ cảnh
"COD payment available"  ← tiếng Anh không phù hợp với khách Việt
```

> **Quy tắc vàng:** Càng nhiều `question_examples` sát với cách khách thường hỏi → RAG tìm đúng càng nhiều → AI trả lời càng tốt.

---

## 8. Cấu trúc dữ liệu Google Sheets

### Tab FAQ (Nguồn gốc – người chỉnh sửa)

```
A        B      C         D               E                         F              G         H
active   brand  category  intent          question_examples         answer         priority  source_id
TRUE     ZeO    shipping  cod_payment     Có COD không?;...        Dạ ZeO hỗ...  80        zeo_faq_v1
TRUE     ZeO    hours     opening_hours   Mấy giờ mở cửa?;...     8h-17h30...   70        zeo_faq_v1
FALSE    CFC    products  ...             ...                       ...            ...       ...
```

### Tab KnowledgeSnapshot (Ghi tự động bởi Luồng 1)

```
A                B              C                D                    E
snapshot_key     brand_scope    knowledge_count  updated_at           snapshot_json
zeo_kb_basic_v1  ZeO/PANO/Oplus 42              2026-07-31T03:00:00Z [{"active":true,...}]
```

### Cấu trúc mỗi item trong `snapshot_json`

```json
{
  "active": true,
  "brand": "ZeO",
  "category": "shipping",
  "intent": "cod_payment",
  "question_examples": ["Có COD không?", "Trả tiền mặt được không?"],
  "answer": "Dạ ZeO hỗ trợ COD toàn quốc bạn ơi...",
  "priority": 80,
  "source_id": "zeo_faq_v1",
  "updated_at": "2026-07-31",
  "row_index": 5
}
```

---

## 9. Prompt Engineering cho Ollama

Prompt được thiết kế theo mẫu **Role + Rules + Context + Question + Output placeholder**:

```
Bạn là nhân viên CSKH của ZeO Vietnam.

LUẬT BẮT BUỘC:
- Chỉ dùng thông tin trong [DỮ LIỆU NỘI BỘ].
- Không lấy thông tin ngoài.
- Không bịa giá, khuyến mãi, tồn kho, chính sách.
- Nếu dữ liệu không đủ, nói nhẹ nhàng rằng admin sẽ hỗ trợ.
- Trả lời ngắn, tự nhiên, thân thiện.
- Xưng hô "mình" và "bạn".
- Nếu câu hỏi khiếu nại/hoàn tiền/sản phẩm lỗi, chỉ ghi nhận và chuyển admin.

[DỮ LIỆU NỘI BỘ]
Nguon 1: zeo_faq_v1
Brand: ZeO
Category: hours
Intent: opening_hours
Answer: ZeO mở cửa từ 8h-17h30 các ngày trong tuần...

[CÂU HỎI KHÁCH]
Shop mở cửa mấy giờ?

[TRẢ LỜI]
← AI điền vào đây
```

### Tại sao cần `[DỮ LIỆU NỘI BỘ]`?

Ollama được huấn luyện với dữ liệu chung của internet. Nếu không có context, nó có thể **bịa** thông tin về ZeO. Bằng cách inject `[DỮ LIỆU NỘI BỘ]` vào prompt, ta **giới hạn phạm vi** AI chỉ được dùng những gì ta cung cấp — đây chính là **"augmentation"** trong RAG.

---

## 10. Checklist triển khai

### Cần cấu hình trước khi chạy

- [ ] **Google Sheets URL**: Điền vào `documentId.value` trong 3 nodes:
  - `ReadFaqRows` (Workflow 1)
  - `WriteKnowledgeSnapshot` (Workflow 1)
  - `GetKnowledgeSnapshot` (Workflow 2)

- [ ] **Google OAuth2 Credential**: Tạo trong n8n → Settings → Credentials → Google Sheets OAuth2.

- [ ] **Facebook App credential**: Cấu hình `facebookGraphApi` cho `NhanKhachAuto` và `NhanKhachFallback`.

- [ ] **Messenger Trigger**: Điền App ID `27651600977802449` + xác nhận Page token.

- [ ] **Ollama URL**: Kiểm tra `http://100.77.47.82:11434` còn hoạt động.

- [ ] **Tạo 2 tab trong Google Sheets**:
  - `FAQ` — nơi nhập dữ liệu thủ công (người chỉnh)
  - `KnowledgeSnapshot` — được ghi tự động (đừng chỉnh tay)

### Kiểm tra sau triển khai

- [ ] Chạy Workflow 1 (Manual) → Tab `KnowledgeSnapshot` có data mới
- [ ] `knowledge_count > 0`
- [ ] Gửi test: "Shop mở cửa mấy giờ?" → nhận trả lời hợp lệ
- [ ] Gửi test: "Có phân bón không?" → nhận fallback
- [ ] Gửi test: "Tôi muốn hoàn tiền" → nhận fallback
- [ ] Gửi test: chỉ gửi emoji 👍 → không có phản hồi (return [])

---

## 11. Lộ trình nâng cấp

| Giai đoạn | Cải tiến | Lợi ích |
|---|---|---|
| **Hiện tại (Basic RAG)** | Keyword scoring | Đơn giản, dễ debug, không cần GPU |
| **V2** | BM25 scoring | Chính xác hơn với tiếng Việt |
| **V3** | Vector embedding (sentence-transformers) | Hiểu ngữ nghĩa, không cần exact keyword |
| **V4** | Hybrid (BM25 + vector) | Tốt nhất cho production |
| **V5** | Multi-turn conversation memory | Nhớ ngữ cảnh hội thoại trước |
| **V6** | Reranker model | Sắp xếp lại kết quả truy xuất chính xác hơn |

---

*Tài liệu này được tạo tự động từ code analysis của `zeo_chatbot.workflow.ts` và `zeo_knowledge_sync_basic.workflow.ts`*  
*Cập nhật: 2026-07-31*
