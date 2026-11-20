"""SQLite history for local, repeatable sourcing scans."""
from contextlib import closing
import json
import sqlite3

from evidence import releases_for

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY,
    observed_at TEXT NOT NULL,
    source_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    published TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (project_id, kind, evidence_id)
);
"""


def observations(project, releases, assessment, footprint=(), research=None):
    yield "project", project["id"], None
    for trace in project["traces"]:
        yield "trace", trace["url"], trace.get("date")
    for release in releases:
        yield "release", release["url"], release["date"]
    for row in footprint:
        # Archive capture URLs embed a timestamp; key on the source and date type instead.
        yield "footprint", f"{row['source']}:{row['date_type']}:{row['url'] if row['source'] != 'Internet Archive' else ''}", row["date"]
    if research:
        facts = research.get("legal") or {}
        # A change of legal entity, register entry or stage (for example "i.G." dropped) is a new signal.
        yield "legal", json.dumps([facts.get("entity"), facts.get("register"), facts.get("stage")], ensure_ascii=False), None
        for row in research.get("signals", []):
            yield "site", row["key"], None
    for key in ("funding", "product"):
        milestone = assessment.get(key)
        if milestone:
            identity = json.dumps([milestone["label"], milestone["url"]], ensure_ascii=False)
            yield key, identity, milestone.get("date")


def record_scan(path, snapshot, assessments):
    """Record only observed evidence and return changes relative to prior scans."""
    path.parent.mkdir(parents=True, exist_ok=True)
    observed_at = snapshot["observed_at"]
    with closing(sqlite3.connect(path, timeout=10)) as db:
        db.executescript(SCHEMA)
        with db:
            db.execute("BEGIN IMMEDIATE")
            baseline_exists = db.execute("SELECT EXISTS (SELECT 1 FROM scans)").fetchone()[0]
            db.execute(
                "INSERT INTO scans (observed_at, source_status) VALUES (?, ?)",
                (observed_at, json.dumps(snapshot["source_status"])),
            )
            for project in snapshot["projects"]:
                releases = releases_for(project, snapshot["releases"])
                assessment = assessments.get(project["id"], {})
                project["changes"] = []
                footprint = snapshot.get("footprints", {}).get(project["id"], [])
                research = snapshot.get("web", {}).get(project["id"])
                for kind, evidence_id, published in observations(project, releases, assessment, footprint, research):
                    key = (project["id"], kind, evidence_id)
                    inserted = db.execute(
                        "INSERT OR IGNORE INTO observations VALUES (?, ?, ?, ?, ?, ?)",
                        (*key, published, observed_at, observed_at),
                    ).rowcount
                    if baseline_exists and inserted and kind not in project["changes"]:
                        project["changes"].append(kind)
                    db.execute(
                        """UPDATE observations SET last_seen = MAX(last_seen, ?)
                           WHERE project_id = ? AND kind = ? AND evidence_id = ?""",
                        (observed_at, *key),
                    )
                project["first_seen"] = db.execute(
                    """SELECT first_seen FROM observations
                       WHERE project_id = ? AND kind = 'project' AND evidence_id = ?""",
                    (project["id"], project["id"]),
                ).fetchone()[0]
    snapshot["has_baseline"] = bool(baseline_exists)
