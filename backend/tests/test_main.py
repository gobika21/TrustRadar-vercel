import sqlite3
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


class _SqliteBackedCursor:
    """Wraps a sqlite3 cursor so it can stand in for a pg8000 cursor in tests.

    Only translates the `%s` placeholder style -- fetchall/fetchone/description
    are passed straight through as raw tuples, matching what pg8000 actually
    returns (storage.py does its own tuple-to-dict conversion via .description).
    """

    def __init__(self, sqlite_cursor: sqlite3.Cursor) -> None:
        self._cursor = sqlite_cursor

    def execute(self, sql: str, params=None) -> None:
        self._cursor.execute(sql.replace("%s", "?"), params or [])

    @property
    def description(self):
        return self._cursor.description

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchone(self):
        return self._cursor.fetchone()


class _SqliteBackedConnection:
    """Stands in for a pg8000 connection, backed by an in-memory SQLite db."""

    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.autocommit = True

    def cursor(self) -> _SqliteBackedCursor:
        return _SqliteBackedCursor(self._conn.cursor())


class AnalyzeEndpointTests(unittest.TestCase):
    def setUp(self):
        self._fake_pg = _SqliteBackedConnection()
        self._env_patch = patch.dict("os.environ", {"POSTGRES_URL": "postgres://fake"})
        self._env_patch.start()
        self._pg_patch = patch("app.storage.pg8000.dbapi.connect", return_value=self._fake_pg)
        self._pg_patch.start()
        self._verify_patch = patch("app.main.verify_live", new=AsyncMock(return_value=[]))
        self._verify_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self._verify_patch.stop()
        self._pg_patch.stop()
        self._env_patch.stop()

    def test_vague_message_with_no_scam_signal_is_blocked_before_scoring(self):
        response = self.client.post(
            "/api/analyze", data={"text": "Hello, you are invited for an interview tomorrow"}
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("enough detail to review", response.json()["detail"])

    def test_jd_gate_rejection_is_not_logged_when_no_agent_call_happened(self):
        # check_jd_validity returns None when agents are disabled -- the
        # heuristic fallback is free, so there's nothing worth logging.
        with patch("app.main.record_blocked_attempt") as mock_record:
            self.client.post(
                "/api/analyze", data={"text": "Hello, you are invited for an interview tomorrow"}
            )
        mock_record.assert_not_called()

    def test_jd_gate_rejection_is_logged_when_a_real_agent_call_happened(self):
        with patch(
            "app.main.check_jd_validity",
            new=AsyncMock(return_value={"is_valid_jd": False, "missing": ["role"], "reason": "too vague"}),
        ), patch("app.main.record_blocked_attempt") as mock_record:
            response = self.client.post(
                "/api/analyze", data={"text": "Hello, you are invited for an interview tomorrow"}
            )

        self.assertEqual(response.status_code, 422)
        mock_record.assert_called_once()
        logged_entry = mock_record.call_args.args[0]
        self.assertIn("jd_gate", logged_entry["reason"])
        self.assertIn("invited for an interview", logged_entry["textSnippet"])

    def test_valid_jd_passes_the_gate_and_returns_a_full_result(self):
        response = self.client.post(
            "/api/analyze",
            data={
                "text": (
                    "We are hiring a Product Designer at Lumen Studio. Standard interview process, "
                    "salary $90k-$110k, apply via the careers page."
                )
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("tier", body)
        self.assertIn("score", body)
        self.assertIn("pattern_findings", body)

    def test_weak_scam_signal_without_jd_detail_is_still_blocked(self):
        response = self.client.post(
            "/api/analyze",
            data={
                "text": (
                    "We're excited to offer you the role! As a welcome gift, you'll receive a "
                    "$100 gift card on your first day."
                )
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_strong_scam_signal_bypasses_the_jd_gate_and_is_scored(self):
        response = self.client.post(
            "/api/analyze",
            data={"text": "Please pay the training fee using a gift card to start work."},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(body["score"], 45)
        self.assertIn(body["tier_level"], {"high", "critical"})

    def test_instant_offer_with_no_process_bypasses_the_jd_gate_and_is_scored(self):
        response = self.client.post(
            "/api/analyze",
            data={
                "text": (
                    "Congrats, you got the job! Send a $100 gift card today to confirm your "
                    "start date."
                )
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        ids = {finding["id"] for finding in body["pattern_findings"]}
        self.assertIn("instant_offer_no_process", ids)
        self.assertNotEqual(body["tier"], "Lower risk")

    def test_vague_offer_with_company_and_salary_but_no_role_is_blocked(self):
        response = self.client.post(
            "/api/analyze",
            data={
                "text": (
                    "welcome, you got offer from trust radar company with salary of 2000 AED, "
                    "please join on Aug,2026"
                )
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        ids = {finding["id"] for finding in body["pattern_findings"]}
        self.assertIn("instant_offer_no_process", ids)
        self.assertNotEqual(body["tier"], "Lower risk")

    def test_url_only_submission_bypasses_the_jd_gate(self):
        with patch(
            "app.main.fetch_submitted_job_descriptions", new=AsyncMock(return_value="")
        ):
            response = self.client.post("/api/analyze", data={"job_url": "https://example.com/careers/12345"})
        self.assertEqual(response.status_code, 200)

    def test_url_only_submission_is_flagged_as_platform_sourced(self):
        with patch(
            "app.main.fetch_submitted_job_descriptions",
            new=AsyncMock(return_value="We are hiring a Senior Engineer at Acme."),
        ), patch(
            "app.main.run_agentic_analysis", new=AsyncMock(return_value=([], None))
        ) as mock_run:
            response = self.client.post("/api/analyze", data={"job_url": "https://example.com/careers/12345"})

        self.assertEqual(response.status_code, 200)
        mock_run.assert_awaited_once()
        _, kwargs = mock_run.call_args
        called_args = mock_run.call_args.args
        self.assertTrue(called_args[1] if len(called_args) > 1 else kwargs.get("sourced_from_platform"))

    def test_pasted_text_alongside_a_url_is_not_flagged_as_platform_sourced(self):
        with patch(
            "app.main.fetch_submitted_job_descriptions",
            new=AsyncMock(return_value="We are hiring a Senior Engineer at Acme."),
        ), patch(
            "app.main.run_agentic_analysis", new=AsyncMock(return_value=([], None))
        ) as mock_run:
            response = self.client.post(
                "/api/analyze",
                data={
                    "text": "hey, you're shortlisted, send your bank details to confirm",
                    "job_url": "https://example.com/careers/12345",
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_run.assert_awaited_once()
        called_args = mock_run.call_args.args
        kwargs = mock_run.call_args.kwargs
        self.assertFalse(called_args[1] if len(called_args) > 1 else kwargs.get("sourced_from_platform"))

    def test_history_round_trip_after_a_successful_analysis(self):
        analyze_response = self.client.post(
            "/api/analyze",
            data={
                "text": (
                    "We are hiring a Product Designer at Lumen Studio. Standard interview process, "
                    "salary $90k-$110k, apply via the careers page."
                )
            },
        )
        self.assertEqual(analyze_response.status_code, 200)

        history_response = self.client.get("/api/history")
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(len(history_response.json()), 1)

        clear_response = self.client.delete("/api/history")
        self.assertEqual(clear_response.status_code, 200)
        self.assertEqual(self.client.get("/api/history").json(), [])

        # Clearing should soft-delete, not destroy -- the row must still be
        # in the underlying table, just flagged and hidden from the API.
        raw_cursor = self._fake_pg.cursor()
        raw_cursor.execute("SELECT deleted_at FROM analyses")
        rows = raw_cursor.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertIsNotNone(rows[0][0])


if __name__ == "__main__":
    unittest.main()
