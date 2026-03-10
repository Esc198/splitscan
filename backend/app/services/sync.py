from __future__ import annotations

import re
import sqlite3
from typing import Any

from fastapi import HTTPException

from ..db.sqlite import now_sqlite, rows_to_dict

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def validate_since(since: str) -> str:
    """Validate the sync cursor format accepted by the API."""
    if since == "1970-01-01 00:00:00" or DATE_RE.match(since):
        return since
    raise HTTPException(status_code=400, detail="Invalid date format")


def fetch_relevant_scope(conn: sqlite3.Connection, user_id: int) -> dict[str, list[int]]:
    """Collect the ids that define the sync scope for a specific user."""
    group_ids = [
        row[0]
        for row in conn.execute("SELECT group_id FROM group_members WHERE user_id = ?", (user_id,)).fetchall()
    ]
    if not group_ids:
        return {"group_ids": [], "expense_ids": [], "item_ids": [], "user_ids": [user_id]}

    group_ph = ",".join("?" for _ in group_ids)
    expense_ids = [
        row[0]
        for row in conn.execute(
            f"SELECT id FROM expenses WHERE group_id IN ({group_ph})", tuple(group_ids)
        ).fetchall()
    ]

    item_ids: list[int] = []
    if expense_ids:
        exp_ph = ",".join("?" for _ in expense_ids)
        item_ids = [
            row[0]
            for row in conn.execute(
                f"SELECT id FROM expense_items WHERE expense_id IN ({exp_ph})", tuple(expense_ids)
            ).fetchall()
        ]

    user_ids = {user_id}
    user_ids.update(
        row[0]
        for row in conn.execute(
            f"SELECT user_id FROM group_members WHERE group_id IN ({group_ph})", tuple(group_ids)
        ).fetchall()
    )

    return {
        "group_ids": group_ids,
        "expense_ids": expense_ids,
        "item_ids": item_ids,
        "user_ids": list(user_ids),
    }


def build_sync_payload(conn: sqlite3.Connection, since: str, user_id: int | None = None) -> dict[str, Any]:
    """Build the sync response payload for the requested scope."""
    normalized_since = validate_since(since)

    if user_id is None:
        return {
            "users": rows_to_dict(conn.execute("SELECT id, name, email, updated_at FROM users WHERE updated_at > ?", (normalized_since,)).fetchall()),
            "groups": rows_to_dict(conn.execute("SELECT id, name, join_code, updated_at FROM groups WHERE updated_at > ?", (normalized_since,)).fetchall()),
            "group_members": rows_to_dict(conn.execute("SELECT group_id, user_id, updated_at FROM group_members WHERE updated_at > ?", (normalized_since,)).fetchall()),
            "expenses": rows_to_dict(conn.execute("SELECT id, group_id, payer_id, total_amount, merchant_name, date, image_data, updated_at FROM expenses WHERE updated_at > ?", (normalized_since,)).fetchall()),
            "expense_participants": rows_to_dict(conn.execute("SELECT expense_id, user_id, updated_at FROM expense_participants WHERE updated_at > ?", (normalized_since,)).fetchall()),
            "expense_items": rows_to_dict(conn.execute("SELECT id, expense_id, name, price, category, updated_at FROM expense_items WHERE updated_at > ?", (normalized_since,)).fetchall()),
            "item_participants": rows_to_dict(conn.execute("SELECT item_id, user_id, percentage, updated_at FROM item_participants WHERE updated_at > ?", (normalized_since,)).fetchall()),
            "incomes": rows_to_dict(conn.execute("SELECT id, user_id, amount, description, date, updated_at FROM incomes WHERE updated_at > ?", (normalized_since,)).fetchall()),
            "categories": rows_to_dict(conn.execute("SELECT id, name, color, icon, updated_at FROM categories WHERE updated_at > ?", (normalized_since,)).fetchall()),
            "server_time": now_sqlite(),
        }

    scope = fetch_relevant_scope(conn, user_id)
    group_ids = scope["group_ids"]
    expense_ids = scope["expense_ids"]
    item_ids = scope["item_ids"]
    user_ids = scope["user_ids"]

    groups: list[dict[str, Any]] = []
    group_members: list[dict[str, Any]] = []
    expenses: list[dict[str, Any]] = []
    expense_participants: list[dict[str, Any]] = []
    expense_items: list[dict[str, Any]] = []
    item_participants: list[dict[str, Any]] = []

    if group_ids:
        group_ph = ",".join("?" for _ in group_ids)
        groups = rows_to_dict(
            conn.execute(
                f"SELECT id, name, join_code, updated_at FROM groups WHERE id IN ({group_ph}) AND updated_at > ?",
                (*group_ids, normalized_since),
            ).fetchall()
        )
        group_members = rows_to_dict(
            conn.execute(
                f"SELECT group_id, user_id, updated_at FROM group_members WHERE group_id IN ({group_ph}) AND updated_at > ?",
                (*group_ids, normalized_since),
            ).fetchall()
        )

    if expense_ids:
        exp_ph = ",".join("?" for _ in expense_ids)
        expenses = rows_to_dict(
            conn.execute(
                f"SELECT id, group_id, payer_id, total_amount, merchant_name, date, image_data, updated_at FROM expenses WHERE id IN ({exp_ph}) AND updated_at > ?",
                (*expense_ids, normalized_since),
            ).fetchall()
        )
        expense_participants = rows_to_dict(
            conn.execute(
                f"SELECT expense_id, user_id, updated_at FROM expense_participants WHERE expense_id IN ({exp_ph}) AND updated_at > ?",
                (*expense_ids, normalized_since),
            ).fetchall()
        )
        expense_items = rows_to_dict(
            conn.execute(
                f"SELECT id, expense_id, name, price, category, updated_at FROM expense_items WHERE expense_id IN ({exp_ph}) AND updated_at > ?",
                (*expense_ids, normalized_since),
            ).fetchall()
        )

    if item_ids:
        item_ph = ",".join("?" for _ in item_ids)
        item_participants = rows_to_dict(
            conn.execute(
                f"SELECT item_id, user_id, percentage, updated_at FROM item_participants WHERE item_id IN ({item_ph}) AND updated_at > ?",
                (*item_ids, normalized_since),
            ).fetchall()
        )

    users: list[dict[str, Any]] = []
    if user_ids:
        user_ph = ",".join("?" for _ in user_ids)
        users = rows_to_dict(
            conn.execute(
                f"SELECT id, name, email, updated_at FROM users WHERE id IN ({user_ph}) AND updated_at > ?",
                (*user_ids, normalized_since),
            ).fetchall()
        )

    incomes = rows_to_dict(
        conn.execute(
            "SELECT id, user_id, amount, description, date, updated_at FROM incomes WHERE user_id = ? AND updated_at > ?",
            (user_id, normalized_since),
        ).fetchall()
    )

    categories = rows_to_dict(
        conn.execute("SELECT id, name, color, icon, updated_at FROM categories WHERE updated_at > ?", (normalized_since,)).fetchall()
    )

    return {
        "users": users,
        "groups": groups,
        "group_members": group_members,
        "expenses": expenses,
        "expense_participants": expense_participants,
        "expense_items": expense_items,
        "item_participants": item_participants,
        "incomes": incomes,
        "categories": categories,
        "server_time": now_sqlite(),
    }
