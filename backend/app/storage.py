from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlparse

import pg8000.dbapi


def get_connection():
    dsn = os.environ.get("POSTGRES_URL")
    if not dsn:
        raise RuntimeError(
            "POSTGRES_URL is not set. Add the Vercel Postgres integration to this "
            "project (or set POSTGRES_URL locally) to enable history storage."
        )
    parsed = urlparse(dsn)
    connection = pg8000.dbapi.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
        ssl_context=True,
    )
    connection.autocommit = True
    return connection


def _rows_to_dicts(cursor) -> list[dict[str, Any]]:
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def initialize_database() -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC)")


def save_analysis(entry: dict[str, Any]) -> None:
    initialize_database()
    result = entry["result"]
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO analyses (id, created_at, label, input_json, result_json, score, tier, tier_level)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            created_at = EXCLUDED.created_at,
            label = EXCLUDED.label,
            input_json = EXCLUDED.input_json,
            result_json = EXCLUDED.result_json,
            score = EXCLUDED.score,
            tier = EXCLUDED.tier,
            tier_level = EXCLUDED.tier_level
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
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT id, created_at, label, input_json, result_json
        FROM analyses
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = _rows_to_dicts(cursor)
    return [row_to_entry(row) for row in rows]


def get_analysis(entry_id: str) -> dict[str, Any] | None:
    initialize_database()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT id, created_at, label, input_json, result_json
        FROM analyses
        WHERE id = %s
        """,
        (entry_id,),
    )
    rows = _rows_to_dicts(cursor)
    return row_to_entry(rows[0]) if rows else None


def clear_analyses() -> None:
    initialize_database()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM analyses")


def row_to_entry(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "createdAt": row["created_at"],
        "label": row["label"],
        "input": json.loads(row["input_json"]),
        "result": json.loads(row["result_json"]),
    }
