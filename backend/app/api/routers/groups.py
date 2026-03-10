from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ...db.sqlite import get_conn, rows_to_dict, sqlite_lastrowid
from ...support.auth import parse_int
from ...support.groups import (
    generate_join_code,
    infer_expense_participants,
    serialize_group_row,
    settlements_from_balances,
)

router = APIRouter(prefix="/api", tags=["groups"])


@router.get("/groups")
def list_groups() -> list[dict[str, Any]]:
    """List groups ordered by most recently updated first."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT g.id, g.name, g.join_code
            FROM groups g
            ORDER BY g.updated_at DESC, g.id DESC
            """
        ).fetchall()

        groups: list[dict[str, Any]] = []
        for row in rows:
            group = serialize_group_row(row)
            group["members"] = []
            group["balance"] = 0
            groups.append(group)
        return groups


@router.get("/groups/{group_id}")
def get_group(group_id: int) -> dict[str, Any]:
    """Return a group with its current members."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, join_code FROM groups WHERE id = ?",
            (group_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Group not found")

        members = rows_to_dict(
            conn.execute(
                """
                SELECT u.id, u.name, u.email
                FROM users u
                JOIN group_members gm ON gm.user_id = u.id
                WHERE gm.group_id = ?
                ORDER BY u.name ASC
                """,
                (group_id,),
            ).fetchall()
        )

        group = serialize_group_row(row)
        group["members"] = members
        group["balance"] = 0
        return group


@router.post("/groups")
def create_group(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a group and optionally attach the provided members and creator."""
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=400, detail="Invalid group name")

    member_ids_raw = payload.get("memberIds") or payload.get("member_ids") or []
    if not isinstance(member_ids_raw, list):
        member_ids_raw = []

    creator_id = parse_int(payload.get("userId") or payload.get("createdBy") or payload.get("creator_id"))

    member_ids = {uid for uid in (parse_int(value) for value in member_ids_raw) if uid is not None}
    if creator_id is not None:
        member_ids.add(creator_id)

    join_code = generate_join_code()

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO groups (name, join_code, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (name.strip(), join_code),
        )
        group_id = sqlite_lastrowid(cur)

        for user_id_value in sorted(member_ids):
            conn.execute(
                "INSERT OR IGNORE INTO group_members (group_id, user_id, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (group_id, user_id_value),
            )

        created = conn.execute(
            "SELECT id, name, join_code FROM groups WHERE id = ?",
            (group_id,),
        ).fetchone()

    if not created:
        raise HTTPException(status_code=500, detail="Group creation failed")

    group = serialize_group_row(created)
    group["members"] = []
    group["balance"] = 0
    return group


@router.post("/groups/join")
def join_group(payload: dict[str, Any]) -> dict[str, Any]:
    """Add a user to a group identified by its join code."""
    join_code = payload.get("joinCode")
    user_id = parse_int(payload.get("userId") or payload.get("user_id"))

    if not isinstance(join_code, str) or user_id is None:
        raise HTTPException(status_code=400, detail="Invalid join data")

    with get_conn() as conn:
        group = conn.execute(
            "SELECT id, name, join_code FROM groups WHERE join_code = ?",
            (join_code.strip().upper(),),
        ).fetchone()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        conn.execute(
            "INSERT OR IGNORE INTO group_members (group_id, user_id, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (group["id"], user_id),
        )
        return serialize_group_row(group)


@router.get("/groups/{group_id}/members")
def group_members(group_id: int) -> list[dict[str, Any]]:
    """List all members belonging to a group."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT users.id, users.name, users.email
            FROM users
            JOIN group_members ON users.id = group_members.user_id
            WHERE group_members.group_id = ?
            ORDER BY users.name ASC
            """,
            (group_id,),
        ).fetchall()
        return rows_to_dict(rows)


@router.get("/groups/{group_id}/expenses")
def group_expenses(group_id: int) -> list[dict[str, Any]]:
    """List expenses associated with a specific group."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, group_id, payer_id, total_amount,
                   COALESCE(merchant_name, 'Gasto') AS title,
                   COALESCE(date, updated_at) AS date,
                   image_data,
                   updated_at
            FROM expenses
            WHERE group_id = ?
            ORDER BY COALESCE(date, updated_at) DESC, id DESC
            """,
            (group_id,),
        ).fetchall()
        return rows_to_dict(rows)


@router.get("/groups/{group_id}/balances")
def group_balances(group_id: int) -> list[dict[str, Any]]:
    """Compute the settlement transfers required to balance a group."""
    with get_conn() as conn:
        members = rows_to_dict(
            conn.execute(
                """
                SELECT users.id, users.name
                FROM users
                JOIN group_members ON users.id = group_members.user_id
                WHERE group_members.group_id = ?
                ORDER BY users.name ASC
                """,
                (group_id,),
            ).fetchall()
        )

        if not members:
            return []

        balances = {int(member["id"]): 0.0 for member in members}
        names = {int(member["id"]): str(member["name"]) for member in members}

        expense_rows = conn.execute(
            "SELECT id, group_id, payer_id, total_amount FROM expenses WHERE group_id = ?",
            (group_id,),
        ).fetchall()

        member_ids = [int(member["id"]) for member in members]

        for exp in expense_rows:
            expense_id = int(exp["id"])
            payer_id = parse_int(exp["payer_id"])
            total = float(exp["total_amount"] or 0)

            participants = infer_expense_participants(conn, expense_id, group_id, payer_id)
            if not participants:
                participants = member_ids

            if payer_id is not None:
                if payer_id not in balances:
                    user_row = conn.execute("SELECT name FROM users WHERE id = ?", (payer_id,)).fetchone()
                    balances[payer_id] = 0.0
                    names[payer_id] = user_row[0] if user_row else f"Usuario {payer_id}"
                balances[payer_id] += total

            share = total / len(participants) if participants else 0
            for participant_id in participants:
                if participant_id not in balances:
                    user_row = conn.execute("SELECT name FROM users WHERE id = ?", (participant_id,)).fetchone()
                    balances[participant_id] = 0.0
                    names[participant_id] = user_row[0] if user_row else f"Usuario {participant_id}"
                balances[participant_id] -= share

        return settlements_from_balances(balances, names)
