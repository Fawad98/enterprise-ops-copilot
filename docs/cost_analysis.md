# Cost Analysis

Measured, not estimated, except where marked. All figures from Application Insights telemetry and
Azure pricing as of July 2026.

---

## Measured token usage

One day of active development and testing, from App Insights:

| Agent | Model | Calls | Input | Output | Cached | Total |
|---|---|---|---|---|---|---|
| `zavaops-supervisor` (hosted) | chat-small | 38 | 73,331 | 31,163 | **0** | 104,494 |
| `action-agent-test` (Portal prompt agent) | gpt-5-mini | 4 | 21,535 | 439 | 15,605 | 21,974 |

### Per-request cost drivers

**Input dominates.** A single *"Look up order ORD-1012"* call consumed **4,827 input tokens against
52 output tokens** — a 93:1 ratio. The system prompt, tool schemas and conversation history are
re-sent on every call; the model generates very little.

**The supervisor pattern compounds this.** Each specialist invocation carries its own system prompt
and tool definitions. The multi-agent money path costs **14,800 tokens across 8 chat calls** for one
user request.

**Prompt caching is not engaging on the hosted agent.** The Portal prompt agent cached 72% of its
input tokens (15,605 / 21,535). The hosted supervisor cached **zero across 38 calls**. Cause
unresolved — this is the single largest identified cost lever, since input is ~70% of spend.

---

## Cost per interaction

At `gpt-5-mini` pricing (verify current rates — these are order-of-magnitude):

| Interaction | Chat calls | Tokens | Approx. cost |
|---|---|---|---|
| Simple policy question | 2 | ~5,000 | fractions of a cent |
| Analytics query | 2–3 | ~8,000 | ~$0.01 |
| Multi-agent money path | 8 | 14,800 | ~$0.02 |
| **Full eval suite (66 cases)** | ~150 | ~250,000 | **~$0.30** |

The eval gate runs on every push. At roughly $0.30 per run, a busy repo would want the split
suggested below.

---

## Infrastructure

| Resource | Tier | Monthly | Notes |
|---|---|---|---|
| Azure AI Search `srch-zavaops-dev` | **Free** | **$0** | Sufficient for 27 chunks. Basic (~$75/mo) needed for SLA and larger semantic ranking quota |
| Function App `func-zavaops-mcp-dev-01` | Consumption | **<$1** | Tool calls are 39–74ms; well inside the free grant |
| Storage `stzavaopsmcpdev` | Standard LRS | **<$1** | Function App runtime only |
| Application Insights | Pay-as-you-go | **<$5** | Trace volume from development |
| Foundry account + project | — | **$0** | No charge for the resource itself |
| Hosted agent runtime | Consumption | **~$0** | 1 CPU / 2 GiB, billed on active sessions |
| Container Registry | Basic | **<$5** | Agent images |
| **Total fixed** | | **~$10/mo** | Plus token usage |

**The dominant cost is tokens, not infrastructure.** Choosing the free Search tier removed what would
otherwise have been the largest line item ($75/mo) at no functional cost for this dataset size.

---

## Where the money goes

From tracing, model inference is >90% of wall-clock time and effectively all of the marginal cost:

| Operation | p50 latency | Marginal cost |
|---|---|---|
| `chat chat-small` (n=28) | 3,526ms | **Everything** |
| `execute_tool search_policies` | 959ms | Embedding call only (~200 tokens) |
| `execute_tool run_pandas` | 47ms | $0 — local compute |
| MCP `get_order` | 74ms | $0 — within Functions free grant |
| MCP `create_ticket` | 39ms | $0 |

Tools are free and fast. **Every optimisation lever is about reducing model round-trips.**

---

## Optimisation levers, ranked

1. **Fix prompt caching on the hosted agent.** Input is ~70% of tokens and currently zero of it is
   cached, while a Portal agent on the same account achieves 72%. Potential saving: substantial.
2. **Reduce specialist invocations.** The supervisor sometimes calls a specialist and then makes a
   further model call to synthesise a one-line answer. A direct-dispatch path for single-domain
   requests would roughly halve calls for simple queries.
3. **Trim system prompts and tool schemas.** These are re-sent on every call to every specialist.
4. **Split the eval gate.** Routing + red-team on PRs (~40 cases, ~20 min, ~$0.18); full suite
   nightly. Currently ~35 min and ~$0.30 per push.
5. **Cheaper model for routing.** The supervisor's routing decision is a classification task and may
   not need the same model as synthesis.

---

## Cost controls in place

- **Budget alert** at $50/month with notifications at 50/80/100%.
- **Free-tier Search**, avoiding the largest infrastructure line item.
- **Consumption plans** for the Function App and hosted agent — near-zero when idle.
- **Small model** (`chat-small`) throughout; no large-model benchmarking was run.
- **`azd down`** tears down agent infrastructure between working sessions.

## Cost controls *not* in place

- **No rate limiting.** A shared demo link could be abused. This is why the project ships a recorded
  demo rather than a public URL.
- **No per-user quotas.** Foundry AI Gateway would provide both.
- **No spend alerting on token usage specifically** — only the overall subscription budget.
