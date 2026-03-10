from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException

from ...db.sqlite import get_conn, rows_to_dict, sqlite_lastrowid
from ...support.auth import normalize_email_from_payload, normalize_name_from_payload

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/users")
def get_users() -> list[dict[str, Any]]:
    """List all registered users."""
    with get_conn() as conn:
        return rows_to_dict(conn.execute("SELECT id, name, email FROM users ORDER BY id ASC").fetchall())


@router.post("/users")
def create_user(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a user from the provided payload."""
    email = normalize_email_from_payload(payload)
    name = normalize_name_from_payload(payload, email)

    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (name, email, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (name, email),
            )
            user_id = sqlite_lastrowid(cur)
            user = conn.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(user) if user else {"id": user_id, "name": name, "email": email}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="User already exists")


@router.get("/users/by-email")
def get_user_by_email(email: str) -> dict[str, Any]:
    """Fetch a user by normalized email address."""
    with get_conn() as conn:
        user = conn.execute(
            "SELECT id, name, email FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return dict(user)


@router.get("/me")
def get_me(email: str) -> dict[str, Any]:
    """Return the current user profile resolved by email."""
    return get_user_by_email(email)
