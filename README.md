# SPIFFE/SPIRE for Agentic AI

This is the next step after the workload-identity demos in
[SPIFFE-SPIRE-demo](https://github.com/SimonDelord/SPIFFE-SPIRE-demo) and
[SPIFFE-PostgreSQL](https://github.com/SimonDelord/SPIFFE-PostgreSQL).

Those projects answer: **which service is this?**  
This project asks: **which agent is this — and can we still tell, when two copies of the same agent disagree?**

---

## The scenario

Run **two agents that are the same**: same image, same model, same instructions, same tools, same starting input.

The only intended difference is SPIFFE identity:

- `spiffe://.../ns/agentic-ai/sa/agent-a`
- `spiffe://.../ns/agentic-ai/sa/agent-b`

Both agents call the **same OpenShift AI model endpoint** (same model, same URL). No SaaS LLM.

Then compare what they do, in two phases:

1. **Divergence** — do they produce different outputs from the same input?
2. **PostgreSQL** — when they talk to the same database, SPIFFE identity (not a shared password) is how Postgres knows *who* connected and *who* wrote the row.

Identity is deterministic. Agent behaviour usually is not. That is the point.

---

## What an AI agent actually is

An agent is not a special Kubernetes object and it is not a person. It is a **program with a loop**.

Typical pieces:

| Piece | Role |
|--------|------|
| **Model** | An OpenShift AI inference endpoint (OpenAI-compatible, usually vLLM/KServe). This is the “brain”. |
| **System prompt** | Standing instructions: who the agent is, what it may do, how to format answers. |
| **Tools** | An **MCP server** in the same pod: incident read/update against PostgreSQL. |
| **Loop** | Send context to the model → if it asks to call a tool, run it and send the result back → repeat until it gives a final answer. |
| **Workload identity** | In this demo: a SPIFFE ID on the pod, used for mTLS to Postgres. The model never sees a database password. |
| **Observability** | **MLflow** on OpenShift AI: one trace per run, spanning LLM calls and MCP tool calls. |

A minimal loop looks like this:

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": starting_input},
]

while True:
    response = llm.chat(messages, tools=TOOLS)

    if response.wants_to_call_a_tool:
        result = run_tool(response.tool_name, response.tool_args)
        messages.append(tool_result(result))
        continue

    return response.text  # done
```

That is the whole idea. Frameworks (LangChain, LangGraph, CrewAI, and so on) wrap this loop. For this demo: one agent process (MCP **client** + OpenAI-compatible client to OpenShift AI), one small MCP **server** beside it, two pods.

```
                    OpenShift AI
         ┌──────────────┴──────────────┐
         │  KServe / vLLM (LLM)        │
         │  MLflow (traces / runs)     │
         └──────┬──────────────┬───────┘
                │              │
     LLM chat   │              │  traces (LLM + MCP spans)
                ▼              ▲
        ┌─────────────────┐         ┌─────────────────┐
        │  Agent A (pod)  │         │  Agent B (pod)  │
        │  MCP client     │         │  MCP client     │
        │       │ stdio   │         │       │ stdio   │
        │  MCP server     │         │  MCP server     │
        │  (incident tools)│        │  (incident tools)│
        └────────┬────────┘         └────────┬────────┘
                 │  X.509-SVID               │  X.509-SVID
                 │  agent-a                  │  agent-b
                 └─────────────┬─────────────┘
                               ▼
                        PostgreSQL
                      (trusts SPIRE CA)
```

SPIRE attests each pod and issues a short-lived X.509-SVID. Postgres is configured to require a client certificate, trust the SPIRE CA, and map the SPIFFE ID to a database role — the same pattern as the EDB use case in SPIFFE-SPIRE-demo.

---

## The model: OpenShift AI

The agents do not embed a model. They call a cluster service.

OpenShift AI (RHOAI) serves that model, typically as a **KServe InferenceService** running **vLLM**. vLLM speaks the OpenAI chat API, so agent code looks like a normal OpenAI client with a different base URL:

```text
MODEL_URL  = http://tinyllama-predictor.agentic-llm.svc.cluster.local/v1
MODEL_NAME = tinyllama
```

Use the **in-cluster Service**, not a public Route. Both agent pods call that same URL. That keeps the “same brain, two identities” experiment honest, and it stays inside the cluster.

What this demo assumes you already have (or will stand up) on the cluster:

- OpenShift AI installed
- A data science project with a single-model serving runtime
- One chat-capable model reachable at `MODEL_URL`
- MLflow on OpenShift AI (tracking URI in the same data science project)

What the agent needs from that endpoint: `POST /v1/chat/completions` (and later, tool-calling if the served model supports it). SPIFFE is still on **agent → PostgreSQL** first; putting SVIDs on **agent → the model server** can come after.

---

## MCP: one client, one small server

Do not build a generic “MCP platform.” Build two programs that match the protocol roles:

| Piece | What we build | Role |
|--------|----------------|------|
| **MCP client** | The agent loop | Talks to OpenShift AI, discovers tools, calls them |
| **MCP server** | Incident tools over Postgres | `get_incident`, `get_service`, `list_similar_incidents`, `update_incident` |

Use the official Python MCP SDK (`mcp`). The agent is `Client(...)`. The toolbox is `MCPServer(...)`. Same image, deployed twice.

**Colocate them in the same pod** (stdio child process, or a localhost sidecar). Then the process that opens Postgres is still the agent workload, so the X.509-SVID on the wire is `agent-a` or `agent-b`.

Do **not** put a shared remote MCP service in front of Postgres for this demo. Postgres would only see the MCP server’s identity, and the SPIFFE punchline disappears.

Do **not** start from a generic Postgres MCP (arbitrary SQL + password). This server is the incident use case only, and it authenticates with the pod SVID.

The task both agents get is the same messy incident: triage it (severity, owner, likely cause, summary) and `update_incident`. That is what we expect to diverge.

---

## Observability: MLflow on OpenShift AI

SPIFFE tells you **who** connected. MLflow tells you **what the agent did** with the LLM and the MCP server.

Use **MLflow tracing** hosted by OpenShift AI (not a separate LLM-ops product). Each incident run is one MLflow trace. Nested spans show every hop in the loop:

```text
trace  (incident-1042, agent-a, spiffe://.../agent-a)
├── llm.chat                     OpenShift AI model: prompt in, completion out
├── mcp.get_incident             tool args + result
├── mcp.get_service
├── mcp.list_similar_incidents
├── llm.chat                     second think, after tools
└── mcp.update_incident          write-back to PostgreSQL
```

Agent B is a second trace: same `incident_id`, different `spiffe_id`. In the MLflow UI you compare tool order, arguments, model output, and latency.

Tag every trace with:

- `agent` (`agent-a` / `agent-b`)
- `spiffe_id` (from the workload SVID, not from the prompt)
- `incident_id`

That is how an MLflow trace and a Postgres row join.

How it is wired:

- Agent pods get `MLFLOW_TRACKING_URI` (OpenShift AI MLflow) plus `MODEL_URL` / `MODEL_NAME`
- The MCP **client** (agent loop) starts the parent trace
- Each OpenAI-compatible call to the in-cluster model is a child span (for example `mlflow.openai.autolog()`)
- Each MCP tool call (`get_incident`, `update_incident`, …) is a child span
- OpenTelemetry underneath is fine; MLflow on OpenShift AI is the UI for this demo

MLflow does **not** replace identity audit:

| You need to see | Where it lives |
|-----------------|----------------|
| Why the model chose that severity, which MCP tools ran, in which order | **MLflow traces** (OpenShift AI) |
| That Postgres accepted this workload, and who wrote the row | **SPIFFE + PostgreSQL** (session logs, `agent_spiffe_id` on the incident) |
| That SPIRE issued this SVID | **SPIRE / workload attestation** |

MLflow will not show the X.509 handshake. Postgres will not show the prompt. Correlate them with `incident_id` + `spiffe_id`.

---

## What we compare

Not only the final paragraph of text. For each run, capture:

| Artifact | Where you look | Why it matters |
|----------|----------------|----------------|
| Model output | MLflow `llm.chat` spans | The visible answer; often diverges even with the same prompt. |
| MCP tool calls | MLflow `mcp.*` spans | Which tools ran, in which order, with which arguments. |
| SQL / writes | MCP spans + Postgres | What actually hit PostgreSQL. |
| DB side effects | Postgres row + `agent_spiffe_id` | Who wrote the update, cryptographically. |

Agent A and Agent B may write different SQL for the same task. The database can still record **who** did it, because the connection used a different SVID.

---

## Phase 1 — same input, two outputs

Keep everything identical except identity:

- Same container image and system prompt
- Same OpenShift AI endpoint, same model, same starting task
- Same tool list
- Different ServiceAccounts → different SPIFFE IDs

Store both runs as MLflow traces (and optionally as files under `compare/`) and diff them. Divergence is expected. You cannot fingerprint an agent from its prose; you *can* from its SVID.

## Phase 2 — PostgreSQL with SPIFFE

Reuse the existing pattern: X.509-SVID, mTLS into PostgreSQL, cert identity mapped to a DB user. No password in a Secret.

That shows three things the text diff cannot:

- **Authentication** — Postgres accepts the agent because of the SVID.
- **Authorization** — same agent code, different identity, different grants (for example `agent-a` can `INSERT`, `agent-b` can only `SELECT`).
- **Audit** — every session and every write is tied to `agent-a` or `agent-b`, even when the generated SQL differs.

---

## What we will add next

This repo starts as the design. Implementation can stay small:

```
.
├── README.md                 # this file
├── openshift-ai/             # OpenShift AI Operator + CPU TinyLlama (KServe)
│   ├── operator/
│   └── llm/
├── agent/                    # MCP client: LLM loop → OpenShift AI
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── mcp-server/               # incident tools; SPIFFE mTLS to Postgres
│   ├── server.py
│   └── requirements.txt
├── compare/                  # optional local diffs; primary compare is MLflow
└── k8s/                      # two ServiceAccounts, two ClusterSPIFFEID, one Postgres
```

Same image (agent + MCP server), two SPIRE registrations, one OpenShift AI model, one MLflow tracking server, one database.

Agent pods get `MODEL_URL`, `MODEL_NAME`, and `MLFLOW_TRACKING_URI` from a ConfigMap. They do not get a database password.

---

## Related work

- [SPIFFE-SPIRE-demo](https://github.com/SimonDelord/SPIFFE-SPIRE-demo) — SPIFFE/SPIRE on OpenShift, including the EDB/PostgreSQL mTLS use case
- [SPIFFE-PostgreSQL](https://github.com/SimonDelord/SPIFFE-PostgreSQL) — X.509 and JWT SVID authentication to PostgreSQL
- [OpenShift AI](openshift-ai/README.md) — operator + CPU TinyLlama on this cluster
- [MLflow tracing](https://mlflow.org/docs/latest/genai/tracing/) — LLM and MCP spans per agent run
- [How AI observability works with MLflow](https://developers.redhat.com/articles/2026/08/26/how-ai-observability-works-mlflow) — Red Hat on agent traces
- [Model Context Protocol](https://modelcontextprotocol.io/) — agent (client) to incident tools (server)
- [SPIFFE](https://spiffe.io/) / [SPIRE](https://spiffe.io/docs/latest/spire-about/)
