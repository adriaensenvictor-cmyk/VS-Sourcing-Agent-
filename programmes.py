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
            rows.append(cohort_listing(row, published, label="Named on the BayStartUP Phase 1 shortlist"))
            if len(rows) == limit:
                return rows
    if not rows:
        raise ValueError("BayStartUP nominations not found")
    return rows


FRAUNHOFER = ("https://www.fraunhofer.de/de/presse/presseinformationen/2026/september-2026/"
             "fraunhofer-auf-der-bits-and-pretzels-2026.html")
SPINLAB = "https://www.spinlab.co/news/spinlab-launches-20th-class"
ROOTCAMP = "https://www.root.camp/blog/agtech-and-foodtech-startups-to-watch-in-2026"
HPI = "https://www.engine.hpi.de/our-ecosystem"


def cohort_listing(row, published, *, label="Named in programme announcement"):
    """Preserve the programme publication date separately from company age."""
    if published:
        row["milestones"] = [
            {"date": published, "url": row["source_url"], "label": label}
        ]
        elapsed = (datetime.now(timezone.utc).date() - datetime.fromisoformat(published).date()).days
        if 0 <= elapsed <= 365:
            row["evidence"].append({"signal": "Recent programme selection", "excerpt": row["description"]})
    return row


def hubspot_date(page, warnings):
    stamp = text(page.select_one("#hubspot-author_data"))
    try:
        return datetime.strptime(stamp.rsplit(",", 1)[0], "%b %d, %Y").date().isoformat()
    except ValueError:
        warnings.append("Programme publication date could not be parsed.")
        return None


def cohort_section(page, heading):
    marker = next((h for h in page.select("h2") if heading in text(h)), None)
    if not marker:
        raise ValueError("Programme cohort heading could not be located")
    for node in marker.next_siblings:
        tag = getattr(node, "name", None)
        if tag == "h2":
            break
        if tag:
            yield node


def scan_rootcamp(warnings):
    page = get_html(ROOTCAMP)
    published = hubspot_date(page, warnings)
    rows = []
    for heading in cohort_section(page, "This is RootCamp Batch"):
        if heading.name != "h3":
            continue
        title, sep, country = text(heading).partition(" | ")
        paragraph = heading.find_next_sibling()
        if not sep or not paragraph or paragraph.name != "p":
            continue
        link = paragraph.select_one("a[href]")
        row = project("rootcamp:" + title.casefold(), title, text(paragraph), "RootCamp", ROOTCAMP,
                      country=country, website=project_url(link["href"]) if link else None,
                      cohort="RootCamp Batch 8")
        rows.append(cohort_listing(row, published))
    if not rows:
        raise ValueError("RootCamp teams could not be read")
    return rows


def scan_spinlab(warnings):
    page = get_html(SPINLAB)
    published = hubspot_date(page, warnings)
    rows = []
    for paragraph in cohort_section(page, "new SpinLab Startups"):
        link = paragraph.select_one("a[href]")
        title = text(link)
        if paragraph.name != "p" or not title:
            continue
        row = project("spinlab:" + title.casefold(), title, text(paragraph), "SpinLab", SPINLAB,
                      website=project_url(link["href"]), cohort="SpinLab Class 20")
        rows.append(cohort_listing(row, published))
    if not rows:
        raise ValueError("SpinLab teams could not be read")
    return rows


def scan_fraunhofer(warnings):
    page = get_html(FRAUNHOFER)
    heading = next((node for node in page.select(".fhg-richtext p")
                    if "Gründerteams" in text(node) and "aktuell" in text(node)
                    and "unterstützt" in text(node)), None)
    if not heading:
        raise ValueError("Fraunhofer team section could not be read")
    stamp = text(page.select_one("time"))
    match = re.fullmatch(r"(\d{1,2})\. September (\d{4})", stamp)
    published = None
    if match:
        try:
            published = datetime(int(match[2]), 9, int(match[1])).date().isoformat()
        except ValueError:
            pass
    if not published:
        warnings.append("Fraunhofer programme publication date could not be parsed.")
    rows = []
    for node in heading.find_next_siblings():
        if node.name != "h4":
            continue
        title, sep, _subtitle = text(node).partition(":")
        paragraph = node.find_next_sibling()
        if not sep or not paragraph or paragraph.name != "p":
            continue
        row = project("fraunhofer:" + title.casefold(), title, text(paragraph),
                      "Fraunhofer AHEAD", FRAUNHOFER, cohort="Fraunhofer Venture and AHEAD at Bits & Pretzels")
        rows.append(cohort_listing(row, published))
    if not rows:
        raise ValueError("Fraunhofer team descriptions could not be read")
    return rows


def scan_hpi(_warnings):
    rows = []
    for card in get_html(HPI).select(".linkblock--startups"):
        title = text(card.select_one("p.weight--500"))
        description = text(card.select_one("p.paragraph--large"))
        attribution = card.select(".grid--foundet-by p")
        if not title or not description:
            continue
        row = project("hpi:" + title.casefold(), title, description, "HPI Engine", HPI)
        if len(attribution) == 2 and text(attribution[0]) == "Founded by:":
            names = [name.strip() for name in re.split(r",|\s+and\s+", text(attribution[1])) if name.strip()]
            row["founders"] = [{"name": name, "source_url": HPI, "role": "Founder"} for name in names]
        rows.append(row)
    if not rows:
        raise ValueError("HPI ecosystem cards could not be read")
    return rows


READERS = {
    "UnternehmerTUM Incubator": scan_unternehmertum,
    "imec.istart": scan_imec,
    "BayStartUP roster": scan_baystartup,
    "Fraunhofer AHEAD": scan_fraunhofer,
    "SpinLab": scan_spinlab,
    "RootCamp": scan_rootcamp,
    "HPI Engine": scan_hpi,
}
