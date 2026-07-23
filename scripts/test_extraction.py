"""Force memory extraction directly, bypassing the provider's background timer."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

STORE = "zavaops_memory"
USER = "emp-001"

c = AIProjectClient(os.environ["FOUNDRY_PROJECT_ENDPOINT"],
                    DefaultAzureCredential(), allow_preview=True)

conversation = [
    {"type": "message", "role": "user",
     "content": "I manage the West region and I mostly care about Electronics."},
    {"type": "message", "role": "assistant",
     "content": "Understood - I'll scope your requests to the West region and Electronics category by default."},
]

print("triggering extraction...")
poller = c.beta.memory_stores.begin_update_memories(
    STORE, scope=USER, items=conversation, update_delay=0
)
result = poller.result()
print("extraction result:", result)

print("\nlisting memories:")
mems = list(c.beta.memory_stores.list_memories(STORE, scope=USER))
print(f"count: {len(mems)}")
for m in mems:
    print(m)