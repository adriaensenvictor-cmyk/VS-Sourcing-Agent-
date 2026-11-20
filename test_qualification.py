import unittest
from unittest.mock import patch

from campus import TeamPage
from qualification import detect_intent, merge_candidates, public_funding_search, qualify


def lead(identity, url, **fields):
    return {
        "id": identity, "title": identity, "source_url": url,
        "linkedin": {"public_links": []}, "evidence": [], **fields,
    }


class QualificationTests(unittest.TestCase):
    def test_unreviewed_is_unknown_and_cue_is_hypothesis(self):
        url = "https://example.org/project"
        item = lead("test", url, intent_cues=detect_intent("Join our waitlist. We're hiring.", url))
        result = qualify([item])
        self.assertEqual(result["funding"]["status"], "unknown")
        self.assertEqual({item["type"] for item in result["claims"]}, {"waitlist", "hiring"})
        self.assertTrue(all(item["status"] == "hypothesis" and item["source_url"] == url
                            for item in result["claims"]))
        self.assertEqual(result["scores"]["entrepreneurial_intent"], 2)

    def test_funding_evidence_overrides_negative_review(self):
        primary = lead("a", "https://example.org/team", funding_status="grant_reported",
                       funding_source="https://example.org/grant")
        funded = lead("b", "https://example.com/team", funding_status="vc_round_reported",
                      funding_source="https://example.com/round")
        negative = {"outcome": "no_funding_found", "queries": ["funding"], "sources": []}
        self.assertEqual(qualify([primary])["funding"]["status"], "unknown")
        self.assertEqual(qualify([primary], search_review=negative)["funding"]["status"], "no_funding_found")
        result = qualify([primary, funded], search_review=negative)
        self.assertEqual(result["funding"]["status"], "funded")
        self.assertEqual(result["scores"]["earliness"], 0)
        self.assertEqual(len(result["funding"]["public_support"]), 1)

    def test_github_and_domain_bridges_merge_transitively(self):
        first = lead("campus", "https://uni.example/team", project_url="https://project.example/")
        second = lead("github", "https://github.com/team/project",
                      project_url="https://github.com/team/project.git")
        bridge = lead("hn", "https://news.ycombinator.com/item?id=1", project_url="https://www.project.example",
                      links={"github": ["https://github.com/Team/Project/releases"]})
        unrelated = lead("other", "https://uni.example/other", project_url="https://project.example/another")
        self.assertEqual(sorted(len(group) for group in merge_candidates([first, second, bridge, unrelated])),
                         [1, 3])

    def test_timeline_uses_dated_events_and_retains_provenance(self):
        item = lead("a", "https://uni.example/team", source_updated_at="2020-01-01",
                    milestones=[{"date": "2025-01-01", "url": "https://uni.example/demo", "label": "Demo"}])
        release = {"date": "2024-09-01", "url": "https://github.com/a/b/releases/1", "label": "Release"}
        result = qualify([item], [release])
        self.assertEqual(result["earliest_verified_public_signal"], release)
        self.assertEqual(len(result["timeline"]), 2)

    def test_reads_only_named_founders_from_university_facts(self):
        parser = TeamPage()
        parser.feed("<main><dl><dt>Founders</dt><dd>Jane Doe<br>John Smith</dd>"
                    "<dt>Lab</dt><dd>Other Person</dd></dl></main>")
        self.assertEqual(parser.founders, ["Jane Doe", "John Smith"])

    @patch("qualification.urlopen", side_effect=OSError("offline"))
    def test_failed_search_stays_unknown(self, _):
        review = public_funding_search({"title": "Example"}, "fake-key")
        self.assertEqual(review["outcome"], "unknown")


if __name__ == "__main__":
    unittest.main()
