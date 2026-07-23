"""Create (or show) the ZavaOps memory store in Foundry Agent Service.

Memory types enabled:
  - user_profile:  stable facts/preferences per employee (e.g. "manages the West region")
  - chat_summary:  continuity across sessions
  - procedural:    learned task patterns (e.g. the damaged-goods sequence)

Preview API: requires AIProjectClient(..., allow_preview=True).
Run:  PYTHONPATH=. python scripts/setup_memory.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    MemoryStoreDefaultDefinition,
    MemoryStoreDefaultOptions,
)

load_dotenv()

STORE_NAME = "zavaops_memory"
THIRTY_DAYS = 30 * 24 * 60 * 60

# Privacy guardrail: tells the extraction model what NOT to retain.
# This is a first-class control, not a prompt hack - see ADR 003.
PROFILE_GUIDANCE = (
    "Store only work-relevant preferences: region ownership, product categories of interest, "
    "reporting cadence, and preferred level of detail. "
    "Never store personal identifiers, financial details, health information, precise location, "
    "credentials, or customer PII from order records."
)


def main() -> None:
    client = AIProjectClient(
        os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        DefaultAzureCredential(),
        allow_preview=True,
    )

    # Idempotent: reuse the store if it already exists.
    for store in client.beta.memory_stores.list():
        if getattr(store, "name", None) == STORE_NAME:
            print(f"Memory store already exists: {STORE_NAME}")
            print(store)
            return

    options = MemoryStoreDefaultOptions(
        user_profile_enabled=True,
        chat_summary_enabled=True,
        procedural_memory_enabled=True,
        default_ttl_seconds=THIRTY_DAYS,
        user_profile_details=PROFILE_GUIDANCE,
    )

    definition = MemoryStoreDefaultDefinition(
        chat_model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],       # chat-small
        embedding_model=os.environ["AZURE_EMBED_DEPLOYMENT_NAME"],     # embed
        options=options,
    )

    store = client.beta.memory_stores.create(
        name=STORE_NAME,
        definition=definition,
        description="ZavaOps agent memory: employee preferences, session continuity, learned procedures.",
    )
    print("Created memory store:")
    print(store)


if __name__ == "__main__":
    main()