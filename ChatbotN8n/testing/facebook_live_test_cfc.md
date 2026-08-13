# CFC Facebook Live Test

Use this checklist after pushing `cfc_cobay_chatbot.workflow.ts` and running the CFC knowledge sync.

## What To Observe

- Bot should remember the same Facebook sender by `senderId`.
- Bot should not ask again for phone or area once both exist in Customer Profile.
- FAQ questions should still receive FAQ answers even when the customer profile is complete.
- Dealer/buy/support requests with full contact should route to admin/review with `lead_contact_ready`.

## New Dealer Lead Flow

1. Send:
   `toi muon lam dai ly co bay`

   Expected:
   Bot asks for phone and area.

2. Send:
   `0987654321`

   Expected:
   Bot says it received the phone and asks only for area.

3. Send:
   `minh o Can Tho`

   Expected:
   Bot says it has phone and area, then admin or regional staff will contact/support. It should not ask for phone again.

4. Send:
   `toi muon mua phan bon`

   Expected:
   Bot should not ask for phone/area again. It should treat this as a ready lead/admin handoff.

5. Send:
   `con nho toi o dau ko, cho toi xin lai so dien thoai cua toi`

   Expected:
   Bot should answer with the saved area and phone. It should not repeat the generic admin handoff message.

## Company FAQ Flow

1. Send:
   `Gioi thieu ve cong ty ban di`

   Expected:
   Bot answers the CFC/Cò Bay company overview directly.

2. Send:
   `cty ban o dua`

   Expected:
   Bot treats this as `cty ban o dau` and answers the company address directly.

## Returning Customer FAQ Flow

1. Send:
   `ben minh co npk khong`

   Expected:
   Bot answers the product-lines FAQ.

2. Send:
   `van chuyen sao shop`

   Expected:
   Bot answers the shipping FAQ. It should not force contact collection again.

3. Send:
   `can nhan vien tu van`

   Expected:
   Bot should use the saved phone/area and route to admin. It should not ask for phone/area again.

## Reset Note

To retest as a totally new customer, use a different Facebook account or delete the Redis key:

`cfc:customer:messenger:{senderId}`
