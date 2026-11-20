"""JSON view adapter and exports for the First Trace dashboard."""
import csv
import io
import json
from pathlib import Path

from discovery_pipeline import campus_record
from emergence import rank_candidates
from engine import load_research_snapshot

ROOT = Path(__file__).resolve().parent
FUNDING_LABELS = {
    "funded": "Funding round reported",
    "no_funding_found": "No public round found in scoped review",
    "unknown": "Unknown · verification required",
}
CSV_FIELDS = ("name", "sector", "location", "origin", "score", "evidence_confidence",
              "lead_status", "funding_status", "funding_label", "source_url", "project_url",
              "earliest_public_date", "shortlisted", "mode")


def load_demo_run():
    rows = [campus_record(row) for row in load_research_snapshot(ROOT / "data/research_snapshot.json")]
    return rank_candidates(rows, limit=10, mode="research_snapshot")


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
        result.append({
            **row,
            "name": row["title"], "sector": row.get("sector") or "Unclassified",
            "origin": row.get("source") or "Unknown source",
            "location": location.get("country") or "Needs verification",
            "location_evidence": location,
            "team": " · ".join(person["name"] for person in founders) or row.get("team", ""),
            "founder_identified": bool(founders or row.get("team")),
            "score": row["founder_emergence_score"],
            "score_components": row.get("emergence_dimensions", {}),
            "funding_status": status,
            "funding_label": FUNDING_LABELS.get(status, FUNDING_LABELS["unknown"]),
            "project_url": row.get("official_website") or row.get("github_url") or row.get("source_url"),
            "earliest_public_date": earliest.get("date"),
            "shortlisted": is_shortlisted,
            "lead_status": "Shortlisted" if is_shortlisted else "Additional candidate",
            "mode": run.get("mode", "research_snapshot"),
        })
    return result


def export_json(run, rows):
    included = {row["id"] for row in rows}
    return json.dumps({
        **run,
        "candidates": [row for row in run.get("candidates", run["shortlist"]) if row["id"] in included],
        "shortlist": [row for row in run["shortlist"] if row["id"] in included],
        "manual_review": [key for key in run.get("manual_review", []) if key in included],
    }, ensure_ascii=False, indent=2)


def export_csv(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        values = {key: row.get(key, "") for key in CSV_FIELDS}
        for key, value in values.items():
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                values[key] = "'" + value
        writer.writerow(values)
    return output.getvalue()
