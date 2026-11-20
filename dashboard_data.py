"""JSON view adapter and exports for the First Trace dashboard."""
import csv
import io
import json
from datetime import date
from pathlib import Path

from discovery_pipeline import campus_record
from emergence import rank_candidates
from pre_vc import annotate
from founder_fit import evaluate
from engine import load_research_snapshot

ROOT = Path(__file__).resolve().parent
FUNDING_LABELS = {
    "funded": "Funding round reported",
    "no_funding_found": "No public round found in scoped review",
    "unknown": "Unknown · verification required",
}
CSV_FIELDS = ("name", "sector", "location", "origin", "score", "evidence_confidence",
              "lead_status", "funding_status", "funding_label", "source_url", "project_url",
              "earliest_public_date", "shortlisted", "mode", "public_trace_age",
              "source_urls", "founder_evidence", "timeline", "claims", "funding_review",
              "early_signal_score", "founder_venture_fit", "pre_vc")


def load_demo_run():
    rows = [campus_record(row) for row in load_research_snapshot(ROOT / "data/research_snapshot.json")]
    return rank_candidates(rows, limit=10, mode="research_snapshot")


def public_trace_age(trace_date, run_date):
    """Measure the age of a public trace using the run date as the reference."""
    if not trace_date or not run_date:
        return "No dated public trace"
    if len(trace_date) == 4 and trace_date.isdecimal():
        return f"Year-only evidence ({trace_date})"
    try:
        observed = date.fromisoformat(trace_date[:10])
        as_of = date.fromisoformat(run_date[:10])
    except ValueError:
        return "Public trace age unavailable"
    if observed > as_of:
        return "Public trace age unavailable"
    months = (as_of.year - observed.year) * 12 + as_of.month - observed.month
    months -= as_of.day < observed.day
    if not months:
        return "Less than one month since earliest public trace"
    unit = "month" if months == 1 else "months"
    return f"{months} {unit} since earliest public trace"


def dashboard_rows(run, *, shortlist_only=False):
    """Map the shared payload to the UI without recalculating rank or eligibility."""
    selected = {row["id"] for row in run["shortlist"]}
    rows = run["shortlist"] if shortlist_only else run.get("candidates", run["shortlist"])
    result = []
    for row in rows:
        funding = row.get("funding") or {}
        status = funding.get("status", "unknown")
        location = row.get("location") or {}
        founders = row.get("founders", [])
        earliest = row.get("earliest_verified_public_signal") or {}
        is_shortlisted = row["id"] in selected
        fit = row.get("founder_venture_fit")
        if fit is None:
            # Historical dossiers retain their original as-of date.
            stamp = run.get("generated_at")
            fit = evaluate([row], date.fromisoformat(stamp[:10]) if stamp else date.min)
        result.append({
            **row,
            "name": row["title"], "sector": row.get("sector") or "Unclassified",
            "origin": row.get("source") or "Unknown source",
            "location": location.get("country") or "Needs verification",
            "location_evidence": location,
            "team": " · ".join(person["name"] for person in founders) or row.get("team", ""),
            "founder_identified": bool(founders or row.get("team")),
            "score": row["founder_emergence_score"],
            "early_signal_score": row["founder_emergence_score"], "founder_venture_fit": fit,
            "score_components": row.get("emergence_dimensions", {}),
            "funding_status": status,
            "funding_label": FUNDING_LABELS.get(status, FUNDING_LABELS["unknown"]),
            "project_url": row.get("official_website") or row.get("github_url") or row.get("source_url"),
            "earliest_public_date": earliest.get("date"),
            "public_trace_age": public_trace_age(earliest.get("date"), run.get("generated_at")),
            "shortlisted": is_shortlisted,
            "lead_status": "Shortlisted" if is_shortlisted else "Additional candidate",
            "mode": run.get("mode", "research_snapshot"),
        })
    return annotate(result)


def export_json(run, rows):
    included = {row["id"]: row["pre_vc"] for row in rows}
    return json.dumps({
        **run,
        "presentation_ids": [r["id"] for r in rows if r["pre_vc"]["status"] == "present"],
        "candidates": [{**row, "pre_vc": included[row["id"]]} for row in run.get("candidates", run["shortlist"]) if row["id"] in included],
        "shortlist": [{**row, "pre_vc": included[row["id"]]} for row in run["shortlist"] if row["id"] in included],
        "manual_review": [key for key in run.get("manual_review", []) if key in included],
    }, ensure_ascii=False, indent=2)


def export_csv(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        values = {key: row.get(key, "") for key in CSV_FIELDS}
        for column, key in (("source_urls", "sources"), ("founder_evidence", "founders"),
                            ("timeline", "timeline"), ("claims", "claims"), ("funding_review", "funding"),
                            ("founder_venture_fit", "founder_venture_fit"), ("pre_vc", "pre_vc")):
            values[column] = json.dumps(row.get(key), ensure_ascii=False)
        for key, value in values.items():
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                values[key] = "'" + value
        writer.writerow(values)
    return output.getvalue()
