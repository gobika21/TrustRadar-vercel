import unittest

from app.analysis import extract_evidence_links
from app.models import Evidence


class ExtractEvidenceLinksTests(unittest.TestCase):
    def test_parses_titles_containing_parentheses(self):
        detail = (
            "Top results: LinkedIn Recruiter Scams on the Rise (https://a.example/1) | "
            "18 LinkedIn Scams I Fell For (So You Don't Have To) (https://b.example/2) | "
            "Scammers impersonate well-known companies (https://c.example/3)"
        )
        item = Evidence("Web search", "found", detail, "query", "high")

        links = extract_evidence_links(item)

        self.assertEqual(len(links), 3)
        self.assertEqual(links[0], {"label": "LinkedIn Recruiter Scams on the Rise", "url": "https://a.example/1"})
        self.assertEqual(
            links[1],
            {"label": "18 LinkedIn Scams I Fell For (So You Don't Have To)", "url": "https://b.example/2"},
        )
        self.assertEqual(links[2], {"label": "Scammers impersonate well-known companies", "url": "https://c.example/3"})

    def test_strips_llm_assessment_suffix(self):
        detail = "Top results: Some article (https://a.example/1) | LLM assessment: looks legitimate."
        item = Evidence("Web search", "found", detail, "query", "info")

        links = extract_evidence_links(item)

        self.assertEqual(links, [{"label": "Some article", "url": "https://a.example/1"}])

    def test_returns_no_links_when_search_was_skipped(self):
        item = Evidence("Web search", "skipped", "No company or domain query was available.", "search")

        self.assertEqual(extract_evidence_links(item), [])

    def test_source_url_link_still_added_for_reachability_evidence(self):
        item = Evidence("URL reachability", "checked", "HTTP 200", "https://example.com/job")

        links = extract_evidence_links(item)

        self.assertEqual(links, [{"label": "URL reachability", "url": "https://example.com/job"}])


if __name__ == "__main__":
    unittest.main()
