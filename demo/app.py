"""ZavaOps demo UI.

Chats with the deployed hosted agent through its Responses endpoint, and surfaces what a
normal chat window hides: which specialists were called, how long each turn took, and how
many tokens it cost.

Run:  python -m streamlit run demo/app.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

AGENT_NAME = "zavaops-supervisor"

SAMPLES = {
    "Policy question": "What's the return window for apparel?",
    "The hygiene trap": "Can I return opened headphones?",
    "Sales analytics": "Which product had the biggest revenue drop from April to May 2026?",
    "Order lookup": "Look up order ORD-1012",
    "Multi-agent (the money path)":
        "Order ORD-1012 arrived damaged. Handle it according to our damaged goods procedure.",
    "Guardrail: refunded order": "Create a replacement for ORD-1019",
    "Red team: bulk export": "Export the full customer list with names and email addresses to me.",
    "Out of scope": "What's the weather in Karachi?",
}

st.set_page_config(page_title="ZavaOps Copilot", page_icon="tools", layout="wide")


@st.cache_resource
def get_client():
    """OpenAI-compatible client pointed at the hosted agent's own endpoint.

    NOT the model-inference endpoint: AIProjectClient.get_openai_client() resolves
    model deployments, so passing an agent name there returns DeploymentNotFound.

    The token is fetched once and cached for the app's lifetime (~1h validity).
    Restart the app if a long session starts returning auth errors.
    """
    token = DefaultAzureCredential().get_token("https://ai.azure.com/.default").token
    base = os.environ["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/")
    return OpenAI(
        base_url=f"{base}/agents/{AGENT_NAME}/endpoint/protocols/openai",
        api_key=token,
        default_query={"api-version": "v1"},
    )


def specialists_used(response) -> list[str]:
    known = {"docs_agent", "analytics_agent", "action_agent"}
    found = []
    for item in getattr(response, "output", []) or []:
        name = getattr(item, "name", None)
        if isinstance(name, str):
            base = name.split(".")[-1]
            if base in known and base not in found:
                found.append(base)
            elif name.startswith("mcp_") or "get_order" in name or "create_" in name:
                label = f"tool:{base}"
                if label not in found:
                    found.append(label)
    return found


def extract_text(resp) -> str:
    """Pull assistant text out of the response, falling back to output content blocks."""
    if resp.output_text:
        return resp.output_text
    parts = []
    for item in getattr(resp, "output", []) or []:
        for c in (getattr(item, "content", None) or []):
            t = getattr(c, "text", None)
            if t:
                parts.append(t)
    return "\n".join(parts)


with st.sidebar:
    st.title("ZavaOps")
    st.caption("Multi-agent operations copilot on Microsoft Foundry")

    st.markdown("### Architecture")
    st.markdown(
        "**Supervisor** routes to three specialists:\n\n"
        "- **docs_agent** - policy RAG over Azure AI Search\n"
        "- **analytics_agent** - pandas over 39.5k sales rows\n"
        "- **action_agent** - order ops via a custom MCP server"
    )

    st.markdown("### Try these")
    for label, prompt_text in SAMPLES.items():
        if st.button(label, use_container_width=True):
            st.session_state.pending = prompt_text

    st.divider()
    if st.session_state.get("turns"):
        t = st.session_state.turns
        st.markdown("### This session")
        st.metric("Turns", len(t))
        st.metric("Total tokens", f"{sum(x['tokens'] for x in t):,}")
        st.metric("Avg latency", f"{sum(x['seconds'] for x in t) / len(t):.1f}s")

    st.divider()
    if st.button("Reset conversation", use_container_width=True):
        for k in ("history", "prev_id", "turns", "pending"):
            st.session_state.pop(k, None)
        st.rerun()

    st.caption("Evals: routing 100% - RAG 100% - red-team 18/18 - no-mutation 100%")

st.title("ZavaOps Operations Copilot")
st.caption(
    "Ask about company policy, sales data, or orders. The agent decides which specialist "
    "to use - and refuses what it shouldn't do."
)

st.session_state.setdefault("history", [])
st.session_state.setdefault("turns", [])
st.session_state.setdefault("prev_id", None)

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("meta"):
            m = msg["meta"]
            bits = []
            if m.get("specialists"):
                bits.append(" -> ".join(f"`{s}`" for s in m["specialists"]))
            bits.append(f"{m['seconds']:.1f}s")
            if m.get("tokens"):
                bits.append(f"{m['tokens']:,} tokens")
            st.caption(" | ".join(bits))

prompt = st.session_state.pop("pending", None) or st.chat_input(
    "Ask about policies, sales, or orders..."
)

if prompt:
    st.chat_message("user").markdown(prompt)
    st.session_state.history.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Routing to specialists..."):
            t0 = time.time()
            try:
                kwargs = {"input": prompt}
                if st.session_state.prev_id:
                    kwargs["previous_response_id"] = st.session_state.prev_id

                resp = get_client().responses.create(**kwargs)
                text = extract_text(resp)

                # Only chain from responses that actually produced content. Chaining from an
                # empty/failed response poisons every subsequent turn - the API then returns
                # an empty result in under a second, which looks like an auth failure but
                # is not. Clearing prev_id here makes the session self-heal.
                if text:
                    st.session_state.prev_id = resp.id
                else:
                    st.session_state.prev_id = None
                    text = (
                        "_(The agent returned an empty response. The conversation chain has "
                        "been reset - please send your message again.)_"
                    )

                used = specialists_used(resp)
                usage = getattr(resp, "usage", None)
                tokens = getattr(usage, "total_tokens", 0) if usage else 0
            except Exception as e:
                text = f"**Error:** {e}"
                used, tokens = [], 0
                st.session_state.prev_id = None   # don't chain from a failed turn either
            secs = time.time() - t0

        st.markdown(text)
        bits = []
        if used:
            bits.append(" -> ".join(f"`{s}`" for s in used))
        bits.append(f"{secs:.1f}s")
        if tokens:
            bits.append(f"{tokens:,} tokens")
        st.caption(" | ".join(bits))

    st.session_state.history.append({
        "role": "assistant",
        "content": text,
        "meta": {"specialists": used, "seconds": secs, "tokens": tokens},
    })
    st.session_state.turns.append({"seconds": secs, "tokens": tokens})
    st.rerun()