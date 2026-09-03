# SQL write viewer

Read-only Flask UI in `agentic-ai`. Two columns: **agent-a** (left) and
**agent-b** (right). Shows the **last 10** rows from `agent_writes`.
The `incidents` table is input only (not updated by agents).

From the repo root:

```bash
./phase-1/sql-ui/deploy.sh
oc get route sql-ui -n agentic-ai
```
