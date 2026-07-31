# ZeO RAG - Kịch bản test CSV tổng hợp 2026-07-31

Nguồn kiểm thử: `Zeo_FAQ_Tong_Hop_2026-07-31.csv` (65 dòng `active=TRUE`).

## 1. Chuẩn bị trước khi test

1. Trong tab `FAQ`, thay thế bộ 15 dòng cũ bằng toàn bộ 65 dòng của CSV mới. Không để hai bộ cùng active vì các intent cũ và mới có thể cùng chấm điểm, làm kết quả khó đoán.
2. Giữ nguyên hàng tiêu đề 9 cột: `active, brand, category, intent, question_examples, answer, priority, source_id, updated_at`.
3. Chạy thủ công workflow `Zeo Knowledge Sync Basic`.
4. Mở tab `KnowledgeSnapshot` và kiểm tra `updated_at` vừa thay đổi.

### Kết quả snapshot mong đợi

- Theo mã Sync hiện tại: `knowledge_count = 64`.
- CSV có 65 dòng, nhưng dòng `floor_cleaner_features` mang brand `ZeO/Oplus`. Whitelist hiện chỉ nhận `ZeO`, `PANO`, `Oplus` và `ZeO/PANO/Oplus`, nên dòng này sẽ bị lọc khỏi snapshot.
- Vì vậy, câu hỏi về nước lau sàn ở phần 5 được kỳ vọng fallback. Nếu `knowledge_count = 65` và câu này trả lời được, workflow live của bạn đã khác hoặc đã được sửa whitelist.

## 2. Cách đánh giá kết quả

| Kết quả mong đợi | Ý nghĩa |
| --- | --- |
| `AI` | Bot gọi Ollama. Câu trả lời có thể khác câu trong CSV về câu chữ, nhưng phải giữ đúng thông tin cốt lõi. |
| `Fallback` | Bot không được gọi Ollama; phản hồi bằng tin nhắn chuyển admin. |
| `Không phản hồi` | Webhook nhận tin không phải text, workflow dừng ngay. |

Khi test một câu `AI`, kiểm tra ba điểm: đúng chủ đề, không tự thêm giá/khuyến mãi/chính sách ngoài CSV, và không lẫn brand khác.

## 3. Smoke test - dữ liệu cơ bản

| # | Gửi cho Messenger | Kết quả | Cần có trong trả lời |
| --- | --- | --- | --- |
| 1 | `Shop mở cửa lúc mấy giờ?` | AI | `8:00` đến `21:00` |
| 2 | `Shop có hỗ trợ COD không?` | AI | giao toàn quốc, **không** COD |
| 3 | `Mua sản phẩm ZeO online ở đâu?` | AI | `bitly.li/Arva` hoặc `1900 5307` nhánh `02` |
| 4 | `Tôi muốn đăng ký làm đại lý` | AI | xin số điện thoại và khu vực |
| 5 | `Admin hỗ trợ mình với` | AI | hỏi thêm vấn đề cần hỗ trợ |
| 6 | `Không biết nên chọn sản phẩm nào` | AI | hỏi nhu cầu/sản phẩm cần tư vấn |
| 7 | `Địa chỉ công ty ở đâu?` | AI | KCN Trà Nóc 1, Cần Thơ |
| 8 | `Công ty được thành lập khi nào?` | AI | năm `1977` |
| 9 | `Slogan của PANO là gì?` | AI | `Nâng niu cảm xúc` |
| 10 | `Tính cách thương hiệu là gì?` | AI | ấm áp, đáng tin cậy hoặc có trách nhiệm |
| 11 | `ZeO nên xưng hô với khách thế nào?` | AI | `mình`, `bạn`; ngắn và rõ |
| 12 | `Bột giặt ZeO dùng công nghệ gì?` | AI | Enzyme Thụy Điển |
| 13 | `Bột giặt ZeO có chứng nhận gì?` | AI | Viện Pasteur / phòng thí nghiệm Singapore |
| 14 | `Nước rửa chén ZeO có thành phần gì?` | AI | nước cốt chanh tự nhiên |
| 15 | `Tẩy Toilet ZeO có diệt khuẩn không?` | AI | `99,9%`, khử mùi/cặn vôi |
| 16 | `Lau Kính ZeO dùng cho bề mặt nào?` | AI | kính, gương hoặc màn hình |
| 17 | `Bột giặt Oplus dùng công nghệ gì?` | AI | công nghệ ION |
| 18 | `PANO có những mùi hương nào?` | AI | Đỏ, Xanh, Hồng, Cam, Tím |
| 19 | `Công nghệ VEILEX có tác dụng gì?` | AI | khử mùi, vải thể thao/đồ trẻ em |
| 20 | `Xịt tẩy đa năng PANO dùng cho đâu?` | AI | bếp, lavabo, gạch hoặc bồn tắm |
| 21 | `Khách da nhạy cảm nên tư vấn gì?` | AI | công thức dịu nhẹ |

## 4. Test chính sách và CSKH

Các dòng chính sách đã nằm trong CSV. Tuy nhiên guardrail đầu vào sẽ chuyển admin khi tin nhắn chứa nguyên cụm `đổi trả`, `hoàn tiền`, `khiếu nại`, `lừa đảo`, `sản phẩm lỗi` hoặc `hàng giả`.

| # | Gửi cho Messenger | Kết quả | Mục đích |
| --- | --- | --- | --- |
| 22 | `Hàng bị lỗi có được đổi không?` | AI | Kiểm tra `return_eligible_cases`; cần nêu các trường hợp được xem xét. |
| 23 | `Lỗi vận chuyển phải báo khi nào?` | AI | Kiểm tra mốc `24 giờ`. |
| 24 | `Đổi hàng lỗi bắt đầu từ đâu?` | AI | Kiểm tra quy trình: hotline/ảnh/video, xác nhận trong 24 giờ. |
| 25 | `Bao lâu thì nhận được tiền hoàn?` | AI | Kiểm tra thời gian tối đa 5 ngày làm việc. |
| 26 | `Sản phẩm bị rò rỉ thì làm sao?` | AI | Kiểm tra yêu cầu ảnh và số lô. |
| 27 | `Giặt không sạch như mong đợi thì xử lý thế nào?` | AI | Kiểm tra hỏi thêm sản phẩm/liều lượng/máy giặt. |
| 28 | `Chính sách đổi trả như thế nào?` | Fallback | Có cụm `đổi trả`; không đánh giá đây là lỗi RAG. |
| 29 | `Tôi muốn hoàn tiền` | Fallback | Có cụm `hoàn tiền`. |
| 30 | `Tôi muốn khiếu nại sản phẩm` | Fallback | Có cụm `khiếu nại`. |

## 5. Test dữ liệu có giới hạn hiện tại

| # | Gửi cho Messenger | Kết quả | Lý do |
| --- | --- | --- | --- |
| 31 | `Nước lau sàn ZeO có đậm đặc không?` | Fallback | Dòng CSV dùng brand `ZeO/Oplus`, hiện bị Sync lọc khỏi snapshot. |
| 32 | `Hello shop` | Fallback | CSV mới không có intent chào hỏi. |
| 33 | `Cho tui xin dja chj` | Fallback | Scoring hiện không sửa teencode `dja chj`; chỉ có bỏ dấu và so khớp từ. |

## 6. Edge cases - RAG vẫn phải tìm đúng

| # | Gửi cho Messenger | Kết quả | Cần có trong trả lời |
| --- | --- | --- | --- |
| 34 | `shop mo cua may gio` | AI | `8:00` đến `21:00` |
| 35 | `MÌNH MUỐN LÀM ĐẠI LÝ` | AI | xin số điện thoại và khu vực |
| 36 | `Ship với COD được không?` | AI | có giao hàng, không COD |
| 37 | `Bột giặt ZeO có thơm lâu không?` | AI | hương nước hoa/lưu hương |
| 38 | `Nước rửa chén Oplus có làm khô da không?` | AI | dịu nhẹ, không gây khô da |
| 39 | `Công ty có hotline chung không?` | AI | `0907 902 546` theo Brand Bible |
| 40 | `Nên trả lời review xấu như thế nào?` | AI | cảm ơn, không tranh luận, giải quyết vấn đề |

## 7. Guardrail bắt buộc

Mỗi trường hợp dưới đây phải `Fallback`, không gọi Ollama.

| # | Gửi cho Messenger | Lý do chặn |
| --- | --- | --- |
| 41 | `Bên shop có bán phân bón Cò Bay không?` | `phân bón` / `cò bay` ngoài phạm vi |
| 42 | `Cho mình hỏi phân bón NPK giá bao nhiêu?` | `phân bón` / `NPK` ngoài phạm vi |
| 43 | `Có phân hữu cơ không?` | ngoài phạm vi |
| 44 | `Sản phẩm lỗi, tôi muốn hoàn tiền` | nhạy cảm |
| 45 | `Shop lừa đảo à, bán hàng giả` | nhạy cảm |
| 46 | Chỉ gửi emoji `👍` | Không phản hồi: không có text |

## 8. Regression - các nhóm dữ liệu còn lại

Chạy tối thiểu một câu trong mỗi nhóm dưới đây sau khi smoke test đạt.

| Nhóm CSV | Câu test gợi ý | Kết quả |
| --- | --- | --- |
| Templates CSKH | `Có mẫu hỏi thăm khách sau mua hàng không?` | AI, có placeholder `[Tên Sản Phẩm]` và mốc 3 ngày |
| Khuyến mãi mẫu | `Có mẫu thông báo khuyến mãi không?` | AI, chỉ là mẫu có placeholder, không phải khuyến mãi đang chạy |
| Tầm nhìn/sứ mệnh | `Sứ mệnh của công ty là gì?` | AI, sản phẩm tẩy rửa an toàn, thân thiện môi trường |
| Quy tắc thương hiệu | `Có được so sánh trực tiếp với đối thủ không?` | AI, không nên |
| Nội dung TikTok | `Video Reels nên mở đầu thế nào?` | AI, hook mạnh trong 3 giây đầu |
| Mô tả Shopee/Tiki | `Có nên viết in hoa toàn bộ mô tả không?` | AI, không nên |
| Email/Zalo Business | `Email CSKH nên viết theo giọng nào?` | AI, chuyên nghiệp nhưng ấm áp |
| PANO Vitamin E | `Nước rửa chén PANO Vitamin E có tác dụng gì?` | AI, dưỡng ẩm/bảo vệ da tay |
| Tẩy Màu ZeO | `Quần áo trắng bị ố vàng dùng sản phẩm nào?` | AI, Tẩy Màu ZeO |
| Javen ZeO | `Tẩy Javen ZeO có công dụng gì?` | AI, tẩy trắng/diệt khuẩn |
| Điểm bán hàng | `Vì sao nên chọn PANO ZeO Oplus?` | AI, lịch sử thương hiệu, công nghệ, đa dạng nhu cầu |

## 9. Ghi kết quả

Ghi lại số test, câu gửi, câu bot trả lời, `AI/Fallback/Không phản hồi` và nhận xét. Nếu một câu ở phần `AI` bị fallback, kiểm tra lần lượt: `knowledge_count`, giá trị `brand`, cột `active`, dấu chấm phẩy trong `question_examples`, rồi mới kiểm tra Ollama.
