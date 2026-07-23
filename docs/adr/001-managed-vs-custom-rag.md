# ADR 001 — Managed RAG (Foundry File Search) vs Custom RAG (Azure AI Search)

**Status:** Accepted
**Date:** 2026-07-22
**Decider:** Muhammad Fawad

---

## Context

The Docs agent must answer Zava employee questions grounded strictly in company policy documents,
with citations, and must refuse when the answer isn't in the policies. I built and compared two
approaches to grounding:

- **Custom RAG** — a hand-built pipeline: paragraph-aware chunking with overlap, `text-embedding-3-small`
  embeddings, an Azure AI Search index with hybrid retrieval (BM25 + vector) and semantic reranking,
  consumed by a Microsoft Agent Framework agent via a `search_policies` tool.
  Files: `src/rag/ingest.py`, `src/rag/retriever.py`, `src/agents/docs_agent.py`.
- **Managed RAG** — a Foundry prompt agent with the built-in **File Search** tool. The same 8 policy
  files were uploaded through the portal; Foundry handled chunking, embedding, vector-store creation,
  and retrieval with no ingestion code.

Both were tested against the same three questions, each targeting a deliberately-planted policy edge
case (these questions are also in `evals/datasets/rag_qa.jsonl`):

1. *"Can I return an opened laptop after 20 days?"* -> tests the opened-electronics **15% restocking fee**.
2. *"What's the return window for apparel?"* -> tests the **45-day category override** (vs the default 30).
3. *"Can I return opened headphones?"* -> tests the **hygiene exclusion** (non-returnable), and whether the
   agent avoids the trap of applying the electronics restocking-fee rule instead.

---

## Results

### Custom RAG (verified)

All three correct, with citations:

1. **Opened laptop** - correctly returned the 30-day electronics window with the **15% restocking fee**,
   and added the nuance that the window is measured from the carrier-recorded delivery date.
   Cited `[returns-policy.md]`.
2. **Apparel** - correctly returned **45 days** (respected the category override, not the default 30) and
   surfaced the original-tags requirement. Cited `[returns-policy.md]`.
3. **Opened headphones** - correctly identified them as **non-returnable (hygiene)**, and - notably -
   proactively disambiguated the trap: it acknowledged the opened-electronics 15% restocking-fee rule
   exists but reasoned that the category-specific hygiene rule governs headphones. It also cross-referenced
   the damaged-goods fallback from `[damaged-goods-procedure.md]`.

Retrieval quality was inspectable: the retriever returned reranker scores (e.g. ~2.46 for the top
`returns-policy.md` chunk on the laptop question), which I can log and later feed into traces/evals.

### Managed RAG (Foundry File Search) - verified

All three correct, with citations. Observed answers (chat-small model, File Search tool):

1. **Opened laptop** - correct: 30-day electronics window with the **15% restocking fee**; also
   surfaced the delivery-date-not-order-date nuance, the 5-business-day refund timing, the
   return-shipping rule, and the damaged-goods exemption. The most *thorough* of the two agents on
   this question. Latency ~21.4s, ~10,821 tokens.
2. **Apparel** - correct: **45 days**, original tags required. Concise. Latency ~5.1s, ~14,240 tokens.
3. **Opened headphones** - correct: **non-returnable** (headphones/earbuds/personal grooming, hygiene).
   Concise and correct, though it did not proactively disambiguate the electronics-restocking-fee trap
   the way the custom agent did (it simply gave the correct exclusion).

**Accuracy: 3/3 - a tie with the custom agent on correctness.**

Observed differences:
- **Citation style:** numbered footnote markers (`[returns-policy.md] 1`, `2`, `3`) with a reference
  list, vs the custom agent's clean inline `[returns-policy.md]`.
- **Observability:** the portal exposes per-turn **traces, latency, and token counts** - useful - but
  does **not** surface retrieval/reranker **scores** the way the custom pipeline does. So it is not a
  total black box, but retrieval-quality signal is not available for eval tuning.
- **Verbosity:** the managed agent was noticeably more verbose on Q1 (volunteered many adjacent policy
  points); the custom agent was tighter. Neither is strictly better - a prompt/temperature choice.

---

## Comparison

| Dimension | Custom (Azure AI Search) | Managed (Foundry File Search) |
|---|---|---|
| Setup effort | Hours: index schema, chunking strategy, embed pipeline, retriever, plus debugging (endpoint routing, SDK drift) | ~15 min: create agent, upload files, wait for indexing |
| Code to maintain | ~2 modules (`ingest.py`, `retriever.py`) | None |
| Edge-case accuracy (3 planted cases) | 3/3 correct with citations | 3/3 correct with citations (tie) |
| Citation format | Clean inline `[filename.md]`, controlled by my tool output + prompt | Numbered footnote markers (`[returns-policy.md] 1, 2, 3`) + reference list |
| Control over retrieval | Full - I set chunk size, overlap, `k`, hybrid + semantic rerank | None - chunking/retrieval are platform-managed defaults |
| Observability into retrieval | Full - reranker scores visible and loggable (feed into Phase 9 traces) | Partial - portal shows traces/latency/tokens, but NOT retrieval/reranker scores |
| Cost model | Azure AI Search service (free tier in dev) + embedding token calls | File Search adds charges beyond model tokens; spins up a managed vector store |
| Data control | I own the index and store | Files stored in project storage; vector store managed by Foundry |
| Portability / lock-in | Portable - the vector store could be swapped for any provider | Tied to Foundry's File Search |
| Time-to-first-answer | Slow to build, fast to iterate once built | Fastest possible start |

---

## Decision

**Use the Custom RAG pipeline for the production Docs agent**, and keep the managed File Search agent
as a documented reference point.

Rationale (note: both agents tied at 3/3 accuracy, so the decision rests on control/observability,
not correctness):
- The custom pipeline exposes **retrieval scores**, which I need for the observability dashboard
  (Phase 9) and for tuning against the eval suite (Phase 8). The managed path shows traces and token
  counts but not retrieval-quality scores.
- I control **chunking and retrieval parameters**, which matters for the planted edge cases where the
  right chunk must be retrieved to avoid the headphones/electronics trap.
- It avoids **lock-in** - the retrieval layer is portable.

The managed path is not "worse." It's the **right call when speed and zero maintenance outweigh
control** - e.g. a freelance client who wants a working prototype this afternoon. For that scenario
I would start with File Search and migrate to a custom pipeline only if retrieval tuning or
observability became necessary.

---

## Consequences

- I must maintain the ingestion pipeline and **re-run `ingest.py` whenever policies change**. (Mitigation:
  make ingestion a step in CI, Phase 10.)
- Reranker scores are available to the observability layer (Phase 9) and eval gate (Phase 8).
- For a speed-first client engagement, the fallback path (managed File Search) is already validated and
  documented here.
- Two grounding implementations exist in the repo; the managed one is clearly labeled as a reference,
  not the production path, to avoid confusion.

---

## Notes for interviews

The reason to build both: understanding the managed abstraction **and** what it hides. Managed File
Search trades control and observability for speed and zero maintenance. Custom RAG earns its keep when
you need to tune retrieval, expose scores to evals/traces, or avoid lock-in. Knowing *when* each is the
right tool - rather than defaulting to one - is the actual engineering judgment.

A concrete "what the abstraction costs" data point: the managed File Search always builds a vector
index and uses a managed retrieval path with its own charges; you trade transparency (no visible
retrieval scores) and per-query cost for not writing or operating any retrieval code.