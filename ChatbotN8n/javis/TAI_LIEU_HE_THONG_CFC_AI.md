# TÀI LIỆU HƯỚNG DẪN & BÁO CÁO HỆ THỐNG CFC AI
## CHATBOT CONTROL CENTER v2.1

*Dự án Chatbot Thông Minh Đa Kênh — ZeO Vietnam & CFC Cò Bay*  
*Cập nhật: 15/08/2026*

---

## 1. TỔNG QUAN HỆ THỐNG VÀ KIẾN TRÚC CÔNG NGHỆ

Hệ thống **CFC AI Chatbot Control Center** là nền tảng quản trị và hỗ trợ khách hàng đa kênh (Messenger, Web, Telegram) cho hai thương hiệu chính:
1. **ZeO Vietnam** (Hóa mỹ phẩm gia dụng sinh học, nước giặt, nước rửa chén...)
2. **CFC Cò Bay** (Phân bón & Dinh dưỡng cây trồng Cần Thơ)

Hệ thống kết hợp giữa **RAG Semantic Search chính xác tốc độ cao** và **AI thế hệ mới (Ollama Local + Free Cloud AI)** để tự động hóa tối đa quy trình chăm sóc khách hàng, tư vấn sản phẩm, điều hướng mua hàng Shopee và chốt lead số điện thoại.

### Các Công Nghệ Cốt Lõi Được Tích Hợp:
- **Backend Service:** FastAPI (Python 3.9+) xử lý API bất đồng bộ hiệu năng cao.
- **Cơ sở dữ liệu Vector & Cache:** RediSearch Vector Search (KNN HNSW/FLAT, BGE-M3 1024 dims) lưu trữ Knowledge Base FAQ, Session khách hàng và Learning Queue.
- **AI Xử Lý Cục Bộ (Local AI):** Ollama phục vụ mô hình `bge-m3` tạo embedding tiếng Việt cực chuẩn và `qwen2.5:7b-instruct` viết lại câu tự nhiên.
- **AI Đám Mây Miễn Phí (Free Cloud AI):** Google Gemini 2.0 Flash (Free), OpenRouter, Groq tự động fallback khi phân tích tài liệu và viết báo cáo điều hành.
- **Telegram Notifier:** Tự động bắn thông báo Lead có SĐT, Báo cáo điều hành và cảnh báo câu hỏi cần hỗ trợ tức thì.
- **Shopee Matcher:** Khớp chính xác tên sản phẩm, quy cách, từ khóa (kể cả không dấu, viết tắt) và gửi link mua hàng đúng chuẩn Shopee Mall.
- **Background Workers:** Quản lý tác vụ ngầm tự động (Sync Shopee Google Sheet mỗi 10 phút, Daily Analytics Snapshot mỗi 1 giờ).

---

## 2. DANH SÁCH CÁC TÍNH NĂNG ĐÃ HOÀN THIỆN ĐẦY ĐỦ

### 🔴 Nhóm A — Nạp Kiến Thức & Tự Học
1. **Upload File `.md` / `.txt` Trực Tiếp:**
   - Cho phép tải file tài liệu trực tiếp từ giao diện Admin.
   - Hệ thống tự động phân đoạn (chunking), tạo embedding và lưu vào Redis Vector Index ngay.
2. **Import Google Sheets FAQ:**
   - Nhập đường dẫn Google Sheets (chế độ chia sẻ công khai).
   - Hệ thống tự đọc bảng dữ liệu FAQ (cột *Câu hỏi | Câu trả lời*), chuyển đổi sang tài liệu chuẩn và nạp thẳng vào Vector Index.
3. **Shopee Catalog CRUD:**
   - Giao diện quản trị danh mục sản phẩm Shopee trực quan.
   - Thêm mới, chỉnh sửa giá, khuyến mãi, quy cách, từ khóa nhận diện và link Shopee trực tiếp trên web.
4. **Auto-Sync Shopee 10 phút:**
   - Background worker tự động chạy ngầm mỗi 10 phút để tải bảng giá mới nhất từ Google Sheets của team Sale và cập nhật vào Catalog.
5. **Fallback Thông Minh 3 Lớp:**
   - **Score ≥ 78%:** Tự tin trả lời trực tiếp từ FAQ.
   - **Score ≥ 55%:** Trả lời + Viết lại bằng AI cho tự nhiên.
   - **Score < 55%:** Tự động gửi câu xin lỗi lịch sự, bắn thông báo Telegram cho Admin và đẩy câu hỏi vào Learning Queue.

### 🟡 Nhóm B — Quản Lý Hội Thoại & Khách Hàng
1. **Xem Lịch Sử Chat Đầy Đủ:**
   - Nhấn nút **💬 Chat** trên từng khách để xem toàn bộ dòng thời gian tin nhắn của khách và phản hồi của bot, kèm nhãn intent và thời gian thực.
2. **Bộ Lọc Nâng Cao:**
   - Lọc nhanh theo thương hiệu: Tất cả / ZeO / CFC.
   - Lọc theo số điện thoại: Tất cả / 📞 Có SĐT / Chưa có SĐT.
   - Lọc theo Lead Stage: Mới, Đang thu thập, Lead sẵn, Qualified, Chuyển admin, Đã xử lý.
3. **Xuất Dữ Liệu CSV:**
   - Nút **📤 Xuất File CSV** tải danh sách khách hàng về máy tính để bàn giao cho đội ngũ telesale / marketing.
4. **Ghi Chú Admin & Tags:**
   - Admin có thể ghi chú riêng tư về từng khách (nhu cầu, lịch hẹn gọi lại) và gắn tag phân loại (`HOT LEAD`, `CHỜ BÁO GIÁ`, `ĐÃ CHỐT`...).

### 🟢 Nhóm C — AI & Phân Tích Thông Minh
1. **AI Tự Đề Xuất FAQ (1-Click):**
   - AI tự động quét toàn bộ các câu hỏi bot chưa tự tin trả lời trong Learning Queue, gom nhóm các câu hỏi cùng chủ đề, đề xuất tên intent và câu trả lời chuẩn. Admin chỉ cần 1 click để duyệt vào FAQ.
2. **Biểu Đồ Xu Hướng 7 Ngày (Trend Analytics):**
   - Biểu đồ cột trực quan theo dõi lượng khách hàng mới và tỷ lệ thu thập SĐT trong 7 ngày gần nhất ngay trên Dashboard.
3. **Báo Cáo Điều Hành AI (Executive Briefing):**
   - Tạo báo cáo tổng hợp tình hình kinh doanh, số lượng khách, top intent trong ngày bằng AI và gửi nhanh qua Telegram.
4. **Trung Tâm Cài Đặt API Keys:**
   - Cấu hình Telegram Bot Token, Chat ID, Google Gemini API Key, Shopee Sheet URL trực tiếp trên web mà không cần sửa code.

---

## 3. CẤU TRÚC THƯ MỤC SOURCE CODE

```
javis/
├── TAI_LIEU_HE_THONG_CFC_AI.md  # Tài liệu hệ thống chi tiết (Markdown)
├── TAI_LIEU_HE_THONG_CFC_AI.docx# File tài liệu Word hoàn chỉnh
├── README.md                    # Hướng dẫn nhanh dự án
├── server/
│   ├── main.py                  # FastAPI app chính + Background Workers (Shopee 10m, Snapshot 1h)
│   ├── admin_routes.py          # Toàn bộ API Endpoints cho Admin Dashboard
│   ├── rag_search.py            # Tìm kiếm ngữ nghĩa + 3-Layer Fallback
│   ├── embedder.py              # Xử lý embedding qua Ollama BGE-M3 (1024 dims)
│   ├── knowledge_sync.py        # Đồng bộ FAQ snapshot vào RediSearch Vector Index
│   ├── document_ingestor.py     # Nạp và phân đoạn tài liệu .md vào Vector Index
│   ├── shopee_matcher.py        # Module nhận diện và khớp sản phẩm Shopee
│   ├── telegram_notifier.py     # Gửi thông báo Lead, Cảnh báo Fallback, Báo cáo qua Telegram
│   ├── ai_engine.py             # Xử lý Cloud AI (Gemini, OpenRouter, Groq)
│   ├── ai_reporter.py           # Sinh Báo Cáo Điều Hành Kinh Doanh Hàng Ngày
│   ├── settings.json            # File lưu toàn bộ cấu hình API Keys & Ngưỡng RAG
│   └── static/                  # Giao diện Admin Dashboard tách đa file
│       ├── admin.html           # Shell HTML gọn sạch, bố cục Sidebar, Topbar, Modals
│       ├── css/
│       │   ├── base.css         # Reset CSS, Biến màu Dark Mode, Typography
│       │   ├── layout.css       # Bố cục Sidebar nhóm, Topbar Breadcrumb, Footer
│       │   └── components.css   # Cards, Tables, Buttons, Badges, Modals, Chat Timeline, Trend Charts
│       └── js/
│           ├── core.js          # Helpers dùng chung, Navigation, Quản lý State
│           └── pages/
│               ├── dashboard.js # Dashboard Stats & Trend Analytics 7 ngày
│               ├── documents.js # Upload File .md & Import Google Sheets
│               ├── shopee.js    # Shopee CRUD & Sync Google Sheet
│               ├── customers.js # Lịch sử chat, Bộ lọc, Export CSV, Notes & Tags
│               ├── learning.js  # Learning Queue & AI Auto-Suggest FAQ
│               ├── n8n.js       # Quản lý Workflows n8n & Đồng bộ
│               ├── test.js      # Công cụ Test Bot ngữ nghĩa
│               ├── reports.js   # Báo cáo điều hành AI
│               └── settings.js  # Cấu hình API Keys trực quan
└── knowledge/
    ├── shopee_catalog.json      # Cơ sở dữ liệu sản phẩm Shopee Mall
    ├── zeo_faq.md               # Tài liệu kiến thức chuẩn ZeO
    └── cfc_faq.md               # Tài liệu kiến thức chuẩn CFC Cò Bay
```

---

## 4. HƯỚNG DẪN VẬN HÀNH & CÁC LỆNH CẦN THIẾT

### 1. Khởi động Server:
```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/javis/server
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Truy cập Giao Diện Admin:
Mở trình duyệt truy cập: **`http://localhost:8000/admin`** (hoặc `http://127.0.0.1:8000/admin`)

### 3. Cấu hình API Keys:
Vào tab **"Cài Đặt & API"** trên menu bên trái để:
- Nhập Telegram Bot Token & Chat ID (bấm *Thử gửi tin nhắn Telegram* để test).
- Nhập Google Gemini API Key (miễn phí từ `aistudio.google.com`).
- Nhập Google Sheets URL danh mục Shopee.
- Bấm **"💾 Lưu Tất Cả Cài Đặt"**.
