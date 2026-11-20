from datetime import date
from unittest import TestCase

from dashboard_data import dashboard_rows
from emergence import rank_candidates
from founder_fit import assessment, evaluate


SOURCE = "https://example.org/"


def project(slug, criteria, country="Germany", *, later_stage=False):
    url = SOURCE + slug
    return {
        "id": slug, "title": slug, "source_url": url, "project_url": url,
        "location": {"country": country, "confidence": "registry", "source_url": url},
        "claims": [{"type": "commercialization", "status": "hypothesis", "source_url": url, "text": "Early pilot"}],
        "fit_evidence": [{"criterion": criterion, "status": "verified", "subject": "Founder Name",
                          "source_url": url, "text": f"Evidence for {criterion}"} for criterion in criteria],
        "funding_status": "seed_stage_reported" if later_stage else "unknown",
    }


class EvaluationTests(TestCase):
    def test_team_evidence_counts_for_sixty_percent_and_missing_criteria_stay_visible(self):
        team_led = project("team-led", ["domain_expertise", "built_technology", "problem_significance"])
        project_led = project("project-led", ["domain_expertise", "technical_feasibility", "customer_validation"])
        fit = evaluate([team_led], date(2026, 11, 20))
        self.assertEqual(fit["score"], 30)
        self.assertTrue(fit["assessment"].startswith("Provisional"))
        self.assertIn("research_contribution", fit["founder"]["missing"])
        self.assertEqual(evaluate([project_led], date(2026, 11, 20))["score"], 28)

    def test_unknown_or_conflicted_axis_leaves_grade_pending(self):
        a = {"score": 80, "conflicts": [], "missing": []}
        b = {"score": None, "conflicts": [], "missing": ["customer_validation"]}
        self.assertIsNone(assessment(a, b)[0])
        self.assertIsNone(assessment(a, {**a, "conflicts": ["customer_validation"]})[0])
        self.assertEqual(assessment(a, {"score": 0, "conflicts": [], "missing": []})[0], 48)

    def test_engine_and_dashboard_rank_consistently_and_preserve_eligibility(self):
        first = project("team-led", ["domain_expertise", "built_technology", "problem_significance"])
        second = project("project-led", ["domain_expertise", "technical_feasibility", "customer_validation"])
        pending = project("pending", ["domain_expertise"])
        abroad = project("other-europe", ["domain_expertise", "technical_feasibility"], "Netherlands")
        funded = project("later", ["domain_expertise", "built_technology", "technical_feasibility",
                                  "customer_validation"], later_stage=True)
        run = rank_candidates([second, abroad, first, pending, funded], limit=10)
        self.assertEqual([x["id"] for x in run["shortlist"]],
                         ["team-led", "project-led", "pending", "other-europe"])
        self.assertEqual([x["id"] for x in dashboard_rows(run)], [x["id"] for x in run["candidates"]])
        self.assertTrue(all("founder_venture_fit" not in x for x in run["candidates"]))
