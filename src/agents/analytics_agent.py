import io
import os
import contextlib
from typing import Annotated

import pandas as pd
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from agent_framework import tool
from agent_framework.openai import OpenAIChatClient

load_dotenv()

_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "sales.csv")
DF = pd.read_csv(_CSV, parse_dates=["date"])

ANALYTICS_PROMPT = """You are Zava's data analyst. You answer questions about sales data by writing
pandas code against a DataFrame `df` with columns:
  date (datetime), product (e.g. SKU-0007), category, region, unit_price, quantity, revenue
Date range: 2025-07-01 to 2026-06-30.

Rules:
- ALWAYS call run_pandas before answering. Never estimate or guess numbers.
- Print results you want to see: the tool returns whatever your code prints.
- Report concrete figures with units (currency, counts, percentages).
- If a query returns nothing useful, revise the code and try again.
- Keep answers concise: the number, the context, and one sentence of interpretation."""


@tool
def run_pandas(
    code: Annotated[str, "Python/pandas code. `df` and `pd` are available. Use print() to output results."]
) -> str:
    """Execute pandas code against the Zava sales DataFrame `df` and return whatever it prints."""
    banned = ("import os", "import sys", "open(", "__", "subprocess", "eval(", "exec(",
              "importlib", "globals(", "locals(")
    if any(b in code for b in banned):
        return "ERROR: disallowed operation in code"
    buf = io.StringIO()
    safe_builtins = {
        "print": print, "len": len, "round": round, "min": min, "max": max,
        "sum": sum, "sorted": sorted, "list": list, "dict": dict, "set": set,
        "range": range, "abs": abs, "str": str, "int": int, "float": float,
        "zip": zip, "enumerate": enumerate,
    }
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, {"df": DF.copy(), "pd": pd, "__builtins__": safe_builtins})
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
    out = buf.getvalue()
    return out[:4000] if out else "(no output - use print() to show results)"


def build_analytics_agent():
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    chat_client = OpenAIChatClient(
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        credential=token_provider,
    )
    return chat_client.as_agent(
        name="analytics_agent",
        description="Answers questions about Zava sales data: revenue, trends, products, regions, categories.",
        instructions=ANALYTICS_PROMPT,
        tools=[run_pandas],
    )
