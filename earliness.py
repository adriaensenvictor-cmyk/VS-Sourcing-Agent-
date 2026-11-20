"""Compare dated public evidence with the time the local engine saw a lead."""

from datetime import date

from early_sources import NOAH_SEED


COMPARISONS = {
    "baystartup:aithea": (
        {"label": "Crunchbase", "kind": "Database listing", "date": None,
         "url": "https://www.crunchbase.com/organization/aithea"},
        {"label": "Munich Startup", "kind": "Public directory", "date": None,
         "url": "https://www.munich-startup.de/en/startups/aithea-gmbh/"},
    ),
    "falling-walls:leitspalt": (
        {"label": "Dealroom", "kind": "Database listing", "date": None,
         "url": "https://app.dealroom.co/companies/leitspalt"},
    ),
    "falling-walls:linque": (
        {"label": "Dealroom", "kind": "Database listing", "date": None,
         "url": "https://app.dealroom.co/companies/linque"},
    ),
    "falling-walls:noah labs": (
        {"label": "Dealroom", "kind": "Database listing", "date": None,
         "url": "https://app.dealroom.co/companies/noah_labs_ug"},
        {"label": "Combination Ventures", "kind": "Investor announcement", "date": "2025-02-20",
         "url": NOAH_SEED},
    ),
}


def exact_day(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def public_trace(item, profile):
    early = item.get("earliest_verified_public_signal") or {}
    traces = [{"date": entry["observed_at"], "url": entry["url"], "label": entry["signal"]}
              for entry in profile.get("dated_signals", []) if entry.get("observed_at") and entry.get("url")]
    if early.get("date"):
        traces.append(early)
    # A year-only trace can be presented at its original precision.
    return min(traces, key=lambda event: event["date"], default={})


def comparison_days(first_seen, benchmark):
    captured = exact_day((first_seen or "")[:10])
    compared = exact_day(benchmark.get("date"))
    return (compared - captured).days if captured and compared else None


def recent_signal(item, profile, now):
    dates = [event.get("date") for event in item.get("timeline", []) if event.get("public_signal", True)]
    dates += [entry.get("observed_at") for entry in profile.get("dated_signals", [])]
    return any(0 <= (now - day).days <= 365 for stamp in dates if (day := exact_day(stamp)))


def comparisons(item):
    return COMPARISONS.get(item["id"], ())
