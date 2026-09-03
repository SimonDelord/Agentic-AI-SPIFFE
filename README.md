# SPIFFE/SPIRE for Agentic AI

This is the next step after the workload-identity demos in
[SPIFFE-SPIRE-demo](https://github.com/SimonDelord/SPIFFE-SPIRE-demo) and
[SPIFFE-PostgreSQL](https://github.com/SimonDelord/SPIFFE-PostgreSQL).

Those projects answer: **which service is this?**  
This project asks: **which agent is this — and can we still tell, when two copies of the same agent disagree?**

**Identity is deterministic. LLM agent behaviour is not.** Two agents can share the same image, the same OpenShift AI GPU model, the same tools, and the same prompt, and still write different answers. SPIFFE is how you tell them apart.

The demo is three phases. Each one keeps the previous punchline and adds a new one.

| Phase | Status | What it proves |
|-------|--------|----------------|
| **[Phase 1](phase-1/)** | Built | Same setup, different SPIFFE IDs, different answers. Internal MCP. IDs stamped on Postgres writes. |
| **[Phase 2](phase-2/)** | Not built | Postgres **authorizes by SPIFFE ID**. Same code, different rows, different answers. |
| **[Phase 3](phase-3/)** | Not built | **External MCP** that authenticates the caller and **passes the agent’s SVID through** to Postgres. |

```
Phase 1  who wrote this?
Phase 2  what is this identity allowed to see?
Phase 3  the MCP in the middle must not eat the identity
```

---

## The scenario

Run **two agents that are the same**: same image, same model, same instructions, same tools, same starting input.

The only intended difference is SPIFFE identity:

- `spiffe://.../ns/agentic-ai/sa/agent-a`
- `spiffe://.../ns/agentic-ai/sa/agent-b`

Both call the **same OpenShift AI model endpoint**. No SaaS LLM.

The use case is messy **incident triage** that ends in a database write: severity, owner, likely cause, summary.

---

## What an AI agent actually is

An agent is not a special Kubernetes object and it is not a person. It is a **program with a loop**.

| Piece | Role |
|--------|------|
| **Model** | An OpenShift AI inference endpoint (OpenAI-compatible, vLLM/KServe). This is the “brain”. |
| **System prompt** | Standing instructions: who the agent is, what it may do, how to format answers. |
| **Tools** | MCP tools against PostgreSQL (`get_incident`, `get_service`, `list_similar_incidents`, `update_incident`). |
| **Loop** | Send context to the model → if it asks to call a tool, run it and send the result back → repeat until it gives a final answer. |
| **Workload identity** | A SPIFFE ID on the pod. The model never sees a database password in later phases; phase 1 still uses a demo password and **stamps** the SPIFFE ID on the write. |
| **Observability** | **MLflow** on OpenShift AI: one trace per run, spanning LLM calls and MCP tool calls. |

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

Frameworks wrap this loop. This demo is one agent process, a small MCP toolbox, two pods.

---

## The three phases

### Phase 1 — same input, two outputs (built)

Everything identical except identity. Each agent has its own MCP **inside the pod** (stdio / in-process). Postgres sees two connections that stamp two SPIFFE IDs. The `incidents` table is **read-only input**; each triage is an `INSERT` into `agent_writes`.

That is the baseline: you cannot fingerprint an agent from its prose; you *can* from its SVID.

Details, manifests, and how to run: **[phase-1/](phase-1/)**.

```
                    OpenShift AI
         ┌──────────────┴──────────────┐
         │  KServe / vLLM (LLM)        │
         │  MLflow (traces / runs)     │
         └──────┬──────────────┬───────┘
                │              │
     LLM chat   │              │  traces
                ▼              ▲
        ┌─────────────────┐         ┌─────────────────┐
        │  Agent A (pod)  │         │  Agent B (pod)  │
        │  MCP client     │         │  MCP client     │
        │  MCP server     │         │  MCP server     │
        │  (in-process)   │         │  (in-process)   │
        └────────┬────────┘         └────────┬────────┘
                 │  SPIFFE ID                │  SPIFFE ID
                 │  agent-a                  │  agent-b
                 └─────────────┬─────────────┘
                               ▼
                        PostgreSQL
                     (password auth;
                    SPIFFE ID stamped)
```

### Phase 2 — Postgres authorizes by SPIFFE ID (not built)

Keep the **internal** MCP. Change Postgres so the SPIFFE ID is not only a stamp: it is **who you are** for SQL.

Same agent code, two identities, **different rows** (for example engineering vs finance, via JWT-SVID + row-level security). They will disagree for a new reason: they did not see the same world.

X.509 mTLS into Postgres is not the goal here. A JWT-SVID is enough. See **[phase-2/](phase-2/)**.

### Phase 3 — external MCP that does not eat the identity (not built)

Move MCP out of the agent pod. The MCP server must:

1. Authenticate the caller’s SVID and **filter tools** (what this agent is allowed to invoke).
2. **Pass that SVID/JWT through** to Postgres so RLS still sees `agent-a` / `agent-b`, not the MCP.

If the MCP connects to Postgres as itself, phase 2 disappears. See **[phase-3/](phase-3/)**.

---

## Repository layout

```
.
├── README.md                 # this file: the three-phase story
├── phase-1/                  # built demo
│   ├── agent/                # MCP client + in-process incident tools
│   ├── k8s/                  # two Jobs, two ServiceAccounts
│   ├── postgres/             # incidents DB (password + SPIFFE stamp)
│   ├── sql-ui/               # last-10 writes, agent-a vs agent-b
│   ├── spire/                # ZTWIM operator + ClusterSPIFFEID
│   └── openshift-ai/         # RHOAI, GPU Llama, MLflow
├── phase-2/                  # design only: SQL authz by SPIFFE ID
└── phase-3/                  # design only: external MCP + SVID passthrough
```

OpenShift AI, SPIRE, and Postgres from phase 1 are the platform later phases reuse. They live under `phase-1/` because that is the working demo today.

---

## Related work

- [SPIFFE-SPIRE-demo](https://github.com/SimonDelord/SPIFFE-SPIRE-demo) — SPIFFE/SPIRE on OpenShift, including PostgreSQL mTLS
- [SPIFFE-PostgreSQL](https://github.com/SimonDelord/SPIFFE-PostgreSQL) — X.509 and JWT-SVID authentication to PostgreSQL (the JWT path is what phase 2 will use)
- [OpenShift AI](phase-1/openshift-ai/README.md) — operator, GPU Llama, MLflow on this cluster
- [MLflow tracing](https://mlflow.org/docs/latest/genai/tracing/) — LLM and MCP spans per agent run
- [How AI observability works with MLflow](https://developers.redhat.com/articles/2026/08/26/how-ai-observability-works-mlflow)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [SPIFFE](https://spiffe.io/) / [SPIRE](https://spiffe.io/docs/latest/spire-about/)
