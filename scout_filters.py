"""Read-only filters for the scouting queue."""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
import re
from urllib.parse import urlsplit


GERMANY = "Germany"
OTHER_EUROPE = "Other Europe"
ALL_EUROPE = "Germany + other Europe"
ANYWHERE = "All locations"
UNKNOWN_REGION = "Unverified or elsewhere"
REGIONS = (GERMANY, OTHER_EUROPE, ALL_EUROPE, ANYWHERE)
FUNDING_STAGES = ("Pre-seed", "Seed", "Series A", "Series B", "Series C+", "Growth", "Other / review", "Unverified")

# UN M49 Europe plus Cyprus (EU member) and Kosovo. Names, including common
# UK constituent names, are matched as full location components only.
EUROPE_NAMES = set("""albania|andorra|austria|belarus|belgium|bosnia and herzegovina|bulgaria|croatia|
cyprus|czechia|czech republic|denmark|estonia|finland|france|greece|hungary|iceland|ireland|italy|kosovo|
latvia|liechtenstein|lithuania|luxembourg|malta|moldova|republic of moldova|monaco|montenegro|netherlands|
the netherlands|north macedonia|norway|poland|portugal|romania|russia|russian federation|san marino|serbia|
slovakia|slovenia|spain|sweden|switzerland|ukraine|united kingdom|uk|u.k.|england|scotland|northern ireland|
wales|vatican city|holy see|åland islands|faroe islands|guernsey|isle of man|jersey|svalbard and jan mayen|
svalbard and jan mayen islands|gibraltar""".replace("\n", "").split("|"))
EUROPE_CODES = set("al ad at by be ba bg hr cy cz dk ee fi fr gr hu is ie it xk lv li lt lu mt md mc me nl mk no pl pt ro ru sm rs sk si es se ch ua gb va ax fo gg im je sj gi".split())


def location_region(item, profile=None):
    country = (profile or {}).get("country") or item.get("country")
    if country:
        place = str(country).strip().casefold()
        if place in {"germany", "deutschland", "de", "deu"}:
            return GERMANY
        return OTHER_EUROPE if place in EUROPE_NAMES | EUROPE_CODES else UNKNOWN_REGION
    # The discovery engine records the GitHub owner's profile location here.
    # A university listing alone similarly does not establish a company's base.
    if item.get("origin") in {"GitHub", "TU Berlin"}:
        return UNKNOWN_REGION
    # Inspect the country at the end, so 'Berlin, Maryland, USA' never matches.
    place = str(item.get("location") or "").rsplit(",", 1)[-1].strip().casefold()
    if place in {"germany", "deutschland"}:
        return GERMANY
    return OTHER_EUROPE if place in EUROPE_NAMES else UNKNOWN_REGION


def region_matches(region, selected):
    return selected == ANYWHERE or region == selected or (selected == ALL_EUROPE and region in {GERMANY, OTHER_EUROPE})


@dataclass(frozen=True)
class Formation:
    value: date | int
    source: str


# Only parse the formation event itself. Publication dates, first traces and
# grant periods must never silently become a company's founding date.
FORMATION_TEXT = re.compile(
    r"\b(?:registration dated|registered on|incorporated on|founded on)\s+"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2} [A-Za-z]+ \d{4})\b", re.I,
)


def web_source(value):
    try:
        parsed = urlsplit(value or "")
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname)
    except (AttributeError, TypeError, ValueError):
        return False


def formation_record(item, profile=None):
    """Return a sourced founding/registration date, retaining year precision."""
    profile = profile or {}
    source = profile.get("founded_source")
    if web_source(source):
        value = profile.get("founded_on") or profile.get("founded_year")
        if re.fullmatch(r"[1-9]\d{3}", str(value)):
            return Formation(int(value), source)
        try:
            return Formation(date.fromisoformat(str(value)), source)
        except ValueError:
            pass
    for evidence in item.get("evidence") or []:
        if evidence.get("signal", "").casefold() not in {"company formation trace", "incorporation", "company registration", "company founding"}:
            continue
        source = evidence.get("url")
        match = FORMATION_TEXT.search(evidence.get("excerpt") or "")
        if not match or not web_source(source):
            continue
        for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
            try:
                return Formation(datetime.strptime(match[1], fmt).date(), source)
            except ValueError:
                continue
    return None


def age_fit(record, years, today):
    """True, False, or unknown when the source cannot resolve this cutoff."""
    if record is None:
        return None
    cutoff_year = today.year - years
    cutoff = date(cutoff_year, today.month, min(today.day, monthrange(cutoff_year, today.month)[1]))
    value = record.value
    if isinstance(value, date):
        return value >= cutoff if value <= today else None
    if value > today.year:
        return None
    earliest = date(value, 1, 1)
    latest = min(today, date(value, 12, 31))
    if latest < cutoff:
        return False
    return True if earliest >= cutoff else None


def funding_stage(status):
    """Classify a reported round, preserving uncertainty and non-equity support."""
    text = str(status or "").replace("_", " ").casefold().strip()
    if not text or re.search(r"\b(unknown|unverified|unconfirmed|unfunded|unclear|not|no|seeking|planned|targeting|raising|rumou?red|undisclosed)\b", text):
        return "Unverified"
    if re.search(r"\b(grant|support|stipend|subsidy)\b", text):
        return "Unverified"
    rounds = set()
    if re.search(r"\bpre[ -]seed\b", text):
        rounds.add("Pre-seed")
    if re.search(r"\bseed\b", re.sub(r"\bpre[ -]seed\b", "", text)):
        rounds.add("Seed")
    for series in re.findall(r"\bseries[ -]([a-z])\b", text):
        rounds.add({"a": "Series A", "b": "Series B"}.get(series, "Series C+"))
    if re.search(r"\bgrowth\b", text):
        rounds.add("Growth")
    return rounds.pop() if len(rounds) == 1 else "Other / review"


def lead_stage(item, profile=None):
    return funding_stage((profile or {}).get("stage") or item.get("funding_status"))
