# Challenges & Solutions

A running log of real problems hit while building the Enterprise Operations Copilot, and how they
were resolved. Kept as an engineering artifact: each entry records the symptom, the root cause, the
fix, and the lesson — the kind of context that's easy to lose once code "just works."

---

## 1. Budget creation blocked: "client does not have authorization to perform action"

**Phase:** 0 (environment setup)

**Symptom:** Creating a cost budget in the Azure Portal failed with an authorization error, even
though my account had **Owner** and **User Access Administrator** on the resource.

**Root cause:** Budgets live under **Cost Management**, which is billing-scoped, not resource-scoped.
Owner on a *resource* doesn't grant `Microsoft.Consumption/budgets/write`. Some subscription types
(free/MSDN/sponsored) also gate budget creation behind a billing scope above the subscription.

**Fix / workaround:** Create the budget from inside the **Subscription blade → Budgets** (pins it to
subscription scope), or fall back to manual cost monitoring via Cost Analysis. Not a blocker for the
project — the budget is a safety convenience, not a dependency.

**Lesson:** Azure RBAC scope matters as much as the role. "Owner" is not omnipotent; billing actions
are a separate permission plane.

---

## 2. `azd ai agent init` reported success but wrote no files

**Phase:** 1 (hosted-agent pipeline validation)

**Symptom:** `azd ai agent init` printed a full success summary (downloaded sample, "Copying template
code…"), but afterward `azure.yaml` didn't exist anywhere, and `azd up` failed with
`no project exists`.

**Root cause:** Working-directory confusion. An earlier `mkdir _validate && cd _validate` where the
`mkdir` failed ("File exists") but the `cd` still ran left the terminal in an ambiguous state, and the
scaffold didn't persist. On a clean re-run from a known-empty folder, the files landed correctly —
but in a **nested subfolder** (`validate/agent-framework-agent-basic-responses/`), not the current dir.

**Fix:** Always scaffold from a fresh, known-empty directory, and immediately verify with
`find . -name "azure.yaml"` before running any `azd` command. `azd` only works from the folder
containing the manifest.

**Lesson:** Never trust a tool's "success" message over the filesystem. Verify artifacts exist
(`ls`/`find`) before the next step. Chained shell commands (`&&`) can partially fail silently.

---

## 3. Embeddings call returned HTTP 404 on `/embeddings`

**Phase:** 3 (RAG ingestion)

**Symptom:** `openai.NotFoundError: Error code: 404` when calling `openai_client.embeddings.create(...)`
in `ingest.py`. Auth clearly worked (no 401) — the URL just didn't exist.

**Root cause (two compounding issues):**
1. The client was pointed at the **project endpoint** (`.../api/projects/zavaops`), but embeddings
   route to the **account (base) endpoint** (`https://<account>.cognitiveservices.azure.com/`).
   The project endpoint doesn't route `/embeddings`.
2. The actual resource names differed from the guide's examples. The account is named
   `zavaops-resource` (auto-named by the Foundry project wizard as `<project>-resource`), and the
   resource group is `foundry-zavaops-dev`, not the assumed `rg-zavaops-dev`.

**Fix:** Build the embedding client with the explicit account endpoint and a stable API version:
```python
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
tp = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
client = AzureOpenAI(azure_endpoint="https://zavaops-resource.cognitiveservices.azure.com/",
                     azure_ad_token_provider=tp, api_version="2024-10-21")
```
Confirmed real names with:
```bash
az cognitiveservices account list -g foundry-zavaops-dev --query "[].{name:name, endpoint:properties.endpoint}" -o table
```

**Lesson:** In Foundry, the **project endpoint** and the **account endpoint** are different URLs with
different routing. Embeddings and direct model calls use the account endpoint. Also: never assume
resource names from a guide — the provisioning wizard auto-names things; verify with the CLI.

---

## 4. Deployment name typo (`enbed` vs `embed`)

**Phase:** 3

**Symptom:** After fixing the endpoint, still a 404 — because the embedding model had been deployed
under the misspelled name `enbed`, while the code referenced `embed`.

**Fix:** Redeployed the model with the correct name and verified deployments with:
```bash
az cognitiveservices account deployment list --name zavaops-resource -g foundry-zavaops-dev \
  --query "[].{name:name, model:properties.model.name, status:properties.provisioningState}" -o table
```

**Lesson:** The deployment **name** (not the model name) is what code calls, and it must match
character-for-character. Verify deployment names against the code constant early.

---

## 5. `ModuleNotFoundError: No module named 'azure'` / `'src'`

**Phase:** 3

**Symptom:** Two related path problems: (a) `azure` not found because dependencies weren't installed
in the active environment; (b) `No module named 'src'` when running a script from inside `scripts/`.

**Fix:**
- (a) Activate the venv (`source .venv/bin/activate`) and `pip install -e ".[dev]"`.
- (b) Run with the repo root on the path: `PYTHONPATH=. python scripts/test_retriever.py`, or add a
  `sys.path.insert(0, <repo-root>)` shim at the top of standalone scripts.

**Lesson:** `python -m package.module` (from root) resolves imports differently than
`python path/to/script.py`. For scripts that import project packages, set `PYTHONPATH=.` or use `-m`.

---

## 6. Agent Framework API drift: class/method names didn't match the guide

**Phase:** 3 (docs agent)

**Symptom:** A cascade of `ImportError` / `AttributeError`:
- `cannot import name 'ChatAgent' from 'agent_framework'`
- `'OpenAIChatClient' object has no attribute 'create_agent'`

**Root cause:** The guide's example code was written against an earlier Agent Framework API. Installed
version was **1.12.0**, where the names had changed.

**Fix — the actual 1.12.0 API (verified via `dir()` and `inspect.signature`):**
- `ChatAgent` → build from a chat client, then call `.as_agent(name=, instructions=, tools=)`.
- `ai_function` decorator → `tool`.
- Chat client lives in `agent_framework.openai.OpenAIChatClient` (installed via the
  `agent-framework-azure-ai` / openai provider extra), and natively supports Azure via
  `azure_endpoint`, `api_version`, `credential`, `model`.

**Debugging technique that worked:** inspect the installed package directly rather than trust docs:
```bash
python -c "import agent_framework as af; print([x for x in dir(af) if not x.startswith('_')])"
python -c "from agent_framework.openai import OpenAIChatClient as C; import inspect; print(inspect.signature(C.__init__))"
python -c "from agent_framework.openai import OpenAIChatClient as C; print([m for m in dir(C) if not m.startswith('_')])"
```

**Lesson:** For fast-moving SDKs, the installed package is ground truth, not the docs or a guide.
`dir()` + `inspect.signature()` resolve API drift in seconds. Pin versions once things work.

---

## 7. Two different API versions needed for two different endpoints

**Phase:** 3 (docs agent)

**Symptom:** With the chat client built, calling `agent.run(...)` failed with
`400 BadRequest: API version not supported`.

**Root cause:** Agent Framework's `OpenAIChatClient` uses the **Responses API** (`/responses`), which
requires a newer API version than the `2024-10-21` that the **embeddings** endpoint uses. Reusing the
embeddings version for the chat client broke it.

**Fix:** Let the chat client use its default API version (removed the explicit `api_version` arg), or
set a Responses-capable preview version. Left the embeddings client on `2024-10-21` (it works there).

**Lesson:** The same account endpoint serves multiple APIs (embeddings via chat/completions-era
versions; agents via the Responses API) that expect **different** API versions. Don't assume one
version string works everywhere.

---

## 8. Terminal heredoc mangling multi-line pastes (Codespaces in browser)

**Phase:** 0–3 (recurring)

**Symptom:** `cat > file << 'EOF' ... EOF` pastes repeatedly collided lines together (e.g.
`api_version="2024-10-21",e.com/...`), corrupting files and leaving the shell stuck at a `>` prompt.

**Fix:** `Ctrl+C` to escape the stuck heredoc. Then create/edit multi-line files in the **VS Code
editor pane** (open file → paste → save), which doesn't suffer the terminal's paste line-collision.
Reserve the terminal for single-line commands.

**Lesson:** Browser-based terminals can mangle bracketed pastes. For anything multi-line, use the
editor, not a terminal heredoc.

---

## Recurring meta-lessons

- **Verify against reality, not documentation.** Resource names (`az ... list`), file existence
  (`find`), and SDK APIs (`dir`/`inspect`) — check the actual state before proceeding.
- **A 404 vs 401 tells you a lot.** 401 = auth/permissions; 404 = wrong URL/route/name. They point
  at different fixes.
- **Isolate before integrating.** Testing the retriever alone, then the embeddings call alone, then
  the agent, made each failure easy to localize.
- **Fast-moving platform = pin versions once working.** Foundry and Agent Framework changed shape
  between the guide being written and this build; lock versions after a green run.