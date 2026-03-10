from __future__ import annotations

import secrets
import sqlite3
from typing import Any


def generate_join_code() -> str:
    """Generate a short uppercase code for joining a group."""
    return secrets.token_hex(4).upper()


def get_group_member_ids(conn: sqlite3.Connection, group_id: int) -> list[int]:
    """Return the user ids currently linked to a group."""
    return [
        int(row[0])
        for row in conn.execute(
            "SELECT user_id FROM group_members WHERE group_id = ?",
            (group_id,),
        ).fetchall()
    ]


def infer_expense_participants(conn: sqlite3.Connection, expense_id: int, group_id: int | None, payer_id: int | None) -> list[int]:
    """Resolve the participants of an expense using explicit, group, or payer fallbacks."""
    explicit = [
        int(row[0])
        for row in conn.execute(
            "SELECT user_id FROM expense_participants WHERE expense_id = ?",
            (expense_id,),
        ).fetchall()
    ]
    if explicit:
        return explicit

    if group_id is not None:
        members = get_group_member_ids(conn, group_id)
        if members:
            return members

    if payer_id is not None:
        return [payer_id]

    return []


def serialize_group_row(group: sqlite3.Row) -> dict[str, Any]:
    """Normalize a group row into the response shape used by the API."""
    return {
        "id": group["id"],
        "name": group["name"],
        "code": group["join_code"],
        "join_code": group["join_code"],
    }


def settlements_from_balances(balances: dict[int, float], names: dict[int, str]) -> list[dict[str, Any]]:
    """Convert net balances into a minimal list of settlement transfers."""
    creditors: list[list[float]] = []
    debtors: list[list[float]] = []

    for uid, balance in balances.items():
        if balance > 0.01:
            creditors.append([float(uid), round(balance, 2)])
        elif balance < -0.01:
            debtors.append([float(uid), round(-balance, 2)])

    creditors.sort(key=lambda item: item[1], reverse=True)
    debtors.sort(key=lambda item: item[1], reverse=True)

    transfers: list[dict[str, Any]] = []
    c_idx = 0
    d_idx = 0

    while c_idx < len(creditors) and d_idx < len(debtors):
        creditor_id = int(creditors[c_idx][0])
        debtor_id = int(debtors[d_idx][0])
        creditor_amt = creditors[c_idx][1]
        debtor_amt = debtors[d_idx][1]

        move = round(min(creditor_amt, debtor_amt), 2)
        if move > 0:
            transfers.append(
                {
                    "from": names.get(debtor_id, f"Usuario {debtor_id}"),
                    "to": names.get(creditor_id, f"Usuario {creditor_id}"),
                    "amount": move,
                }
            )

        creditors[c_idx][1] = round(creditor_amt - move, 2)
        debtors[d_idx][1] = round(debtor_amt - move, 2)

        if creditors[c_idx][1] <= 0.01:
            c_idx += 1
        if debtors[d_idx][1] <= 0.01:
            d_idx += 1

    return transfers
