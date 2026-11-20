import json
import unittest
from unittest.mock import patch

from ui_brief import citable_evidence, generate_brief


class BriefTests(unittest.TestCase):
    def setUp(self):
        entry = {"signal": "University grant", "excerpt": "Awarded a research grant.",
                 "url": "https://example.org/award"}
        self.sources = citable_evidence({"evidence": [entry]})

    def test_citations_require_public_http_links_and_deduplicate(self):
        entry = self.sources[0]
        lead = {"evidence": [entry, None, dict(entry, url="file:///etc/passwd"),
                             dict(entry, url="https://token@example.org")]}
        self.assertEqual(citable_evidence(lead, [entry]), [entry])

    @patch("ui_brief.requests.post")
    def test_complete_and_cited_response(self, post):
        points = [{"text": "The team received grant support.", "source_id": 1}]
        post.return_value.json.return_value = self.response(points)
        self.assertEqual(generate_brief("Test", self.sources, "What support?", "test"), points)
        payload = post.call_args.kwargs["json"]
        self.assertFalse(payload["store"])
        self.assertNotIn("https://example.org", payload["input"])
        self.assertNotIn("Authorization", payload["input"])

    def response(self, points):
        return {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps({"points": points})}
        ]}]}

    @patch("ui_brief.requests.post")
    def test_rejects_foreign_citations_and_invented_links(self, post):
        for point in ({"text": "A claim", "source_id": 8},
                      {"text": "https://invented.example", "source_id": 1}):
            post.return_value.json.return_value = self.response([point])
            with self.subTest(point=point), self.assertRaises(ValueError):
                generate_brief("Test", self.sources, "Overview", "test")

    @patch("ui_brief.requests.post")
    def test_no_key_or_evidence_never_contacts_api(self, post):
        for sources, key in (([], "test"), (self.sources, "")):
            with self.assertRaises(ValueError):
                generate_brief("Test", sources, "Overview", key)
        post.assert_not_called()
