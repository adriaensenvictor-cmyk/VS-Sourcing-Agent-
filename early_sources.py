"""Public event rosters for discovery and project-only school programme records."""

from datetime import date, datetime
import re
from urllib.parse import urljoin, urlsplit

from engine import get_html
from programmes import cohort_listing, project, text


TUM_AWARD = "https://www.tum.de/en/innovation/entrepreneurship/news-events/tum-ideaward/"
FALLING_WALLS = "https://falling-walls.com/activities/venture/finalists"
JUGEND = "https://www.jugend-gruendet.de/finale-2026"
JUNIOR = (
    "https://wm.baden-wuerttemberg.de/de/service/presse-und-oeffentlichkeitsarbeit/pressemitteilung/"
    "pid/zwei-iw-junior-schuelerfirmen-aus-baden-wuerttemberg-gewinnen-in-koeln"
)
CLIPRO = JUGEND + "/clipro"
NOAH_SEED = "https://www.combination.vc/news/noah-labs-secures-eu3m-to-advance-telemonitoring-and-voice-diagnostics-for-heart-disease"
BRINEWORKS_SEED = "https://brineworks.tech/updates/brineworks-raises-eu5m-seed-to-scale-direct-air-capture"
FAST_AI_MOVIES = (
    "https://www.gruendunginschool.de/de/aktuelles/meldungen/detail/"
    "der-gruendungswettbewerb-als-tueroeffner-fuers-start-up"
)
PUBLIC_TRANSITIONS = ({
    "name": "FAST AI Movies",
    "milestone": "JUGEND GRÜNDET business plan (2021) → operating company",
    "url": FAST_AI_MOVIES,
},)


def iso_day(stamp):
    try:
        return date.fromisoformat((stamp or "")[:10]).isoformat()
    except ValueError:
        return None


def award_rows(page, url, year, warnings):
    meta = page.select_one('meta[property="article:published_time"]')
    published = iso_day(meta.get("content") if meta else None)
    if not published:
        warnings.append("TUM results publication date could not be verified.")
    rows = []
    for heading in page.select(".ce-textmedia__content h2"):
        result = re.fullmatch(r"(First|Second|Third) place:\s*(.+)", text(heading), re.I)
        if not result:
            continue
        title = result[2]
        body = heading.find_parent(class_="ce-textmedia__content").find("p")
        row = project("ideaward:" + title.casefold(), title, text(body), "TUM IDEAward", url,
                      cohort=f"TUM IDEAward {year}")
        if title.casefold() == "verdira biotech":
            # The team reports this site and TUM documents its research base and founders.
            team = "https://www.tum-venture-labs.de/teams/verdira-biotech/"
            row["project_url"] = "https://www.verdirabiotech.com/"
            row["location"] = {"country": "Germany", "confidence": "ecosystem", "source_url": url}
            row["founders"] = [
                {"name": name, "role": "Founder", "source_url": team}
                for name in ("Amelie Skopp", "Matea Marosevic")
            ]
            row["funding_status"] = "grant_reported"
            row["funding_source"] = team
        rows.append(cohort_listing(row, published, label="TUM published IDEAward results"))
        # TUM publishes the ceremony date separately from the results article.
        if year == "2025":
            row["evidence"].append({
                "signal": "Award ceremony", "excerpt": "The public final pitches were held on 27 November 2025.",
                "source_url": "https://www.tum.de/en/news-and-events/events/details/tum-ideaward-award-ceremony-2025",
            })
    if not rows:
        raise ValueError("TUM award winners could not be read")
    return rows


def scan_tum_award(warnings):
    archive = get_html(TUM_AWARD)
    editions = {
        text(link): urljoin(TUM_AWARD, link["href"]) for link in archive.select("a[href]")
        if re.fullmatch(r"20\d{2}", text(link))
        and urlsplit(urljoin(TUM_AWARD, link["href"])).hostname == "www.tum.de"
    }
    if not editions:
        raise ValueError("TUM IDEAward archive could not be read")
    latest = max(editions)
    return award_rows(get_html(editions[latest]), editions[latest], latest, warnings)


def scan_falling_walls(warnings):
    roster = get_html(FALLING_WALLS)
    headings = [(match[1], heading) for heading in roster.select(".paragraph--type--persons-manually h2")
                if (match := re.match(r"Finalists (20\d{2})\b", text(heading)))]
    if not headings:
        raise ValueError("Falling Walls edition could not be read")
    year = max(edition for edition, _ in headings)
    cards = [
        card for edition, heading in headings if edition == year
        for card in heading.find_parent(class_="paragraph--type--persons-manually").select(
            'a[rel="bookmark"][href^="/foundation/people/"]')
    ]
    announcement = urljoin(FALLING_WALLS, f"/falling-walls-foundation-announces-finalists-{year}-global-call")
    try:
        press = get_html(announcement)
    except (OSError, ValueError):
        press = None
    timestamp = press.select_one("time[datetime]") if press else None
    published = iso_day(timestamp.get("datetime") if timestamp else None)
    if not published:
        warnings.append("Falling Walls lineup publication date could not be verified.")
    press_titles = {}
    if press:
        section = next((h for h in press.select("h2") if "venture" in text(h).casefold()
                        and "finalists" in text(h).casefold()), None)
        if section:
            for entry in section.find_next_siblings():
                if entry.name == "h2":
                    break
                title, tagline = text(entry.find("strong")), text(entry.find("em"))
                if title and tagline:
                    press_titles[re.sub(r"\s+", "", title).casefold()] = tagline

    schedule = re.search(r"jury on stage in Berlin on (\d{1,2} [A-Za-z]+)", roster.get_text(" ", strip=True))
    try:
        pitch_date = datetime.strptime(f"{schedule[1]} {year}", "%d %B %Y").date().isoformat() if schedule else None
    except ValueError:
        pitch_date = None
    rows = []
    for card in cards:
        title = text(card.select_one("h3.node-title"))
        country = text(card.select_one(".field--name-field-institution"))
        if not title or not country:
            continue
        url = urljoin(FALLING_WALLS, card["href"])
        country = {"United States of America": "United States", "The Netherlands": "Netherlands"}.get(country, country)
        tagline = press_titles.get(re.sub(r"\s+", "", title).casefold())
        description = f"{title} was selected to pitch at Falling Walls Venture {year}."
        if tagline:
            description += f" Listed pitch: {tagline}."
        row = project("falling-walls:" + title.casefold(), title, description, "Falling Walls Venture", url,
                      country=country, cohort=f"Falling Walls Venture {year}")
        row["evidence"] = [{"signal": "Selected event pitch", "excerpt": description}]
        funding_source = {"noah labs": NOAH_SEED, "brineworks": BRINEWORKS_SEED}.get(title.casefold())
        if funding_source:
            row.update(funding_status="vc_round_reported", funding_source=funding_source)
        if pitch_date:
            row["evidence"].append({"signal": "Scheduled pitch", "excerpt": pitch_date, "source_url": url})
        if published and tagline:
            row["milestones"] = [{"date": published, "url": announcement,
                                  "label": "Organizer published Falling Walls Venture finalists"}]
        rows.append(row)
    if not rows:
        raise ValueError("Falling Walls finalists could not be read")
    return rows


def scan_jugend(_warnings):
    rows = []
    for card in get_html(JUGEND).select(".team-card"):
        name = text(card.select_one(".name-label"))
        if name:
            rows.append({
                "name": name, "milestone": "National finalist · 2026", "url": JUGEND,
                "project": "Industrial pipe leak-warning system (OleoClip)" if name == "CLIPRO" else "",
            })
    if not rows:
        raise ValueError("JUGEND GRÜNDET teams could not be read")
    return rows


def scan_junior(_warnings):
    page = get_html(JUNIOR)
    stamp = page.select_one("time[datetime]")
    published = iso_day(stamp.get("datetime") if stamp else None)
    names = dict.fromkeys(
        name for paragraph in page.select(".article__section--list .text p")
        for name in re.findall(r'Schülerfirma\s+„([^“”]+)[“”]', text(paragraph))
    )
    if not names:
        raise ValueError("IW JUNIOR results could not be read")
    return [{"name": name, "milestone": f"National results · {published or '2026'}", "url": JUNIOR, "project": ""}
            for name in names]


EVENT_READERS = {"TUM IDEAward": scan_tum_award, "Falling Walls Venture": scan_falling_walls}
SCHOOL_READERS = {"JUGEND GRÜNDET": scan_jugend, "IW JUNIOR": scan_junior}
