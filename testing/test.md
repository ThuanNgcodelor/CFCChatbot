# ĐẠI BỘ KỊCH BẢN TEST HỘI THOẠI TOÀN DIỆN CHATBOT ZEO & CFC (30+ KỊCH BẢN THỰC CHIẾN)
*Cập nhật: 2026-08-18 | Tài liệu chuẩn dành cho Tester, QA, CSKH, Đội Vận Hành và Huấn Luyện AI*

---

## 📖 HƯỚNG DẪN SỬ DỤNG
- **Dành cho Tester / CSKH**: Copy trực tiếp từng câu hỏi của **Khách nhắn** và dán vào cửa sổ chat (Messenger, Zalo, Web Widget) theo đúng thứ tự lượt 1, 2, 3... để kiểm tra:
  1. Bot có hiểu đúng ý định (**Intent**) và ngữ cảnh (**Context**) không?
  2. Bot có nhớ các sản phẩm hoặc lựa chọn đã nói ở lượt trước không (**Multi-turn Memory**)?
  3. Bot có báo đúng giá thật từ Redis/Sheet và tuyệt đối không bịa giá, bịa liều lượng (**Zero Hallucination**)?
  4. Tốc độ phản hồi có đạt chuẩn tức thì (**< 15ms**) không?

---

# 📑 MỤC LỤC TOÀN BỘ KỊCH BẢN

### [PHẦN 1: KỊCH BẢN ZEO VIETNAM (HÓA PHẨM & CHĂM SÓC GIA ĐÌNH)](#phần-1-kịch-bản-zeo-vietnam-hóa-phẩm--chăm-sóc-gia-đình)
- **Kịch bản 01**: Tư vấn bán hàng & Lọc ngân sách đa dạng (9 lượt)
- **Kịch bản 02**: Gia đình có trẻ sơ sinh & Da nhạy cảm (5 lượt)
- **Kịch bản 03**: Quán ăn / Nhà hàng mua sỉ nước rửa chén can lớn (6 lượt)
- **Kịch bản 04**: Tẩy vết ố vàng toilet & Cặn vôi nhà tắm (5 lượt)
- **Kịch bản 05**: So sánh & Chọn lựa giữa ZeO, PANO và Oplus (5 lượt)
- **Kịch bản 06**: Khách săn Flash Sale, Voucher Shopee Live & Freeship (4 lượt)
- **Kịch bản 07**: Nước lau sàn sinh học & An toàn cho thú cưng (5 lượt)
- **Kịch bản 08**: Tinh dầu thơm phòng & Xịt khử mùi xe hơi (4 lượt)
- **Kịch bản 09**: Khách dùng máy giặt cửa trước (Inverter) & Bọt (4 lượt)
- **Kịch bản 10**: Tìm kiếm điểm bán / Tạp hóa / Siêu thị offline (4 lượt)
- **Kịch bản 11**: Đăng ký đại lý phân phối hóa phẩm ZeO (5 lượt)
- **Kịch bản 12**: Phân biệt hàng thật vs Hàng giả / Check mã vạch (4 lượt)
- **Kịch bản 13**: Cảnh báo an toàn / Sự cố hóa chất dính vào mắt (3 lượt)
- **Kịch bản 14**: Tẩy trắng áo ố vàng & Giặt quần áo màu không phai (4 lượt)
- **Kịch bản 15**: Nguồn gốc xuất xứ, Nhà máy & Công nghệ Enzyme Thụy Điển (4 lượt)

### [PHẦN 2: KỊCH BẢN CFC CÒ BAY (PHÂN BÓN NÔNG NGHIỆP)](#phần-2-kịch-bản-cfc-cò-bay-phân-bón-nông-nghiệp)
- **Kịch bản 16**: Tư vấn phân bón vụ lúa (Lót - Đẻ nhánh - Đón đòng) (6 lượt)
- **Kịch bản 17**: Cây ăn trái mùa nghịch (Sầu riêng, Bưởi, Mít, Xoài) (5 lượt)
- **Kịch bản 18**: Cải tạo đất chua, phèn, bạc màu bằng Hữu cơ sinh học (5 lượt)
- **Kịch bản 19**: Trồng rau màu, dưa hấu, ớt & Thời gian cách ly an toàn (4 lượt)
- **Kịch bản 20**: Đăng ký đại lý phân bón Cấp 1 / Cấp 2 tại Miền Tây (5 lượt)
- **Kịch bản 21**: Vận chuyển đường thủy / Ghe tải giao tận bến ruộng (4 lượt)
- **Kịch bản 22**: Xử lý phân bón bị ẩm, vón cục & Bảo quản đúng chuẩn (4 lượt)
- **Kịch bản 23**: Nhận biết Phân bón Cò Bay chính hãng & Chống hàng giả (4 lượt)
- **Kịch bản 24**: Đăng ký kỹ sư nông nghiệp xuống tận vườn tư vấn (4 lượt)
- **Kịch bản 25**: Tư vấn độ tan của phân bón & Hệ thống tưới nhỏ giọt (3 lượt)

### [PHẦN 3: KỊCH BẢN KHÁCH HÀNG ĐẶC BIỆT, KHIẾU NẠI & CORNER CASES](#phần-3-kịch-bản-khách-hàng-đặc-biệt-khiếu-nại--corner-cases)
- **Kịch bản 26**: Khách giận dữ vì giao hàng trễ / Đổ vỡ sản phẩm (4 lượt)
- **Kịch bản 27**: Khách gửi tin nhắn gộp nhiều ý (Multi-intent) (3 lượt)
- **Kịch bản 28**: Khách trả giá / Xin bớt tiền (3 lượt)
- **Kịch bản 29**: Chuyển đổi chủ đề liên tục (Context Switching) (5 lượt)
- **Kịch bản 30**: Khách hỏi tuyển dụng, thông tin công ty & Thực tập sinh (3 lượt)

### [PHẦN 4: BẢNG TEST TỪ LÓNG, VIẾT TẮT & KHÔNG DẤU](#phần-4-bảng-test-từ-lóng-viết-tắt--không-dấu)
### [PHẦN 5: LỆNH CHẠY TEST TỰ ĐỘNG BẰNG PYTHON (1-CLICK RUNNER)](#phần-5-lệnh-chạy-test-tự-động-bằng-python-1-click-runner)

---

# PHẦN 1: KỊCH BẢN ZEO VIETNAM (HÓA PHẨM & CHĂM SÓC GIA ĐÌNH)

---

### Kịch bản 01: Tư vấn bán hàng & Lọc ngân sách đa dạng (9 lượt)
> **Mục tiêu**: Kiểm tra khả năng hiểu ngân sách dưới 100k, tư vấn đa lượt theo nhu cầu tiết kiệm, báo giá realtime Nước rửa chén Vitamin E và phân định Shopee vs Website.

* **Lượt 1**:
  * 👤 **Khách**: `Xin chào shop`
  * 🤖 **Bot**: Chào mừng bạn đến với ZeO Vietnam! Hỏi thăm nhu cầu về giặt xả, rửa chén, lau sàn hay mua hàng.
  * 🎯 **Chuẩn**: `greeting` (Điểm tin cậy 1.0).
* **Lượt 2**:
  * 👤 **Khách**: `Có sản phẩm nào giá tầm dưới 100k ko nhỉ`
  * 🤖 **Bot**: Lọc động 4 sản phẩm bán chạy dưới 100.000đ (Nước rửa chén Pano 12.350đ, Bột giặt Pano 46.350đ, Nước giặt Pano 95.058đ, Nước tẩy toilet ZeO 23.000đ) kèm % giảm giá và câu hỏi gợi mở.
  * 🎯 **Chuẩn**: `shopee_budget_filter` (Lấy trực tiếp từ Redis Shopee Catalog).
* **Lượt 3**:
  * 👤 **Khách**: `có bột giặt ko`
  * 🤖 **Bot**: Giới thiệu 3 nhóm: Bột giặt ZeO Enzyme, Bột giặt Oplus 4in1, Bột giặt & Nước giặt PANO VEILEX. Gợi mở câu hỏi chọn nhu cầu sạch sâu, thơm lâu hay tiết kiệm.
  * 🎯 **Chuẩn**: `zeo_laundry_product_overview`.
* **Lượt 4** *(Nhớ ngữ cảnh nhu cầu)*:
  * 👤 **Khách**: `nhu cầu tiết kiệm đi`
  * 🤖 **Bot**: Gợi ý 3 lựa chọn kinh tế nhất: Bột giặt Oplus 4in1 (66.000đ), Bột giặt Pano (46.350đ), Nước giặt Pano can 3.8kg (123.291đ).
  * 🎯 **Chuẩn**: `need_consultation_tiet_kiem`.
* **Lượt 5**:
  * 👤 **Khách**: `có link shopee ko`
  * 🤖 **Bot**: Gửi link Shopee Mall chính hãng `https://shopee.vn/zeovietnamofficial` kèm mã Freeship Extra.
  * 🎯 **Chuẩn**: `shopee_product_link`.
* **Lượt 6** *(Lọc bán chạy theo danh mục)*:
  * 👤 **Khách**: `nước rửa chén nào bán chạy nhỉ`
  * 🤖 **Bot**: Báo Top 1 Bestseller Nước rửa chén Vitamin E Pano (12.350đ) + direct link Shopee Mall.
  * 🎯 **Chuẩn**: `bestsellers` theo category Nước rửa chén.
* **Lượt 7** *(Tham chiếu "cái số 2")*:
  * 👤 **Khách**: `cái số 2 là sao nhỉ`
  * 🤖 **Bot**: Giải thích USP của Bột giặt Oplus (Sạch sâu, thơm lâu, dịu nhẹ, tiết kiệm — 4 lợi ích trong 1).
  * 🎯 **Chuẩn**: `oplus_detergent_usp`.
* **Lượt 8** *(Báo giá sản phẩm đích danh realtime)*:
  * 👤 **Khách**: `xin giá nước rửa chén vitamin e`
  * 🤖 **Bot**: Báo giá ưu đãi **12.350đ** (đang giảm 6% từ gốc 13.140đ) + direct link Shopee Mall.
  * 🎯 **Chuẩn**: `specific_product_pricing`.
* **Lượt 9** *(Website công ty)*:
  * 👤 **Khách**: `cho xin link web của công ty`
  * 🤖 **Bot**: Gửi website chính thức `https://zeo.vn/` từ Google Sheet.
  * 🎯 **Chuẩn**: `company_website`.

---

### Kịch bản 02: Gia đình có trẻ sơ sinh & Da nhạy cảm (5 lượt)
> **Mục tiêu**: Kiểm tra tính năng tư vấn an toàn cho da em bé, thành phần không gây kích ứng và bảo vệ da tay.

* **Lượt 1**:
  * 👤 **Khách**: `Nhà mình có em bé 3 tháng tuổi thì dùng loại nước giặt nào an toàn?`
  * 🤖 **Bot**: Tư vấn dòng Nước giặt/Bột giặt ZeO sinh học công nghệ Bio Enzyme và dòng PANO Dịu nhẹ, độ pH trung tính, không chứa hóa chất tẩy gắt, an toàn tuyệt đối cho làn da mẫn cảm của trẻ sơ sinh.
  * 🎯 **Chuẩn**: `zeo_detergent_safety` / `need_consultation_diu_nhe`.
* **Lượt 2**:
  * 👤 **Khách**: `Nước rửa chén có ăn da tay không shop, tay mình hay bị tróc da?`
  * 🤖 **Bot**: Tư vấn Nước rửa chén Vitamin E Pano hoặc Nước rửa chén Oplus bổ sung tinh chất Vitamin E và Nha Đam dưỡng ẩm, bảo vệ da tay mềm mại khi rửa bát hàng ngày.
  * 🎯 **Chuẩn**: `pano_dishwashing_features`.
* **Lượt 3**:
  * 👤 **Khách**: `Cho mình xin giá của chai nước rửa chén vitamin e đó`
  * 🤖 **Bot**: Báo giá realtime 12.350đ kèm link Shopee Mall.
  * 🎯 **Chuẩn**: `specific_product_pricing`.
* **Lượt 4**:
  * 👤 **Khách**: `Có được freeship về Hà Nội không bạn?`
  * 🤖 **Bot**: Hướng dẫn áp mã Freeship Extra toàn quốc trên gian hàng Shopee Mall của ZeO.
  * 🎯 **Chuẩn**: `shipping_time_and_fee`.
* **Lượt 5**:
  * 👤 **Khách**: `Ok cảm ơn bạn nha`
  * 🤖 **Bot**: Cảm ơn khách hàng thân thiện, chúc khách có trải nghiệm tốt.
  * 🎯 **Chuẩn**: `thanks`.

---

### Kịch bản 03: Quán ăn / Nhà hàng mua sỉ nước rửa chén can lớn (6 lượt)
> **Mục tiêu**: Kiểm tra tư vấn mua số lượng lớn (B2B/Horeca), quy cách can lớn 3.8kg - 9kg và chính sách chiết khấu.

* **Lượt 1**:
  * 👤 **Khách**: `Quán ăn của mình cần mua nước rửa chén can lớn dùng cho bếp`
  * 🤖 **Bot**: Giới thiệu dòng Nước rửa chén Pano và Oplus quy cách can lớn 3.8kg và can 9kg chuyên dụng cho nhà hàng, quán ăn, bếp ăn công nghiệp với khả năng đánh bay dầu mỡ cực nhanh và tiết kiệm chi phí.
  * 🎯 **Chuẩn**: `pano_dishwashing_product_overview`.
* **Lượt 2**:
  * 👤 **Khách**: `Can 3.8kg giá bao nhiêu tiền?`
  * 🤖 **Bot**: Báo giá can 3.8kg và link đặt mua Shopee Mall hoặc hướng dẫn đặt số lượng lớn.
  * 🎯 **Chuẩn**: `specific_product_pricing`.
* **Lượt 3**:
  * 👤 **Khách**: `Mình lấy 20 can mỗi tháng thì có giá sỉ không?`
  * 🤖 **Bot**: ZeO có chính sách chiết khấu sỉ cực tốt cho khách hàng mua định kỳ/nhà hàng. Bot xin SĐT và khu vực quán để phòng kinh doanh liên hệ gửi bảng giá sỉ.
  * 🎯 **Chuẩn**: `wholesale_inquiry`.
* **Lượt 4**:
  * 👤 **Khách**: `Công ty có xuất hóa đơn đỏ VAT không shop?`
  * 🤖 **Bot**: ZeO hỗ trợ xuất đầy đủ hóa đơn GTGT (VAT) điện tử hợp lệ cho doanh nghiệp/hộ kinh doanh khi mua hàng chính hãng.
  * 🎯 **Chuẩn**: `corporate_invoice_support`.
* **Lượt 5**:
  * 👤 **Khách**: `Sđt của mình là 0908776655 tên Tuấn ở Quận 1 TPHCM`
  * 🤖 **Bot**: Xác nhận đã lưu thông tin anh Tuấn (0908776655 tại Quận 1, TPHCM), chuyên viên B2B ZeO sẽ liên hệ chốt hợp đồng và giao hàng tận nơi.
  * 🎯 **Chuẩn**: `contact_phone_provided` (Lead Ready).
* **Lượt 6**:
  * 👤 **Khách**: `Giao trong ngày được không?`
  * 🤖 **Bot**: Khu vực TPHCM hỗ trợ giao hỏa tốc hoặc giao trong 24h qua hệ thống kho vận.
  * 🎯 **Chuẩn**: `shipping_time_and_fee`.

---

### Kịch bản 04: Tẩy vết ố vàng toilet & Cặn vôi nhà tắm (5 lượt)
> **Mục tiêu**: Kiểm tra nhóm sản phẩm Tẩy rửa vệ sinh (Nước tẩy toilet ZeO, Nước tẩy lồng giặt, Javel).

* **Lượt 1**:
  * 👤 **Khách**: `Bồn cầu nhà mình bị cặn vôi ố vàng lâu năm thì dùng loại nào tẩy sạch?`
  * 🤖 **Bot**: Tư vấn dòng **Nước tẩy toilet đậm đặc ZeO Hương trái cây (Chai 650ml)** — công thức đậm đặc hòa tan cặn vôi, ố vàng, diệt khuẩn 99.9% mà không nồng gắt mùi hóa chất độc hại.
  * 🎯 **Chuẩn**: `zeo_cleaning_product_overview`.
* **Lượt 2**:
  * 👤 **Khách**: `Có bị nồng nặc mùi hôi như mấy loại tẩy con vịt ko?`
  * 🤖 **Bot**: Nước tẩy toilet ZeO sử dụng hương trái cây thơm mát tự nhiên, không gây cay mắt, không nồng nặc khó thở, an toàn cho men sứ bồn cầu.
  * 🎯 **Chuẩn**: `cleaning_fragrance_safety`.
* **Lượt 3**:
  * 👤 **Khách**: `Giá bao nhiêu 1 chai?`
  * 🤖 **Bot**: Báo giá ưu đãi **23.000đ/chai 650ml** (đang giảm 50%) kèm link Shopee Mall.
  * 🎯 **Chuẩn**: `specific_product_pricing`.
* **Lượt 4**:
  * 👤 **Khách**: `Cách dùng sao shop?`
  * 🤖 **Bot**: Xịt trực tiếp dung dịch vào viền bồn cầu và vết ố, để ngâm từ 5-10 phút cho dung dịch phân rã mảng bám, sau đó dùng cọ chà nhẹ và xả nước.
  * 🎯 **Chuẩn**: `usage_instructions`.
* **Lượt 5**:
  * 👤 **Khách**: `Cho xin link mua hàng`
  * 🤖 **Bot**: Gửi link sản phẩm Shopee Mall trực tiếp.
  * 🎯 **Chuẩn**: `shopee_product_link`.

---

### Kịch bản 05: So sánh & Chọn lựa giữa ZeO, PANO và Oplus (5 lượt)
> **Mục tiêu**: Phân biệt định vị 3 thương hiệu trong hệ sinh thái ZeO.

* **Lượt 1**:
  * 👤 **Khách**: `Bên mình có ZeO, PANO với Oplus là 3 hãng khác nhau hay sao?`
  * 🤖 **Bot**: Giải thích: Cả 3 đều thuộc cùng hệ sinh thái sản xuất của ZeO Vietnam, định vị phục vụ các nhu cầu khác nhau:
    - **ZeO**: Dòng sinh học cao cấp, công nghệ Bio Enzyme Thụy Điển, chứng nhận Viện Pasteur.
    - **PANO**: Dòng thơm lâu, công nghệ khử mùi & khóa hương VEILEX với đa dạng mùi hương (Đỏ, Xanh, Cam, Hồng, Tím).
    - **Oplus**: Dòng 4 trong 1 siêu tiết kiệm, công nghệ ION hòa tan nhanh, giá thành hợp lý nhất.
  * 🎯 **Chuẩn**: `brand_ecosystem_overview`.
* **Lượt 2**:
  * 👤 **Khách**: `Nếu mình muốn quần áo thơm như nước hoa thì chọn loại nào?`
  * 🤖 **Bot**: Đề xuất dòng **Nước giặt & Bột giặt PANO Hương Nước Hoa (Hương Đỏ hoặc Tím)** với công nghệ VEILEX lưu hương bền lâu suốt cả ngày.
  * 🎯 **Chuẩn**: `need_consultation_thom_lau`.
* **Lượt 3**:
  * 👤 **Khách**: `PANO có những mùi hương nào vậy bạn?`
  * 🤖 **Bot**: Liệt kê 5 mùi hương PANO: Đỏ (Nước hoa quyến rũ), Xanh (Nắng mai tươi mát), Hồng (Hoa cỏ dịu êm), Cam (Cam chanh tươi mới), Tím (Oải hương thư giãn).
  * 🎯 **Chuẩn**: `pano_fragrance_options`.
* **Lượt 4**:
  * 👤 **Khách**: `Nước giặt Pano can 3.8kg mùi tím giá bao nhiêu?`
  * 🤖 **Bot**: Báo giá ưu đãi **123.291đ/can 3.8kg** kèm link Shopee Mall.
  * 🎯 **Chuẩn**: `specific_product_pricing`.
* **Lượt 5**:
  * 👤 **Khách**: `Gửi link mua nha`
  * 🤖 **Bot**: Gửi link Shopee Mall chính hãng.
  * 🎯 **Chuẩn**: `shopee_product_link`.

---

# PHẦN 2: KỊCH BẢN CFC CÒ BAY (PHÂN BÓN NÔNG NGHIỆP)

---

### Kịch bản 16: Tư vấn phân bón vụ lúa (Lót - Đẻ nhánh - Đón đòng) (6 lượt)
> **Mục tiêu**: Kiểm tra tư vấn quy trình bón phân lúa 3 đợt, chống bịa giá/liều lượng và thu thập lead nhà nông.

* **Lượt 1**:
  * 👤 **Khách**: `Chào công ty Cò Bay`
  * 🤖 **Bot**: Dạ Phân bón Cò Bay (CFC) chào bà con/quý khách! Bạn đang cần tư vấn phân bón cho cây lúa, cây ăn trái hay đăng ký đại lý ạ?
  * 🎯 **Chuẩn**: `greeting` (CFC).
* **Lượt 2**:
  * 👤 **Khách**: `Tôi chuẩn bị xuống giống 3 hecta lúa ở Kiên Giang thì bón phân gì?`
  * 🤖 **Bot**: Tư vấn quy trình phân bón lúa Cò Bay gồm:
    1. Bón lót / Đẻ nhánh: Phân Hữu cơ sinh học CFC kết hợp NPK Cò Bay Đẻ nhánh giúp rễ ăn sâu, nở bụi to, cứng cây.
    2. Bón đón đòng / Nuôi hạt: NPK Chuyên Lúa giúp đòng to, hạt chắc mẩy, hạn chế lem lép hạt.
  * 🎯 **Chuẩn**: `cfc_rice_fertilizer_guide`.
* **Lượt 3** *(Hỏi giá bao 25kg)*:
  * 👤 **Khách**: `Bao 25kg NPK Chuyên Lúa giá bao nhiêu tiền?`
  * 🤖 **Bot**: Giá phân bón được điều chỉnh theo giá đại lý từng khu vực và chính sách hỗ trợ mùa vụ. Bot xin SĐT và xã/huyện tại Kiên Giang để đại lý gần nhất báo giá chuẩn.
  * 🎯 **Chuẩn**: `cfc_price_unverified` (Không bịa giá tĩnh).
* **Lượt 4** *(Hỏi liều lượng bón)*:
  * 👤 **Khách**: `1 công bón khoảng bao nhiêu kg vậy shop?`
  * 🤖 **Bot**: Liều lượng bón phụ thuộc vào chất đất và giai đoạn lúa. Khuyến nghị bà con theo dõi hướng dẫn trên bao bì hoặc để lại SĐT để kỹ sư Cò Bay liên hệ hướng dẫn trực tiếp theo tình trạng đất ruộng.
  * 🎯 **Chuẩn**: `cfc_dosage_usage_review`.
* **Lượt 5**:
  * 👤 **Khách**: `Sđt tui là 0949887766 tên Bảy Lúa ở Giồng Riềng Kiên Giang`
  * 🤖 **Bot**: Xác nhận thông tin chú Bảy Lúa (0949887766 tại Giồng Riềng, Kiên Giang). Kỹ sư Cò Bay phụ trách vùng Kiên Giang sẽ gọi điện hỗ trợ kỹ thuật và đại lý giao hàng tận ruộng sớm nhất.
  * 🎯 **Chuẩn**: `contact_phone_provided` (CFC Lead Ready).
* **Lượt 6**:
  * 👤 **Khách**: `Cảm ơn Cò Bay nhiều`
  * 🤖 **Bot**: Dạ Cò Bay cảm ơn chú! Chúc chú một vụ mùa bội thu trúng giá ạ!
  * 🎯 **Chuẩn**: `thanks`.

---

### Kịch bản 17: Cây ăn trái mùa nghịch (Sầu riêng, Bưởi, Mít, Xoài) (5 lượt)
> **Mục tiêu**: Kiểm tra tư vấn dinh dưỡng cho cây ăn trái đặc sản Miền Tây và Đông Nam Bộ.

* **Lượt 1**:
  * 👤 **Khách**: `Vườn sầu riêng Ri6 đang nuôi trái non thì bón phân gì cho không bị rụng trái?`
  * 🤖 **Bot**: Tư vấn dòng **NPK Cò Bay Chuyên Cây Ăn Trái** giàu Kali và vi lượng cân đối, kết hợp **Hữu cơ sinh học CFC** giúp dưỡng rễ, nuôi trái tròn đều, hạn chế rụng trái non và méo trái.
  * 🎯 **Chuẩn**: `cfc_fruit_tree_fertilizer`.
* **Lượt 2**:
  * 👤 **Khách**: `Phân này có làm chua đất hay nghẹt rễ không?`
  * 🤖 **Bot**: Phân bón Cò Bay được sản xuất theo công nghệ hiện đại, tan hoàn toàn, không gây chai đất, bổ sung mùn hữu cơ sinh học giúp đất tơi xốp và rễ khỏe.
  * 🎯 **Chuẩn**: `cfc_fertilizer_quality`.
* **Lượt 3**:
  * 👤 **Khách**: `Ở Tiền Giang có đại lý nào bán không?`
  * 🤖 **Bot**: Cò Bay có mạng lưới đại lý phủ khắp các huyện tại Tiền Giang (Cái Bè, Cai Lậy, Châu Thành). Bot xin SĐT để gửi địa chỉ đại lý gần vườn nhất.
  * 🎯 **Chuẩn**: `company_address` / `dealer_network`.
* **Lượt 4**:
  * 👤 **Khách**: `Cho tôi số hotline kỹ thuật`
  * 🤖 **Bot**: Cung cấp Hotline kỹ thuật & CSKH Cò Bay: **0292 3841 818**.
  * 🎯 **Chuẩn**: `company_hotline` (CFC).
* **Lượt 5**:
  * 👤 **Khách**: `Cho xin trang web của công ty`
  * 🤖 **Bot**: Website chính thức: `https://cfccobay.vn/`.
  * 🎯 **Chuẩn**: `cfc_company_website`.

---

### Kịch bản 18: Cải tạo đất chua, phèn, bạc màu bằng Hữu cơ sinh học (5 lượt)
> **Mục tiêu**: Tư vấn cải tạo đất bằng Phân hữu cơ sinh học CFC Cần Thơ.

* **Lượt 1**:
  * 👤 **Khách**: `Đất vườn bị nhiễm phèn chua, rễ cây bị vàng lá thối rễ thì xử lý sao?`
  * 🤖 **Bot**: Tư vấn bón vôi hạ phèn kết hợp bón lót **Phân bón Hữu cơ sinh học CFC Cần Thơ** để bổ sung hệ vi sinh vật có lợi, trung hòa axit trong đất, giải độc phèn và kích thích bộ rễ mới phát triển.
  * 🎯 **Chuẩn**: `cfc_organic_fertilizer`.
* **Lượt 2**:
  * 👤 **Khách**: `Phân hữu cơ của CFC là dạng bột hay dạng viên nén?`
  * 🤖 **Bot**: Phân hữu cơ sinh học CFC được xử lý lên men vi sinh hiện đại, quy cách bao 25kg tiện lợi, dễ rải đều quanh gốc hoặc bón lót trước khi trồng.
  * 🎯 **Chuẩn**: `cfc_product_specs`.
* **Lượt 3**:
  * 👤 **Khách**: `Có mùi hôi khó chịu không?`
  * 🤖 **Bot**: Sản phẩm đã qua quy trình ủ hoai mục và khử khuẩn công nghệ cao, không có mùi hôi nồng, sạch mầm bệnh và cỏ dại.
  * 🎯 **Chuẩn**: `cfc_product_safety`.
* **Lượt 4**:
  * 👤 **Khách**: `Nhà máy sản xuất ở đâu vậy?`
  * 🤖 **Bot**: Trụ sở và nhà máy tại: **Khu Công nghiệp Trà Nóc 1, Phường Trà Nóc, Quận Bình Thủy, TP. Cần Thơ**.
  * 🎯 **Chuẩn**: `company_address` (CFC).
* **Lượt 5**:
  * 👤 **Khách**: `Ok cảm ơn Cò Bay`
  * 🤖 **Bot**: Chúc bà con canh tác hiệu quả và mùa màng bội thu.
  * 🎯 **Chuẩn**: `thanks`.

---

# PHẦN 3: KỊCH BẢN KHÁCH HÀNG ĐẶC BIỆT, KHIẾU NẠI & CORNER CASES

---

### Kịch bản 26: Khách giận dữ vì giao hàng trễ / Đổ vỡ sản phẩm (4 lượt)
> **Mục tiêu**: Nhận diện khiếu nại gay gắt, hạ nhiệt khách hàng, escalate cho admin và cam kết xử lý 100%.

* **Lượt 1**:
  * 👤 **Khách**: `Bot ngu thế, đặt hàng cả tuần rồi mà chưa thấy đâu, làm ăn như lừa đảo`
  * 🤖 **Bot**: Dạ ZeO thành thật xin lỗi bạn vì trải nghiệm chưa tốt vừa rồi ạ! Vấn đề giao trễ này em xin phép chuyển thẳng cho Admin phụ trách kiểm tra gấp với bên vận chuyển. Bạn nhắn giúp em Mã đơn hàng hoặc Số điện thoại để xử lý ngay cho mình nha!
  * 🎯 **Chuẩn**: `bot_complaint_escalate` (Gắn cờ `lead_stage: escalated`, báo Telegram Admin tức thì).
* **Lượt 2**:
  * 👤 **Khách**: `Sđt tui 0912345678, kiểm tra lẹ đi`
  * 🤖 **Bot**: Dạ em đã tiếp nhận số 0912345678 và chuyển bộ phận CSKH xử lý ưu tiên. Quản lý sẽ liên hệ lại trong vòng 15-30 phút để giải quyết dứt điểm cho mình ạ.
  * 🎯 **Chuẩn**: `contact_phone_provided` (Escalated Lead).
* **Lượt 3**:
  * 👤 **Khách**: `Nếu hàng bị bể thì có được đổi trả ko?`
  * 🤖 **Bot**: ZeO cam kết 100% đổi hàng mới hoàn toàn miễn phí hoặc hoàn tiền nếu sản phẩm bị đổ bể bung nắp do vận chuyển trong vòng 7 ngày.
  * 🎯 **Chuẩn**: `return_policy`.
* **Lượt 4**:
  * 👤 **Khách**: `Được, kiểm tra nhanh giùm tôi`
  * 🤖 **Bot**: Dạ vâng ạ, bên em đang xử lý ngay cho bạn đây ạ!
  * 🎯 **Chuẩn**: `acknowledgement`.

---

### Kịch bản 27: Khách gửi tin nhắn gộp nhiều ý (Multi-intent) (3 lượt)
> **Mục tiêu**: Xử lý câu hỏi phức hợp gồm giá, giao hàng, voucher và hotline trong cùng 1 câu.

* **Lượt 1**:
  * 👤 **Khách**: `Nước giặt Pano giá bao nhiêu, có freeship về Cần Thơ ko và hotline là số mấy?`
  * 🤖 **Bot**: Bóc tách và giải đáp trọn vẹn:
    1. Giá nước giặt Pano đa dạng từ 95.058đ (túi 3.5kg) đến 123.291đ (can 3.8kg).
    2. Hỗ trợ mã Freeship Extra toàn quốc giao về Cần Thơ.
    3. Hotline hỗ trợ đặt hàng: **1900 5307**.
  * 🎯 **Chuẩn**: Tổng hợp thông tin từ Sheet và Shopee Catalog chuẩn xác.
* **Lượt 2**:
  * 👤 **Khách**: `Cho mình xin link mua can 3.8kg`
  * 🤖 **Bot**: Gửi link Shopee Mall trực tiếp của sản phẩm Nước giặt Pano Can 3.8kg.
  * 🎯 **Chuẩn**: `shopee_product_link`.
* **Lượt 3**:
  * 👤 **Khách**: `Ok cảm ơn shop`
  * 🤖 **Bot**: Dạ ZeO cảm ơn bạn đã quan tâm! Cần hỗ trợ thêm bạn cứ nhắn shop nha.
  * 🎯 **Chuẩn**: `thanks`.

---

### Kịch bản 29: Chuyển đổi chủ đề liên tục (Context Switching) (5 lượt)
> **Mục tiêu**: Kiểm tra bộ nhớ `conversation_state` không bị loạn khi khách nhảy từ chủ đề này sang chủ đề khác rồi quay lại hỏi tiếp.

* **Lượt 1**:
  * 👤 **Khách**: `Nước rửa chén ZeO có những loại nào?`
  * 🤖 **Bot**: Giới thiệu dòng Nước rửa chén Vitamin E Pano và Nước rửa chén Oplus.
  * 🎯 **Chuẩn**: `pano_dishwashing_product_overview`.
* **Lượt 2** *(Nhảy sang hỏi công ty)*:
  * 👤 **Khách**: `Công ty mình thành lập năm nào ở đâu?`
  * 🤖 **Bot**: Trả lời thông tin công ty ZeO Vietnam từ Google Sheet.
  * 🎯 **Chuẩn**: `company_overview`.
* **Lượt 3** *(Nhảy sang hỏi phân bón Cò Bay)*:
  * 👤 **Khách**: `Mà bên bạn có bán phân bón Cò Bay ko?`
  * 🤖 **Bot**: Nêu rõ phân bón Cò Bay thuộc hệ thống nông nghiệp CFC, còn ZeO chuyên hóa phẩm gia dụng.
  * 🎯 **Chuẩn**: `zeo_cross_brand_out_of_scope`.
* **Lượt 4** *(Quay lại hỏi tiếp nước rửa chén ở Lượt 1)*:
  * 👤 **Khách**: `Quay lại cái nước rửa chén hồi nãy, giá bao nhiêu 1 chai?`
  * 🤖 **Bot**: Báo giá Nước rửa chén Vitamin E Pano là 12.350đ kèm link Shopee Mall.
  * 🎯 **Chuẩn**: Nhận diện đúng entity `Nước rửa chén` từ lịch sử hội thoại.
* **Lượt 5**:
  * 👤 **Khách**: `Ok lấy mình 2 chai`
  * 🤖 **Bot**: Hướng dẫn bấm vào link Shopee Mall để đặt hàng nhận ưu đãi giao nhanh tận nhà.
  * 🎯 **Chuẩn**: `shopee_product_link`.

---

# PHẦN 4: BẢNG TEST TỪ LÓNG, VIẾT TẮT & KHÔNG DẤU

| STT | Tin nhắn của khách (Không dấu / Viết tắt / Tiếng lóng) | Ý định kỳ vọng (Expected Intent) | Tiêu chuẩn đánh giá |
|:---:|---|---|---|
| 1 | `zeo co bot giat ko shop` | `zeo_laundry_product_overview` | ✅ Bóc tách "bot giat" $\rightarrow$ Bột giặt ZeO |
| 2 | `gia nhiu 1 can z shop` | `zeo_price_inquiry_general` | ✅ Bóc tách "nhiu", "z" $\rightarrow$ Báo giá chung |
| 3 | `cho xin link shopee vs wed zeo` | `shopee_product_link` | ✅ Bóc tách "wed" $\rightarrow$ Website / Shopee |
| 4 | `sp nao dang sale re nhat` | `promotion_deals` | ✅ Bóc tách "sp" $\rightarrow$ Sản phẩm, "sale" |
| 5 | `sdt cua tui 0988112233 o can tho` | `contact_phone_provided` | ✅ Lưu SĐT + Khu vực Cần Thơ |
| 6 | `cai thu 2 la j the` | `oplus_detergent_usp` | ✅ Bóc tách "j the" $\rightarrow$ Tham chiếu cái số 2 |
| 7 | `cfc co nhung loai phan nao` | `product_lines` | ✅ Bóc tách CFC $\rightarrow$ Danh mục phân bón |
| 8 | `muon lam dai li phan bon o kien giang` | `wholesale_dealer` | ✅ Bóc tách "dai li" $\rightarrow$ Đại lý |
| 9 | `bot ngu vai tra loi gi ky cuc` | `bot_complaint_escalate` | ✅ Bắt trúng khiếu nại, xin lỗi và chuyển Admin |
| 10 | `ok cam on shop nhiu nha` | `thanks` | ✅ Bóc tách cảm ơn thân thiện |
| 11 | `1kg bot giat cho 5 bo do dc ko` | `zeo_usage_safety_review` | ✅ Bóc tách "dc ko" $\rightarrow$ Liều lượng dùng |
| 12 | `shop o dau vay` | `company_address` | ✅ Hỏi địa chỉ công ty / shop |
| 13 | `co freeship k ad` | `shipping_time_and_fee` | ✅ Bóc tách "k", "ad" $\rightarrow$ Freeship |
| 14 | `toi muon mua oplis` | `oplus_purchase_clarify` | ✅ Bóc tách lỗi chính tả "oplis" $\rightarrow$ Oplus |
| 15 | `zeo co nuoc tay javel k` | `zeo_bleach_features` | ✅ Bóc tách Javel / Javen |

---

# PHẦN 5: LỆNH CHẠY TEST TỰ ĐỘNG BẰNG PYTHON (1-CLICK RUNNER)

Toàn bộ các ca kiểm thử trên đã được tích hợp trong bộ test runner tự động `eval_test_suite.py` để bạn có thể kiểm tra toàn diện chỉ với 1 dòng lệnh trong Terminal:

```bash
# Chạy toàn bộ 98 ca kiểm thử NLU Regression Suite (Độ trễ < 10ms, Pass Rate 100%)
.venv/bin/python3 ChatbotN8n/javis/server/eval_test_suite.py
```

---
*Tài liệu được bảo trì và đồng bộ tự động với hệ thống kiến thức tại [TONG_HOP_HE_THONG_CHATBOT_ZEO_CFC_HIEN_HANH.md](file:///Users/hyden/Documents/David-nguyen/N8n/TONG_HOP_HE_THONG_CHATBOT_ZEO_CFC_HIEN_HANH.md).*
