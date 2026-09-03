"""Simple two-pane viewer for agent_writes in PostgreSQL."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import psycopg2
from flask import Flask, jsonify, render_template_string
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://app:demo-incidents@postgres.agentic-db.svc.cluster.local:5432/incidents",
)
INCIDENT_ID = int(os.environ.get("INCIDENT_ID", "1042"))
WRITE_LIMIT = int(os.environ.get("WRITE_LIMIT", "10"))

app = Flask(__name__)

PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent SQL writes — incident {{ incident_id }}</title>
  <style>
    :root {
      --bg: #0f1419;
      --panel: #1a2332;
      --line: #2c3a4d;
      --text: #e8eef5;
      --muted: #93a4b8;
      --a: #5b9fd4;
      --b: #c48a4a;
      --chip: #243044;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header {
      padding: 1.25rem 1.5rem 0.75rem;
      border-bottom: 1px solid var(--line);
    }
    header h1 { margin: 0 0 0.35rem; font-size: 1.25rem; font-weight: 600; }
    header p { margin: 0.2rem 0; color: var(--muted); font-size: 0.92rem; }
    .alert {
      margin-top: 0.75rem;
      padding: 0.75rem 1rem;
      background: var(--chip);
      border-radius: 8px;
      color: var(--text);
      font-size: 0.92rem;
      line-height: 1.45;
    }
    .toolbar {
      display: flex;
      gap: 0.75rem;
      align-items: center;
      padding: 0.75rem 1.5rem;
    }
    button {
      background: var(--chip);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0.4rem 0.8rem;
      cursor: pointer;
    }
    button:hover { border-color: var(--muted); }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1rem;
      padding: 0 1.5rem 1.5rem;
      align-items: start;
    }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
    .col {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      min-height: 12rem;
    }
    .col.a { border-top: 3px solid var(--a); }
    .col.b { border-top: 3px solid var(--b); }
    .col h2 {
      margin: 0;
      padding: 0.9rem 1rem;
      font-size: 1.05rem;
      border-bottom: 1px solid var(--line);
    }
    .col.a h2 { color: var(--a); }
    .col.b h2 { color: var(--b); }
    .empty { padding: 1rem; color: var(--muted); }
    .card {
      padding: 0.9rem 1rem 1rem;
      border-bottom: 1px solid var(--line);
    }
    .card:last-child { border-bottom: 0; }
    .row {
      display: grid;
      grid-template-columns: 8.5rem 1fr;
      gap: 0.4rem 0.75rem;
      margin: 0.28rem 0;
      font-size: 0.9rem;
    }
    .k { color: var(--muted); }
    .v { word-break: break-all; }
    .v.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.8rem; }
    .muted { color: var(--muted); }
    .badge {
      display: inline-block;
      background: var(--chip);
      border-radius: 999px;
      padding: 0.1rem 0.55rem;
      font-size: 0.78rem;
      color: var(--muted);
      margin-bottom: 0.4rem;
    }
  </style>
</head>
<body>
  <header>
    <h1>PostgreSQL writes — incident {{ incident_id }}</h1>
    <p>Last {{ write_limit }} rows from <code>agent_writes</code> (append-only). <code>incidents</code> is read-only input. Left is agent-a, right is agent-b.</p>
    {% if incident %}
    <div class="alert">
      <strong>{{ incident.title }}</strong> (read-only input)<br>
      {{ incident.alert_text }}
    </div>
    {% endif %}
  </header>
  <div class="toolbar">
    <button type="button" onclick="location.reload()">Refresh from SQL</button>
    <span style="color:var(--muted);font-size:0.85rem">showing {{ write_count }} of last {{ write_limit }} write(s)</span>
  </div>
  <div class="grid">
    {% for agent, writes in panes %}
    <section class="col {{ 'a' if agent == 'agent-a' else 'b' }}">
      <h2>{{ agent }}</h2>
      {% if not writes %}
      <p class="empty">No rows in <code>agent_writes</code> for {{ agent }}.</p>
      {% endif %}
      {% for w in writes %}
      <article class="card">
        <div class="badge">write id {{ w.id }} · {{ w.written_at }}</div>
        <div class="row"><div class="k">incident_id</div><div class="v">{{ w.incident_id }}</div></div>
        <div class="row"><div class="k">agent_name</div><div class="v">{{ w.agent_name }}</div></div>
        <div class="row"><div class="k">spiffe_id</div><div class="v mono">{{ w.spiffe_id or "—" }}</div></div>
        <div class="row"><div class="k">severity</div><div class="v">{{ w.severity or "—" }}</div></div>
        <div class="row"><div class="k">owner</div><div class="v">{{ w.owner or "—" }}</div></div>
        <div class="row"><div class="k">root_cause</div><div class="v">{{ w.root_cause or "—" }}</div></div>
        <div class="row"><div class="k">summary</div><div class="v">{{ w.summary or "—" }}</div></div>
        <div class="row"><div class="k">written_at</div><div class="v">{{ w.written_at }}</div></div>
      </article>
      {% endfor %}
    </section>
    {% endfor %}
  </div>
</body>
</html>
"""


def _conn():
    return psycopg2.connect(DATABASE_URL)


def _fmt(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def fetch() -> dict[str, Any]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM incidents WHERE id = %s", (INCIDENT_ID,))
            incident = cur.fetchone()
            cur.execute(
                """
                SELECT id, incident_id, agent_name, spiffe_id, payload, written_at
                FROM agent_writes
                WHERE incident_id = %s
                ORDER BY written_at DESC, id DESC
                LIMIT %s
                """,
                (INCIDENT_ID, WRITE_LIMIT),
            )
            writes = cur.fetchall()
    incident_out = None
    if incident:
        incident_out = {k: _fmt(v) for k, v in dict(incident).items()}
    rows = []
    for row in writes:
        payload = row["payload"] or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        rows.append(
            {
                "id": row["id"],
                "incident_id": row["incident_id"],
                "agent_name": row["agent_name"],
                "spiffe_id": row["spiffe_id"],
                "severity": payload.get("severity"),
                "owner": payload.get("owner"),
                "root_cause": payload.get("root_cause"),
                "summary": payload.get("summary"),
                "written_at": _fmt(row["written_at"]),
            }
        )
    return {"incident": incident_out, "writes": rows}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/writes")
def api_writes():
    return jsonify(fetch())


@app.get("/")
def index():
    data = fetch()
    writes = data["writes"]
    panes = [
        ("agent-a", [w for w in writes if w["agent_name"] == "agent-a"]),
        ("agent-b", [w for w in writes if w["agent_name"] == "agent-b"]),
    ]
    return render_template_string(
        PAGE,
        incident_id=INCIDENT_ID,
        incident=data["incident"],
        panes=panes,
        write_count=len(writes),
        write_limit=WRITE_LIMIT,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
