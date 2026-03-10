from __future__ import annotations

import re
import sqlite3
from typing import Any

from fastapi import HTTPException

INTEGER_RE = re.compile(r"-?\d+")


def parse_int(value: Any) -> int | None:
    """Safely coerce common scalar values to integers."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if raw and INTEGER_RE.fullmatch(raw):
            return int(raw)
    return None


def normalize_email_from_payload(payload: dict[str, Any]) -> str:
    """Extract and normalize an email address from a request payload."""
    email = payload.get("email")
    if isinstance(email, dict):
        email = email.get("email")
    if not isinstance(email, str):
        raise HTTPException(status_code=400, detail="Invalid email")

    normalized = email.strip().lower()
    if "@" not in normalized:
        raise HTTPException(status_code=400, detail="Invalid email")
    return normalized


def normalize_name_from_payload(payload: dict[str, Any], fallback_email: str) -> str:
    """Extract a display name or derive one from the email local part."""
    name = payload.get("name")
    if isinstance(name, dict):
        name = name.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return fallback_email.split("@", 1)[0].replace(".", " ").title()


def auth_user_response(row: sqlite3.Row) -> dict[str, Any]:
    """Build the development auth response returned by login and register."""
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "token": f"dev-token-{row['id']}",
    }
