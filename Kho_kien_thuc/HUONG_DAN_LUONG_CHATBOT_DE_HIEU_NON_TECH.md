# BẢN HƯỚNG DẪN DỄ HIỂU: ĐƯỜNG ĐI CỦA TIN NHẮN TRONG CHATBOT AI
### (Dành cho Quản lý, Nhân viên tư vấn & Người không chuyên kỹ thuật)

---

## 🌟 1. HÌNH DUNG NHANH HỆ THỐNG NHƯ MỘT "TRỢ LÝ BÁN HÀNG THÔNG MINH"

Hãy tưởng tượng Chatbot như một **nhân viên trực Fanpage siêu tốc độ**:
- ⚡ **Trả lời cực nhanh** (chưa tới 0.2 giây).
- 🧠 **Thuộc lòng toàn bộ sản phẩm** và giá cả của công ty.
- 🎯 **Nhớ số điện thoại & địa chỉ** của khách để gửi cho bộ phận Sale.
- 🛡️ **Đặc biệt: KHÔNG BAO GIỜ BỊA ĐẶT**. Nếu gặp câu hỏi chưa từng học hoặc câu hỏi quá khó, bot sẽ **lịch sự hẹn khách và gọi ngay nhân viên thật qua Telegram** chứ không đoán bừa.

---

## 🗺️ 2. ĐƯỜNG ĐI CỦA 1 TIN NHẮN (SƠ ĐỒ TRỰC QUAN)

```
[Khách nhắn tin trên Messenger]
               │
               ▼
   [BƯỚC 1: ĐỌC & DỌN DẸP TIN NHẮN]
   • Sửa lỗi chính tả, dịch từ viết tắt (vd: "k, ko" -> "không", "sp" -> "sản phẩm")
   • Tự động gom Số Điện Thoại & Tỉnh/Thành phố của khách
               │
               ▼
   [BƯỚC 2: TRA CỨU TRONG KHO KIẾN THỨC]
   • Bot lục tìm trong kho câu hỏi - câu trả lời chuẩn của công ty
               │
   ┌───────────┴───────────────────────────────────────────┐
   │                                                       │
   ▼ (Trường hợp 1)                                        ▼ (Trường hợp 2)
🟢 CÂU HỎI QUEN THUỘC (Đúng 100%)                       🔴 CÂU HỎI LẠ / KHÓ / KHIẾU NẠI
   • Hỏi giá, cách dùng, link Shopee...                    • Khách chửi bot, hỏi ngoài ngành...
   • Bot trả lời ngay lập tức!                             • Bot KHÔNG đoán bừa
               │                                           • Gửi chuông báo qua Telegram cho Quản lý
               │                                           • Nhẹ nhàng hẹn khách đợi nhân viên hỗ trợ
               │                                           • Lưu câu hỏi vào "Sổ tay học tập"
               │                                                       │
               └───────────────────────────┬───────────────────────────┘
                                           │
                                           ▼
                      [BƯỚC 3: GỬI CÂU TRẢ LỜI VỀ MESSENGER]
                      (Khách nhận được tin nhắn tự nhiên, lịch sự)
```

---

## 🚦 3. BA TÌNH HUỐNG THỰC TẾ TRÊN MẠNG XÃ HỘI

### 🟢 Tình huống 1: Khách hỏi thông tin bình thường (Hỏi giá, mua ở đâu, link Shopee)
- **Khách nhắn:** *"Nước giặt ZeO can 3.6kg giá bn shop, có freeship k?"*
- **Đường đi:**
  1. Bot dịch: *"bn"* → *"bao nhiêu"*, *"k"* → *"không"*.
  2. Bot nhận diện đây là sản phẩm **Nước giặt ZeO 3.6kg**.
  3. Bot lấy giá chuẩn trong kho và tự động đính kèm đường link **Shopee Mall chính hãng**.
  4. Trả lời ngay cho khách chỉ sau **0.15 giây**.

---

### 🟡 Tình huống 2: Khách để lại Số Điện Thoại hoặc Muốn làm Đại Lý sỉ
- **Khách nhắn:** *"Mình ở Rạch Giá muốn nhập 50 bao phân lúa Cò Bay, alo mình số 0912345678 nhé"*
- **Đường đi:**
  1. Bot tự động bóc tách:
     - **SĐT:** `0912345678`
     - **Khu vực:** `Rạch Giá - Kiên Giang`
     - **Nhu cầu:** `50 bao phân lúa (Mua sỉ/Đại lý)`
  2. Bot tự lưu thông tin này vào danh bạ khách hàng.
  3. **Bắn ngay một thông báo đỏ vào nhóm Telegram của nhân viên Sale/Chủ shop**:  
     *🚨 "Có khách sỉ mới ở Rạch Giá - SĐT: 0912345678 cần tư vấn 50 bao phân lúa!"*
  4. Bot nhắn lại khách: *"Dạ CFC Cò Bay đã nhận được số điện thoại của anh/chị, chuyên viên tư vấn khu vực Kiên Giang sẽ gọi lại cho mình ngay ạ!"*

---

### 🔴 Tình huống 3: Câu hỏi lạ, Khách khiếu nại hoặc Chê bot
- **Khách nhắn:** *"Bot trả lời tào lao vậy, hàng hôm bữa giao bị bể nắp giờ đổi sao?"*
- **Đường đi:**
  1. Bot nhận diện từ khóa nhạy cảm: *"bể nắp"*, *"đổi sao"*, *"trả lời tào lao"*.
  2. **Bot lập tức DỪNG chế độ trả lời tự động** (để tránh cãi tay đôi hoặc nói sai với khách).
  3. Bot tự động chuyển trạng thái: **Cần người thật hỗ trợ**.
  4. Bắn thông báo khẩn cấp lên **Telegram** cho đội ngũ CSKH vào can thiệp.
  5. Đưa câu hỏi này vào **"Learning Queue"** (Phòng chờ duyệt) trên trang Quản trị để quản lý xem lại sau.
  6. Nhắn nhẹ nhàng với khách: *"Dạ ZeO chân thành xin lỗi bạn về sự cố đơn hàng. Em đã chuyển ngay thông tin đến bộ phận hỗ trợ khiếu nại để liên hệ xử lý đổi mới cho mình ngay nhé ạ!"*

---

## 🛡️ 4. TẠI SAO HỆ THỐNG NÀY ĐẢM BẢO AN TOÀN TUYỆT ĐỐI?

| Nỗi sợ thường gặp | Cách hệ thống giải quyết |
|---|---|
| **Sợ bot nói bậy, nói sai giá?** | Bot chỉ được phép lấy giá và thông tin từ bảng dữ liệu do công ty đã duyệt sẵn. |
| **Sợ bot cãi nhau với khách?** | Khi khách bực mình hoặc chê bot, bot tự động nhận lỗi và mời người thật vào chat. |
| **Sợ mất khách sỉ / sót số điện thoại?** | Cứ có số điện thoại là hệ thống báo ngay về điện thoại Telegram của nhân viên trong 1 giây. |
| **Sợ bot không thông minh lên?** | Tất cả các câu hỏi bot chưa biết trả lời đều được gom vào một danh sách, quản lý chỉ cần bấm 1 nút là bot tự học câu trả lời mới. |

---

## 📋 5. TÓM TẮT DỄ NHỚ

> **"Dễ & Đã học"** ➔ **Bot tự trả lời siêu nhanh kèm link Shopee.**  
> **"Có SĐT / Mua Sỉ"** ➔ **Bot lưu danh bạ và báo ngay Telegram cho Sale.**  
> **"Khó / Khiếu nại / Chưa học"** ➔ **Bot xin lỗi lịch sự, ghi nhận vào sổ chờ duyệt và gọi người thật hỗ trợ.**
