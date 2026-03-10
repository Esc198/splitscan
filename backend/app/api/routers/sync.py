from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ...db.sqlite import get_conn
from ...services.sync import build_sync_payload

router = APIRouter(prefix="/api", tags=["sync"])


@router.get("/sync")
def sync(since: str = Query("1970-01-01 00:00:00"), user_id: int | None = Query(default=None)) -> dict[str, Any]:
    """Return records updated after the cursor, optionally limited to one user scope."""
    with get_conn() as conn:
        return build_sync_payload(conn, since, user_id)
