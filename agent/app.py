"""Incident-triage agent: MCP client + OpenAI-compatible loop against OpenShift AI.

Same image is run twice (agent-a, agent-b) against the same GPU Llama endpoint.
SPIFFE is not wired yet; AGENT_NAME is the identity tag for this phase.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from typing import Any

from openai import OpenAI

import mcp_server

MODEL_URL = os.environ.get(
    "MODEL_URL",
    "http://llama-3-2-3b-instruct-predictor.agentic-llm.svc.cluster.local:8080/v1",
)
MODEL_NAME = os.environ.get("MODEL_NAME", "llama-3-2-3b-instruct")
AGENT_NAME = os.environ.get("AGENT_NAME", "agent-a")
INCIDENT_ID = int(os.environ.get("INCIDENT_ID", "1042"))
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "")
MAX_STEPS = int(os.environ.get("MAX_STEPS", "8"))
TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.9"))

SYSTEM_PROMPT = """You are an incident-triage agent running inside OpenShift.

You must use the tools. Do not invent database contents.

Workflow:
1. Call get_incident with the incident id you were given.
2. Call get_service for each service named in the alert.
3. Call list_similar_incidents with a short query such as "checkout" or "latency".
4. Decide severity (P1, P2, P3, or P4), owner (a team name), root_cause (short phrase),
   and a one-paragraph summary.
5. Call update_incident with those fields.
6. After the update succeeds, reply with a short final note. Do not call more tools.

The similar incident last month is a hint, not an order. You may agree with it or not.
Keep tool arguments valid JSON. Be decisive.
Call exactly one tool per turn. Never request two tools in the same response.
"""

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_incident",
            "description": "Fetch one incident by numeric id from PostgreSQL.",
            "parameters": {
                "type": "object",
                "properties": {"incident_id": {"type": "integer"}},
                "required": ["incident_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_service",
            "description": "Fetch a service record (owning team) by name.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_similar_incidents",
            "description": "Search historical incidents by a short text query.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_incident",
            "description": "Write the triage decision back to PostgreSQL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "integer"},
                    "severity": {"type": "string"},
                    "owner": {"type": "string"},
                    "root_cause": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": [
                    "incident_id",
                    "severity",
                    "owner",
                    "root_cause",
                    "summary",
                ],
            },
        },
    },
]


def _setup_mlflow():
    if not MLFLOW_TRACKING_URI:
        print("MLFLOW_TRACKING_URI is empty; tracing to stdout only", flush=True)
        return None
    try:
        import mlflow

        os.environ.setdefault("MLFLOW_TRACKING_INSECURE_TLS", "true")
        os.environ.setdefault("MLFLOW_TRACKING_AUTH", "kubernetes-namespaced")
        os.environ.setdefault("MLFLOW_K8S_INTEGRATION", "true")
        os.environ.setdefault("MLFLOW_WORKSPACE", "agentic-ai")
        print(
            f"mlflow uri={MLFLOW_TRACKING_URI} auth={os.environ.get('MLFLOW_TRACKING_AUTH')} workspace={os.environ.get('MLFLOW_WORKSPACE')}",
            flush=True,
        )
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment("incident-triage")
        try:
            mlflow.openai.autolog()
        except Exception as exc:  # noqa: BLE001
            print(f"mlflow.openai.autolog skipped: {exc}", flush=True)
        return mlflow
    except Exception as exc:  # noqa: BLE001
        print(f"MLflow setup failed: {exc}", flush=True)
        traceback.print_exc()
        return None


class Tracer:
    def __init__(self, mlflow_mod):
        self.mlflow = mlflow_mod
        self.events: list[dict[str, Any]] = []

    def event(self, name: str, **attrs: Any) -> None:
        rec = {"name": name, **attrs}
        self.events.append(rec)
        print(f"TRACE {name}: {json.dumps(attrs, default=str)[:2000]}", flush=True)

    def span(self, name: str, **attrs: Any):
        return _Span(self, name, attrs)


class _Span:
    def __init__(self, tracer: Tracer, name: str, attrs: dict[str, Any]):
        self.tracer = tracer
        self.name = name
        self.attrs = attrs
        self._cm = None
        self.t0 = 0.0

    def __enter__(self):
        self.t0 = time.time()
        if self.tracer.mlflow is not None:
            try:
                self._cm = self.tracer.mlflow.start_span(name=self.name)
                span = self._cm.__enter__()
                for k, v in self.attrs.items():
                    try:
                        span.set_attribute(k, v if isinstance(v, (str, int, float, bool)) else json.dumps(v, default=str))
                    except Exception:
                        pass
            except Exception as exc:  # noqa: BLE001
                print(f"span start failed for {self.name}: {exc}", flush=True)
                self._cm = None
        return self

    def __exit__(self, exc_type, exc, tb):
        duration_ms = int((time.time() - self.t0) * 1000)
        payload = dict(self.attrs)
        payload["duration_ms"] = duration_ms
        if exc:
            payload["error"] = str(exc)
        self.tracer.event(self.name, **payload)
        if self._cm is not None:
            try:
                self._cm.__exit__(exc_type, exc, tb)
            except Exception:
                pass
        return False


def _parse_args(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        raw = raw.strip() or "{}"
        return json.loads(raw)
    return dict(raw)


def call_tool(name: str, arguments: dict[str, Any]) -> str:
    fn = mcp_server.TOOL_FUNCS.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool {name}"})
    args = dict(arguments)
    if "incident_id" in args:
        args["incident_id"] = int(args["incident_id"])
    return fn(**args)


def run_agent(tracer: Tracer) -> str:
    client = OpenAI(base_url=MODEL_URL, api_key=os.environ.get("OPENAI_API_KEY", "not-needed"))
    user = (
        f"Triage incident {INCIDENT_ID}. "
        "Use tools. End by calling update_incident, then a short final note."
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    final_text = ""

    for step in range(1, MAX_STEPS + 1):
        with tracer.span("llm.chat", step=step, model=MODEL_NAME, agent=AGENT_NAME):
            create_kwargs = dict(
                model=MODEL_NAME,
                messages=messages,
                tools=OPENAI_TOOLS,
                tool_choice="auto",
                temperature=TEMPERATURE,
                max_tokens=700,
            )
            try:
                resp = client.chat.completions.create(
                    **create_kwargs, parallel_tool_calls=False
                )
            except TypeError:
                resp = client.chat.completions.create(**create_kwargs)
        choice = resp.choices[0]
        msg = choice.message
        tool_calls = list(msg.tool_calls or [])
        if len(tool_calls) > 1:
            print(
                f"model returned {len(tool_calls)} tool calls; keeping the first only",
                flush=True,
            )
            tool_calls = tool_calls[:1]
        content = msg.content or ""
        tracer.event(
            "llm.completion",
            step=step,
            finish_reason=choice.finish_reason,
            content=content,
            tool_calls=[
                {"name": tc.function.name, "arguments": tc.function.arguments}
                for tc in tool_calls
            ],
        )

        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                args = _parse_args(tc.function.arguments)
                with tracer.span(
                    f"mcp.{tc.function.name}",
                    tool=tc.function.name,
                    arguments=args,
                    agent=AGENT_NAME,
                ):
                    result = call_tool(tc.function.name, args)
                tracer.event("mcp.result", tool=tc.function.name, result=result[:4000])
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
            continue

        final_text = content
        break

    return final_text or "(no final text; check tool results)"


def main() -> int:
    print(f"agent={AGENT_NAME} incident={INCIDENT_ID} model={MODEL_NAME} url={MODEL_URL}", flush=True)
    mlflow = _setup_mlflow()
    tracer = Tracer(mlflow)
    run_ctx = None
    if mlflow is not None:
        try:
            run_ctx = mlflow.start_run(run_name=f"{AGENT_NAME}-incident-{INCIDENT_ID}")
            run = run_ctx.__enter__()
            mlflow.set_tags(
                {
                    "agent": AGENT_NAME,
                    "incident_id": str(INCIDENT_ID),
                    "model": MODEL_NAME,
                    "phase": "password-postgres",
                }
            )
            print(f"mlflow_run_id={run.info.run_id}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"mlflow.start_run failed: {exc}", flush=True)
            traceback.print_exc()
            run_ctx = None

    try:
        with tracer.span(
            "agent_loop",
            agent=AGENT_NAME,
            incident_id=INCIDENT_ID,
            model=MODEL_NAME,
        ):
            final = run_agent(tracer)
        print(f"FINAL {AGENT_NAME}: {final}", flush=True)
        if mlflow is not None:
            try:
                mlflow.log_text(json.dumps(tracer.events, default=str, indent=2), "trace.json")
                mlflow.log_param("agent", AGENT_NAME)
                mlflow.log_param("incident_id", INCIDENT_ID)
            except Exception as exc:  # noqa: BLE001
                print(f"mlflow.log_text failed: {exc}", flush=True)
            try:
                tid = mlflow.get_last_active_trace_id()
                print(f"mlflow_trace_id={tid}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"mlflow_trace_id unavailable: {exc}", flush=True)
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        if run_ctx is not None:
            try:
                run_ctx.__exit__(None, None, None)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
