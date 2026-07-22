import os
from typing import Annotated
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from agent_framework import tool
from agent_framework.openai import OpenAIChatClient

from src.rag.retriever import hybrid_search
from src.rag.ingest import embed

load_dotenv()

DOCS_SYSTEM_PROMPT = """You are Zava's policy expert. Answer ONLY from retrieved policy excerpts.
Rules:
- ALWAYS call search_policies before answering.
- Cite sources inline like [returns-policy.md].
- If the excerpts don't contain the answer, say "I couldn't find this in our policies" — never guess.
- Quote exact numbers (days, percentages, fees) precisely."""


@tool
def search_policies(query: Annotated[str, "The search query for policy documents"]) -> str:
    """Search Zava company policy documents for returns, shipping, warranties, and procedures."""
    vec = embed([query])[0]
    hits = hybrid_search(query, vec, k=4)
    return "\n\n---\n\n".join(f"[{h['source']}]\n{h['content']}" for h in hits)


def build_docs_agent():
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    chat_client = OpenAIChatClient(
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        credential=token_provider,
    )
    return chat_client.as_agent(
        name="docs_agent",
        instructions=DOCS_SYSTEM_PROMPT,
        tools=[search_policies],
    )