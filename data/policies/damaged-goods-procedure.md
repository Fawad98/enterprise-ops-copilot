# Zava Damaged Goods Procedure

**Policy ID:** PROC-DMG-001
**Effective date:** 2026-01-01
**Owner:** Customer Operations

This procedure defines the exact steps to handle an order reported as damaged on arrival. Operations staff and automated agents must follow these steps in order.

## Eligibility

This procedure applies when a customer reports an item as **damaged or defective on arrival**, reported within **14 days** of the delivery date. Damaged items are exempt from any restocking fee (see returns-policy.md, Section 6).

## Procedure (follow in order)

1. **Verify the order.** Look up the order by its ID and confirm it exists and that its status is one that can be damaged on arrival (for example: `delivered` or `shipped`). If the order is already `refunded` or `cancelled`, do not proceed — escalate instead.

2. **Confirm the damage report is within 14 days** of the delivery date. If it is outside 14 days, route to a warranty claim instead (see warranty-policy.md).

3. **Create a replacement order** for the same items, at no cost to the customer, linked to the original order. Record the reason as "damaged on arrival."

4. **Create a support ticket** documenting the incident, referencing both the original and replacement order IDs, with priority `high` if the item is Electronics or over $200, otherwise `normal`.

5. **Notify the customer** by email: confirm the replacement is on its way, provide the new order ID, and apologize for the inconvenience. Do not ask the customer to return the damaged item unless it is over $200 in value.

6. **For items over $200**, include a prepaid return label in the customer email and note in the ticket that the damaged item must be returned for inspection.

## What NOT to do

- Do not issue both a replacement and a refund for the same damaged item.
- Do not charge the customer for the replacement or its shipping.
- Do not create a replacement if the order is already refunded or cancelled — escalate to a human per supplier-escalation.md.

## Related policies

- returns-policy.md
- warranty-policy.md
- supplier-escalation.md
