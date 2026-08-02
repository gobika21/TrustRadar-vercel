from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import pg8000.dbapi


# Different Vercel Postgres marketplace providers (Neon, Prisma Postgres,
# Supabase, ...) inject the connection string under different env var names.
# Check them in order and use whichever is actually set.
POSTGRES_URL_ENV_VARS = [
    "POSTGRES_URL",
    "DATABASE_URL",
    "POSTGRES_PRISMA_URL",
    "PRISMA_DATABASE_URL",
    "POSTGRES_URL_NON_POOLING",
]


def _find_postgres_dsn() -> str | None:
    for name in POSTGRES_URL_ENV_VARS:
        value = os.environ.get(name)
        if value:
            return value
    return None


def get_connection():
    dsn = _find_postgres_dsn()
    if not dsn:
        raise RuntimeError(
            "No Postgres connection string found. Checked env vars: "
            f"{', '.join(POSTGRES_URL_ENV_VARS)}. Add a Postgres integration to "
            "this Vercel project (or set one of these locally) to enable history storage."
        )
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise RuntimeError(
            f"Found a connection string but it doesn't look like a direct Postgres DSN "
            f"(scheme: {parsed.scheme!r}). If you're using Prisma Postgres, use the direct "
            "connection string (not the prisma+postgres:// Accelerate URL) -- check your "
            "provider's dashboard for a postgres:// or postgresql:// URL."
        )
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
            tier_level TEXT NOT NULL,
            deleted_at TEXT
        )
        """
    )
    # Deployments created before soft-delete existed won't have this column
    # yet -- add it if missing. Best-effort: CREATE TABLE above already
    # covers fresh databases, so a failure here (e.g. a test double that
    # doesn't support this syntax) is safe to ignore.
    try:
        cursor.execute("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS deleted_at TEXT")
    except Exception:
        pass
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
        WHERE deleted_at IS NULL
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
        WHERE id = %s AND deleted_at IS NULL
        """,
        (entry_id,),
    )
    rows = _rows_to_dicts(cursor)
    return row_to_entry(rows[0]) if rows else None


def clear_analyses() -> None:
    """Soft-delete every visible analysis rather than destroying the rows.

    Clearing history from the UI shouldn't be an irreversible data-loss event
    -- flag rows as deleted instead so they're hidden from the app but still
    recoverable directly from the database if needed.
    """
    initialize_database()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE analyses SET deleted_at = %s WHERE deleted_at IS NULL",
        (datetime.now(timezone.utc).isoformat(),),
    )


def row_to_entry(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "createdAt": row["created_at"],
        "label": row["label"],
        "input": json.loads(row["input_json"]),
        "result": json.loads(row["result_json"]),
    }
