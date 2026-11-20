import copy
from datetime import date, datetime
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import json

import footprint
import readiness
import scout
import web
import server
import sources
from history import record_scan
from sources import CompetitionParser, FinalistParser


def candidate(name, **extra):
    return {"name": name, "tags": ["software"], "noise": False, **extra}


class PipelineTests(unittest.TestCase):
    def test_competition_uses_first_published_date_and_only_roster_rows(self):
        parser = CompetitionParser()
        parser.feed("""
          <time itemprop="datePublished">02.03.2026</time>
          <h3><strong>Digitale Infrastruktur, KI und Software</strong></h3>
          <ul><li><strong>Example (München)</strong> – Product</li></ul>
          <h3>Next steps</h3><ul><li><strong>Other (München)</strong></li></ul>
          <time itemprop="datePublished">02. März 2026</time>
        """)
        self.assertEqual(len(parser.projects), 1)
        self.assertEqual(parser.projects[0]["location"], "München")
        self.assertEqual(datetime.strptime("".join(parser.publication), "%d.%m.%Y").date().isoformat(), "2026-03-02")

    def test_name_collisions_require_a_verified_alias(self):
        with patch.object(scout, "campus_projects", return_value=[candidate("Example")]), \
                patch.object(scout, "competition_projects", return_value=[candidate("Example", published="2026-03-02")]):
            unlinked, _, _ = scout.collect_projects({})
            linked, _, _ = scout.collect_projects({
                "competition:example": {"id": "campus:example", "url": "https://example.com/verification"}
            })
        self.assertEqual(len(unlinked), 2)
        self.assertEqual(len(linked), 1)
        self.assertEqual(len(linked["campus:example"]["traces"]), 2)
        leads = scout.build_inbox({
            "projects": list(unlinked.values()),
            "releases": {"Example": [{"date": "2026-03-02"}]},
        }, {}, {})
        by_id = {lead["id"]: lead for lead in leads}
        self.assertEqual(len(by_id["campus:example"]["releases"]), 1)
        self.assertEqual(by_id["competition:example"]["releases"], [])

    def test_one_unavailable_source_keeps_the_other_source_visible(self):
        with patch.object(scout, "campus_projects", side_effect=OSError("Unavailable")), \
                patch.object(scout, "competition_projects", return_value=[candidate("Example")]):
            projects, statuses, errors = scout.collect_projects({})
        self.assertIn("competition:example", projects)
        self.assertEqual(statuses["campus"]["state"], "failed")
        self.assertIn("UnternehmerTUM", errors[0])

    def test_old_snapshot_still_works_and_cutoff_excludes_undated_evidence(self):
        snapshot = scout.prepare_replay({
            "projects": [candidate("Example")],
            "releases": {"Example": [
                {"date": "2025-01-01", "title": "Old release", "url": "https://example.com/old"},
                {"date": "2026-01-01", "title": "New release", "url": "https://example.com/new"},
            ]},
        })
        cutoff = scout.apply_cutoff(snapshot, "2025-12-31")
        leads = scout.build_inbox(cutoff, {}, {})
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]["traces"], [])
        self.assertEqual(leads[0]["tags"], [])
        self.assertEqual([release["title"] for release in leads[0]["releases"]], ["Old release"])

    def test_repeat_scans_flag_new_evidence_once(self):
        first = {
            "observed_at": "2026-11-20T12:00:00+00:00", "source_status": {},
            "projects": [candidate("Example", id="campus:example", traces=[])],
            "releases": {},
        }
        second = copy.deepcopy(first)
        second["observed_at"] = "2026-11-20T13:00:00+00:00"
        second["releases"]["Example"] = [
            {"date": "2026-11-19", "url": "https://example.com/release"},
        ]
        third = copy.deepcopy(second)
        third["observed_at"] = "2026-11-20T14:00:00+00:00"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "history.sqlite"
            record_scan(path, first, {})
            record_scan(path, second, {})
            record_scan(path, third, {})
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM observations").fetchone()[0], 2)
        self.assertEqual(first["projects"][0]["changes"], [])
        self.assertEqual(second["projects"][0]["changes"], ["release"])
        self.assertEqual(third["projects"][0]["changes"], [])
        self.assertEqual(third["projects"][0]["first_seen"], first["observed_at"])


FINALE = """
  <time itemprop="datePublished">29.07.2026</time>
  <h2 class="section-headline">Das sind die acht Startups im Finale:</h2>
  <h2>Venedy aus München: KI findet Schwachstellen in digitalen Schnittstellen</h2><p>Venedy prüft APIs.</p>
  <h2>Soul of Concrete aus Nördlingen in Bayerisch-Schwaben: Carbon statt Stahl</h2><p>Bewehrung aus Carbon.</p>
"""
WINNERS = """
  <time itemprop="datePublished">29.07.2026</time>
  <h2>Platz 1: Venedy schützt Schnittstellen</h2>
  <h2>1. Platz: Helmit aus Höhenkirchen-Siegertsbrunn bei München</h2><p>Helmit entwickelt eine KI-gestützte Software.</p>
  <h2>Weitere nominierte Startups der Phase 2:</h2>
"""


class CompetitionProgressTests(unittest.TestCase):
    def test_finalist_and_placed_formats(self):
        finale = FinalistParser()
        finale.feed(FINALE)
        rows = finale.finalists()
        self.assertEqual([row["name"] for row in rows], ["Venedy", "Soul of Concrete"])
        self.assertEqual(rows[0]["tags"], ["Digital tech"])
        self.assertEqual(rows[1]["location"], "Nördlingen")
        winners = FinalistParser()
        winners.feed(WINNERS)
        self.assertEqual(winners.winners(), [(1, "Venedy schützt Schnittstellen")])
        placed = winners.placed()
        self.assertEqual((placed[0]["name"], placed[0]["location"], placed[0]["place"]), ("Helmit", "Höhenkirchen-Siegertsbrunn", 1))

    def test_rosters_join_within_organizer_and_rank_progression(self):
        nominees = """<time itemprop="datePublished">02.03.2026</time>
          <h3>Digitale Infrastruktur, KI und Software</h3><ul><li><strong>VENEDY (München)</strong></li></ul>"""
        pages = {
            sources.COMPETITION_INDEX: '<a href="/startupdate/acht-startups-im-finale-des-muenchner-businessplan-wettbewerbs-2026">x</a>'
                                       '<a href="/startupdate/bayerisches-finale-female-founders-contest-2026">y</a>',
            sources.COMPETITION: nominees,
            sources.BAYSTARTUP + "/startupdate/acht-startups-im-finale-des-muenchner-businessplan-wettbewerbs-2026": FINALE,
        }
        with patch.object(sources, "fetch", side_effect=pages.__getitem__):
            rows = sources.competition_projects([])
        self.assertEqual(rows[0]["title"], "Munich BPW · Phase 1 nomination")
        with patch.object(scout, "campus_projects", return_value=[]), \
                patch.object(scout, "competition_projects", return_value=rows):
            projects, status, _ = scout.collect_projects({})
        self.assertEqual(status["competition"]["pages"], 2)
        venedy = projects["competition:venedy"]
        self.assertEqual([trace["title"] for trace in venedy["traces"]],
                         ["Munich BPW · Phase 1 nomination", "Munich BPW · Finalist"])
        leads = scout.build_inbox({"projects": list(projects.values()), "releases": {}}, {}, {})
        self.assertEqual(leads[0]["name"], "VENEDY")
        self.assertEqual(leads[0]["momentum"], "Finalist")


class FootprintTests(unittest.TestCase):
    def test_only_analyst_domains_and_exact_hosts_count(self):
        responses = {
            "web.archive.org": json.dumps([["timestamp", "original"], ["20240917073037", "http://www.example.com/"]]),
            "hn.algolia.com": json.dumps({"hits": [
                {"objectID": "2", "url": "https://notexample.com/x", "created_at": "2020-01-01T00:00:00Z", "title": "Other"},
                {"objectID": "3", "url": "https://app.example.com/", "created_at": "2025-05-01T00:00:00Z", "title": "Show HN"},
            ]}),
        }
        fake = lambda url: next(body for host, body in responses.items() if host in url)
        with patch.object(footprint, "fetch", side_effect=fake):
            found, status = footprint.collect({"campus:a": {"domain": "example.com"}, "campus:b": {}}, [])
        self.assertEqual(list(found), ["campus:a"])
        archived, post = found["campus:a"]
        self.assertEqual((archived["date"], archived["date_type"]), ("2024-09-17", "archived"))
        self.assertEqual(post["url"], "https://news.ycombinator.com/item?id=3")
        self.assertEqual(status, {"state": "fresh", "count": 1})

    def test_cutoff_drops_later_footprint(self):
        snapshot = scout.prepare_replay({
            "projects": [candidate("Example", id="campus:example", traces=[
                {"source": "UnternehmerTUM", "url": "https://example.com", "title": "Listing", "date": "2025-01-01"}])],
            "releases": {},
            "footprints": {"campus:example": [
                {"source": "Internet Archive", "title": "x", "url": "https://web.archive.org/web/1/x", "date": "2026-01-01", "date_type": "archived"}]},
        })
        self.assertEqual(scout.apply_cutoff(snapshot, "2025-12-31")["footprints"]["campus:example"], [])


class ReleaseCacheTests(unittest.TestCase):
    def test_rate_limited_repository_keeps_last_fetched_releases(self):
        release = {"title": "repo · v1", "url": "https://github.com/org/repo/releases/tag/v1", "date": "2025-04-19"}
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "cache.json"
            cache.write_text(json.dumps({"repo": {"fetched_at": "2026-11-20T00:00:00", "releases": [release]}}))
            with patch.object(scout, "RELEASE_CACHE", cache), \
                    patch.object(scout, "collect_projects", return_value=(
                        {"campus:example": {"id": "campus:example", "name": "Example", "traces": []}}, {}, [])), \
                    patch.object(scout, "repository_releases", side_effect=OSError("HTTP Error 403: rate limit exceeded")), \
                    patch.object(scout.footprint, "collect", return_value=({}, {"state": "fresh", "count": 0})), \
                    patch.object(scout.web, "collect", return_value=({}, {"state": "fresh", "count": 0})):
                snapshot = scout.discover({"Example": {"repositories": ["org/repo"]}}, {})
        self.assertEqual(snapshot["releases"]["Example"], [release])
        self.assertEqual(snapshot["source_status"]["github"], {"state": "partial", "count": 0, "cached": 1})
        self.assertIn("Showing 1 releases fetched 2026-11-20", snapshot["errors"][0])


IMPRESSUM = """Impressum
Anbieter
Bevelites GmbH
Schleißheimer Str. 188
80797 München, Germany
Handelsregister: District Court of Munich, HRB 303590
Verantwortlich nach § 55 Abs. 2 RStV
Razvan-Ion Radulescu
Managing Director"""
PRE_COMPANY = """Impressum
Angaben gemäß § 5 DDG
Venture-Team „CAELIA Health“ am Fraunhofer EMFT
Hansastraße 27d
80686 München
Deutschland"""


class CompanyResearchTests(unittest.TestCase):
    def test_legal_notice_gives_entity_register_and_directors(self):
        facts = web.parse_legal(IMPRESSUM, "Bevel")
        self.assertEqual(facts["entity"], "Bevelites GmbH")
        self.assertFalse(facts["brand_match"])
        self.assertEqual((facts["register"], facts["court"], facts["address"]), ("HRB 303590", "Munich", "80797 München"))
        self.assertEqual(facts["directors"], ["Razvan-Ion Radulescu"])
        self.assertTrue(facts["german"])
        self.assertEqual(facts["stage"], "Incorporated · GmbH")

    def test_pre_company_team_and_identity_rule(self):
        facts = web.parse_legal(PRE_COMPANY, "CAELIA Health")
        self.assertEqual(facts["stage"], "Being incorporated")
        self.assertEqual(web.identity(facts, PRE_COMPANY, "CAELIA Health", "München", False),
                         "Name, city and German address match the legal notice")
        # Same name, different city: never accepted automatically.
        self.assertIsNone(web.identity(facts, PRE_COMPANY, "CAELIA Health", "Hamburg", False))
        self.assertIsNone(web.identity(facts, PRE_COMPANY, "Other Name", "München", False))

    def test_signals_quote_the_site_and_ignore_generic_backing(self):
        found = {row["key"] for row in web.site_signals(
            "Join our pilot program. Backed by deep-tech and venture-building ecosystems. For investors: get in touch.")}
        self.assertEqual(found, {"pilot", "raising"})

    def test_readiness_is_sourced_and_window_closes_on_named_investors(self):
        lead = {
            "name": "Example", "tags": ["Digital tech"], "fit": "Adjacent", "momentum": "Finalist", "hold": None,
            "assessment": {}, "review": {}, "releases": [], "footprint": [], "location": "München",
            "traces": [{"source": "BayStartUP", "title": "Munich BPW · Finalist", "url": "https://example.com/r", "date": "2026-07-29"}],
            "web": {"url": "https://example.com", "legal_url": "https://example.com/impressum",
                    "legal": web.parse_legal(IMPRESSUM.replace("Bevelites", "Example"), "Example"),
                    "signals": [{"key": "pilot", "label": "Pilot program", "quote": "…pilot…"}]},
        }
        result = readiness.assess(lead, date(2026, 11, 20))
        self.assertEqual(result["score"], 100)
        self.assertTrue(all(row["detail"] for row in result["checks"]))
        self.assertEqual(result["window"]["zone"], 1)
        lead["web"]["signals"].append({"key": "investors", "label": "Names investors", "quote": "…backed by X Ventures…"})
        closing = readiness.assess(lead, date(2026, 11, 20))
        self.assertEqual(closing["window"]["label"], "Window closing")
        self.assertEqual(closing["score"], 90)


class DeskTests(unittest.TestCase):
    def test_scan_requires_header_and_runs_once(self):
        with tempfile.TemporaryDirectory() as temp:
            desk = server.Desk(Path(temp) / "history.sqlite3")
            started = []
            with patch.object(server.threading, "Thread") as thread:
                thread.return_value.start.side_effect = lambda: started.append(True)
                self.assertTrue(desk.start_scan())
                self.assertFalse(desk.start_scan())
            self.assertEqual(len(started), 1)
            self.assertTrue(desk.status()["scanning"])

    def test_first_start_shows_labeled_demo_and_scans_in_background(self):
        with tempfile.TemporaryDirectory() as temp:
            desk = server.Desk(Path(temp) / "history.sqlite3")
            with patch.object(desk, "start_scan") as start:
                desk.prepare()
            start.assert_called_once()
            page = desk.page.read_text(encoding="utf-8")
            self.assertIn('"mode": "Snapshot replay"', page)
            self.assertIn('"server": true', page)


if __name__ == "__main__":
    unittest.main()
