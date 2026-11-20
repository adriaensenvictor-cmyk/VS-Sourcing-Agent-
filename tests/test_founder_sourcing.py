import unittest
from unittest.mock import patch

from founder_sourcing import candidate, discover, previous_projects


def post(uid="10", body="I previously worked at Jane Street. We built a tool.", **fields):
    return {"objectID": uid, "story_text": body, "title": "Show HN: Tool", "author": "builder",
            "created_at": "2026-03-09T12:00:00Z", "url": "https://example.org/", **fields}


class FounderSourcingTests(unittest.TestCase):
    def test_employment_requires_an_explicit_first_person_statement(self):
        self.assertIsNone(candidate(post(body="We built this with OpenAI. Our customer is Goldman Sachs.")))
        row = candidate(post())
        self.assertEqual(row["career_evidence"][0]["name"], "Jane Street")
        self.assertEqual(row["career_evidence"][0]["status"], "author_self_report")
        self.assertIsNone(row["location"]["country"])
        self.assertNotIn("founders", row)

    def test_geography_is_about_the_team(self):
        self.assertIsNone(candidate(post(body="I live in Paris. I built a developer tool.")))
        row = candidate(post(body="We are headquartered in Paris. We built a developer tool."))
        self.assertEqual(row["location"]["country"], "France")
        conflict = candidate(post(body="I left Anthropic. We are based in Paris. We are based in London. We built a tool."))
        self.assertIsNone(conflict["location"]["country"])

    def test_history_requires_same_author_earlier_date_and_distinct_project(self):
        row = candidate(post())
        earlier = post("8", body="I built this.", title="Show HN: Prior", url="https://previous.example/",
                       created_at="2025-04-01T00:00:00Z")
        invalid = [dict(earlier, author="different"), dict(earlier, created_at=None),
                   dict(earlier, created_at="2027-01-01T00:00:00Z"),
                   dict(earlier, url="https://www.example.org"), dict(earlier, story_text="Someone built this."),
                   dict(earlier, title=row["title"])]
        with patch("founder_sourcing.search", return_value=[*invalid, earlier, earlier]) as search:
            projects = previous_projects(row)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["source_url"], "https://news.ycombinator.com/item?id=8")
        self.assertEqual(search.call_args.kwargs["tags"], "show_hn,author_builder")

    def test_duplicate_hits_and_partial_history(self):
        with (patch("founder_sourcing.QUERIES", ("Paris", "Jane Street")),
              patch("founder_sourcing.search", return_value=[post()]),
              patch("founder_sourcing.previous_projects", side_effect=OSError)):
            warnings = []
            rows = discover(warnings)
        self.assertEqual(len(rows), 1)
        self.assertTrue(warnings)
        self.assertEqual(rows[0]["career_evidence"][0]["subject"], "builder")

    def test_all_queries_unavailable(self):
        with patch("founder_sourcing.QUERIES", ("Paris",)), patch("founder_sourcing.search", side_effect=OSError):
            with self.assertRaises(OSError):
                discover([])
