from unittest import TestCase
from unittest.mock import patch

from bs4 import BeautifulSoup

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

    def test_mentions_negation_and_current_venture_do_not_count(self):
        notes = ["Alex Doe works with Goldman Sachs.", "Alex Doe's mentor worked at Goldman Sachs.",
                 "Alex Doe never worked at Goldman Sachs.", "Alex Doe previously founded Alpha.",
                 "Someone worked at Goldman Sachs alongside Alex Doe."]
        self.assertEqual(founder_history("Alpha", ["Alex Doe"], notes, BIO), [])

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
