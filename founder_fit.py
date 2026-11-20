"""Evidence-backed diligence rubric. This layer never changes the discovery ranking."""
import calendar
import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

# Each criterion can contribute its budget once across all sources and team members.
FOUNDER = {"domain_expertise": 20, "relevant_achievement": 15, "built_technology": 20,
           "operating_experience": 20, "complementary_team": 10, "research_contribution": 15}
VENTURE = {"problem_significance": 15, "differentiation": 15, "market_opportunity": 15,
           "technical_feasibility": 20, "commercial_path": 15, "customer_validation": 20}
FOUNDER_WEIGHT = 60
VENTURE_WEIGHT = 40
FORMATION = {"legal_formation", "unincorporated"}
CLAIMS = {"domain_experience": "domain_expertise", "prototype": "technical_feasibility", "launch": "commercial_path",
          "commercialization": "commercial_path", "pilot": "customer_validation",
          "customer_discovery": "problem_significance"}
AGE_LABELS = {"within_three_years": "Within three years", "older_than_three_years": "Older than three years",
              "unknown": "Unknown / requires verification"}


@lru_cache(maxsize=1)
def reviewed_sources():
    path = Path(__file__).with_name("research") / "fit_evidence.json"
    return json.loads(path.read_text(encoding="utf-8"))


def public_url(value):
    try:
        url = urlsplit(value or "")
        return url.scheme in {"http", "https"} and bool(url.hostname)
    except (TypeError, ValueError):
        return False


def collect_evidence(records, as_of):
    observations = []
    for record in records:
        urls = [record.get("source_url"), *record.get("source_record_urls", []),
                *record.get("sources", [])]
        for url in dict.fromkeys(filter(None, urls)):
            review = reviewed_sources().get(url.rstrip("/"))
            if review and review["reviewed_on"] <= as_of.isoformat():
                observations.extend({**entry, "status": "verified", "reviewed_on": review["reviewed_on"],
                                     "source_url": entry.get("source_url", url)}
                                    for entry in review["observations"])
        observations.extend(record.get("fit_evidence", []))
        for claim in record.get("claims", []):
            kind = claim.get("type")
            criterion = CLAIMS.get(kind, kind)
            if criterion not in FOUNDER and criterion not in VENTURE and criterion not in FORMATION:
                continue
            observation = {**claim, "criterion": criterion}
            if criterion in FOUNDER and not claim.get("subject"):
                # Attribute only when a verified founder name occurs in the cited claim.
                names = [p["name"] for p in record.get("founders", [])
                         if p.get("source_url") and p.get("name") and
                         p["name"].casefold() in claim.get("text", "").casefold()]
                if names:
                    observation["subject"] = ", ".join(names)
            observations.append(observation)
    facts = {}
    for entry in observations:
        key = entry.get("criterion")
        if key not in FOUNDER and key not in VENTURE and key not in FORMATION:
            continue
        if entry.get("status") != "verified" or not public_url(entry.get("source_url")) or not entry.get("text"):
            continue
        if entry.get("direction", "supports") not in {"supports", "limits"}:
            continue
        if key in FOUNDER and not entry.get("subject"):
            continue
        if entry.get("reviewed_on", "") > as_of.isoformat():
            continue
        fact = {k: entry[k] for k in ("criterion", "text", "source_url", "subject", "date", "reviewed_on") if k in entry}
        fact["direction"] = entry.get("direction", "supports")
        facts[json.dumps(fact, sort_keys=True)] = fact
    return list(facts.values())


def axis(budget, facts):
    score = 0
    strengths, gaps, limitations, conflicts = [], [], [], []
    for criterion, points in budget.items():
        evidence = [fact for fact in facts if fact["criterion"] == criterion]
        directions = {fact["direction"] for fact in evidence}
        if not directions:
            gaps.append(criterion)
        elif len(directions) > 1:
            conflicts.append(criterion)
        elif "supports" in directions:
            strengths.append(criterion)
            score += points
        else:
            limitations.append(criterion)
    return {"score": score if strengths or limitations else None, "strengths": strengths,
            "limitations": limitations, "missing": gaps, "conflicts": conflicts,
            "assessed": len(strengths) + len(limitations), "total": len(budget)}


def weighted_points(axis_result, weight):
    score = axis_result["score"]
    return None if score is None else round(score * weight / 100, 1)


def assessment(founder, venture):
    if founder["conflicts"] or venture["conflicts"]:
        return None, "Conflicting evidence · manual review"
    team_points = weighted_points(founder, FOUNDER_WEIGHT)
    project_points = weighted_points(venture, VENTURE_WEIGHT)
    if team_points is None or project_points is None:
        return None, "Evidence needed on both dimensions"
    score = round(team_points + project_points)
    if any(part["missing"] for part in (founder, venture)):
        return score, "Provisional · based on documented strengths"
    return score, "All criteria reviewed"


def review_priority(country, grade, early_signal):
    """Keep Germany first, then rank evidenced grades before pending assessments."""
    return (country == "Germany", grade is not None, grade if grade is not None else 0, early_signal)


def three_years(facts, as_of, university):
    formation = [f for f in facts if f["criterion"] in FORMATION]
    dates = {f.get("date") for f in formation if f["criterion"] == "legal_formation"}
    unincorporated = [f for f in formation if f["criterion"] == "unincorporated"]
    result = {"status": "unknown", "as_of": as_of.isoformat(), "formation_date": None,
              "reason": "No verified legal formation date", "university_review": university,
              "evidence": formation}
    if any(f["direction"] == "limits" for f in formation) or len(dates) > 1 or (dates and unincorporated):
        return {**result, "reason": "Conflicting company formation evidence"}
    if not dates:
        return {**result, "reason": "Reported unincorporated · review" if unincorporated else result["reason"]}
    try:
        founded = date.fromisoformat(next(iter(dates)))
        if founded > as_of or founded.isoformat() not in dates:
            raise ValueError
    except (TypeError, ValueError):
        return {**result, "reason": "Formation date needs verification"}
    year = founded.year + 3
    anniversary = (year, founded.month, min(founded.day, calendar.monthrange(year, founded.month)[1]))
    within = (as_of.year, as_of.month, as_of.day) <= anniversary
    return {**result, "status": "within_three_years" if within else "older_than_three_years",
            "formation_date": founded.isoformat(), "reason": "Verified legal formation date",
            "university_review": False}


def evaluate(records, as_of):
    facts = collect_evidence(records, as_of)
    founder, venture = axis(FOUNDER, facts), axis(VENTURE, facts)
    score, label = assessment(founder, venture)
    university = any(name in {"TU Berlin", "TUM Venture Labs", "TUM public EXIST-related announcement"}
                     for row in records for name in [row.get("source"), *row.get("source_names", [])])
    coverage = founder["assessed"] + venture["assessed"]
    return {"version": 1, "founder": founder, "venture": venture, "score": score, "assessment": label,
            "coverage": f"{coverage}/12 criteria assessed", "evidence": facts,
            "three_year_eligibility": three_years(facts, as_of, university)}
