"""Dated public footprint for company domains that an analyst has linked to a lead.

Identity comes from the analyst-provided domain, never from name matching.
Each row keeps its date type: an archive capture is not a launch date.
"""
import json
import re
from urllib.parse import quote, urlparse

from sources import fetch

WAYBACK = "https://web.archive.org/cdx/search/cdx?url={domain}&output=json&limit=1&fl=timestamp,original"
HACKER_NEWS = (
    "https://hn.algolia.com/api/v1/search?query={query}&restrictSearchableAttributes=url"
    "&typoTolerance=false&hitsPerPage=50"
)
MAX_DOMAINS = 15
DOMAIN = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}")


def wayback_first(domain):
    rows = json.loads(fetch(WAYBACK.format(domain=quote(domain))) or "[]")
    if len(rows) < 2:
        return []
    timestamp, original = rows[1][:2]
    return [{
        "source": "Internet Archive", "title": "Company website first archived",
        "url": f"https://web.archive.org/web/{timestamp}/{original}",
        "date": f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}", "date_type": "archived",
    }]


def hacker_news(domain):
    hits = json.loads(fetch(HACKER_NEWS.format(query=quote(f'"{domain}"'))))["hits"]
    linked = [
        hit for hit in hits
        if hit.get("url") and urlparse(hit["url"]).hostname
        and (urlparse(hit["url"]).hostname == domain or urlparse(hit["url"]).hostname.endswith("." + domain))
    ]
    if not linked:
        return []
    first = min(linked, key=lambda hit: hit["created_at"])
    return [{
        "source": "Hacker News", "title": f"First post linking {domain} · {first.get('title') or 'untitled'}",
        "url": f"https://news.ycombinator.com/item?id={first['objectID']}",
        "date": first["created_at"][:10], "date_type": "published",
        "count": len(linked),
    }]


def collect(assessments, errors):
    """Return ({project_id: [rows]}, status) for leads with an analyst-verified domain."""
    footprints = {}
    checked = 0
    failed = 0
    for project_id, assessment in assessments.items():
        domain = (assessment.get("domain") or "").lower()
        if not DOMAIN.fullmatch(domain) or checked >= MAX_DOMAINS:
            continue
        checked += 1
        rows = []
        for label, lookup in (("Internet Archive", wayback_first), ("Hacker News", hacker_news)):
            try:
                rows.extend(lookup(domain))
            except (OSError, ValueError, KeyError, TypeError) as error:
                failed += 1
                errors.append(f"{label} for {domain}: {error}")
        footprints[project_id] = rows
    state = "fresh" if not failed else "partial" if failed < checked * 2 else "failed"
    return footprints, {"state": state, "count": checked}
