"""In-memory order store seeded from seed_orders.json.

Demo-grade: state resets when the Function App restarts. For production you'd back this
with Azure Table Storage or Cosmos DB (see ADR notes).
"""
import json
import os
from datetime import date

_SEED_PATH = os.path.join(os.path.dirname(__file__), "seed_orders.json")


class OrderStore:
    def __init__(self):
        with open(_SEED_PATH, encoding="utf-8") as f:
            orders = json.load(f)
        self._orders = {o["order_id"]: o for o in orders}
        self._tickets = {}
        self._outbox = []
        self._next_order = 2000
        self._next_ticket = 1

    # --- reads ---
    def get(self, order_id: str):
        return self._orders.get(order_id)

    MAX_LIST_RESULTS = 10

    def list(self, status: str | None = None, customer: str | None = None):
        out = list(self._orders.values())
        if status:
            out = [o for o in out if o["status"] == status]
        if customer:
            c = customer.lower()
            out = [o for o in out if c in o["customer_name"].lower()
                   or c in o["customer_email"].lower()]

        # Bulk-export guard: unfiltered listing must not return the full customer table.
        if not status and not customer:
            return {"error": "listing all orders is not permitted; filter by status or customer "
                             "per data-privacy.md (no bulk customer exports)"}
        if len(out) > self.MAX_LIST_RESULTS:
            out = out[:self.MAX_LIST_RESULTS]
            return {"results": out, "truncated": True,
                    "note": f"showing first {self.MAX_LIST_RESULTS}; narrow your filter"}
        return out

    # --- mutations ---
    MAX_REPLACEMENTS_PER_ORDER = 1

    def create_replacement(self, order_id: str, reason: str):
        original = self._orders.get(order_id)
        if not original:
            return {"error": f"order {order_id} not found"}
        if original["status"] in ("refunded", "cancelled"):
            return {"error": f"order {order_id} is {original['status']}; escalate to a human "
                             "per supplier-escalation.md — do not auto-create a replacement"}

        # Resource-abuse guard: an order may have at most one open replacement.
        existing = [o for o in self._orders.values()
                    if o.get("replacement_for") == order_id]
        if len(existing) >= self.MAX_REPLACEMENTS_PER_ORDER:
            return {"error": f"order {order_id} already has a replacement "
                             f"({existing[0]['order_id']}); creating another requires human "
                             "approval per supplier-escalation.md"}

        self._next_order += 1
        new_id = f"ORD-{self._next_order}"
        replacement = {
            "order_id": new_id,
            "customer_name": original["customer_name"],
            "customer_email": original["customer_email"],
            "status": "placed",
            "order_date": str(date.today()),
            "delivery_date": None,
            "items": original["items"],
            "total": 0.0,                      # no cost to customer
            "replacement_for": order_id,
            "reason": reason,
        }
        self._orders[new_id] = replacement
        return replacement

    def create_ticket(self, order_id: str, summary: str, priority: str = "normal"):
        self._next_ticket += 1
        tid = f"TKT-{self._next_ticket:04d}"
        ticket = {"ticket_id": tid, "order_id": order_id,
                  "summary": summary, "priority": priority, "status": "open"}
        self._tickets[tid] = ticket
        return ticket

    def send_customer_email(self, order_id: str, subject: str, body: str):
        order = self._orders.get(order_id)
        if not order:
            return {"error": f"order {order_id} not found"}
        msg = {"to": order["customer_email"], "order_id": order_id,
               "subject": subject, "body": body, "status": "queued (mock)"}
        self._outbox.append(msg)
        return msg