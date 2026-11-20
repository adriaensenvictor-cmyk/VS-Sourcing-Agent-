import unittest

from emergence import activity, combine, score_candidate
from qualification import merge_candidates

URL = "https://example.org/startup"


def row(**fields):
    return {"id": "x", "title": "Sample", "source_url": URL, **fields}


class EmergenceTests(unittest.TestCase):
    def test_verified_commercialization_outweighs_hypotheses(self):
        cue = {"type": "pilot", "status": "hypothesis"}
        verified = {**cue, "status": "verified"}
        tentative = score_candidate([cue], [], [], None, "unknown", [URL])
        confirmed = score_candidate([verified], [], [], None, "unknown", [URL])
        self.assertGreater(confirmed["commercialization"], tentative["commercialization"])
        self.assertGreater(confirmed["market_potential"], tentative["market_potential"])
        self.assertEqual(confirmed["early_stage"], 0)
        self.assertLessEqual(sum(confirmed.values()), 100)

    def test_funded_and_unknown_are_distinct_and_filters_are_separate(self):
        candidate = row(funding={"status": "funded"})
        self.assertIn("funded_or_later_stage", combine([candidate])["shortlist_exclusions"])
        self.assertEqual(combine([row()])["funding"]["status"], "unknown")
        self.assertNotIn("funded_or_later_stage", combine([row()])["shortlist_exclusions"])

    def test_uncertain_repo_creation_does_not_override_public_demo(self):
        events = [{"date": "2024-04-10", "url": URL, "label": "Created", "public_signal": False},
                  {"date": "2025-02-20", "url": URL, "label": "Public demo"}]
        self.assertEqual(combine([row(timeline=events)])["earliest_verified_public_signal"], events[1])

    def test_activity_requires_two_people_across_multiple_weeks(self):
        def commit(login, day, kind="User"):
            return {"author": {"login": login, "type": kind},
                    "commit": {"committer": {"date": f"2026-11-{day:02}T00:00:00Z"}}}

        sample = [commit("dev1", 1), commit("dev1", 10), commit("dev2", 2),
                  commit("robot", 2, "Bot"), commit("robot", 10, "Bot")]
        self.assertFalse(activity(sample)["sustained_collaboration"])
        self.assertTrue(activity(sample + [commit("dev2", 10)])["sustained_collaboration"])

    def test_names_do_not_merge_without_shared_identity(self):
        campus = row(project_url="https://a.example/project")
        hacker_news = row(project_url="https://b.example/project")
        code = row(links={"github": ["https://github.com/team/product"]})
        self.assertEqual(len(merge_candidates([campus, hacker_news, code])), 3)
        campus["links"] = {"github": ["https://github.com/team/product/releases"]}
        self.assertEqual(len(merge_candidates([campus, hacker_news, code])), 2)


if __name__ == "__main__":
    unittest.main()
