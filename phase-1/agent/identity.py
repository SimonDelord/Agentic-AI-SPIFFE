"""Fetch this pod's SPIFFE ID from the SPIRE Workload API (CSI-mounted socket).

Postgres still uses password auth. The SVID is only read so the agent can
stamp spiffe_id on the row it writes.
"""

from __future__ import annotations

import os
import time

SPIFFE_ENDPOINT_SOCKET = os.environ.get(
    "SPIFFE_ENDPOINT_SOCKET",
    "unix:///spiffe-workload-api/spire-agent.sock",
)


def fetch_spiffe_id(timeout_s: int = 90) -> str:
    """Block until SPIRE issues an X.509-SVID, then return its SPIFFE ID."""
    os.environ["SPIFFE_ENDPOINT_SOCKET"] = SPIFFE_ENDPOINT_SOCKET
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            from spiffe import X509Source

            with X509Source() as source:
                svid = source.svid
                if svid is None:
                    raise RuntimeError("Workload API returned no default X.509-SVID")
                spiffe_id = str(svid.spiffe_id)
                if not spiffe_id.startswith("spiffe://"):
                    raise RuntimeError(f"unexpected SPIFFE ID: {spiffe_id}")
                return spiffe_id
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"waiting for SVID: {exc}", flush=True)
            time.sleep(2)
    raise RuntimeError(f"could not fetch SPIFFE ID from {SPIFFE_ENDPOINT_SOCKET}: {last_err}")
