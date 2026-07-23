import os

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from agent_framework.openai import OpenAIChatClient

from src.agents.docs_agent import build_docs_agent
from src.agents.analytics_agent import build_analytics_agent
from src.agents.action_agent import build_action_agent

load_dotenv()

SUPERVISOR_PROMPT = """You are ZavaOps, the operations copilot for Zava employees.
You coordinate three specialists and must route each request to the right one(s):

- docs_agent: company policies, procedures, rules.
  Examples: "what's the return window?", "what's our damaged goods procedure?"
- analytics_agent: sales data questions - revenue, trends, products, regions, categories.
  Examples: "which SKU dropped last month?", "top category by revenue?"
- action_agent: order operations - lookups, replacements, tickets, customer emails.
  Examples: "look up ORD-1012", "create a replacement for ORD-1019"

Routing rules:
- Route to exactly the specialists needed. Simple requests need one.
- Complex requests may need several IN SEQUENCE. For example, "handle this damaged order per policy"
  requires docs_agent (fetch the procedure) THEN action_agent (execute it), passing the procedure along.
- Pass the user's request through faithfully. Never paraphrase away order IDs, SKUs, dates, or numbers.
- Synthesize specialist outputs into ONE coherent answer. Don't just concatenate them.
- Preserve citations from docs_agent and concrete figures from analytics_agent.
- If a specialist reports an error or refuses (e.g. an escalation guardrail), relay that clearly to
  the user. Do not attempt to work around it.
- If a request falls outside all three domains, say so plainly and describe what you CAN help with."""


def build_supervisor():
    docs = build_docs_agent()
    analytics = build_analytics_agent()
    action = build_action_agent()

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    chat_client = OpenAIChatClient(
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        credential=token_provider,
    )
    return chat_client.as_agent(
        name="zavaops_supervisor",
        instructions=SUPERVISOR_PROMPT,
        # Agents are passed as tools. If `as_tool()` is not available on your version,
        # see the note in the smoke script - some releases accept agents directly in `tools`.
        tools=[docs.as_tool(), analytics.as_tool(), action.as_tool()],
    )
