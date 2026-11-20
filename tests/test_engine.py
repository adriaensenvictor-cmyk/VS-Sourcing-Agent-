"""Offline unit tests: no live network calls required."""
import unittest
from unittest.mock import patch
import engine


class ScoutingTests(unittest.TestCase):
    def test_german_location_does_not_accept_delaware(self):
        self.assertFalse(engine.german_location("Wilmington, DE, USA"))
        self.assertTrue(engine.german_location("Berlin, Germany"))

    def test_unidentified_founder_caps_score(self):
        lead = engine.candidate("x", "Industrial robotics AI", "GitHub", "https://github.com/a/b",
             "Pilot customers, paid enterprise software prototype from university research",
             "Berlin, Germany", team="co-founder", founder_identified=False)
        self.assertLessEqual(lead["score"], 68)
        self.assertEqual(lead["funding_status"], "Unknown — requires independent diligence")

    def test_existed_grant_is_not_a_vc_round(self):
        lead = engine.candidate("x", "Climate tool", "TU Berlin", "https://tu.berlin/",
            "Industrial climate platform", "Berlin, Germany", team="Jane Doe",
            founder_identified=True, evidence_items=[engine.evidence(
               "EXIST support", "An EXIST grant", "https://tu.berlin/")])
        self.assertEqual(lead["funding_status"], "Unknown — requires independent diligence")
        self.assertIn("university venture support", lead["score_components"])

    def test_hn_location_mention_not_sufficient(self):
        response = {"hits": [{"title": "Show HN: My new AI robot", "story_text":
             "I love visiting Berlin, but I am based in NYC", "objectID": "123",
             "created_at": "2026-10-01T00:00:00Z", "url": "https://example.com"}]}
        with patch("engine.get_json", return_value=response):
            self.assertEqual(engine.scan_hackernews(cities=("Berlin",)), [])

    def test_hn_self_reported_location_qualifies(self):
        response = {"hits": [{"title": "Show HN: A manufacturing analytics MVP",
             "story_text": "We are based in Berlin and just launched a demo for pilot customers",
             "objectID": "124", "created_at": "2026-10-01T00:00:00Z",
             "url": "https://example.com"}]}
        with patch("engine.get_json", return_value=response):
            result = engine.scan_hackernews(cities=("Berlin",))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "hn:124")
        self.assertTrue(result[0]["evidence"])
        self.assertLessEqual(result[0]["score"], 68)

    def test_dedupe_same_project_link(self):
        first = engine.candidate("a", "Project One", "Hacker News", "https://news.ycombinator.com/item?id=1",
             "Industrial automation", "Berlin, Germany",
             project_url="https://github.com/startup/repo")
        second = engine.candidate("b", "Project One", "GitHub", "https://github.com/startup/repo",
             "Industrial automation", "Berlin, Germany",
             project_url="https://github.com/startup/repo")
        self.assertEqual(len(engine.deduplicate([first, second])), 1)


if __name__ == "__main__":
    unittest.main()
