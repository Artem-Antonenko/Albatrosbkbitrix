"""Работа с SQLite: абонементы фитнес-клуба.

Этот модуль остаётся в проекте как внутренняя деталь LocalProvider.
Бот напрямую к нему больше не обращается — все вызовы идут через
интерфейс DataProvider.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "members.db")


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Создать таблицу members, если её нет."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS members (
                card_id       TEXT PRIMARY KEY,
                name          TEXT,
                sessions_left INTEGER,
                valid_until   TEXT   -- 'YYYY-MM-DD'
            )
        """)
        conn.commit()
    print(f"[DB] База данных готова: {DB_PATH}")


def find_member(card_id: str) -> dict | None:
    """Найти абонемент по номеру карты. Возвращает dict или None."""
    with _connect() as conn:
        cur = conn.execute(
            "SELECT card_id, name, sessions_left, valid_until "
            "FROM members WHERE card_id = ?",
            (card_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "card_id":       row[0],
        "name":          row[1],
        "sessions_left": row[2],
        "valid_until":   row[3],
    }
