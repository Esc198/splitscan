from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException

from ...db.sqlite import get_conn, rows_to_dict, sqlite_lastrowid

router = APIRouter(prefix="/api", tags=["categories"])


@router.get("/categories")
def get_categories() -> list[dict[str, Any]]:
    """List all available categories sorted by name."""
    with get_conn() as conn:
        return rows_to_dict(conn.execute("SELECT * FROM categories ORDER BY name ASC").fetchall())


@router.post("/categories")
def create_category(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a custom expense category."""
    name = payload.get("name")
    color = payload.get("color") or "#64748b"
    icon = payload.get("icon") or "Tag"

    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=400, detail="Name required")

    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO categories (name, color, icon, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (name.strip(), color, icon),
            )
            return {"id": sqlite_lastrowid(cur), "name": name.strip(), "color": color, "icon": icon}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Category already exists")


@router.delete("/categories/{cat_id}")
def delete_category(cat_id: int) -> dict[str, bool]:
    """Delete a category by id."""
    with get_conn() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    return {"success": True}
