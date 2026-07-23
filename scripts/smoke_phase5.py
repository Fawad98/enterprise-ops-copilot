"""Phase 5 smoke tests. Run each stage separately so failures are easy to localize.

Usage:
    PYTHONPATH=. python scripts/smoke_phase5.py analytics
    PYTHONPATH=. python scripts/smoke_phase5.py action
    PYTHONPATH=. python scripts/smoke_phase5.py supervisor
    PYTHONPATH=. python scripts/smoke_phase5.py routing
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()


async def run(agent, questions):
    for q in questions:
        print("\n" + "=" * 72)
        print(f"Q: {q}")
        print("-" * 72)
        try:
            r = await agent.run(q)
            print(f"A: {r.text}")
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")


async def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "supervisor"

    if which == "analytics":
        from src.agents.analytics_agent import build_analytics_agent
        # Ground truth (from data/generate_data.py): SKU-0007 biggest May drop,
        # Electronics top category, West ~25% -> ~40% share from April 2026.
        await run(build_analytics_agent(), [
            "Which product had the biggest revenue drop from April to May 2026?",
            "Which category has the highest total revenue?",
            "How did the West region's share of orders change after April 2026?",
        ])

    elif which == "action":
        from src.agents.action_agent import build_action_agent
        await run(build_action_agent(), [
            "Look up order ORD-1012",
            "Create a replacement for ORD-1012, reason: damaged on arrival",
            "Create a replacement for ORD-1019",   # refunded -> should hit the guardrail
        ])

    elif which == "routing":
        from src.agents.supervisor import build_supervisor
        await run(build_supervisor(), [
            "What's the return window for apparel?",              # -> docs
            "Which category has the highest total revenue?",      # -> analytics
            "Look up order ORD-1012",                             # -> action
            "What's the weather in Karachi?",                     # -> none, should decline
        ])

    else:  # supervisor - the money path
        from src.agents.supervisor import build_supervisor
        await run(build_supervisor(), [
            "Order ORD-1012 arrived damaged. Handle it according to our damaged goods procedure.",
        ])


asyncio.run(main())
