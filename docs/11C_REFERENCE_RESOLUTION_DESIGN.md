# 11C — Reference Resolution Design

## 1. Mục tiêu

Khi khách hỏi “sản phẩm đó”, “cái số 2”, “loại này”, bot phải hiểu khách đang nối tiếp lượt trước. Nếu không resolve chắc chắn, bot phải hỏi lại thay vì đoán.

## 2. State đang dùng

`conversation_state` trong Redis/RAM session gồm các phần quan trọng:

```text
active_entities.product
active_entities.product_intent
active_entities.category
active_entities.product_id
active_entities.shopee_url
last_products_shown[]
recent_turns[]
active_flow
last_source_id
```

## 3. Resolution hiện tại

`chat_pipeline.py` vẫn giữ resolver chính `_resolve_reference()`. QueryPlan không thay resolver này; nó đọc kết quả resolver và ghi lại:

```text
references.mentions_previous_turn
references.resolved
references.ordinal
references.product
references.product_id
references.category
```

## 4. Hành vi đúng

| Câu khách | Điều kiện | Hành vi |
|---|---|---|
| `xin link sản phẩm đó` | Có `product_id`/product trước đó | Gọi Shopee reference matcher |
| `cái đầu tiên giá nhiu` | Có `last_products_shown[0]` | Gọi price matcher/reference |
| `cái đó còn không` | Không resolve rõ | Hỏi lại sản phẩm/số thứ tự |
| `nước xả giá bao nhiêu` | Có entity mới rõ | Không dùng stale context cũ |
| `SĐT tui là...` | Có số điện thoại | Lead capture ưu tiên trước advisory/context |

## 5. Thay đổi trong lần này

- QueryPlan ghi trace có cấu trúc để biết câu nào cần context.
- Route CFC advisory không được bắt nhầm câu có số điện thoại/tên “Bảy Lúa”.
- Câu explicit CFC price như “Bao 25kg NPK...” không bị context lúa trước đó kéo thành `contextual_price_unverified`.

## 6. Điểm còn cần làm

- `last_products_shown` cần `source_version` bắt buộc.
- Redis session nên có TTL/version hoặc optimistic update để chống multi-worker stale state.
- Cần test restart/multi-worker vì RAM cache chỉ là process-local.
