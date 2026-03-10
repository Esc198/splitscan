from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ...db.sqlite import get_conn, sqlite_lastrowid
from ...support.auth import auth_user_response, normalize_email_from_payload, normalize_name_from_payload

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def auth_login(payload: dict[str, Any]) -> dict[str, Any]:
    """Authenticate an existing user in the development auth flow."""
    email = normalize_email_from_payload(payload)
    with get_conn() as conn:
        user = conn.execute(
            "SELECT id, name, email FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if not user:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "AUTH_USER_NOT_FOUND",
                    "message": "Usuario no encontrado. RegÃ­strate primero.",
                },
            )
        return auth_user_response(user)


@router.post("/register")
def auth_register(payload: dict[str, Any]) -> dict[str, Any]:
    """Register a user, or return the existing one for idempotent signup."""
    email = normalize_email_from_payload(payload)
    name = normalize_name_from_payload(payload, email)

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, name, email FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if existing:
            return auth_user_response(existing)

        cur = conn.execute(
            "INSERT INTO users (name, email, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (name, email),
        )
        user_id = sqlite_lastrowid(cur)
        created = conn.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone()
        if not created:
            raise HTTPException(status_code=500, detail="No se pudo crear el usuario")
        return auth_user_response(created)
