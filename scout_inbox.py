"""Persist scout decisions and observe additions to the existing discovery payload."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit


WATCH_FOR = ("Any sourced change", "Customer or pilot", "Disclosed equity")
DECISIONS = ("Meet", "Watch", "Pass")


def valid_url(value):
    if not isinstance(value, str) or any(c.isspace() for c in value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username:
            return value
    except ValueError:
        pass
    return None


def timestamp(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).isoformat()


def observations(lead):
    """Evidence changes only. Scraper timestamps, scores and text edits stay quiet."""
    for event in lead.get("timeline", []):
        if event.get("date") and event.get("public_signal", True) and valid_url(event.get("url")):
            yield "Public milestone", event["url"], event["date"], event["label"]
    for claim in lead.get("claims", []):
        if claim.get("status") == "verified" and claim.get("type") in {"pilot", "customer_discovery", "commercialization"}:
            if valid_url(claim.get("source_url")):
                yield "Customer or pilot", claim["source_url"], claim.get("date", ""), claim["text"]
    if lead.get("funding", {}).get("status") == "funded":
        for equity in lead["funding"].get("rounds", []):
            if valid_url(equity.get("source_url")):
                yield "Disclosed equity", equity["source_url"], equity.get("date", ""), "Public equity round reported"


class ScoutInbox:
    def __init__(self, path=None):
        default = Path.home() / ".firsttrace" / "scout-workflow.sqlite3"
        self.path = Path(path or os.getenv("FIRSTTRACE_DB_PATH") or default).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    captured_at TEXT PRIMARY KEY, payload TEXT NOT NULL, usable INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS leads (
                    id TEXT PRIMARY KEY, first_seen TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    lead_id TEXT, fingerprint TEXT, first_seen TEXT NOT NULL,
                    PRIMARY KEY (lead_id, fingerprint)
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    scope TEXT, lead_id TEXT, decision TEXT NOT NULL, owner TEXT NOT NULL,
                    reason TEXT NOT NULL, watch_for TEXT NOT NULL, saved_at TEXT NOT NULL,
                    PRIMARY KEY (scope, lead_id)
                );
                CREATE TABLE IF NOT EXISTS inbox (
                    id INTEGER PRIMARY KEY, lead_id TEXT NOT NULL, name TEXT NOT NULL,
                    captured_at TEXT NOT NULL, kind TEXT NOT NULL, source TEXT, detail TEXT NOT NULL,
                    reviewed INTEGER NOT NULL DEFAULT 0
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def record(self, outcome):
        if outcome.get("mode") != "live":
            raise ValueError("Only live runs enter the scout inbox.")
        captured_at = timestamp(outcome["generated_at"])
        statuses = outcome["source_status"]
        usable = any(source["state"] in {"ok", "partial"} for source in statuses.values())
        report = {"recorded": False, "new_leads": 0, "watch_matches": 0}
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT MAX(captured_at) FROM runs").fetchone()[0]
            if previous and previous >= captured_at:
                return report
            db.execute("INSERT INTO runs VALUES (?, ?, ?)", (captured_at, json.dumps(outcome), usable))
            report["recorded"] = True
            if not usable:
                return report
            shortlist = {lead["id"] for lead in outcome["shortlist"]}
            for lead in outcome["candidates"]:
                if lead.get("record_provenance") == "reviewed public reference":
                    continue
                key, name = lead["id"], lead["title"]
                db.execute("INSERT OR IGNORE INTO leads VALUES (?, ?)", (key, captured_at))
                previously_shortlisted = db.execute(
                    "SELECT 1 FROM inbox WHERE lead_id = ? AND kind = 'First seen in shortlist'", (key,)
                ).fetchone()
                if key in shortlist and not previously_shortlisted:
                    self._notice(db, key, name, captured_at, "First seen in shortlist",
                                 valid_url(lead.get("source_url")), "Review the founding team and earliest trace.")
                    report["new_leads"] += 1
                decision = db.execute("SELECT * FROM decisions WHERE scope = 'live' AND lead_id = ?", (key,)).fetchone()
                for kind, url, date, detail in observations(lead):
                    fingerprint = sha256(json.dumps([kind, url, date, detail if kind == "Public milestone" else ""]).encode()).hexdigest()
                    inserted = db.execute("INSERT OR IGNORE INTO evidence VALUES (?, ?, ?)",
                                          (key, fingerprint, captured_at)).rowcount
                    if inserted and decision and decision["decision"] == "Watch" and decision["watch_for"] in (kind, WATCH_FOR[0]):
                        self._notice(db, key, name, captured_at, kind, url, detail)
                        report["watch_matches"] += 1
        return report

    def _notice(self, db, key, name, captured_at, kind, source, detail):
        db.execute("INSERT INTO inbox (lead_id, name, captured_at, kind, source, detail) VALUES (?, ?, ?, ?, ?, ?)",
                   (key, name, captured_at, kind, source, detail))

    def latest_run(self, *, usable_only=False):
        query = "SELECT payload FROM runs"
        if usable_only:
            query += " WHERE usable = 1"
        with self.connect() as db:
            result = db.execute(query + " ORDER BY captured_at DESC LIMIT 1").fetchone()
        return json.loads(result["payload"]) if result else None

    def decisions(self, scope):
        with self.connect() as db:
            return {row["lead_id"]: dict(row) for row in db.execute("SELECT * FROM decisions WHERE scope = ?", (scope,))}

    def decide(self, scope, lead_id, decision, owner, reason, watch_for, through=0):
        if decision not in DECISIONS or watch_for not in WATCH_FOR or not reason.strip():
            raise ValueError("Choose a decision and enter a reason.")
        with self.connect() as db:
            db.execute("""INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?)
                          ON CONFLICT(scope, lead_id) DO UPDATE SET
                          decision=excluded.decision, owner=excluded.owner, reason=excluded.reason,
                          watch_for=excluded.watch_for, saved_at=excluded.saved_at""",
                       (scope, lead_id, decision, owner.strip(), reason.strip(), watch_for,
                        datetime.now(timezone.utc).isoformat()))
            if scope == "live":
                db.execute("UPDATE inbox SET reviewed = 1 WHERE lead_id = ? AND id <= ?", (lead_id, through))

    def first_seen(self, lead_id):
        with self.connect() as db:
            row = db.execute("SELECT first_seen FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return row["first_seen"] if row else None

    def acknowledge(self, notice_id):
        with self.connect() as db:
            db.execute("UPDATE inbox SET reviewed = 1 WHERE id = ?", (notice_id,))

    def inbox(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM inbox WHERE reviewed = 0 ORDER BY id DESC")]


def main():
    from discovery_pipeline import run_discovery
    from emergence import DISCOVERY_SOURCES

    parser = argparse.ArgumentParser(description="Run discovery and update the scout inbox.")
    parser.add_argument("--db", help="Path shared with the dashboard (default: FIRSTTRACE_DB_PATH)")
    parser.add_argument("--sources", nargs="+", choices=DISCOVERY_SOURCES, default=DISCOVERY_SOURCES)
    options = parser.parse_args()
    run = run_discovery(tuple(options.sources), github_limit=4)
    summary = ScoutInbox(options.db).record(run)
    print(json.dumps({**summary, "generated_at": run["generated_at"], "source_status": run["source_status"]}))
    return 0 if any(s["state"] in {"ok", "partial"} for s in run["source_status"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
