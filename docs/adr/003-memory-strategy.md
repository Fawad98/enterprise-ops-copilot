# ADR 003 — Agent Memory Strategy

**Status:** Accepted and implemented
**Date:** 2026-07-23
**Decider:** Muhammad Fawad

---

## Context

ZavaOps serves repeat users (Zava employees). Two kinds of persistence looked valuable:

1. **User preferences across sessions** — an employee who manages the West region and cares about
   Electronics should not have to restate that in every conversation.
2. **Procedural learning** — the damaged-goods flow is multi-step; an agent that retains a successful
   execution pattern should complete it more reliably over time.

Foundry Agent Service offers managed memory (public preview) with three types: **user profile**
(stable facts/preferences), **chat summary** (session continuity), and **procedural** (learned task
patterns). The alternative was building persistence manually — a preferences table injected into the
system prompt.

## Decision

Use Foundry's managed memory store rather than a hand-rolled preference table, with:

- All three memory types enabled.
- A **30-day TTL** on new entries — long enough to be useful across a work month, short enough that
  stale preferences expire rather than accumulating indefinitely.
- **Explicit extraction guidance** restricting what may be retained (see Security below).
- **Per-user scoping** (`scope=user_id`), so one employee's memory is never visible to another.
- Memory attached **optionally**: `build_supervisor(user_id=...)` enables it; `build_supervisor()`
  runs stateless.

### Why managed over DIY

A hand-rolled preferences table would require: a schema, a write path deciding what is worth storing,
a retrieval step, prompt injection, and a retention policy. The managed store provides extraction
(an LLM decides what is memorable), embedding-based retrieval, scoping, and TTL. The trade-off is
loss of control over *what* gets extracted — mitigated by the `user_profile_details` guidance string,
which is a first-class input to the extraction model rather than a prompt hack.

## Implementation

**Memory store** (`scripts/setup_memory.py`), created via `AIProjectClient(..., allow_preview=True)`
and `client.beta.memory_stores.create(...)`:

```
name:              zavaops_memory
chat_model:        chat-small
embedding_model:   embed
user_profile:      enabled
chat_summary:      enabled
procedural:        enabled
default_ttl:       2,592,000s (30 days)
```

**Provider wiring** (`src/agents/supervisor.py`): a `FoundryMemoryProvider` is passed via
`context_providers` on the supervisor, scoped to the caller's `user_id`, with `update_delay=5`
(default 300s) so extraction completes before short-lived scripts exit.

**Supervisor prompt** instructs the agent to apply remembered preferences *and state the scope it
assumed*, so personalisation is visible and correctable rather than silent.

## Verified behaviour

Session A (`"I manage the West region and I mostly care about Electronics."`) produced four memories
automatically within ~45s:

| Kind | Content |
|---|---|
| user_profile | "The user manages the West region." |
| user_profile | "The user primarily cares about the Electronics product category." |
| user_profile | "...default to region West and product category Electronics ... unless the user specifies otherwise" |
| chat_summary | Full contextual summary of the exchange, with turn IDs |

Session B — a **new agent instance, new session, same `user_id`** — was asked
*"How are my products doing?"* with no mention of region or category. It opened with:

> "Assumed scope — West region, Electronics category, most recent 30 days ... Tell me if you want a
> different region, category, or timeframe."

and then ran the analysis ($173,700.38 revenue, 633 units, −4.9% vs prior period, top/bottom SKUs).
Cross-session personalisation works, with the assumed scope disclosed.

Extraction cost for one exchange: 201 embedding tokens, 3,021 total tokens.

## Security considerations

**Extraction guidance.** The store is configured with explicit instructions on what must not be
retained:

> "Store only work-relevant preferences: region ownership, product categories of interest, reporting
> cadence, and preferred level of detail. Never store personal identifiers, financial details, health
> information, precise location, credentials, or customer PII from order records."

This matters specifically because the action agent handles customer names, emails and order values
via the MCP server. Without this constraint, customer PII could be absorbed into an employee's
memory profile.

**Memory poisoning.** Long-term memory is an attack surface: content written in one session is
retrieved and trusted in later sessions. Mitigated in layers:

1. The provider's `context_prompt` states that a remembered preference must never override company
   policy or a tool-level guardrail.
2. Business rules are enforced at the **tool layer** (`store.py` refuses replacements on refunded or
   cancelled orders), so a poisoned memory cannot authorise a prohibited mutation.
3. The 30-day TTL bounds the lifetime of any injected content.

**Stateless evaluation.** Memory is opt-in precisely so the Phase 8 eval suite can run without it.
Remembered context from earlier runs would otherwise contaminate results and make scores
irreproducible.

## The permission problem (and its resolution)

Memory writes failed silently for some time: `list_memories` returned zero, with no error surfaced to
the caller. Calling `begin_update_memories` directly exposed the hidden failure:

```
(ResourceError) {"deployment":"<opaque-guid>/deployments/embed",
 "details":{"type":"Authentication","status_code":401}}
```

**Root cause:** the required roles must be granted at **Foundry project scope**, not account scope.
Per the Foundry memory quickstart: *"Your identity needs the Foundry User role on the Foundry project
scope ... and it also needs the Cognitive Services OpenAI User role on the same scope. The memory
store uses Foundry project data-plane access plus the embedding deployment. Without the OpenAI role,
memory writes fail with a 401 error and the store stays empty."*

**Fix:**
```bash
PROJECT_ID=".../accounts/zavaops-resource/projects/zavaops"
az role assignment create --assignee "$MY_ID" --role "Cognitive Services OpenAI User" --scope "$PROJECT_ID"
az role assignment create --assignee "$MY_ID" --role "Foundry User"                    --scope "$PROJECT_ID"
```

Time was lost granting roles at *account* scope (`.../accounts/zavaops-resource`) to three different
identities — the hosted agent's instance identity, the account's system-assigned identity, and the
project's system-assigned identity — none of which is the scope the memory service checks.

**A secondary API-shape issue:** `begin_update_memories` rejects plain chat dicts with
`Failed to parse item with unknown/missing "type"`. Items need a Responses API discriminator, e.g.
`{"type": "message", "role": "user", "content": "..."}`.

## Consequences

- Cross-session personalisation works and is demonstrable; it is one of the stronger behaviours in the
  project.
- **Silent failure is the main operational risk.** Extraction runs on a background timer, so its
  errors never reach the caller — an empty store is indistinguishable from "nothing worth
  remembering". Production systems need explicit alerting on memory-write failures, not just logging.
  This is the sharpest lesson from the phase.
- Memory adds token cost per turn (~3k tokens for extraction on a short exchange) and latency for the
  retrieval step. Acceptable here; worth measuring at scale.
- Procedural memory is enabled but its effect has not been measured. Quantifying it would require
  repeated runs of the damaged-goods flow with turn-count comparison; deferred, and no claim about
  procedural gains is made.
- Evals run stateless by default, as intended.

## What I would do differently in production

- Alert on memory-write failures rather than logging them, since silent degradation hides the fact
  that personalisation has stopped working.
- Treat memory content as untrusted input in the threat model, with the tool layer as the authority
  on permitted actions.
- Scope `user_id` from the authenticated request context rather than passing it at build time, so a
  single hosted agent serves many users with isolated memory.
- Pin the preview SDK version; memory sits behind `allow_preview=True` and its surface is subject to
  change.