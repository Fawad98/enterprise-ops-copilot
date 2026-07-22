import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from src.agents.docs_agent import build_docs_agent

QUESTIONS = [
    "Can I return an opened laptop after 20 days?",
    "What's the return window for apparel?",
    "Can I return opened headphones?",
]

async def main():
    agent = build_docs_agent()
    for q in QUESTIONS:
        print("\n" + "=" * 70)
        print(f"Q: {q}")
        print("-" * 70)
        r = await agent.run(q)
        print(f"A: {r.text}")

asyncio.run(main())