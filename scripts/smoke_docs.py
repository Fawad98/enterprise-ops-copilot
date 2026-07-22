# scripts/smoke_docs.py
import asyncio
from src.agents.docs_agent import build_docs_agent

async def main():
    agent = build_docs_agent()
    r = await agent.run("Can I return an opened laptop after 20 days?")
    print(r.text)

asyncio.run(main())