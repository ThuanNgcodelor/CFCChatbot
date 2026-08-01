# Kế hoạch Nâng cấp Kiến trúc Chatbot ZeO Vietnam

Để giải quyết bài toán mở rộng tri thức (Knowledge Base) linh hoạt bằng Google Sheets và tối ưu hóa tốc độ phản hồi bằng Cache, tôi đề xuất một kiến trúc hệ thống chuyên nghiệp và toàn diện hơn cho Chatbot ZeO Vietnam của bạn.

## Vấn đề hiện tại
- Tri thức (Knowledge Base) đang được hardcode trực tiếp trong Node Code của n8n, gây khó khăn cho việc cập nhật hoặc thêm mới nội dung.
- Quá trình xử lý (RAG - Retrieval-Augmented Generation) hiện tại chỉ dùng thuật toán so sánh từ khóa đơn giản, không hiểu được ý nghĩa ngữ nghĩa (semantic search) của câu hỏi.
- Mọi câu hỏi đều phải gọi sang Ollama (AI model), khiến thời gian phản hồi bị chậm (độ trễ lớn) và tốn tài nguyên máy chủ.

## Kiến trúc Đề xuất Mới

Chúng ta sẽ chia hệ thống thành 2 luồng (Workflow) riêng biệt để dễ quản lý:

### Luồng 1: Đồng bộ Tri thức (Knowledge Ingestion Workflow)
Luồng này có nhiệm vụ đọc dữ liệu từ Google Sheets, chia nhỏ (split text), mã hóa (embed) và lưu trữ vào cơ sở dữ liệu véc-tơ (Vector DB).

1. **Google Sheets Trigger/Node**: Đọc định kỳ hoặc tự động kích hoạt khi có cập nhật mới trong file Google Sheets chứa các cặp Q&A hoặc tài liệu sản phẩm.
2. **Text Splitter (LangChain/LlamaIndex Node)**: Cắt dữ liệu thô thành các đoạn văn bản (chunks) vừa phải để AI dễ hiểu.
3. **Embeddings Node**: Dùng model nhúng (ví dụ: `nomic-embed-text` qua Ollama hoặc OpenAI) để chuyển đổi văn bản thành các véc-tơ số học.
4. **Vector Database Node**: Lưu trữ véc-tơ vào các DB chuyên dụng như Qdrant, Pinecone hoặc Supabase. (n8n hỗ trợ sẵn rất nhiều Vector Store nodes).

### Luồng 2: Xử lý Tin nhắn có Cache (Chatbot Workflow)
Luồng này tiếp nhận tin nhắn từ Facebook, kiểm tra bộ nhớ đệm (Redis), nếu không có mới tìm kiếm trong Vector DB và gọi AI.

1. **Facebook Messenger Trigger**: Nhận tin nhắn của người dùng.
2. **Redis Read Node**: Kiểm tra xem câu hỏi này (hoặc câu hỏi có ý nghĩa tương tự) đã từng được AI trả lời và lưu trong Cache chưa.
   - **Cache HIT**: Trả lời ngay lập tức bằng dữ liệu trong Redis (tốc độ < 100ms), bỏ qua Ollama.
   - **Cache MISS**: Chuyển sang bước RAG.
3. **Vector Store Search**: Nhúng câu hỏi của người dùng thành véc-tơ và tìm kiếm tài liệu liên quan nhất trong Vector DB (Qdrant/Pinecone).
4. **Ollama Chat Node**: Đưa câu hỏi và tài liệu (Context) tìm được vào Prompt để AI (minimax-m3:cloud) suy luận ra câu trả lời chuẩn xác.
5. **Redis Write Node**: Lưu câu trả lời vừa sinh ra vào Redis (kèm thời gian sống - TTL ví dụ 24h) để tái sử dụng cho các khách hàng hỏi câu tương tự.
6. **Facebook API Node**: Trả tin nhắn về cho người dùng.

> [!TIP]
> Việc áp dụng Redis (Cache) sẽ giúp giảm đến 60-70% số lượng request đẩy sang mô hình AI, giúp tăng tốc độ phản hồi cực kỳ đáng kể, làm khách hàng cảm thấy bot trả lời "tức thì".

> [!NOTE]
> Việc dùng Vector Database thay vì dò Keyword sẽ giúp bot nhận diện được ý định dù khách hàng dùng từ đồng nghĩa hoặc gõ sai chính tả nhẹ (Semantic Search).

## Open Questions

Dưới đây là một số thông tin tôi cần bạn quyết định để có thể bắt tay vào triển khai:

> [!IMPORTANT]
> 1. **Cơ sở dữ liệu Véc-tơ (Vector DB)**: Bạn muốn sử dụng dịch vụ đám mây miễn phí như **Pinecone**, hay muốn tự cài một DB nội bộ trên server (như **Qdrant** hoặc Postgres pgvector)?
> 2. **Redis**: Máy chủ (hoặc máy tính local) của bạn hiện tại đã được cài đặt Redis chưa? Nếu chưa, bạn có sẵn sàng cài đặt thêm nó qua Docker không?
> 3. **Google Sheets**: Bạn có sẵn một file Google Sheets Q&A chưa? (Nên chia thành 2 cột: Cột A chứa danh sách câu hỏi / từ khóa, Cột B chứa câu trả lời chuẩn).

## Kế hoạch Thực thi (Verification Plan)
- **Giai đoạn 1**: Thiết lập Google Sheets và kết nối nó vào n8n, đẩy dữ liệu thử nghiệm.
- **Giai đoạn 2**: Cấu hình Vector DB (Pinecone/Qdrant) và Node tạo Embeddings qua Ollama. Xây dựng Luồng 1.
- **Giai đoạn 3**: Thiết lập Redis và viết logic Cache HIT/MISS cho Luồng 2.
- **Giai đoạn 4**: Ghép nối lại với mô hình `minimax-m3` và Facebook Messenger. Chạy thử nghiệm thực tế nghiệm thu.

Vui lòng cho tôi biết lựa chọn của bạn về **Vector DB** và **Redis** để chúng ta bắt đầu!
