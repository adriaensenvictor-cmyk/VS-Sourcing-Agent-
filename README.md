# FirstTrace

**Who should we call this week?** FirstTrace is a sourcing desk for HTGF's "Find the Founders Before Everyone Else" challenge (MAIN Summit 2026). It reads Bavarian university grants, every business plan competition roster, GitHub and each company's legally required German legal notice (Impressum), does the first research on every early team, and ranks them on HTGF's criteria with every point linked to its source.

## For the jury: run it in one minute

No installation and no API key. Pick one:

1. **Just look:** open [`FirstTrace-offline.html`](FirstTrace-offline.html) in any browser (double-click it). It is the complete site on the real scan captured on 20 November 2026, clearly labeled *Snapshot replay*: search, call list, lead briefs, exports. No Python needed.
2. **Run the live engine** (needs [Python 3.9+](https://www.python.org/downloads/) and internet):
   - macOS: double-click `run-mac.command` (the first time: right-click › Open), or run `python3 scout.py --serve`
   - Windows: double-click `run-windows.bat`, or run `py scout.py --serve`
   - Linux: `python3 scout.py --serve`

   Your browser opens at http://127.0.0.1:8765/. It shows the captured scan at once and runs a live scan of every source in the background (about a minute), then reloads with fresh data. Press **Run live scan** at any time to rescan; a second scan shows what changed under **New signals**.
3. **Check the tests:** `python3 -m unittest discover -s tests -v` (offline, no network).

Things to try: type *API security in Munich*, *Talking to investors now* or *Finalists, not funded yet*; open **Venedy** (our best find), **Bevel** (legal entity differs from the brand) and **CAELIA Health** (not incorporated yet); press **Weekly brief**, **Export to CRM** and **Copy outreach draft**.

## Run the desk

Python 3.9+ and a browser. Live mode uses public endpoints and needs no API key.

```sh
export GITHUB_TOKEN=...   # optional: raises GitHub's limit from 60 to 5,000 requests/hour
python3 scout.py --serve  # opens http://127.0.0.1:8765/
```

Press **Run live scan** to fetch every source again. The page reloads when the scan finishes (under a minute) and opens **New signals** when something changed since the previous scan.

What the analyst gets:

- **Ask in plain words.** "AI for medical practices", "API security in Munich", "Finalists, not funded yet", "Not incorporated yet", "Talking to investors now". The search reads roster and grant descriptions (German and English), company websites and legal notices, shows what it understood and highlights why each result matched.
- **This week's call list.** Leads with an open investment window, ranked by HTGF readiness: eight sourced checks (German base, company formed, people identified, digital tech fit, product signal, young enough for HTGF, independent validation, no equity round seen).
- **A one-page brief per lead**: why now, where the lead sits on the window (early traces → first round → everyone knows), automatic company research, evidence timeline and three first-call questions. **Copy outreach draft**, **Print brief**, **Weekly brief** (Markdown) and **Export to CRM** (CSV) turn it into the analyst's weekly workflow. Add `--every 6` to rescan automatically every six hours. The desk listens on 127.0.0.1 only and keeps its history in `.firsttrace/`.

Each scan reads:

- the UnternehmerTUM prototype-grant directory;
- every Munich and Nordbayern business plan competition roster linked from BayStartUP's news index (nominees, phase winners, finalists, winners). New rosters are picked up automatically. Teams that judges advance across rounds get a **Jury progression** badge, matched only within BayStartUP's own rosters;
- GitHub releases for analyst-linked repositories. If GitHub rate-limits the scan, the last successfully fetched releases stay visible and the source shows as incomplete;
- automatic company research: the company website and its legally required German legal notice (Impressum, § 5 DDG), giving the legal entity, register court and number, address, managing directors and whether the team is incorporated yet, plus website signals (pilot, beta, demo, pricing, customers, hiring, named investors, investor pages) with the exact quote. A website is only accepted automatically when its legal notice names the company and a matching city or German address; analyst-verified domains (`domain` in `data/assessments.json`) always win;
- a founder footprint for analyst-verified and researched company domains (`domain` in `data/assessments.json`): the first Internet Archive capture of the site (an archive date, not a launch date) and the first Hacker News post linking it.

## Run once from the command line

```sh
python3 scout.py --output report.html
open report.html
```

To rehearse offline or present during an outage, replay the captured live scan. The report labels the mode and original observation time.

```sh
python3 scout.py --replay data/demo-snapshot.json --output report.html
open report.html
```

To rebuild the jury's offline file from the capture, run `python3 scout.py --replay data/demo-snapshot.json --output FirstTrace-offline.html`. To capture a fresh snapshot, run `python3 scout.py --snapshot data/demo-snapshot.json`. Live scans record first-seen dates, new evidence and source status in `.firsttrace/history.sqlite3`. Run twice against the same database to establish and compare against a baseline. Use `--history path/to/history.sqlite3` for an isolated run. Replay reads the capture without touching scan history.

## Review leads

- Search by team, company, location or trace. Select multiple **Funding stage** or **Product stage** chips. Selections are OR within a group and AND across groups. Use **Unverified** where the stage is unknown. **Grant-backed** is a separate filter.
- Use **Watch**, **Pass**, or **Needs verification** to triage a lead. Open **Watchlist** and **Held** to revisit decisions. Saved searches and decisions live in this browser, so open the same report path to reuse them.
- **New signals** shows observations first recorded relative to an existing local baseline. **Change digest** exports new signals and source links matching the current filters. Identical reruns create no duplicate evidence.
- Use `--replay data/demo-snapshot.json --as-of 2025-12-31` to inspect dated public traces available by a chosen date. This retrospective view suppresses undated evidence and current assessments. The identities were reviewed using later material.

Competition rosters are discovered from the organizer's news index on every scan; the 2026 Phase 1 roster is always included. [Analyst reviews](data/reviews.json) and [stage and identity assessments](data/assessments.json) provide manual, linked corroboration. A grant, nomination, or public release alone does not establish a funding stage. Supported funding stages with no matching evidence show an empty list.

Run offline checks with `python3 -m unittest discover -s tests -v`.

## Team workspace

- [Product prompt, findings and three-minute demo path](planning/PRODUCT.md)
- [Overnight roadmap and prompts](planning/ROADMAP.md)
- [Prompt for Codex and Claude](planning/PROMPT.md)
- [HTGF research and concept selection](planning/RESEARCH.md)
- [18-hour build plan and team workflow](planning/BUILD.md)
- [Best find, validation and pitch](planning/DEMO.md)
- [Source map and product notes](planning/NEXT.md)
- [Agent instructions](AGENTS.md)
