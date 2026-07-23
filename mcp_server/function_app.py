import json
import azure.functions as func
from store import OrderStore

app = func.FunctionApp()
store = OrderStore()


def _args(context) -> dict:
    return json.loads(context).get("arguments", {}) or {}


@app.generic_trigger(
    arg_name="context", type="mcpToolTrigger",
    toolName="get_order",
    description="Get full details of an order by its ID.",
    toolProperties=json.dumps([
        {"propertyName": "order_id", "propertyType": "string",
         "description": "The order ID, e.g. ORD-1012"}]))
def get_order(context) -> str:
    a = _args(context)
    return json.dumps(store.get(a.get("order_id")) or {"error": "order not found"})


@app.generic_trigger(
    arg_name="context", type="mcpToolTrigger",
    toolName="list_orders",
    description="List orders, optionally filtered by status (placed, shipped, delivered, damaged, refunded) or customer name/email.",
    toolProperties=json.dumps([
        {"propertyName": "status", "propertyType": "string",
         "description": "Optional status filter"},
        {"propertyName": "customer", "propertyType": "string",
         "description": "Optional customer name or email substring"}]))
def list_orders(context) -> str:
    a = _args(context)
    return json.dumps(store.list(a.get("status"), a.get("customer")))


@app.generic_trigger(
    arg_name="context", type="mcpToolTrigger",
    toolName="create_replacement",
    description="Create a free replacement order for a damaged or lost order. Returns the new order. Refuses if the original is refunded or cancelled.",
    toolProperties=json.dumps([
        {"propertyName": "order_id", "propertyType": "string",
         "description": "Original order ID"},
        {"propertyName": "reason", "propertyType": "string",
         "description": "Reason for the replacement, e.g. 'damaged on arrival'"}]))
def create_replacement(context) -> str:
    a = _args(context)
    return json.dumps(store.create_replacement(a.get("order_id"), a.get("reason", "")))


@app.generic_trigger(
    arg_name="context", type="mcpToolTrigger",
    toolName="create_ticket",
    description="Create a support ticket for an order. Priority must be one of: urgent, high, normal, low.",
    toolProperties=json.dumps([
        {"propertyName": "order_id", "propertyType": "string",
         "description": "The order ID the ticket relates to"},
        {"propertyName": "summary", "propertyType": "string",
         "description": "Short description of the issue"},
        {"propertyName": "priority", "propertyType": "string",
         "description": "urgent | high | normal | low"}]))
def create_ticket(context) -> str:
    a = _args(context)
    return json.dumps(store.create_ticket(
        a.get("order_id"), a.get("summary", ""), a.get("priority", "normal")))


@app.generic_trigger(
    arg_name="context", type="mcpToolTrigger",
    toolName="send_customer_email",
    description="Send an email to the customer associated with an order. This is a mock outbox; no real email is sent.",
    toolProperties=json.dumps([
        {"propertyName": "order_id", "propertyType": "string",
         "description": "The order ID whose customer should be emailed"},
        {"propertyName": "subject", "propertyType": "string",
         "description": "Email subject line"},
        {"propertyName": "body", "propertyType": "string",
         "description": "Email body text"}]))
def send_customer_email(context) -> str:
    a = _args(context)
    return json.dumps(store.send_customer_email(
        a.get("order_id"), a.get("subject", ""), a.get("body", "")))