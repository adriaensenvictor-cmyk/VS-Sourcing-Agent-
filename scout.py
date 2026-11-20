"""Discover campus projects and prioritize evidence-backed leads."""
import argparse
from datetime import date, datetime, timezone
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
COHORT = "https://funding.unternehmertum.de/supportedteams-2/"
GITHUB = "https://api.github.com"
SECTOR = re.compile(
    r"\b(?:enterprise|infrastructure|developer|codebases?|cybersecurity|"
    r"data (?:platform|pipeline|teams)|software|llms?)\b", re.IGNORECASE
)
NOISE = re.compile(
    r"\b(?:student[- ]initiated team|student club|student assignment|digital agency|"
    r"student association)\b",
    re.IGNORECASE,
)


class CohortParser(HTMLParser):
    """Read names and descriptions from the programme's project cards."""

    def __init__(self):
        super().__init__()
        self.projects = []
        self.card = None
        self.field = None

    def handle_starttag(self, tag, attrs):
        if tag == "utum-tile":
            self.card = {"h2": [], "p": []}
        elif self.card is not None and tag in self.card:
            self.field = tag

    def handle_endtag(self, tag):
        if tag == self.field:
            self.field = None
        if tag == "utum-tile" and self.card is not None:
            name, description = (
                " ".join("".join(self.card[field]).split()) for field in ("h2", "p")
            )
            if name and description:
                tags = sorted({match.group().lower() for match in SECTOR.finditer(description)})
                noise = NOISE.search(description)
                self.projects.append({"name": name, "tags": tags, "noise": bool(noise)})
            self.card = None
            self.field = None

    def handle_data(self, data):
        if self.field:
            self.card[self.field].append(data)


def fetch(url):
    request = Request(url, headers={"User-Agent": "FirstTrace-Hackathon/1.0"})
    with urlopen(request, timeout=12) as response:
        return response.read().decode("utf-8")


def get_releases(repositories):
    releases = []
    for repo in repositories:
        data = json.loads(fetch(f"{GITHUB}/repos/{repo}/releases?per_page=100"))
        published = [
            release for release in data
            if release["published_at"] and not release["draft"] and not release["prerelease"]
        ]
        if published:
            first = min(published, key=lambda release: release["published_at"])
            releases.append({
                "title": f"{repo.split('/')[1]} · {first['tag_name']}",
                "url": first["html_url"],
                "date": first["published_at"][:10],
            })
    return sorted(releases, key=lambda release: release["date"])


def discover(reviews):
    parser = CohortParser()
    parser.feed(fetch(COHORT))
    projects = {
        project["name"].casefold(): project for project in parser.projects
    }
    if not projects:
        raise ValueError("No project cards found. Check the source page structure.")
    releases = {}
    errors = []
    for name, review in reviews.items():
        repositories = review.get("repositories", [])
        if name.casefold() in projects and repositories:
            for repository in repositories:
                try:
                    releases.setdefault(name, []).extend(get_releases([repository]))
                except (OSError, ValueError, KeyError, TypeError) as error:
                    errors.append(f"GitHub releases for {repository}: {error}")
            releases.setdefault(name, []).sort(key=lambda release: release["date"])
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "projects": list(projects.values()),
        "releases": releases,
        "errors": errors,
    }


def rank(projects, releases, reviews):
    ranked = []
    filtered = []
    for project in projects:
        name = project["name"]
        review = reviews.get(name, {})
        if review.get("hold"):
            filtered.append({
                **project, "reason": review["hold"], "url": review["hold_url"],
                "comparison": review.get("comparison"),
            })
            continue
        if project["noise"]:
            filtered.append({**project, "reason": "Possible club, assignment or agency", "url": COHORT})
            continue
        if not project["tags"]:
            continue
        proofs = releases.get(name, [])
        factors = {"In scope": 1}
        if review.get("team_url") and review.get("product_url"):
            factors["Verified team and German base"] = 2
        if proofs:
            factors["Dated public release"] = 2
        if review.get("market"):
            factors["Analyst buyer hypothesis"] = 1
        ranked.append({
            **project, "review": review, "releases": proofs,
            "factors": factors, "score": sum(factors.values()),
        })
    return sorted(ranked, key=lambda lead: (-lead["score"], lead["name"].casefold())), filtered


def link(url, label):
    if not url.startswith("https://"):
        raise ValueError("Source links must use HTTPS.")
    return f'<a href="{escape(url)}">{escape(label)}</a>'


def lead_details(lead, is_first):
    review = lead["review"]
    citations = link(COHORT, "UnternehmerTUM · project listing")
    tags = ", ".join(lead["tags"])
    details = [
        f'<p><strong>Matched terms</strong> {escape(tags)}</p>',
        f'<p class="muted">{citations} · publication date unavailable</p>',
    ]
    if review.get("team_url"):
        details.append(f'<p><strong>Team</strong> {escape(review["team"])} · {link(review["team_url"], "TUM")}</p>')
    if review.get("product_url"):
        details.append(f'<p><strong>Today</strong> {escape(review["product"])} · {link(review["product_url"], "Company")}</p>')
    if review.get("market"):
        details.append(f'<p><strong>Why take a call?</strong> {escape(review["market"])}</p>')
    if lead["releases"]:
        entries = "".join(
            f'<li><time>{escape(item["date"])}</time> {link(item["url"], item["title"])}</li>'
            for item in lead["releases"]
        )
        details.append(f'<h3>Earliest releases observed per repository</h3><ul>{entries}</ul>')
        details.append('<p class="muted">Days ahead of database coverage unavailable. The historical listing date is unverified.</p>')
    funding = review.get("funding", "Equity status unreviewed.")
    funding_link = f' · {link(review["funding_url"], "Database check")}' if review.get("funding_url") else ""
    details.append(f'<p><strong>Funding</strong> {escape(funding)}{funding_link}</p>')
    factors = " · ".join(f"{name} +{weight}" for name, weight in lead["factors"].items())
    details.append(f'<p class="muted">{escape(factors)}</p>')
    opened = " open" if is_first else ""
    return (
        f'<details{opened}><summary>{escape(lead["name"])}'
        f'<span>{lead["score"]}/6 evidence points</span></summary>'
        f'<div class="detail">{"".join(details)}</div></details>'
    )


def render(snapshot, ranked, filtered, replay):
    mode = "Snapshot replay" if replay else "Live scan"
    cards = "".join(lead_details(lead, index == 0) for index, lead in enumerate(ranked))
    exclusions = "".join(
        f'<li><strong>{escape(project["name"])}</strong> {escape(project["reason"])} '
        f'{link(project["url"], "Source")}</li>' for project in filtered
    )
    comparisons = []
    for project in filtered:
        case = project.get("comparison")
        if case:
            gap = (date.fromisoformat(case["baseline_date"]) - date.fromisoformat(case["signal_date"])).days
            comparisons.append(
                f'<p><strong>{escape(project["name"])} · {gap} days</strong> from '
                f'{link(case["signal_url"], "competition nomination")} '
                f'({escape(case["signal_date"])}) to '
                f'{link(case["baseline_url"], "press coverage of pre-seed")} '
                f'({escape(case["baseline_date"])}).</p>'
            )
    comparison_section = (
        '<h2>Historical comparison</h2>' + "".join(comparisons)
        + '<p class="muted">Selected retrospectively. This gap compares source publication dates. '
        'The engine first observed this case in the current scan.</p>'
        if comparisons else ""
    )
    errors = "".join(f'<li>{escape(error)}</li>' for error in snapshot["errors"])
    error_notice = f"<h2>Source warnings</h2><ul>{errors}</ul>" if errors else ""
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FirstTrace · Sourcing desk</title>
<style>
:root {{color-scheme: light; --ink:#183229; --paper:#f4f3e9; --line:#d5ded0; --muted:#486154}}
* {{box-sizing:border-box}}
body {{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}
header {{background:#16392e;color:#faf9ef;padding:44px max(24px,calc((100% - 920px)/2))}}
header p {{margin:0;color:#dae9ce}}
h1 {{font:clamp(46px,8vw,86px)/.95 Georgia,serif;margin:9px 0 17px;letter-spacing:-.055em}}
main {{max-width:968px;margin:auto;padding:28px 24px 48px}}
.meta {{display:flex;flex-wrap:wrap;gap:6px 24px;color:var(--muted);margin-bottom:26px}}
h2 {{font:32px/1.2 Georgia,serif;margin:28px 0 12px}}
h3 {{font-size:1rem;margin-bottom:0}}
details {{background:#fffdf6;border:1px solid var(--line);border-radius:9px;margin:9px 0}}
summary {{cursor:pointer;padding:14px 18px;font-weight:700;overflow-wrap:anywhere}}
summary span {{display:inline-block;margin-left:12px;color:var(--muted);font-weight:500;font-size:.87rem}}
.detail {{border-top:1px solid var(--line);padding:0 18px 8px}}
.muted,time {{color:var(--muted);font-size:.89rem}}
a {{color:#20583f;text-underline-offset:.18em}}
a:focus-visible,summary:focus-visible {{outline:2px solid #27684e;outline-offset:2px}}
li {{margin:8px 0}}
</style>
<header><p>Munich · B2B software and infrastructure</p><h1>FirstTrace</h1><p>Early startup signals for the HTGF sourcing desk</p></header>
<main>
<div class="meta"><strong>{mode}</strong><time>{escape(snapshot["observed_at"])}</time>
<span>{len(snapshot["projects"])} scanned · {len(ranked)} in scope · {len(filtered)} held aside</span></div>
{error_notice}
<h2>Lead inbox</h2>
<p>Evidence points indicate what we can verify. Start with the team and its earliest dated product trace.</p>
{cards or "<p>No matching projects were found.</p>"}
<details><summary>Held aside ({len(filtered)})</summary><div class="detail"><ul>{exclusions}</ul></div></details>
{comparison_section}
</main>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--replay", type=Path, help="Read a saved scan and label the report as replay")
    mode.add_argument("--snapshot", type=Path, help="Save a live scan for later replay")
    parser.add_argument("--output", type=Path, default=Path("report.html"))
    args = parser.parse_args()
    try:
        reviews = json.loads((ROOT / "data/reviews.json").read_text(encoding="utf-8"))
        snapshot = (
            json.loads(args.replay.read_text(encoding="utf-8")) if args.replay else discover(reviews)
        )
        if args.snapshot:
            args.snapshot.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ranked, filtered = rank(snapshot["projects"], snapshot["releases"], reviews)
        args.output.write_text(render(snapshot, ranked, filtered, bool(args.replay)), encoding="utf-8")
    except (OSError, KeyError, ValueError, TypeError) as error:
        parser.exit(1, f"Scan failed: {error}\n")
    print(f"{len(snapshot['projects'])} scanned, {len(ranked)} in scope, {len(filtered)} held aside")
    for warning in snapshot["errors"]:
        print(f"Source warning: {warning}")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
