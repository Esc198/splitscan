from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

try:
    from app.api.router_setup import register_routers
    from app.application import create_application
    from app.core.config import settings
    from app.core.logging import configure_backend_logging
    from app.db.sqlite import get_conn, rows_to_dict, sqlite_lastrowid
    from app.lifecycle import build_lifespan
    from app.runtime import donut_inference_service
    from app.support.auth import parse_int
    from app.support.groups import generate_join_code, get_group_member_ids
except ImportError:  # pragma: no cover - alternate launch mode
    from backend.app.api.router_setup import register_routers
    from backend.app.application import create_application
    from backend.app.core.config import settings
    from backend.app.core.logging import configure_backend_logging
    from backend.app.db.sqlite import get_conn, rows_to_dict, sqlite_lastrowid
    from backend.app.lifecycle import build_lifespan
    from backend.app.runtime import donut_inference_service
    from backend.app.support.auth import parse_int
    from backend.app.support.groups import generate_join_code, get_group_member_ids

configure_backend_logging(settings.backend_log_level)

LOGGER = logging.getLogger("backend.main")


def add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    """Add a column to an existing table only when the schema does not include it yet."""
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if column not in [c[1] for c in cols]:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def ensure_schema() -> None:
    """Create the database schema and apply lightweight migrations and seed data."""
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT UNIQUE NOT NULL,
              updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS groups (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              join_code TEXT UNIQUE,
              updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS incomes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER,
              amount REAL,
              description TEXT,
              date TEXT,
              updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS group_members (
              group_id INTEGER,
              user_id INTEGER,
              updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(group_id) REFERENCES groups(id),
              FOREIGN KEY(user_id) REFERENCES users(id),
              PRIMARY KEY(group_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS expenses (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              group_id INTEGER,
              payer_id INTEGER,
              total_amount REAL,
              merchant_name TEXT,
              date TEXT,
              image_data TEXT,
              updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(group_id) REFERENCES groups(id),
              FOREIGN KEY(payer_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS expense_participants (
              expense_id INTEGER,
              user_id INTEGER,
              updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(expense_id) REFERENCES expenses(id),
              FOREIGN KEY(user_id) REFERENCES users(id),
              PRIMARY KEY(expense_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS expense_items (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              expense_id INTEGER,
              name TEXT,
              price REAL,
              category TEXT,
              updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(expense_id) REFERENCES expenses(id)
            );

            CREATE TABLE IF NOT EXISTS item_participants (
              item_id INTEGER,
              user_id INTEGER,
              percentage REAL,
              updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(item_id) REFERENCES expense_items(id),
              FOREIGN KEY(user_id) REFERENCES users(id),
              PRIMARY KEY(item_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS categories (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT UNIQUE NOT NULL,
              color TEXT,
              icon TEXT,
              updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        add_column_if_missing(conn, "users", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        add_column_if_missing(conn, "groups", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        add_column_if_missing(conn, "groups", "join_code", "TEXT UNIQUE")
        add_column_if_missing(conn, "incomes", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        add_column_if_missing(conn, "group_members", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        add_column_if_missing(conn, "expenses", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        add_column_if_missing(conn, "expenses", "image_data", "TEXT")
        add_column_if_missing(conn, "expense_participants", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        add_column_if_missing(conn, "expense_items", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        add_column_if_missing(conn, "item_participants", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")

        group_rows = conn.execute("SELECT id FROM groups WHERE join_code IS NULL").fetchall()
        for row in group_rows:
            conn.execute("UPDATE groups SET join_code = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (generate_join_code(), row[0]))

        conn.executescript(
            """
            UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;
            UPDATE groups SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;
            UPDATE group_members SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;
            UPDATE expenses SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;
            UPDATE expense_participants SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;
            UPDATE expense_items SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;
            UPDATE item_participants SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;
            UPDATE incomes SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;
            UPDATE categories SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;
            """
        )

        cat_count = conn.execute("SELECT count(*) FROM categories").fetchone()[0]
        if cat_count == 0:
            for name, color, icon in [
                ("Alimentación", "#10b981", "Utensils"),
                ("Transporte", "#3b82f6", "Car"),
                ("Ocio", "#f59e0b", "Music"),
                ("Vivienda", "#ef4444", "Home"),
                ("Salud", "#ec4899", "Heart"),
                ("Otros", "#64748b", "Tag"),
            ]:
                conn.execute(
                    "INSERT INTO categories (name, color, icon, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    (name, color, icon),
                )
app = create_application(
    settings=settings,
    lifespan=build_lifespan(
        ensure_schema=ensure_schema,
        preload_model=settings.donut_preload_model,
        inference_service=donut_inference_service,
        logger=LOGGER,
    ),
)
register_routers(app)
@app.post("/api/incomes")
def add_income(payload: dict[str, Any]) -> dict[str, int]:
    """Create an income record for a user."""
    user_id = parse_int(payload.get("user_id") or payload.get("userId"))
    amount = payload.get("amount")
    description = payload.get("description")
    date = payload.get("date")

    if user_id is None or not isinstance(amount, (int, float)):
        raise HTTPException(status_code=400, detail="Invalid income data")

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO incomes (user_id, amount, description, date, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (user_id, float(amount), description, date or datetime.now(timezone.utc).isoformat()),
        )
        return {"id": sqlite_lastrowid(cur)}


@app.get("/api/expenses")
def list_expenses() -> list[dict[str, Any]]:
    """List all expenses across the application."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, group_id, payer_id, total_amount,
                   COALESCE(merchant_name, 'Gasto') AS title,
                   COALESCE(date, updated_at) AS date,
                   image_data,
                   updated_at
            FROM expenses
            ORDER BY COALESCE(date, updated_at) DESC, id DESC
            """
        ).fetchall()
        return rows_to_dict(rows)


@app.post("/api/expenses")
def save_expense(payload: dict[str, Any]) -> dict[str, Any]:
    """Create an expense, its participants, and its item rows from the payload."""
    group_id = parse_int(payload.get("group_id") if "group_id" in payload else payload.get("groupId"))
    payer_id = parse_int(payload.get("payer_id") if "payer_id" in payload else payload.get("paidBy"))
    total_amount_raw = payload.get("total_amount", payload.get("totalAmount", 0))
    merchant_name_raw = payload.get("merchant_name") or payload.get("title") or "Gasto"
    date = payload.get("date")
    image_data = payload.get("image_data")
    participants_raw = payload.get("participants")
    items = payload.get("items") or []

    if payer_id is None:
        raise HTTPException(status_code=400, detail="Invalid expense data: payer is required")

    try:
        total_amount = float(total_amount_raw or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid expense data: totalAmount")

    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="Invalid expense data: items")
    if participants_raw is not None and not isinstance(participants_raw, list):
        raise HTTPException(status_code=400, detail="Invalid expense data: participants")

    merchant_name = merchant_name_raw.strip() if isinstance(merchant_name_raw, str) and merchant_name_raw.strip() else "Gasto"
    date_value = date if isinstance(date, str) and date.strip() else datetime.now(timezone.utc).isoformat()

    participants: list[int] = []
    if isinstance(participants_raw, list):
        participants = [uid for uid in (parse_int(value) for value in participants_raw) if uid is not None]

    with get_conn() as conn:
        if group_id is not None:
            group_exists = conn.execute("SELECT id FROM groups WHERE id = ?", (group_id,)).fetchone()
            if not group_exists:
                raise HTTPException(status_code=404, detail="Group not found")

            conn.execute(
                "INSERT OR IGNORE INTO group_members (group_id, user_id, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (group_id, payer_id),
            )

        if not participants:
            if group_id is not None:
                participants = get_group_member_ids(conn, group_id)
            if not participants:
                participants = [payer_id]

        if payer_id not in participants:
            participants.append(payer_id)

        if group_id is not None:
            for participant_id in participants:
                conn.execute(
                    "INSERT OR IGNORE INTO group_members (group_id, user_id, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (group_id, participant_id),
                )

        cur = conn.execute(
            """
            INSERT INTO expenses (group_id, payer_id, total_amount, merchant_name, date, image_data, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (group_id, payer_id, total_amount, merchant_name, date_value, image_data),
        )
        expense_id = sqlite_lastrowid(cur)

        for participant_id in sorted(set(participants)):
            conn.execute(
                "INSERT OR IGNORE INTO expense_participants (expense_id, user_id, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (expense_id, participant_id),
            )

        default_category = payload.get("category") if isinstance(payload.get("category"), str) else "Otros"
        for item in items:
            if not isinstance(item, dict):
                continue

            item_name_raw = item.get("name") if "name" in item else item.get("description")
            item_name = item_name_raw.strip() if isinstance(item_name_raw, str) and item_name_raw.strip() else "Item"

            item_price_raw = item.get("price") if "price" in item else item.get("amount")
            try:
                item_price = float(item_price_raw or 0)
            except (TypeError, ValueError):
                item_price = 0.0

            category = item.get("category") if isinstance(item.get("category"), str) else default_category
            item_cur = conn.execute(
                "INSERT INTO expense_items (expense_id, name, price, category, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (expense_id, item_name, item_price, category),
            )
            item_id = sqlite_lastrowid(item_cur)

            item_participants_raw = item.get("participants")
            if isinstance(item_participants_raw, list):
                valid_item_participants = [uid for uid in (parse_int(value) for value in item_participants_raw) if uid is not None]
                valid_item_participants = list(sorted(set(valid_item_participants)))
                if valid_item_participants:
                    per_user = 1 / len(valid_item_participants)
                    for uid in valid_item_participants:
                        conn.execute(
                            "INSERT OR IGNORE INTO item_participants (item_id, user_id, percentage, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                            (item_id, uid, per_user),
                        )

        return {"id": expense_id, "status": "success"}


@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: int) -> dict[str, bool]:
    """Delete an expense together with its dependent participant records."""
    with get_conn() as conn:
        expense = conn.execute("SELECT id FROM expenses WHERE id = ?", (expense_id,)).fetchone()
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")

        item_ids = [
            row[0]
            for row in conn.execute("SELECT id FROM expense_items WHERE expense_id = ?", (expense_id,)).fetchall()
        ]
        if item_ids:
            item_ph = ",".join("?" for _ in item_ids)
            conn.execute(f"DELETE FROM item_participants WHERE item_id IN ({item_ph})", tuple(item_ids))

        conn.execute("DELETE FROM expense_items WHERE expense_id = ?", (expense_id,))
        conn.execute("DELETE FROM expense_participants WHERE expense_id = ?", (expense_id,))
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))

    return {"success": True}


@app.get("/api/pyg/{user_id}")
def get_pyg(user_id: int) -> list[dict[str, Any]]:
    """Return per-category spending totals attributed to a user."""
    with get_conn() as conn:
        query = """
        SELECT
          ei.category,
          SUM(
            CASE
              WHEN ip.user_id IS NOT NULL THEN ei.price * ip.percentage
              WHEN ep.user_id IS NOT NULL
                AND NOT EXISTS (SELECT 1 FROM item_participants WHERE item_id = ei.id)
                THEN ei.price / (SELECT COUNT(*) FROM expense_participants WHERE expense_id = e.id)
              ELSE 0
            END
          ) AS amount
        FROM expense_items ei
        JOIN expenses e ON ei.expense_id = e.id
        LEFT JOIN item_participants ip ON ei.id = ip.item_id AND ip.user_id = ?
        LEFT JOIN expense_participants ep ON e.id = ep.expense_id AND ep.user_id = ?
        GROUP BY ei.category
        """
        return rows_to_dict(conn.execute(query, (user_id, user_id)).fetchall())


