"""Bounded public portfolio collection. Program affiliation is not financing."""
from datetime import datetime, timezone
import re
from urllib.parse import urljoin, urlsplit

from emergence import PROGRAMME_SOURCES
from engine import german_location, get_html, sector
from qualification import detect_intent

UTUM = "https://incubator.unternehmertum.de/portfolio/"
IMEC = "https://www.imecistart.com/portfolio?sort_year=desc"
BAYSTARTUP = "https://www.baystartup.de/startupdate/die-nominierten-im-muenchener-businessplan-wettbewerb-2026-phase-1"


def text(node):
    return node.get_text(" ", strip=True) if node else ""


def project_url(value):
    try:
        parsed = urlsplit(value or "")
        if parsed.scheme == "https" and parsed.hostname and not parsed.username:
            if not parsed.hostname.endswith(("linkedin.com", "facebook.com", "instagram.com")):
                return value
    except ValueError:
        pass
    return None


def project(uid, title, description, source, url, *, country=None, website=None, cohort=None):
    profile = {"country": country, "confidence": "ecosystem" if country else "unknown",
               "source_url": url if country else None}
    return {"id": uid, "title": title, "description": description, "source": source,
            "source_url": url, "sector": sector(title + " " + description),
            "cohort": cohort, "project_url": website, "location": profile,
            "intent_cues": detect_intent(description, url),
            "evidence": [{"signal": "Programme listing", "excerpt": description or title}]}


def scan_unternehmertum(_warnings, limit=35):
    cards = get_html(UTUM).select("utum-tile")
    rows = []
    for card in cards:
        title = text(card.select_one("h2, h3, h4"))
        description = text(card.select_one("p"))
        link = card.select_one("a[href]")
        if title and description:
            rows.append(project("utum:" + title.casefold(), title, description, PROGRAMME_SOURCES[0],
                                UTUM, website=project_url(link["href"]) if link else None))
        if len(rows) == limit:
            break
    if not rows:
        raise ValueError("UnternehmerTUM portfolio cards not found")
    return rows


def scan_imec(warnings, limit=25):
    cards = get_html(IMEC).select(".portfolio-item")
    if not cards:
        raise ValueError("imec.istart portfolio cards not found")
    rows = []
    cutoff = datetime.now(timezone.utc).year - 2
    for card in cards:
        title = text(card.select_one('[fs-list-field="name"]'))
        description = text(card.select_one('[fs-list-field="desc"]'))
        joined = text(card.select_one('[fs-list-field="year"]'))
        country = text(card.select_one('[fs-list-field="country"]'))
        if country == "The Netherlands":
            country = "Netherlands"
        link = card.select_one('a[href^="/portfolio/"]')
        if not title or not link or not joined.isdecimal() or not cutoff <= int(joined) <= cutoff + 2:
            continue
        url = urljoin(IMEC, link["href"])
        rows.append(project("imec:" + link["href"].rsplit("/", 1)[-1], title, description,
                            PROGRAMME_SOURCES[1], url, country=country or None,
                            cohort="Programme portfolio year " + joined))
        if len(rows) == limit:
            break
    if not rows:
        warnings.append("No recent profile cards could be read.")
    return rows


def scan_baystartup(warnings, limit=30):
    page = get_html(BAYSTARTUP)
    publication = text(page.select_one('time[itemprop="datePublished"]'))
    try:
        published = datetime.strptime(publication, "%d.%m.%Y").date().isoformat()
    except ValueError:
        warnings.append("Competition roster date could not be parsed.")
        published = None
    rows = []
    categories = ("Digitale Infrastruktur, KI und Software", "Medizintechnik, Life Sciences und Pharma",
                  "Industrie, Robotik, Energie und Agrar")
    for heading in page.find_all("h3"):
        if text(heading) not in categories:
            continue
        listing = heading.find_next(["ul", "h3"])
        if not listing or listing.name != "ul":
            continue
        for item in listing.find_all("li", recursive=False):
            label = text(item.find("strong"))
            match = re.fullmatch(r"(.+?)\s+\(([^()]+)\)", label)
            if not match:
                continue
            title, location = match.groups()
            description = text(item).removeprefix(label).strip(" –—-")
            row = project("baystartup:" + title.casefold(), title, description, PROGRAMME_SOURCES[2],
                          BAYSTARTUP, country="Germany" if german_location(location) else None,
                          cohort="Munich Business Plan Competition 2026")
            row["evidence"].append({"signal": "Competition location", "excerpt": location})
            if published:
                row["milestones"] = [{"date": published, "url": BAYSTARTUP,
                                      "label": "Named on the BayStartUP Phase 1 shortlist"}]
            rows.append(row)
            if len(rows) == limit:
                return rows
    if not rows:
        raise ValueError("BayStartUP nominations not found")
    return rows
