"""Incident MCP server. Tools talk to PostgreSQL.

This process runs in the same pod as the agent (stdio). Postgres therefore
sees the agent workload identity, not a shared remote MCP service.
SPIFFE mTLS is not wired yet; DATABASE_URL is password auth for this phase.
"""

from __future__ import annotations

import json
import os
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://app:demo-incidents@postgres.agentic-db.svc.cluster.local:5432/incidents",
)
AGENT_NAME = os.environ.get("AGENT_NAME", "unknown-agent")


def _conn():
    return psycopg2.connect(DATABASE_URL)


def _dump(value: Any) -> str:
    return json.dumps(value, default=str, indent=2)


def get_incident(incident_id: int) -> str:
    """Fetch one incident by id."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM incidents WHERE id = %s", (incident_id,))
            row = cur.fetchone()
    if not row:
        return _dump({"error": f"incident {incident_id} not found"})
    return _dump(dict(row))


def get_service(name: str) -> str:
    """Fetch a service and its owning team."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM services WHERE name = %s", (name,))
            row = cur.fetchone()
    if not row:
        return _dump({"error": f"service {name} not found"})
    return _dump(dict(row))


def list_similar_incidents(query: str) -> str:
    """Find historical incidents whose title or alert text matches the query."""
    like = f"%{query}%"
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, title, severity, owner, root_cause, summary
                FROM incidents
                WHERE title ILIKE %s OR alert_text ILIKE %s
                ORDER BY id
                LIMIT 10
                """,
                (like, like),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return _dump(rows)


def update_incident(
    incident_id: int,
    severity: str,
    owner: str,
    root_cause: str,
    summary: str,
) -> str:
    """Write the agent's triage decision back to Postgres."""
    payload = {
        "severity": severity,
        "owner": owner,
        "root_cause": root_cause,
        "summary": summary,
        "agent_name": AGENT_NAME,
    }
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE incidents
                SET severity = %s,
                    owner = %s,
                    root_cause = %s,
                    summary = %s,
                    agent_name = %s,
                    updated_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (severity, owner, root_cause, summary, AGENT_NAME, incident_id),
            )
            row = cur.fetchone()
            cur.execute(
                """
                INSERT INTO agent_writes (incident_id, agent_name, payload)
                VALUES (%s, %s, %s::jsonb)
                RETURNING id, incident_id, agent_name, written_at
                """,
                (incident_id, AGENT_NAME, json.dumps(payload)),
            )
            write = cur.fetchone()
    if not row:
        return _dump({"error": f"incident {incident_id} not found"})
    return _dump({"incident": dict(row), "write": dict(write)})


TOOL_FUNCS = {
    "get_incident": get_incident,
    "get_service": get_service,
    "list_similar_incidents": list_similar_incidents,
    "update_incident": update_incident,
}


def _register_fastmcp(mcp) -> None:
    mcp.tool()(get_incident)
    mcp.tool()(get_service)
    mcp.tool()(list_similar_incidents)
    mcp.tool()(update_incident)


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        from mcp.server import FastMCP  # type: ignore

    mcp = FastMCP("incident-tools")
    _register_fastmcp(mcp)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
