from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ...db.sqlite import get_conn
from ...services.summary import build_summary_for_user
from ...support.auth import parse_int

router = APIRouter(prefix="/api", tags=["summary"])


@router.get("/summary")
def get_summary(userId: str | None = Query(default=None), user_id: int | None = Query(default=None)) -> dict[str, Any]:
    """Return the financial summary for a user identified by either supported query parameter."""
    resolved_user_id = user_id if user_id is not None else parse_int(userId)
    if resolved_user_id is None:
        raise HTTPException(status_code=400, detail="userId is required")

    with get_conn() as conn:
        exists = conn.execute("SELECT id FROM users WHERE id = ?", (resolved_user_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="User not found")
        return build_summary_for_user(conn, resolved_user_id)
