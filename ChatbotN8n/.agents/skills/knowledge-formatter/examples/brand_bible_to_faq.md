# Brand Bible → FAQ Conversion Guide

Đây là ví dụ cách chuyển tài liệu **Brand Bible / Tone of Voice** (thường dài, không có Q&A)
thành các entry FAQ dùng được cho chatbot.

---

## Nguyên tắc chuyển đổi

Brand Bible thường chứa:
- Thông tin sản phẩm / USP (Unique Selling Points)
- Giá trị thương hiệu
- Đối tượng khách hàng mục tiêu
- Tone giọng văn

→ Từ đây, đặt câu hỏi: **"Khách hàng sẽ hỏi gì về điều này?"**

---

## Ví dụ chuyển đổi

### Input (đoạn từ Brand Bible):

```
ZeO là thương hiệu chăm sóc cá nhân cao cấp của Công ty CFC.
Sản phẩm ZeO được sản xuất tại nhà máy đạt chuẩn ISO 22716,
sử dụng nguyên liệu nhập khẩu từ Châu Âu và Hàn Quốc.
USP: không paraben, không SLS, thân thiện với da nhạy cảm.
Đối tượng: nữ 25-45 tuổi, quan tâm đến skincare tự nhiên.
```

### Output (knowledge entries):

```markdown
## product_origin

**question_examples:**
- Sản phẩm ZeO sản xuất ở đâu?
- ZeO có phải hàng Việt Nam không?
- Nhà máy ZeO đạt chuẩn gì?
- ZeO có chứng nhận gì không?

**answer:**
Dạ sản phẩm ZeO được sản xuất tại nhà máy đạt chuẩn ISO 22716 bạn ơi,
dùng nguyên liệu nhập khẩu từ Châu Âu và Hàn Quốc nha.

---

## product_ingredients

**question_examples:**
- Sản phẩm có paraben không?
- ZeO có SLS không?
- Dùng được cho da nhạy cảm không?
- Thành phần có an toàn không?
- Da nhạy cảm dùng được không?

**answer:**
Dạ sản phẩm ZeO không chứa paraben và SLS bạn ơi,
an toàn cho da nhạy cảm nha.
```

---

## Checklist khi xử lý Brand Bible

- [ ] Trích xuất: tên thương hiệu, xuất xứ, chứng nhận, thành phần đặc biệt
- [ ] Trích xuất: USP (điểm khác biệt so với đối thủ)
- [ ] Trích xuất: đối tượng khách hàng
- [ ] Trích xuất: các sản phẩm/dòng sản phẩm cụ thể
- [ ] Tự đặt câu hỏi từ góc độ khách hàng cho mỗi thông tin
- [ ] KHÔNG đưa vào: nội dung nội bộ, chiến lược giá, thông tin cạnh tranh
- [ ] Category nên đặt là `brand` hoặc `product` (không phải `faq`)
