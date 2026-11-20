"""Capture explicitly attributed founder history from published biographies."""
import re


from founder_employers import EMPLOYER_ALIASES


# Prefer specific employers and full aliases over a shorter prefix like Siemens.
EMPLOYER_NAME = "|".join(re.escape(name) for name in sorted(EMPLOYER_ALIASES, key=len, reverse=True))
END_OF_NAME = r"(?![\w'’])"
EMPLOYMENT = re.compile(
    rf"\b(?:worked|was employed|spent [\w ]{{1,24}} years?) at\s+(?P<employer>{EMPLOYER_NAME}){END_OF_NAME}"
    rf"|\b(?:formerly|previously)\s+(?:an?\s+[\w -]{{1,36}}\s+)?at\s+(?P<former>{EMPLOYER_NAME}){END_OF_NAME}"
    rf"|\b(?:ex[-– ]|ehemals bei\s+|arbeitete (?:zuvor )?bei\s+|war zuvor bei\s+"
    rf"|a travaillé chez\s+|ancien(?:ne)? de\s+)(?P<alumni>{EMPLOYER_NAME}){END_OF_NAME}"
    rf"|\bformer\s+(?P<role_employer>{EMPLOYER_NAME})\s+"
    r"(?:engineer|researcher|trader|developer|scientist|employee|product manager|operator|consultant)\b",
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
                if not match or re.search(r"\b(?:never|denied|rumou?red|wants? to|hopes? to|nie|niemals|jamais)\b", sentence, re.I):
                    continue
                name_start = sentence.casefold().find(named[0].casefold())
                between = sentence[name_start + len(named[0]):match.start()]
                if name_start >= match.start() or not re.fullmatch(
                    r"[, ()]*(?:(?:who|was|is|had|has|also|previously|a|an) ){0,3}[, ()]*", between, re.I
                ):
                    continue
                reference = next(value for value in match.groupdict().values() if value)
                reference = (EMPLOYER_ALIASES[reference.casefold()] if label == "Previous employer"
                             else reference.strip(" ."))
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
