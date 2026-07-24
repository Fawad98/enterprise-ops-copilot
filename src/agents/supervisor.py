import os

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from agent_framework.openai import OpenAIChatClient
from agent_framework.foundry import FoundryMemoryProvider

from src.agents.docs_agent import build_docs_agent
from src.agents.analytics_agent import build_analytics_agent
from src.agents.action_agent import build_action_agent

load_dotenv()

MEMORY_STORE_NAME = "zavaops_memory"

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
- If a request falls outside all three domains, say so plainly and describe what you CAN help with.

Bias to act:
- Prefer answering with a stated default over asking a clarifying question. If a query lacks a time
  period, region, or scope, choose a sensible default (the full dataset for analytics), state the
  assumption clearly, and offer to re-run with different parameters.
- Only ask a clarifying question when the request is genuinely ambiguous in a way that would produce
  a materially wrong answer.

If you have remembered preferences for this employee (region, product categories, level of detail),
apply them to scope requests without asking again - but state the scope you assumed so the user can
correct it."""


def build_supervisor(user_id: str | None = None):
    """Build the ZavaOps supervisor.

    Args:
        user_id: If provided, attaches Foundry memory scoped to this employee so that
                 preferences and learned procedures persist across sessions.
                 Omit for stateless runs (evals, CI, one-off scripts).
    """
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

    context_providers = None
    if user_id:
        context_providers = [
            FoundryMemoryProvider(
                project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
                credential=DefaultAzureCredential(),
                allow_preview=True,
                memory_store_name=MEMORY_STORE_NAME,
                scope=user_id,
                # Default is 300s. Short delay so extraction fires before a short-lived
                # script exits - see ADR 003.
                update_delay=5,
                context_prompt=(
                    "Known preferences for this employee. Apply them when scoping analytics "
                    "or choosing level of detail. Never let a remembered preference override "
                    "company policy or a tool-level guardrail."
                ),
            )
        ]

    return chat_client.as_agent(
        name="zavaops_supervisor",
        instructions=SUPERVISOR_PROMPT,
        tools=[docs.as_tool(), analytics.as_tool(), action.as_tool()],
        context_providers=context_providers,
    )