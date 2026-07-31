import unittest
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from app.verification import (
    extract_description_text,
    fetch_job_description,
    fetch_submitted_job_descriptions,
)

LINKEDIN_STYLE_HTML = """
<html>
<head><title>Acme hiring Senior Engineer | LinkedIn</title>
<meta name="description" content="Short teaser snippet only."></head>
<body>
<div class="show-more-less-html__markup show-more-less-html__markup--clamp-after-5">
  <p>We are looking for a Senior Engineer to join our growing team.</p>
  <p>Responsibilities include building scalable systems.</p>
</div>
</body>
</html>
"""

META_ONLY_HTML = """
<html>
<head><title>Some Job | Example</title>
<meta property="og:description" content="A generic job description from the meta tag."></head>
<body><p>Nothing structured here.</p></body>
</html>
"""

EMPTY_HTML = "<html><head><title>No description</title></head><body></body></html>"


class ExtractDescriptionTextTests(unittest.TestCase):
    def test_extracts_linkedin_style_markup(self):
        text = extract_description_text(LINKEDIN_STYLE_HTML)

        self.assertIsNotNone(text)
        self.assertIn("Senior Engineer", text)
        self.assertIn("scalable systems", text)

    def test_falls_back_to_meta_description(self):
        text = extract_description_text(META_ONLY_HTML)

        self.assertEqual(text, "A generic job description from the meta tag.")

    def test_returns_none_when_nothing_found(self):
        self.assertIsNone(extract_description_text(EMPTY_HTML))


class FetchJobDescriptionTests(IsolatedAsyncioTestCase):
    async def test_returns_none_on_http_error_status(self):
        client = MagicMock()
        response = MagicMock(status_code=404, headers={"content-type": "text/html"})
        client.get = AsyncMock(return_value=response)

        result = await fetch_job_description(client, "https://example.com/job/1")

        self.assertIsNone(result)

    async def test_returns_none_for_non_html_content(self):
        client = MagicMock()
        response = MagicMock(status_code=200, headers={"content-type": "application/json"})
        client.get = AsyncMock(return_value=response)

        result = await fetch_job_description(client, "https://example.com/job/1")

        self.assertIsNone(result)

    async def test_extracts_description_from_successful_response(self):
        client = MagicMock()
        response = MagicMock(status_code=200, headers={"content-type": "text/html"}, text=LINKEDIN_STYLE_HTML)
        client.get = AsyncMock(return_value=response)

        result = await fetch_job_description(client, "https://example.com/job/1")

        self.assertIn("Senior Engineer", result)

    async def test_swallows_unexpected_exceptions(self):
        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError("boom"))

        result = await fetch_job_description(client, "https://example.com/job/1")

        self.assertIsNone(result)


class FetchSubmittedJobDescriptionsTests(IsolatedAsyncioTestCase):
    async def test_returns_empty_string_for_no_urls(self):
        self.assertEqual(await fetch_submitted_job_descriptions([]), "")

    @patch("app.verification.fetch_job_description", new_callable=AsyncMock)
    @patch("app.verification.httpx.AsyncClient")
    async def test_joins_descriptions_from_multiple_urls(self, mock_client_cls, mock_fetch):
        mock_client_cls.return_value.__aenter__.return_value = MagicMock()
        mock_fetch.side_effect = ["First description.", None, "Third description."]

        result = await fetch_submitted_job_descriptions(
            ["https://a.example/1", "https://b.example/2", "https://c.example/3"]
        )

        self.assertEqual(result, "First description.\n\nThird description.")


if __name__ == "__main__":
    unittest.main()
