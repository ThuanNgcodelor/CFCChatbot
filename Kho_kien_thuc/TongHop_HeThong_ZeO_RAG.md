# TỔNG HỢP KIẾN TRÚC HỆ THỐNG ZEO RAG CHATBOT

Hệ thống Chatbot RAG của bạn bao gồm **2 luồng quy trình (workflow)** tách biệt nhau, không gọi trực tiếp cho nhau mà giao tiếp thông qua một "cái cầu nối" là **Google Sheets**.

---

## 1. Luồng Học Kiến Thức (zeo_knowledge_sync_basic.workflow.ts)

**Mục đích:** Đóng gói toàn bộ kiến thức rời rạc thành một "bộ não nén" cho AI đọc siêu nhanh.

**Luồng dữ liệu đi như thế nào?**
1. **Lấy từ đâu:** Từ Tab `FAQ` trong Google Sheets (đây là nơi con người nhập liệu).
2. **Lọc dữ liệu (Node Normalize Knowledge):** 
   - Chỉ lấy những dòng có chữ `TRUE` ở cột `active`.
   - Vứt bỏ các thương hiệu không liên quan (như `CFC`). Chỉ giữ `ZeO, PANO, Oplus`.
   - Gom tất cả các dòng đạt chuẩn lại thành 1 cục dữ liệu nguyên khối (JSON).
3. **Đẩy đi đâu:** Ghi đè cục dữ liệu nguyên khối đó vào Tab `KnowledgeSnapshot` trong Google Sheets với mã nhận diện là `zeo_kb_basic_v1`.
4. **Khi nào chạy:** Nó tự động chạy ngầm mỗi 30 phút một lần, hoặc bạn bấm nút Execute bằng tay.

---

## 2. Luồng Trả Lời Khách Hàng (zeo_chatbot.workflow.ts)

**Mục đích:** Bắt tin nhắn khách hàng, lôi "bộ não nén" ra tra cứu và nhờ AI soạn câu trả lời.

**Luồng dữ liệu đi như thế nào?**
1. **Lấy tin nhắn:** Node `Messenger Trigger` hứng tin nhắn từ Facebook khách gửi tới. Nó cũng lấy tên khách hàng để xưng hô.
2. **Lấy bộ não:** Ngay lập tức, node `Get Knowledge Snapshot` nhảy vào Google Sheets (Tab `KnowledgeSnapshot`) kéo cái cục dữ liệu `zeo_kb_basic_v1` về bộ nhớ tạm thời của n8n.
3. **Tìm kiếm (Node RAG Tìm Kiếm):**
   - Đem câu hỏi của khách hàng đi "chấm điểm" (score) với từng dòng trong bộ não.
   - Nó bóc tách từng chữ, bỏ dấu tiếng Việt, so sánh từ khóa. 
   - Câu nào trong bộ não đạt từ **12 điểm trở lên** thì được bốc ra làm "tài liệu tham khảo".
4. **Hàng rào bảo vệ (Router Guardrail):**
   - Rà quét xem câu hỏi của khách có chứa từ cấm không (`phân bón, NPK, cò bay`...).
   - Nếu có từ cấm -> Dừng ngay lập tức, bẻ lái sang node `Nhắn Khách Fallback` để báo câu mặc định *"Admin sẽ hỗ trợ..."*.
5. **Đẩy cho AI (Node Gọi Ollama Local):**
   - Nếu câu hỏi an toàn, hệ thống ném **Tài liệu tham khảo + Câu hỏi của khách** cho AI Ollama đọc.
   - Ollama bị ép theo bộ luật thép: *"Chỉ lấy thông tin trong tài liệu, xưng hô mình-bạn, không dài dòng"*.
   - Ollama nhả ra câu trả lời cuối cùng.
6. **Đầu ra (Node Nhắn Khách Auto):** Đẩy câu trả lời mượt mà đó về lại Messenger.

---

## TÓM LẠI
- Bạn hoặc nhân viên chỉ cần quan tâm Tab `FAQ`. Cứ có gì mới thì điền vào đó.
- Cứ 30 phút, **Workflow Sync** sẽ tự động gom rác, dọn dẹp, đóng gói đẩy sang Tab `KnowledgeSnapshot`.
- Khi khách chat, **Workflow Chatbot** chỉ việc bốc Tab `KnowledgeSnapshot` ra cho AI đọc. Việc tách rời này giúp Chatbot chạy cực kỳ nhanh vì không phải đọc từng dòng Excel mỗi khi có người chat.
