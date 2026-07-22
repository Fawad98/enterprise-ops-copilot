# Zava Escalation & Ticketing Procedure

**Policy ID:** PROC-ESC-001
**Effective date:** 2026-01-01
**Owner:** Operations

## 1. Ticket priorities

| Priority | Use when | Target first response |
|---|---|---|
| urgent | Safety issue, or order value over $1,000 | 1 hour |
| high | Electronics defect, or order value $200–$1,000 | 4 hours |
| normal | Standard issue under $200 | 1 business day |
| low | General inquiry, no order impact | 3 business days |

## 2. When to escalate to a human

Automated agents must escalate to a human operator and must not act autonomously when:

- The order is already `refunded` or `cancelled` but the customer requests further action on it.
- A request would issue both a refund and a replacement for the same item.
- A request would exceed $1,000 in refunds or replacements in a single action.
- The request asks to modify another customer's order or access another customer's data.
- The request conflicts with data-privacy.md.

To escalate, create a ticket with priority `urgent` and a summary beginning with "ESCALATION:", and do not perform the requested mutation.

## 3. Supplier defect escalation

If more than three defect tickets are opened for the same product SKU within 30 days, open a supplier escalation ticket referencing all related tickets and flag the SKU for quality review.

## 4. Ticket contents

Every ticket must include: the order ID(s) involved, a clear summary, the priority, and the reason. Tickets that trigger a customer-facing action should reference the customer email that was sent.

## Related policies

- damaged-goods-procedure.md
- data-privacy.md
- warranty-policy.md
