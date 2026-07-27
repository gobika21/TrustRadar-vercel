from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_DIR / "trustradar.sqlite3"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                label TEXT NOT NULL,
                input_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                score INTEGER NOT NULL,
                tier TEXT NOT NULL,
                tier_level TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC)")


def save_analysis(entry: dict[str, Any]) -> None:
    initialize_database()
    result = entry["result"]
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO analyses (
                id, created_at, label, input_json, result_json, score, tier, tier_level
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["id"],
                entry["createdAt"],
                entry["label"],
                json.dumps(entry["input"]),
                json.dumps(result),
                result["score"],
                result["tier"],
                result["tier_level"],
            ),
        )


def list_analyses(limit: int = 20) -> list[dict[str, Any]]:
    initialize_database()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, label, input_json, result_json
            FROM analyses
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [row_to_entry(row) for row in rows]


def get_analysis(entry_id: str) -> dict[str, Any] | None:
    initialize_database()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, created_at, label, input_json, result_json
            FROM analyses
            WHERE id = ?
            """,
            (entry_id,),
        ).fetchone()
    return row_to_entry(row) if row else None


def clear_analyses() -> None:
    initialize_database()
    with get_connection() as connection:
        connection.execute("DELETE FROM analyses")


def row_to_entry(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "createdAt": row["created_at"],
        "label": row["label"],
        "input": json.loads(row["input_json"]),
        "result": json.loads(row["result_json"]),
    }
