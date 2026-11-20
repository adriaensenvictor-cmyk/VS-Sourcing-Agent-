from base64 import b64encode
from unittest import TestCase
from unittest.mock import patch

from bs4 import BeautifulSoup

from emergence import github_record
from founder_signals import founder_history
from programmes import scan_imec, scan_unternehmertum


BIO = "https://incubator.example.org/teams/alpha"


class FounderSignalsTests(TestCase):
    def test_public_named_history_includes_employer_and_a_previous_startup(self):
        notes = ["Alex Doe previously worked at Jane Street.",
                 "Alex Doe founded and sold Skylark."]
        signals = founder_history("Alpha", ["Alex Doe"], notes, BIO)
        self.assertEqual({s["reference"] for s in signals}, {"Jane Street", "Skylark"})
        self.assertTrue(all(s["source_url"] == BIO and s["subject"] == "Alex Doe" for s in signals))

    def test_new_employers_and_aliases_match_only_attributed_past_jobs(self):
        notes = [
            "Alex Doe previously worked at Delivery Hero.",
            "Alex Doe formerly at TransferWise.",
            "Alex Doe, a former DeepMind researcher.",
            "Alex Doe worked at Siemens Energy.",
            "Alex Doe a travaillé chez Robert Bosch.",
            "Alex Doe worked at Block Inc.",
            "Alex Doe worked with PayPal.",
            "Alex Doe worked at King's College.",
        ]
        signals = founder_history("Alpha", ["Alex Doe"], notes, BIO)
        self.assertEqual({s["reference"] for s in signals},
                         {"Delivery Hero", "Wise", "Google DeepMind", "Siemens Energy", "Bosch", "Block"})

    def test_mentions_negation_and_current_venture_do_not_count(self):
        notes = ["Alex Doe works with Goldman Sachs.", "Alex Doe's mentor worked at Goldman Sachs.",
                 "Alex Doe never worked at Goldman Sachs.", "Alex Doe previously founded Alpha.",
                 "Someone worked at Goldman Sachs alongside Alex Doe."]
        self.assertEqual(founder_history("Alpha", ["Alex Doe"], notes, BIO), [])

    def test_readme_history_attaches_only_to_its_named_founder(self):
        readme = b"Founder: Alex Doe\nAlex Doe worked at Zalando.\nSomeone else worked at Wise."
        document = {"encoding": "base64", "content": b64encode(readme).decode(),
                    "html_url": "https://github.com/example/alpha/blob/main/README.md"}
        repo = {"full_name": "example/alpha", "name": "Alpha", "html_url": "https://github.com/example/alpha",
                "created_at": "2026-11-19T00:00:00Z"}
        with patch("emergence.github_api", side_effect=[document, [], []]):
            row = github_record(repo, "2026-10-01")
        self.assertEqual([e["reference"] for e in row["evidence"]], ["Zalando"])
        self.assertEqual(row["evidence"][0]["source_url"], document["html_url"])

    def test_incubator_listing_does_not_infer_company_location_or_equity(self):
        html = "<utum-tile><h2>Alpha</h2><p>Industrial software</p></utum-tile>"
        with patch("programmes.get_html", return_value=BeautifulSoup(html, "html.parser")):
            row = scan_unternehmertum([])[0]
        self.assertIsNone(row["location"]["country"])
        self.assertNotIn("funding_status", row)
        self.assertNotIn("milestones", row)

    def test_imec_filters_portfolio_year_and_retains_reported_country(self):
        html = '''<div class="portfolio-item"><h3 fs-list-field="name">Sample</h3>
                   <p fs-list-field="desc">Industrial analytics</p>
                   <p fs-list-field="year">2026</p><p fs-list-field="country">Belgium</p>
                   <a href="/portfolio/sample"></a></div>'''
        with patch("programmes.get_html", return_value=BeautifulSoup(html, "html.parser")):
            from datetime import datetime
            with patch("programmes.datetime") as clock:
                clock.now.return_value = datetime(2026, 11, 20)
                row = scan_imec([])[0]
        self.assertEqual(row["location"]["country"], "Belgium")
        self.assertEqual(row["cohort"], "Programme portfolio year 2026")
        self.assertNotIn("milestones", row)
