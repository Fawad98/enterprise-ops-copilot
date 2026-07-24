"""Phase 7 memory demo.

  PYTHONPATH=. python scripts/demo_memory.py a       # store a preference, wait, verify
  PYTHONPATH=. python scripts/demo_memory.py b       # fresh session - does it recall?
  PYTHONPATH=. python scripts/demo_memory.py check   # just list what's stored
  PYTHONPATH=. python scripts/demo_memory.py clear   # wipe this user's memories
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.agents.supervisor import build_supervisor

USER = "emp-001"
STORE = "zavaops_memory"


def _client():
    from azure.identity import DefaultAzureCredential
    from azure.ai.projects import AIProjectClient
    return AIProjectClient(os.environ["FOUNDRY_PROJECT_ENDPOINT"],
                           DefaultAzureCredential(), allow_preview=True)


def show_memories():
    mems = list(_client().beta.memory_stores.list_memories(STORE, scope=USER))
    print(f"\n--- memories stored for {USER}: {len(mems)} ---")
    for m in mems:
        print(m)
    print("-" * 40)
    return mems


def clear_memories():
    c = _client()
    c.beta.memory_stores.delete_scope(STORE, scope=USER)
    print(f"cleared memories for {USER}")


async def session_a():
    agent = build_supervisor(user_id=USER)
    r = await agent.run("I manage the West region and I mostly care about Electronics.")
    print("A:", r.text)
    print("\nwaiting 45s for memory extraction...")
    await asyncio.sleep(45)
    show_memories()


async def session_b():
    print("Memories available BEFORE this session:")
    show_memories()
    agent = build_supervisor(user_id=USER)
    r = await agent.run("How are my products doing?")
    print("\nB:", r.text)


which = sys.argv[1] if len(sys.argv) > 1 else "a"
if which == "check":
    show_memories()
elif which == "clear":
    clear_memories()
else:
    asyncio.run(session_a() if which == "a" else session_b())