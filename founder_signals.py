"""Capture explicitly attributed founder history from published biographies."""
import re


EMPLOYERS = (
    "Goldman Sachs", "Jane Street", "Deutsche Bank", "Bloomberg", "Google DeepMind",
    "DeepMind", "Google", "Microsoft", "Amazon", "Meta", "NVIDIA", "ASML",
    "Airbus", "Siemens", "Bosch", "SAP", "Stripe", "Revolut",
)
EMPLOYER_NAME = "|".join(map(re.escape, EMPLOYERS))
EMPLOYMENT = re.compile(
    rf"\b(?:worked|was employed|spent [\w ]{{1,24}}) (?:at|with)\s+(?P<employer>{EMPLOYER_NAME})\b"
    rf"|\b(?:formerly|previously)\s+(?:an?\s+[\w -]{{1,36}}\s+)?at\s+(?P<former>{EMPLOYER_NAME})\b"
    rf"|\b(?:ex[-– ]|ehemals bei\s+|arbeitete bei\s+)(?P<alumni>{EMPLOYER_NAME})\b",
    re.I,
)
PRIOR_COMPANY = re.compile(
    r"\b(?i:(?:previously|earlier) (?:co[- ]?)?founded|(?:co[- ]?)?founded and sold|(?:was (?:the |a )?)?co[- ]founder of|gründete zuvor) "
    r"(?P<company>[A-Z][\w&.-]*(?: [A-Z][\w&.-]*){0,3})"
)
HISTORY_LABELS = {"Previous employer", "Previous startup"}


def founder_history(title, names, excerpts, url):
    """Return attributed source excerpts. A bare brand mention never qualifies."""
    signals = {}
    for excerpt in excerpts:
        for sentence in re.split(r"(?<=[.!?;])\s+", excerpt):
            if not sentence or len(sentence) > 550:
                continue
            named = [name for name in names if name and re.search(
                r"(?<!\w)" + re.escape(name) + r"(?!\w)", sentence, re.I
            )]
            if len(named) != 1:
                continue
            for pattern, label in ((EMPLOYMENT, "Previous employer"), (PRIOR_COMPANY, "Previous startup")):
                match = pattern.search(sentence)
                if not match or re.search(r"\b(?:never|denied|rumou?red|wants? to|hopes? to)\b", sentence, re.I):
                    continue
                name_start = sentence.casefold().find(named[0].casefold())
                between = sentence[name_start + len(named[0]):match.start()]
                if name_start >= match.start() or not re.fullmatch(
                    r"[, ()]*(?:who |had |has |also |previously )?[, ()]*", between, re.I
                ):
                    continue
                reference = next(value for value in match.groupdict().values() if value).strip(" .")
                if reference.casefold() == title.casefold().strip():
                    continue
                key = (label, named[0], reference.casefold())
                signals[key] = {"signal": label, "excerpt": sentence,
                                "subject": named[0], "reference": reference, "source_url": url}
    return list(signals.values())


def track_record(item):
    """Combine live snippets and reviewed biographies for the selected dossier."""
    records = [entry for entry in item.get("evidence", []) if entry.get("signal") in HISTORY_LABELS]
    for fact in item.get("founder_venture_fit", {}).get("evidence", []):
        if subject := fact.get("subject"):
            # Reviewed facts already attribute the excerpt to this person.
            surname = subject.rsplit(" ", 1)[-1]
            matches = founder_history(item["name"], [surname], [fact["text"]], fact["source_url"])
            records.extend({**entry, "subject": subject} for entry in matches)
    return list({(e["subject"], e["signal"], e["reference"].casefold(), e["source_url"]): e
                 for e in records}.values())
