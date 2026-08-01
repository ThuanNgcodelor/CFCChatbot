# Hướng dẫn kết nối n8n với Meta Messenger & Google Sheets

Để Bot có thể nhận tin nhắn trực tiếp từ Fanpage và lưu thông tin vào file Excel của bạn trên Google, bạn cần cung cấp "Chìa khóa" (API Keys / Credentials) cho n8n.

Dưới đây là hướng dẫn từng bước:

---

## 1. Cấu hình Meta (Facebook Messenger)

Bạn cần tạo một Ứng dụng (App) trên hệ thống Meta để nó đóng vai trò trung gian lấy tin nhắn từ Fanpage truyền cho n8n.

### Bước 1.1: Tạo Ứng dụng (App) trên Meta
1. Truy cập [Meta for Developers](https://developers.facebook.com/) và đăng nhập bằng tài khoản Facebook của bạn.
2. Bấm vào **My Apps** (Ứng dụng của tôi) ở góc phải trên cùng, sau đó chọn **Create App** (Tạo ứng dụng).
3. Khi được hỏi "What do you want your app to do?", chọn **Other** -> **Next**.
4. Chọn **Business** -> **Next**.
5. Điền tên ứng dụng (ví dụ: `Zeo Chatbot n8n`) và chọn Tài khoản Kinh doanh (nếu có). Bấm **Create app**.

### Bước 1.2: Lấy Access Token (Chìa khóa bảo mật)
1. Trong bảng điều khiển (Dashboard) của App vừa tạo, cuộn xuống tìm ô **Messenger** và bấm **Set Up**.
2. Tìm phần **Access Tokens**, bấm nút **Add or Remove Pages** để liên kết Fanpage của bạn (ví dụ: Trang "Zeo Việt Nam" hoặc "Cò Bay").
3. Bấm nút **Generate Token** bên cạnh tên Fanpage vừa liên kết.
4. Một đoạn mã dài hiện ra, hãy **Copy đoạn mã đó**. (Đây chính là `Access Token`).

### Bước 1.3: Cấu hình Webhook trong n8n
1. Mở n8n của bạn lên, vào Workflow `Zeo Chatbot Demo (Production Ready)`.
2. Bấm đúp vào Node đầu tiên **"Messenger Trigger"**.
3. Ở phần **Credential for Facebook Messenger API**, bấm **Create New Credential**.
4. Dán cái đoạn mã dài bạn vừa copy ở trên vào ô **Access Token**.
5. Điền **App Secret** (Lấy trong phần *App Settings -> Basic* bên Meta for Developers). Bấm **Save**.
6. Copy cái đường link ở mục **Webhook URL** trong Node này (thường bắt đầu bằng `https://...` hoặc `http://...`).
7. Quay lại trang Meta, tìm phần **Webhooks** ở dưới phần Access Token, bấm **Add Callback URL**.
8. Dán Webhook URL vào đó, và tự đặt một chuỗi bí mật (Verify Token, ví dụ: `my_secret_zeo`), sau đó lưu lại trên cả n8n và Meta.

---

## 2. Cấu hình Google Sheets

Để n8n có thể tự động viết vào file Google Sheets của bạn, bạn cần cấp quyền cho nó thông qua Google Cloud.

### Bước 2.1: Tạo Google Cloud Project
1. Truy cập [Google Cloud Console](https://console.cloud.google.com/). Đăng nhập bằng Gmail của bạn.
2. Bấm vào mũi tên xổ xuống ở trên cùng bên trái, chọn **New Project** (Tạo dự án mới). Tên tùy ý (ví dụ: `n8n-sheets`).

### Bước 2.2: Bật (Enable) Google Sheets API
1. Tìm thanh tìm kiếm ở trên cùng, gõ "Google Sheets API" và click vào kết quả đầu tiên.
2. Bấm nút màu xanh **Enable** (Bật).

### Bước 2.3: Tạo Tài khoản Dịch vụ (Service Account - Khuyên dùng cho n8n)
1. Trong menu bên trái, chọn **APIs & Services** -> **Credentials**.
2. Bấm **Create Credentials** ở trên cùng -> Chọn **Service account**.
3. Điền tên (ví dụ: `n8n-bot`) -> Bấm **Create and Continue** -> **Done**.
4. Bạn sẽ thấy một địa chỉ email đặc biệt vừa được tạo (ví dụ: `n8n-bot@n8n-sheets-xxx.iam.gserviceaccount.com`). Hãy **Copy email này**.
5. Click vào cái Service account vừa tạo -> Chuyển sang tab **Keys** -> **Add Key** -> **Create new key**.
6. Chọn định dạng **JSON** -> Bấm **Create**. Một file `.json` sẽ tải xuống máy tính của bạn. Mở file đó ra (bằng Notepad/VS Code).

### Bước 2.4: Nhập Credentials vào n8n
1. Mở Workflow trên n8n, click vào Node **Lưu Khách Hàng (Google Sheets)**.
2. Ở mục Credential, bấm **Create New Credential**. Chọn loại **Google API (Service Account)**.
3. Trong ô **Service Account Email**, dán email bạn đã copy ở bước 2.3.4.
4. Trong ô **Private Key**, copy toàn bộ đoạn mã trong file JSON tải về ném vào (bắt đầu từ `-----BEGIN PRIVATE KEY-----`). Bấm **Save**.

### Bước 2.5: Cấp quyền cho n8n ghi vào file Sheet của bạn
1. Bạn vào Google Drive, tạo một file Google Sheets mới để lưu data khách hàng (Có 2 cột: `Sender ID` và `Tin nhắn`).
2. Bấm nút **Share** (Chia sẻ) màu xanh ở góc phải trên cùng.
3. Dán địa chỉ email Service Account (cái email `n8n-bot@...` ở bước 2.3.4) vào, và cấp quyền **Editor** (Người chỉnh sửa). Bấm **Send**.
4. Trở lại Node Google Sheets trên n8n, bấm vào ô **Document** và chọn file Sheet bạn vừa tạo là xong!

---
> Chúc bạn cài đặt thành công! Nếu gặp vướng mắc ở bước nào hãy nhắn tôi nhé.
