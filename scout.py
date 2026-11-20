"""Discover public startup signals and build an offline-ready sourcing inbox."""
import argparse
from datetime import date, datetime, timezone
from pathlib import Path
import json
import sqlite3

import footprint
import readiness
import web
from evidence import releases_for
from history import record_scan
from report import render
from sources import (
    COHORT, SOURCES, campus_projects, competition_projects, normalized, repository_releases,
)

ROOT = Path(__file__).resolve().parent
SOURCE_ERRORS = (OSError, ValueError, KeyError, TypeError)
RUN_ERRORS = (*SOURCE_ERRORS, sqlite3.Error)


def collect_projects(aliases):
    projects = {}
    source_status = {}
    errors = []
    # Within one organizer, rosters spell the same team differently; dedupe on a normalized key.
    same_source = {}
    for source, load in (("campus", campus_projects), ("competition", competition_projects)):
        label, url = SOURCES[source]
        warnings = []
        try:
            rows = load(warnings) if source == "competition" else load()
        except SOURCE_ERRORS as error:
            errors.append(f"{label}: {error}")
            source_status[source] = {"state": "failed", "count": 0}
            continue
        errors.extend(warnings)
        pages = len({row.get("url", url) for row in rows})
        source_status[source] = {"state": "partial" if warnings else "fresh", "count": len(rows)}
        if source == "competition":
            source_status[source]["pages"] = pages
        for row in rows:
            source_id = same_source.setdefault(
                (source, normalized(row["name"])), f"{source}:{row['name'].casefold()}"
            )
            association = aliases.get(source_id, {})
            project_id = association.get("id", source_id)
            project = projects.setdefault(project_id, {
                "id": project_id,
                "name": row["name"],
                "tags": [],
                "noise": False,
                "traces": [],
                "descriptions": [],
            })
            project["tags"] = sorted(set(project["tags"]) | set(row["tags"]))
            project["noise"] = project["noise"] or row["noise"]
            if row.get("location"):
                project["location"] = row["location"]
            trace = {
                "source": label, "url": row.get("url", url),
                "title": row.get("title", "Prototype grant directory" if source == "campus" else "Phase 1 nomination"),
                "date": row.get("published"),
            }
            if association:
                trace["identity_url"] = association["url"]
            if trace not in project["traces"]:
                project["traces"].append(trace)
            description = row.get("description")
            if description and description not in [item["text"] for item in project["descriptions"]]:
                project["descriptions"].append({"source": label, "text": description, "url": trace["url"]})
    if not projects:
        raise ValueError("No discovery feeds returned projects. " + " | ".join(errors))
    return projects, source_status, errors


RELEASE_CACHE = ROOT / ".firsttrace/release-cache.json"
WEB_CACHE = ROOT / ".firsttrace/web-cache.json"


def load_release_cache():
    """Last successful release fetch per repository, seeded from the captured demo scan."""
    try:
        return json.loads(RELEASE_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    cache = {}
    try:
        capture = json.loads((ROOT / "data/demo-snapshot.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cache
    for rows in capture.get("releases", {}).values():
        for row in rows:
            repo_name = row.get("title", "").split(" · ")[0]
            entry = cache.setdefault(repo_name, {"fetched_at": capture["observed_at"], "releases": []})
            entry["releases"].append(row)
    return cache


def discover(reviews, aliases, assessments=None):
    projects, source_status, errors = collect_projects(aliases)
    releases = {}
    repository_count = 0
    github_state = "fresh"
    cache = load_release_cache()
    cache_changed = False
    cached_repositories = 0
    for name, review in reviews.items():
        if f"campus:{name.casefold()}" not in projects:
            continue
        for repo in review.get("repositories", []):
            target = releases.setdefault(projects[f"campus:{name.casefold()}"]["name"], [])
            try:
                found, capped = repository_releases(repo)
                target.extend(found)
                repository_count += 1
                cache[repo.split("/")[1]] = {"fetched_at": datetime.now(timezone.utc).isoformat(), "releases": found}
                cache_changed = True
                if capped:
                    github_state = "partial"
                    errors.append(f"GitHub releases for {repo}: reached the three-page limit")
            except SOURCE_ERRORS as error:
                github_state = "partial"
                # Published release dates and URLs do not change, so keep the last fetched list visible.
                previous = cache.get(repo.split("/")[1])
                if previous:
                    target.extend(previous["releases"])
                    cached_repositories += 1
                    errors.append(
                        f"GitHub releases for {repo}: {error}. Showing {len(previous['releases'])} releases "
                        f"fetched {previous['fetched_at'][:10]}. Set GITHUB_TOKEN to raise the rate limit."
                    )
                else:
                    errors.append(f"GitHub releases for {repo}: {error}")
    if cache_changed:
        RELEASE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        RELEASE_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    source_status["github"] = {"state": github_state, "count": repository_count}
    if cached_repositories:
        source_status["github"]["cached"] = cached_repositories
    assessments = assessments or {}
    # Research every lead that could enter the inbox: tagged, reviewed or assessed.
    reviewed = {f"campus:{name.casefold()}" for name in reviews}
    candidates = [
        {**project, "location": assessments.get(project["id"], {}).get("location") or project.get("location", "")}
        for project in projects.values()
        if project.get("tags") or project["id"] in assessments or project["id"] in reviewed
    ]
    research, source_status["web"] = web.collect(candidates, assessments, WEB_CACHE, errors)
    domains = {key: {"domain": value["domain"]} for key, value in research.items()}
    domains.update({key: value for key, value in assessments.items() if key in projects and value.get("domain")})
    footprints, source_status["footprint"] = footprint.collect(domains, errors)
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "projects": list(projects.values()),
        "releases": releases,
        "footprints": footprints,
        "web": research,
        "errors": errors,
        "source_status": source_status,
    }


def prepare_replay(snapshot):
    for project in snapshot["projects"]:
        project.setdefault("id", f"campus:{project['name'].casefold()}")
        project.setdefault("traces", [{
            "source": "UnternehmerTUM", "url": COHORT,
            "title": "Prototype grant directory", "date": None,
        }])
    return snapshot


def apply_cutoff(snapshot, cutoff):
    """Keep only traces whose publication dates were known by the cutoff."""
    projects = []
    releases = {}
    footprints = {}
    for project in snapshot["projects"]:
        traces = [
            trace for trace in project["traces"]
            if trace.get("date") and trace["date"] <= cutoff
        ]
        published_releases = [
            release for release in releases_for(project, snapshot["releases"])
            if release["date"] <= cutoff
        ]
        published_footprint = [
            row for row in snapshot.get("footprints", {}).get(project["id"], [])
            if row["date"] <= cutoff
        ]
        if traces or published_releases:
            projects.append({
                "id": project["id"], "name": project["name"], "traces": traces,
                "tags": [], "noise": False,
            })
            releases[project["name"]] = published_releases
            footprints[project["id"]] = published_footprint
    return {
        **snapshot, "projects": projects, "releases": releases, "footprints": footprints, "web": {},
        "cutoff": cutoff, "has_baseline": False,
    }


def build_inbox(snapshot, reviews, assessments):
    observed = (snapshot.get("cutoff") or snapshot.get("observed_at") or "")[:10]
    today = date.fromisoformat(observed) if observed else date.today()
    by_id = {f"campus:{name.casefold()}": review for name, review in reviews.items()}
    leads = []
    for project in snapshot["projects"]:
        review = by_id.get(project["id"], {})
        assessment = assessments.get(project["id"], {})
        hold = assessment.get("hold") or review.get("hold")
        hold_url = assessment.get("hold_url") or review.get("hold_url")
        if project["noise"] and not hold:
            hold, hold_url = "Possible student group, assignment or agency.", COHORT
        releases = sorted(
            releases_for(project, snapshot["releases"]), key=lambda row: row["date"]
        )
        if not project["tags"] and not hold and not (snapshot.get("cutoff") and (project["traces"] or releases)):
            continue
        rosters = {trace["title"] for trace in project["traces"] if trace["source"] == "BayStartUP"}
        momentum = next((
            stage for stage in ("Winner", "Finalist", "Phase 2 winner", "Phase 2 nomination")
            if len(rosters) > 1 and any(stage in title for title in rosters)
        ), None)
        priority = "Adjacent"
        if review.get("market") or assessment.get("fit") == "Core fit":
            priority = "Core fit"
        elif "Digital tech" not in project["tags"] and not any(
            tag in {"enterprise", "developer", "infrastructure", "software"} for tag in project["tags"]
        ):
            priority = "Unreviewed"

        research = snapshot.get("web", {}).get(project["id"])
        facts = (research or {}).get("legal") or {}
        if facts.get("stage") == "Registered association (e.V.)" and not hold:
            hold, hold_url = "Registered association (e.V.) per its legal notice: typical of student initiatives, not a company.", research.get("legal_url")
        location = assessment.get("location", project.get("location", ""))
        if not location and facts.get("german") and facts.get("address"):
            location = facts["address"].split(" ", 1)[-1]
        lead = {
            **project,
            "descriptions": project.get("descriptions", []),
            "web": research,
            "location": location,
            "assessment": assessment,
            "review": {key: value for key, value in review.items() if key != "repositories"},
            "releases": releases,
            "footprint": sorted(snapshot.get("footprints", {}).get(project["id"], []), key=lambda row: row["date"]),
            "momentum": momentum,
            "hold": hold,
            "hold_url": hold_url,
            "fit": priority,
            "evidence": sum((
                bool(review.get("team_url") or assessment.get("team") or facts.get("directors")),
                bool(review.get("product_url") or assessment.get("product") or research),
                bool(releases), len(project["traces"]) > 1,
            )),
        }
        lead.update(readiness.assess(lead, today))
        leads.append(lead)
    return sorted(leads, key=lambda row: (bool(row["hold"]), -row["score"], row["name"].casefold()))


def load_config():
    reviews = json.loads((ROOT / "data/reviews.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "data/assessments.json").read_text(encoding="utf-8"))
    return reviews, config


def run_live(history, output, snapshot_path=None, server=False):
    """Scan public sources, record history, write the report and return a short summary."""
    reviews, config = load_config()
    assessments = config["stages"]
    snapshot = discover(reviews, config["aliases"], assessments)
    record_scan(history, snapshot, assessments)
    snapshot.update(reviews=reviews, assessments=assessments)
    if snapshot_path:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    leads = build_inbox(snapshot, reviews, assessments)
    output.write_text(render(snapshot, leads, False, server=server), encoding="utf-8")
    return summarize(snapshot, leads)


def summarize(snapshot, leads):
    held = sum(bool(lead["hold"]) for lead in leads)
    return {
        "observed_at": snapshot["observed_at"], "scanned": len(snapshot["projects"]),
        "inbox": len(leads) - held, "held": held,
        "new_signals": sum(bool(lead.get("changes")) for lead in leads),
        "has_baseline": snapshot.get("has_baseline", False), "errors": snapshot["errors"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--replay", type=Path, help="Read a saved scan and label the report as replay")
    mode.add_argument("--snapshot", type=Path, help="Save a live scan for later replay")
    mode.add_argument("--serve", action="store_true",
                      help="Run a local sourcing desk with a Run live scan button")
    parser.add_argument("--output", type=Path, default=Path("report.html"))
    parser.add_argument("--history", type=Path, default=ROOT / ".firsttrace/history.sqlite3")
    parser.add_argument("--as-of", type=date.fromisoformat, metavar="YYYY-MM-DD",
                        help="With --replay, show only dated evidence published by this date")
    parser.add_argument("--port", type=int, default=8765, help="With --serve, local port (default 8765)")
    parser.add_argument("--every", type=float, metavar="HOURS",
                        help="With --serve, rescan automatically at this interval")
    args = parser.parse_args()
    if args.as_of and not args.replay:
        parser.error("--as-of requires --replay")
    if (args.every or args.port != 8765) and not args.serve:
        parser.error("--every and --port require --serve")
    if args.every is not None and args.every < 0.25:
        parser.error("--every must be at least 0.25 hours to respect source rate limits")
    if args.serve:
        from server import serve
        serve(args.history, args.port, args.every)
        return
    try:
        if args.replay:
            reviews, config = load_config()
            assessments = config["stages"]
            snapshot = prepare_replay(json.loads(args.replay.read_text(encoding="utf-8")))
            reviews = snapshot.get("reviews", reviews)
            assessments = snapshot.get("assessments", assessments)
            if args.as_of:
                snapshot = apply_cutoff(snapshot, args.as_of.isoformat())
                reviews, assessments = {}, {}
            leads = build_inbox(snapshot, reviews, assessments)
            args.output.write_text(render(snapshot, leads, True), encoding="utf-8")
            summary = summarize(snapshot, leads)
        else:
            summary = run_live(args.history, args.output, args.snapshot)
    except RUN_ERRORS as error:
        parser.exit(1, f"Scan failed: {error}\n")

    print(f"{summary['scanned']} scanned, {summary['inbox']} in inbox, {summary['held']} held aside")
    if summary["has_baseline"]:
        count = summary["new_signals"]
        print(f"{count} {'lead' if count == 1 else 'leads'} with new signals since the previous scan")
    for warning in summary["errors"]:
        print(f"Source warning: {warning}")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
