from __future__ import annotations

import sqlite3
from typing import Any

from ..support.auth import parse_int
from ..support.groups import infer_expense_participants


def build_summary_for_user(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    """Aggregate balances and recent expenses for the dashboard summary."""
    group_ids = [row[0] for row in conn.execute("SELECT group_id FROM group_members WHERE user_id = ?", (user_id,)).fetchall()]

    if group_ids:
        group_ph = ",".join("?" for _ in group_ids)
        expense_rows = conn.execute(
            f"""
            SELECT DISTINCT e.id, e.group_id, e.payer_id, e.total_amount,
                   COALESCE(e.merchant_name, 'Gasto') AS title,
                   COALESCE(e.date, e.updated_at) AS date,
                   e.updated_at
            FROM expenses e
            LEFT JOIN expense_participants ep ON ep.expense_id = e.id
            WHERE e.payer_id = ? OR ep.user_id = ? OR e.group_id IN ({group_ph})
            ORDER BY COALESCE(e.date, e.updated_at) DESC
            """,
            (user_id, user_id, *group_ids),
        ).fetchall()
    else:
        expense_rows = conn.execute(
            """
            SELECT DISTINCT e.id, e.group_id, e.payer_id, e.total_amount,
                   COALESCE(e.merchant_name, 'Gasto') AS title,
                   COALESCE(e.date, e.updated_at) AS date,
                   e.updated_at
            FROM expenses e
            LEFT JOIN expense_participants ep ON ep.expense_id = e.id
            WHERE e.payer_id = ? OR ep.user_id = ?
            ORDER BY COALESCE(e.date, e.updated_at) DESC
            """,
            (user_id, user_id),
        ).fetchall()

    to_receive = 0.0
    to_pay = 0.0
    recent_expenses: list[dict[str, Any]] = []

    for exp in expense_rows:
        exp_id = int(exp["id"])
        group_id = parse_int(exp["group_id"])
        payer_id = parse_int(exp["payer_id"])
        total = float(exp["total_amount"] or 0)

        participants = infer_expense_participants(conn, exp_id, group_id, payer_id)
        if not participants:
            continue

        user_involved = user_id in participants or payer_id == user_id
        if not user_involved:
            continue

        share = total / len(participants) if participants else 0.0
        personal_amount = share if user_id in participants else 0.0

        if payer_id == user_id:
            net = total - personal_amount
        else:
            net = -personal_amount

        if net > 0:
            to_receive += net
        elif net < 0:
            to_pay += -net

        category_row = conn.execute(
            "SELECT category FROM expense_items WHERE expense_id = ? ORDER BY id ASC LIMIT 1",
            (exp_id,),
        ).fetchone()
        category = category_row[0] if category_row and category_row[0] else "Otros"

        recent_expenses.append(
            {
                "id": exp_id,
                "title": exp["title"],
                "totalAmount": round(total, 2),
                "personalAmount": round(personal_amount, 2),
                "date": exp["date"],
                "category": category,
            }
        )

    return {
        "toReceive": round(to_receive, 2),
        "toPay": round(to_pay, 2),
        "recentExpenses": recent_expenses[:5],
    }
