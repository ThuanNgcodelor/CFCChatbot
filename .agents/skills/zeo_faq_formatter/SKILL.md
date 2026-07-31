---
name: ZeoFaqFormatter
description: Chuyển đổi các tài liệu thô (docx, pdf, txt, nội dung chat) thành định dạng CSV chuẩn 9 cột của ZeO Chatbot FAQ.
---

# Kỹ năng chuyển đổi tài liệu thô thành FAQ CSV (ZeO RAG)

Khi người dùng cung cấp bất kỳ tài liệu thô nào (bài viết, file docx, nội dung chat, quy định) và yêu cầu biến nó thành dữ liệu cho chatbot, bạn hãy sử dụng prompt/quy tắc sau để tự động parse nó thành file CSV chuẩn xác.

## QUY TẮC ĐỊNH DẠNG CSV ĐẦU RA

File CSV bắt buộc phải có đúng 9 cột với header như sau (ngăn cách bằng dấu phẩy):
`active,brand,category,intent,question_examples,answer,priority,source_id,updated_at`

### Các quy tắc điền cột:
1. **active**: Luôn luôn là `TRUE`.
2. **brand**: Điền `ZeO` (hoặc `ZeO/PANO/Oplus` nếu áp dụng chung). Không dùng `CFC`.
3. **category**: Phân loại hợp lý (ví dụ: `faq`, `product`, `shipping`, `policy`, `payment`, `support`, `operations`).
4. **intent**: Tên viết thường, cách nhau bằng gạch dưới, mô tả ngắn ý định (ví dụ: `return_policy`, `product_usage`). Không được trùng lặp cho các ý khác nhau.
5. **question_examples**: **QUAN TRỌNG NHẤT**. Phải tạo ra TỐI THIỂU 4-6 biến thể câu hỏi mà khách hàng có thể nhắn tin. Các câu hỏi ngăn cách nhau bằng dấu chấm phẩy `;`. 
   - *Ví dụ: "Có đổi trả không?;Chính sách đổi trả thế nào?;Mua về không ưng có đổi được không?;Hàng lỗi đổi sao?;Cho xem chính sách trả hàng"*
6. **answer**: Câu trả lời rõ ràng, lấy TỪ TÀI LIỆU GỐC, tuyệt đối không bịa đặt. Xưng hô là "mình" và "bạn", giọng văn lịch sự, nhẹ nhàng như nhân viên trực page.
7. **priority**: Số nguyên từ 10 đến 100. (100 = Rất quan trọng, hay hỏi; 80 = Bình thường; 50 = Ít hỏi).
8. **source_id**: Đặt tên gợi nhớ nguồn gốc (ví dụ: `zeo_policy_docx_v1`).
9. **updated_at**: Định dạng `YYYY-MM-DD` của ngày hôm nay.

## VÍ DỤ MINH HỌA

**Tài liệu thô từ User:**
"Bên mình freeship cho đơn hàng từ 500k. Đơn dưới 500k thì phí ship toàn quốc đồng giá 30k nhé. Khách hàng nhận hàng được kiểm tra trước khi thanh toán."

**Đầu ra CSV mong đợi:**
```csv
active,brand,category,intent,question_examples,answer,priority,source_id,updated_at
TRUE,ZeO,shipping,freeship_condition,"Có freeship không?;Đơn bao nhiêu thì được freeship?;Mua mấy sản phẩm thì miễn phí ship?;Phí ship tính sao?;Ship bao nhiêu?;Bao nhiêu miễn phí vận chuyển?","Dạ ZeO freeship cho đơn hàng từ 500k ạ. Đơn dưới 500k phí ship toàn quốc là 30k nha bạn.",100,doc_freeship,2026-07-31
TRUE,ZeO,policy,inspect_before_payment,"Có được kiểm hàng không?;Được xem hàng trước khi thanh toán không?;Cho kiểm tra hàng không?;Nhận hàng có được bóc ra xem không?","Dạ bạn hoàn toàn được kiểm tra hàng trước khi thanh toán nha. Bạn cứ yên tâm ạ.",90,doc_freeship,2026-07-31
```

## LƯU Ý KHI RÁP VÀO FILE CSV TRONG CODE
- Các cột chứa dấu phẩy (như `question_examples` hoặc `answer`) **bắt buộc phải được đặt trong dấu ngoặc kép `" "`**.
- Nếu trong `answer` có dấu ngoặc kép, hãy biến nó thành 2 dấu ngoặc kép `""` theo chuẩn CSV.

## HƯỚNG DẪN SỬ DỤNG CHO NGƯỜI DÙNG:
Bất cứ khi nào có file tài liệu mới, bạn chỉ cần ném file đó vào đoạn chat và gọi: *"Dùng skill ZeoFaqFormatter chuyển file này thành CSV cho tôi"*. Hệ thống sẽ tự động đọc, chia nhỏ ý và tạo ra file CSV chuẩn chỉnh nhất!
