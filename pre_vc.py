"""Dated, source-backed gate for projects presented to an investor."""
import calendar
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

STAGES = {"prelaunch", "first_prototype", "first_pilot", "first_customers"}
LABEL = "Early stage · team reports no prior VC investment"


def registry():
    return json.loads(Path(__file__).with_name("research").joinpath("pre_vc_reviews.json").read_text())


def parsed_date(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


def host(url):
    try:
        parts = urlsplit(url or "")
        if parts.scheme in ("http", "https") and not parts.username:
            return (parts.hostname or "").lower().removeprefix("www.")
    except (TypeError, ValueError):
        pass
    return ""


def evidence(item, as_of, max_days):
    stamp = parsed_date(item.get("date"))
    return bool(stamp and 0 <= (as_of - stamp).days <= max_days and host(item.get("url"))
                and str(item.get("summary") or "").strip())


def assess(row, reviews, as_of):
    funding = row.get("funding") or {}
    labels = {row.get("funding_status"), funding.get("status")}
    labels.update(r.get("reported_as") for r in funding.get("reviews", []))
    fit_age = (row.get("founder_venture_fit") or {}).get("three_year_eligibility") or {}
    formation = parsed_date(fit_age.get("formation_date") or row.get("formation_date"))
    age_limit = as_of.year - 3
    cutoff = date(age_limit, as_of.month, min(as_of.day, calendar.monthrange(age_limit, as_of.month)[1]))
    result = {"as_of": as_of.isoformat(), "status": "watch", "reasons": [], "evidence": {}}
    hard_exclusions = set(row.get("shortlist_exclusions", []))
    if (labels & {"funded", "vc_round_reported", "seed_stage_reported"}
            or funding.get("rounds") or "funded_or_later_stage" in hard_exclusions):
        return {**result, "status": "excluded", "reasons": ["Prior funding or later stage reported"]}
    if fit_age.get("status") == "older_than_three_years" or (formation and formation < cutoff):
        return {**result, "status": "excluded", "reasons": ["Company exceeds the three-year mandate"]}
    if row.get("red_flags") or hard_exclusions or "pre_seed_financing_reported" in labels:
        result["reasons"].append("Resolve existing diligence flags or financing signals")
    if formation and formation > as_of:
        result["reasons"].append("Conflicting company formation date")

    review = reviews.get(row["id"], {})
    urls = {row.get("source_url"), row.get("profile_url"), row.get("project_url"), row.get("official_website")}
    urls.update(s.get("url") for s in row.get("signals", []))
    if not review.get("identity_url") or review["identity_url"] not in urls:
        review = {}
    stage = review.get("stage", {})
    declaration = review.get("declaration", {})
    check = review.get("cross_check", {})
    if stage.get("kind") in STAGES and evidence(stage, as_of, 180):
        result["evidence"]["stage"] = stage
    else:
        result["reasons"].append("Verify a prelaunch, first prototype, pilot or customer signal within 180 days")
    if (declaration.get("kind") == "no_prior_vc" and declaration.get("issuer") in {"founder", "company"}
            and evidence(declaration, as_of, 90)):
        result["evidence"]["declaration"] = declaration
    else:
        result["reasons"].append("Obtain a dated founder or company statement covering all prior VC investment")
    if (check.get("kind") in {"prior_vc", "later_stage"} and host(check.get("url")) and parsed_date(check.get("date"))
            and parsed_date(check["date"]) <= as_of and check.get("summary")):
        return {**result, "status": "excluded", "reasons": ["Contrary financing or later-stage evidence"],
                "evidence": {**result["evidence"], "cross_check": check}}
    if (check.get("kind") == "no_public_vc_found" and check.get("independent") is True and evidence(check, as_of, 30)
            and host(check["url"]) != host(declaration.get("url"))
            and (check.get("date") or "") >= (declaration.get("date") or "")):
        result["evidence"]["cross_check"] = check
    else:
        result["reasons"].append("Complete an independent financing check after the declaration, within 30 days")
    if not result["reasons"]:
        result["status"] = "present"
    return result


def annotate(rows, as_of=None):
    reviews = registry()
    today = as_of or date.today()
    return [{**row, "pre_vc": assess(row, reviews, today)} for row in rows]
