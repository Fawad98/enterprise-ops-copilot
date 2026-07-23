import os

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from agent_framework import MCPStreamableHTTPTool
from agent_framework.openai import OpenAIChatClient

load_dotenv()

ACTION_PROMPT = """You are Zava's operations executor. You handle order issues using your tools.

READS (get_order, list_orders): perform immediately, no confirmation needed.

WRITES (create_replacement, create_ticket, send_customer_email):
- Look up the order with get_order FIRST to verify it exists and check its status.
- If the user has already given an explicit instruction (e.g. "create a replacement for ORD-1012,
  reason: damaged"), execute it directly - do not ask for redundant confirmation.
- Never invent order IDs. If you don't have one, ask for it.
- If a tool returns an error or escalation message, relay it verbatim and STOP.
  Do not attempt a workaround, alternate tool, or partial completion.

Follow damaged-goods procedure when handling damaged orders: verify the order, create a replacement,
create a ticket (priority 'high' for Electronics or orders over $200, otherwise 'normal'), then email
the customer with the new order ID."""


def _mcp_tool() -> MCPStreamableHTTPTool:
    """Connect to the deployed Zava orders MCP server (Azure Functions)."""
    key = os.environ["MCP_EXTENSION_KEY"]
    url = f"{os.environ['MCP_SERVER_URL']}?code={key}"
    return MCPStreamableHTTPTool(
        "zava_orders",
        url,
        description="Zava order management: look up orders, create replacements, tickets, and customer emails.",
        approval_mode="never_require",
        request_timeout=120,
    )


def build_action_agent():
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    chat_client = OpenAIChatClient(
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        credential=token_provider,
    )
    return chat_client.as_agent(
        name="action_agent",
        description="Executes order operations: lookups, replacements, support tickets, customer emails.",
        instructions=ACTION_PROMPT,
        tools=[_mcp_tool()],
    )
