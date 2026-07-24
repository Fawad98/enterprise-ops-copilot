# ADR 002 — Multi-Agent Orchestration Pattern

**Status:** Accepted
**Date:** 2026-07-24
**Decider:** Muhammad Fawad

---

## Context

ZavaOps must answer three unrelated kinds of request against three unrelated backends:

| Domain | Backend | Tools |
|---|---|---|
| Company policy | Azure AI Search (hybrid retrieval over 27 indexed chunks) | 1 |
| Sales analytics | pandas over a 39,555-row CSV | 1 |
| Order operations | Custom MCP server on Azure Functions | 5 |

Requests range from single-domain lookups ("what's the return window for apparel?") to sequences
that need policy *and* action ("Order ORD-1012 arrived damaged — handle it per our procedure").

Four orchestration patterns were considered.

## Options considered

### 1. Single agent with all seven tools

One agent, one prompt, seven tools spanning retrieval, code execution and order mutation.

*Rejected.* Tool-selection accuracy degrades as tool count and domain diversity grow, and there is no
way to give retrieval, code execution and order mutation the different system prompts they each need.
The action tools require strict safety framing ("look up before mutating", "relay guardrail errors
verbatim and stop") that would sit awkwardly in the same instruction block as "always call
search_policies before answering". A single prompt would have to be a compromise across three jobs.

It also collapses the eval story: a routing failure and a retrieval failure would be
indistinguishable, because there would be no routing decision to measure.

### 2. Handoff / swarm

Specialists talk to the user directly; control passes between them.

*Rejected.* Multi-domain requests would produce several disconnected replies rather than one coherent
answer, and no component would own the final synthesis. It also makes safety harder: with the action
agent addressing the user directly, there is no supervisor to relay a guardrail refusal and stop —
which is exactly the behaviour required in the damaged-goods flow.

### 3. Fixed workflow graph

A hard-coded DAG: classify, then follow a predetermined path.

*Rejected as premature.* It would handle the known money path well but requires a new branch for every
request shape. The observed traffic is open-ended employee questions, not a fixed process. Worth
revisiting if a small number of flows come to dominate usage, where determinism would beat flexibility.

### 4. Supervisor with agents-as-tools — **chosen**

One supervisor owns the conversation and calls specialists as tools
(`docs.as_tool()`, `analytics.as_tool()`, `action.as_tool()`).

## Decision

**Supervisor with agents-as-tools.**

Rationale:

- **Separate prompts per domain.** Each specialist gets instructions appropriate to its risk profile:
  the docs agent is told to never answer without retrieving; the action agent gets explicit READ vs
  WRITE rules and "relay tool errors verbatim and STOP"; the analytics agent gets the dataframe schema.
- **One coherent answer.** The supervisor synthesises specialist output rather than concatenating it,
  and preserves citations and figures.
- **Routing is measurable.** Because routing is an explicit decision, it can be evaluated
  independently of answer quality (22 dedicated eval cases).
- **Safety composes.** A guardrail refusal from the tool layer propagates up through the specialist to
  the supervisor, which relays it and stops — verified in red-team testing.
- **Small tool count per agent** (1, 1, 5) keeps selection accuracy high within each domain.

## Evidence

**Routing accuracy: 100% across 22 cases** (5 docs, 5 analytics, 4 action, 3 multi-agent sequences,
5 out-of-scope). Baseline was 90.9%; the two failures were the supervisor asking clarifying questions
on under-specified queries, fixed with a "bias to act" instruction. Notably, red-team refusal rate
stayed at 100% after that change — biasing toward action did not weaken adversarial refusal.

**The supervisor does real orchestration, not just dispatch.** In the money-path trace, it did not
forward the user's question to `action_agent`; it composed a seven-step task specification, with the
eligibility gate embedded, and named the downstream context:

> "Handle Order ORD-1012 per the damaged-goods procedure. Steps to perform:
> 1) Verify order ORD-1012 exists and retrieve its current status and delivery date.
> 2) Confirm the damage report is within 14 days of the delivery date. If outside 14 days, stop and
> escalate/route to warranty (do not create replacement). …"

It had first asked `docs_agent` for "the damaged goods procedure steps **and any required fields or
evidence needed for the action_agent to execute the procedure**" — framing the first specialist's task
in terms of the second's needs.

**Sequencing works on multi-domain requests.** The same trace shows
`docs_agent` (20.07s) → `action_agent` (27.10s), with the policy context passed forward. The action
agent then computed eligibility (34 days since delivery, outside the 14-day window), declined to
create a replacement, created escalation ticket TKT-0002 at `high` priority (Electronics + >$200), and
reported an explicit "Actions NOT performed" list.

**Out-of-scope requests are declined rather than force-routed** (5/5), e.g. a weather question
produced a scope explanation and an offer to help with anything Zava-related.

## Consequences

- **Latency cost.** Each specialist call is a nested agent invocation with its own model round-trips.
  The money path took 70.0s across 8 chat calls and 54 spans. Tracing shows **>90% of wall-clock is
  model inference**; retrieval (858ms) and all MCP calls (30–74ms each) together are under 2 seconds.
  A single-agent design would be faster but would sacrifice the separation above. Optimisation should
  target the number of model round-trips, not tool performance.
- **Token cost.** 14,800 tokens for one money-path request, driven by context being restated to each
  specialist.
- **Debuggability is good.** The trace tree shows supervisor → specialist → tool → HTTP, so a failure
  can be attributed to a layer immediately.
- **Prompt surface is larger.** Four prompts to maintain instead of one, and instructions can conflict
  across them — the "bias to act" rule had to be checked against red-team refusal behaviour.

## Revisit if

- A small number of flows come to dominate traffic — a fixed workflow graph would then give
  determinism and lower latency for those paths.
- Latency becomes a product constraint — a router that dispatches to a *single* specialist without a
  synthesis round-trip would cut model calls roughly in half for single-domain requests.
- Specialist count grows beyond about five — the supervisor's own tool-selection accuracy would then
  face the problem this pattern was chosen to avoid.