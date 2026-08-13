# ZeO Facebook Live Test

Use this checklist after pushing `zeo_chatbot.workflow.ts` and running the ZeO knowledge sync.

## What To Observe

- Bot should remember the same Facebook sender by `senderId`.
- Bot should not ask again for phone or area once both exist in Customer Profile.
- FAQ questions should still receive FAQ answers even when the customer profile is complete.
- Lead/admin requests with full contact should route to admin/review with `lead_contact_ready`.

## New Customer Flow

1. Send:
   `toi muon lam dai ly zeo`

   Expected:
   Bot asks for phone and area.

2. Send:
   `0912345678`

   Expected:
   Bot says it received the phone and asks only for area.

3. Send:
   `minh o Binh Duong`

   Expected:
   Bot says it has phone and area, then admin will contact/support. It should not ask for phone again.

4. Send:
   `minh muon lay si tiep`

   Expected:
   Bot should not ask for phone/area again. It should treat this as a ready lead/admin handoff.

5. Send:
   `toi o dau`

   Expected:
   Bot should answer with the saved area from Customer Profile.

6. Send:
   `con nho toi o dau ko, cho toi xin lai so dien thoai cua toi`

   Expected:
   Bot should answer with the saved area and phone. It should not repeat the generic admin handoff message.

7. Send:
   `can ho tro`

   Expected:
   Bot should ask what product or service issue needs support. It should not repeat the generic "already has phone and area" handoff message.

8. Send:
   `Da Lat co nha phan phoi chua`

   Expected:
   Bot should say ZeO will check distributor availability for Da Lat/admin review. It should not reuse the generic full-contact handoff message.

9. Send:
   `toi hoi so lai thi tiep tuc gui`

   Expected:
   Bot should answer with the saved phone number from Customer Profile.

10. Send:
    `toi muon lam dai li`

    Expected:
    Bot should understand this as dealer/wholesale intent, use the saved phone and area, and explain that admin will check the region/conditions. It should not repeat only "ZeO has phone and area".

11. Send:
    `Roi co so dien thoai thi lam gi nua`

    Expected:
    Bot should explain the next step based on the last need: admin checks product/link/region/person in charge and contacts back. It should not repeat the same lead handoff sentence.

12. Send:
    `gui toi link web`

    Expected:
    Bot should return only the official website: `https://zeo.vn/`.

13. Send:
    `Pano la san pham gi kia`

    Expected:
    Bot should explain that PANO is a home-cleaning product line with laundry, dishwashing, and multipurpose cleaner groups. It should not return the generic product catalog.

14. Send after a PANO answer:
    `la san pham gi kia`

    Expected:
    Bot should use session context and explain PANO product groups.

15. Send:
    `co ve van session van chua on nhi`

    Expected:
    Bot should apologize and route the issue to learning/admin review. It should not treat this as product consultation.

16. Send:
    `toi muon 2kg nuoc giat va 2 chai thuoc tay`

    Expected:
    Bot should capture this as an order request. If phone and area are already saved, it should say ZeO recorded the requested items and admin will confirm product/spec/stock/price. It should not answer with PANO brand positioning.

17. Send:
    `hihi do ngu`

    Expected:
    Bot should apologize briefly and route to learning/admin review. It should not answer with a product FAQ.

18. Send:
    `toi chui ban ma sao ban tra loi gi v`

    Expected:
    Bot should recognize this as feedback about a wrong answer. It should not answer complaint SLA/policy.

19. Send:
    `Lien quan gi toi khieu nai dau`

    Expected:
    Bot should not save this sentence as the customer's area. The saved customer area should remain unchanged.

20. Send:
    `chan ghe`

    Expected:
    Bot should treat this as frustration/feedback and avoid random product FAQ retrieval.

## Returning Customer FAQ Flow

1. Send:
   `shop co ship k`

   Expected:
   Bot answers shipping/COD FAQ. It should not force admin handoff only because profile is complete.

2. Send:
   `bot giat zeo co mui gi`

   Expected:
   Bot answers product/fragrance FAQ.

3. Send:
   `toi can nhan vien goi tu van`

   Expected:
   Bot should use the saved phone/area and route to admin. It should not ask for phone/area again.

## Reset Note

To retest as a totally new customer, use a different Facebook account or delete the Redis key:

`zeo:customer:messenger:{senderId}`
