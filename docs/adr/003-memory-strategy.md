# ADR 003 — Agent Memory Strategy

**Status:** Partially implemented; retrieval deferred (preview limitation)
**Date:** 2026-07-23
**Decider:** Muhammad Fawad

---

## Context

ZavaOps serves repeat users (Zava employees). Two kinds of persistence looked valuable:

1. **User preferences across sessions** — an employee who manages the West region and cares about
   Electronics should not have to restate that every conversation.
2. **Procedural learning** — the damaged-goods flow is multi-step; an agent that retains a successful
   execution pattern should complete it more reliably over time.

Foundry Agent Service offers managed memory (public preview) with three types: **user profile**
(stable facts/preferences), **chat summary** (session continuity), and **procedural** (learned task
patterns). The alternative was building persistence myself — a database of user preferences injected
into the system prompt.

## Decision

Use Foundry's managed memory store rather than a hand-rolled preference table, with:

- All three memory types enabled.
- A **30-day TTL** on new entries — long enough to be useful across a work month, short enough that
  stale preferences expire rather than accumulating indefinitely.
- **Explicit extraction guidance** restricting what may be retained (see Security below).
- **Per-user scoping** (`scope=user_id`), so one employee's memory is never visible to another.
- Memory attached **optionally** — `build_supervisor(user_id=...)` enables it; `build_supervisor()`
  runs stateless.

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
`context_providers` on the supervisor, scoped to the caller's `user_id`.

## Security considerations

**Extraction guidance.** The store is configured with explicit instructions on what must not be
retained:

> "Store only work-relevant preferences: region ownership, product categories of interest, reporting
> cadence, and preferred level of detail. Never store personal identifiers, financial details, health
> information, precise location, credentials, or customer PII from order records."

This matters specifically because the action agent handles customer names, emails and order values via
the MCP server. Without this constraint, customer PII could be absorbed into an employee's memory
profile.

**Memory poisoning.** Long-term memory is an attack surface: content written during one session is
retrieved and trusted in later sessions. The mitigation here is layered:

1. The provider's `context_prompt` states that a remembered preference must never override company
   policy or a tool-level guardrail.
2. Business rules are enforced at the **tool layer** (`store.py` refuses replacements on refunded or
   cancelled orders), so a poisoned memory cannot authorise a prohibited mutation.
3. The 30-day TTL bounds the lifetime of any injected content.

**Stateless evaluation.** Memory is opt-in precisely so the Phase 8 eval suite can run without it.
Remembered context from earlier runs would otherwise contaminate results and make scores
irreproducible.

## Outcome: extraction blocked by a preview limitation

The store was created successfully and the provider wired in, but **no memories are ever written**.
`list_memories` consistently returns zero for the scope, so retrieval has nothing to find.

**Diagnosis.** Bypassing the provider and calling the extraction API directly
(`beta.memory_stores.begin_update_memories`) surfaced the error that had been failing silently in the
provider's background task:

```
HttpResponseError: (ResourceError)
{"message":"Provided Azure resource encountered an error.",
 "deployment":"fd0b5fc6ebba4d28a8faf76fc090d8bd/deployments/embed",
 "details":{"type":"Authentication","status_code":401,
            "description":"Authentication to the Azure OpenAI resource failed."}}
```

The managed memory service accepts the request, starts the long-running operation, and then fails
authenticating to the **embedding deployment** it was configured with. Because the provider performs
extraction on a background timer (`update_delay`, default 300s), this error is never surfaced to the
caller — the only symptom is that memories silently never appear.

This also explains earlier intermittency: the **search** path sometimes succeeded (returning empty
without needing an embedding call), while the **extraction** path failed every time, since it must
embed.

**What was investigated.** Foundry has at least three distinct managed identities in play, none named
in the error:

| Identity | Used for | Granted |
|---|---|---|
| Hosted agent instance identity | The agent's own model + Search calls | Cognitive Services OpenAI Contributor, Search Index Data Reader |
| Account system-assigned identity (`zavaops-resource`) | Account-level operations | Cognitive Services OpenAI Contributor |
| Project system-assigned identity (`zavaops`) | Assumed to be the memory service | Cognitive Services OpenAI Contributor |

Finding the third required querying the project resource's `identity` block directly
(`az resource show --ids .../projects/zavaops --query identity`); nothing in the error points to it.

Also ruled out:
- The `embed` deployment is healthy (`text-embedding-3-small`, `Succeeded`).
- Key-based auth is enabled on the account (`disableLocalAuth: false`), so the service is not being
  refused a key-auth path.
- The opaque identifier `fd0b5fc6ebba4d28a8faf76fc090d8bd` in the error does not correspond to any of
  the three principals above and cannot be resolved to a grantable object ID via the Azure CLI.

**A secondary API-shape issue was found and fixed along the way:** `begin_update_memories` rejects
plain chat dicts with `Failed to parse item with unknown/missing "type"`. Items must carry a Responses
API discriminator, e.g. `{"type": "message", "role": "user", "content": "..."}`.

**Decision: stop and document.** Three identities granted the correct role at the correct scope, a
verified-healthy deployment, key auth available, and a failure against an identity that cannot be
enumerated is a preview-service limitation rather than a configuration defect. Further investigation
has poor expected value relative to the remaining project work; the appropriate next step would be a
support/GitHub issue with the request IDs, not more role assignments.

## Consequences

- The memory design, security reasoning and wiring are complete and version-controlled; only the
  service-side extraction step fails. If the preview stabilises, no code changes should be required.
- The agent **degrades gracefully**: the run completes normally with no remembered context. But the
  failure is *silent* — extraction happens on a background timer, so its error never reaches the
  caller. This is the sharpest lesson from the phase: a background task that fails quietly is
  indistinguishable from one that has nothing to do. Production systems need explicit alerting on
  memory-write failures, not just logging.
- The procedural-memory experiment (measuring turn-count reduction across repeated damaged-goods runs)
  is deferred; no claim about procedural gains is made in this project.
- Evals run stateless by default, which was the intent regardless.

## What I would do differently in production

- Wrap the preview Memory Store REST API directly rather than depending on SDK surface that is gated
  behind `allow_preview=True` and subject to change.
- Alert on memory-search failures instead of logging them, since silent degradation hides the fact
  that personalisation has stopped working.
- Treat memory writes as untrusted input in the threat model, with the tool layer as the authority on
  what actions are permitted.