# Báo Cáo Triển Khai Chatbot ZeO / CFC

Ngày cập nhật: 17/08/2026

## 1. Tổng quan

Hệ thống chatbot ZeO / CFC đã được triển khai và hiện đã chạy ổn định hơn. Chatbot có thể tiếp nhận tin nhắn khách hàng, đọc dữ liệu kiến thức từ Google Sheet, tìm câu trả lời phù hợp và phản hồi tự động qua workflow n8n.

Mục tiêu chính của hệ thống là hỗ trợ trả lời khách hàng nhanh hơn, đúng dữ liệu hơn, hạn chế trả lời sai hoặc tự bịa thông tin khi dữ liệu chưa có trong hệ thống.

## 2. Thành phần chính

Hệ thống hiện gồm các phần chính:

- Google Sheet: nơi quản lý dữ liệu kiến thức, FAQ, câu hỏi mẫu và câu trả lời chuẩn.
- n8n workflow: tiếp nhận tin nhắn, điều phối luồng xử lý và gửi phản hồi lại cho khách.
- Python FastAPI server: xử lý logic chatbot chính, nhận diện intent, đọc dữ liệu và trả lời nhanh.
- Redis: lưu dữ liệu kiến thức đã đồng bộ, hồ sơ khách hàng, lịch sử chat và vector search.
- Ollama: chạy mô hình AI local để hỗ trợ embedding và xử lý ngữ nghĩa.
- BGE-M3: mô hình embedding dùng để hiểu ngữ nghĩa tiếng Việt và tìm câu trả lời gần đúng trong kho kiến thức.

## 3. Cách hoạt động cơ bản

Khi khách hàng nhắn tin:

1. n8n nhận tin nhắn từ kênh chat.
2. n8n gửi nội dung sang Python FastAPI server.
3. Server kiểm tra các trường hợp nhanh như hỏi sản phẩm, hỏi giá, hỏi website, hotline, đại lý, thông tin cá nhân.
4. Nếu cần tìm kiến thức, hệ thống tra cứu trong Redis bằng RAG/vector search.
5. Dữ liệu trả lời được lấy từ Google Sheet đã đồng bộ, không tự ý bịa thêm.
6. Bot gửi câu trả lời lại cho khách hàng.

## 4. Những phần đã cải thiện

Đã xử lý các vấn đề quan trọng:

- Bot đã đọc được dữ liệu danh mục sản phẩm từ Google Sheet/Redis.
- Sửa lỗi Redis có dữ liệu nhưng bot vẫn báo “chưa tải được kiến thức”.
- Hạn chế việc bot tự bịa giá khi Google Sheet không có giá.
- Câu hỏi viết tắt như “sp” đã được hiểu là “sản phẩm”.
- Tách riêng dữ liệu ZeO và CFC để tránh trả lời lẫn thương hiệu.
- Bot có thể nhớ số điện thoại/khu vực khách đã gửi trong cùng hồ sơ chat.
- Output trả lời đã được format lại đẹp hơn, có xuống dòng và đánh số rõ ràng.
- Workflow đồng bộ kiến thức đã có bước gọi lại `/sync` để cập nhật vector index sau khi Google Sheet thay đổi.

## 5. Ví dụ kết quả hiện tại

Câu hỏi:

```text
hiện tại zeo có dòng sp nào vậy
```

Bot trả lời:

```text
Dạ ZeO Vietnam có 4 nhóm sản phẩm chăm sóc gia đình chính:

1. Giặt giũ (Bột giặt & Nước giặt sinh học ZeO, PANO, Oplus)
2. Rửa chén (Nước rửa chén ZeO/ZIF 100% cốt chanh, PANO Chanh, PANO Vitamin E, Oplus)
3. Lau sàn (Nước lau sàn sinh học ZeO, Oplus đậm đặc 2X)
4. Tẩy rửa vệ sinh (Javen ZeO, Tẩy Toilet diệt khuẩn 99.9%, Tẩy màu, Lau kính & Xịt tẩy đa năng PANO).

Bạn đang quan tâm nhóm nào để mình gửi thông tin và ưu đãi chi tiết nha!
```

## 6. Lợi ích hiện tại

- Khách hàng được phản hồi nhanh hơn.
- Nội dung trả lời bám sát dữ liệu trong Google Sheet.
- Dễ cập nhật kiến thức mới mà không phải sửa code nhiều.
- Có thể mở rộng thêm sản phẩm, FAQ, chính sách, đại lý và kịch bản chăm sóc khách hàng.
- Giảm rủi ro bot trả lời sai giá, sai sản phẩm hoặc lẫn giữa ZeO và CFC.

## 7. Hướng phát triển tiếp theo

Các bước nên làm tiếp:

- Tiếp tục bổ sung câu hỏi mẫu trong Google Sheet theo tin nhắn thật của khách.
- Kiểm tra định kỳ các câu bot không trả lời được để đưa vào dữ liệu huấn luyện.
- Chuẩn hóa thêm format câu trả lời trong Google Sheet.
- Tăng bộ test để kiểm tra các tình huống giá, sản phẩm, đại lý, giao hàng và chăm sóc khách hàng.
- Theo dõi log để phát hiện các câu hỏi khách thường hỏi nhưng hệ thống chưa có dữ liệu.

## 8. Kết luận

Hệ thống chatbot ZeO / CFC hiện đã được triển khai và hoạt động ổn định hơn. Kiến thức chính được quản lý qua Google Sheet, server Python xử lý trả lời, Redis lưu và tìm kiếm dữ liệu, còn Ollama với BGE-M3 hỗ trợ hiểu ngữ nghĩa tiếng Việt.

Hệ thống đã sẵn sàng để tiếp tục test thực tế với khách hàng và mở rộng thêm dữ liệu theo nhu cầu kinh doanh.
