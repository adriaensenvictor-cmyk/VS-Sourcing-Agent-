# First Trace

First Trace is an evidence-first startup discovery dashboard for the HTGF Venture Capital Challenge. It surfaces German and European founding teams that merit closer review.

**Team** · Matei · Mathia · Victor · Jinansh

## Run the dashboard

Python 3.10+.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Choose **Live discovery**, select sources, and click **Run sourcing engine**. The lookback controls Show HN. TUM and TU Berlin use their current public directories, and GitHub uses its bounded search windows. Start with the shortlist, or turn off the shortlist filter to inspect excluded and lower-confidence candidates. The table and dossier show funding status, original sources, score components, evidence confidence and dated traces. The dossier distinguishes the age of the earliest public trace from the unknown company age. JSON exports keep the shared contract. CSV exports include the screening fields and JSON-encoded source URLs, founder evidence, claims, timeline, and funding review. The additional CSV columns are additive.

**Verified research snapshot** loads the original manually researched examples for Simra AI, TerraTask and Jouly. The UI and exports label this mode. The independently captured PR #3 shortlist is in `research/founder-shortlist.json`.

## Scout workflow

In **Screening**, filter by geography, company age, funding, and sector. Give a lead a **Meet**, **Watch**, or **Pass** decision with a reason. Live decisions and saved evidence appear in **New since review**. **Historical replay** presents a curated case with later evidence revealed after the scout makes a call.

The desk stores its own workflow state. Run `python scout_inbox.py` to refresh it outside Streamlit. The scanner and dashboard use `FIRSTTRACE_DB_PATH` or `~/.firsttrace/scout-workflow.sqlite3`. For the optional sourced OpenAI brief, provide `OPENAI_API_KEY` to the dashboard process. The written brief and downloads are usable offline. A model call occurs when the analyst explicitly submits a question.

In **LinkedIn scouting**, open a targeted search in LinkedIn and save a public founder
announcement with its permalink and your own summary. The next dashboard or n8n scan
includes these records under **LinkedIn (analyst submissions)**. This source keeps the
scout’s assessment distinct from independently verified evidence. The [former-employer
catalogue and its sources](research/founder-employers.md) power the search presets and
prior-employer detection.

See the [competitive review, demo sequence, and n8n runbook](research/scout-workflow.md).
The dossier uses the reviewed, deterministic founder–venture fit and legal registration evidence
from [Victor's PR #6](https://github.com/adriaensenvictor-cmyk/VS-Sourcing-Agent-/pull/6).
The evaluation uses 60 points for the team and 40 for the project, based on documented evidence.
The score is provisional while some criteria remain open. A missing axis or conflicting evidence
leaves the overall grade pending. Germany comes first, then the evaluation score, with early
signals breaking ties or ordering pending candidates. The same eligibility rules govern shortlisting.

Live discovery also reads UnternehmerTUM Incubator, imec.istart, the BayStartUP
2026 roster, Fraunhofer AHEAD, SpinLab, RootCamp and HPI Engine. The **Incubators
in Germany** workspace indexes public German centre listings. **Early follow-up
only** shows sourced projects with product and traction details still to verify. Open **All locations** to review records that lack location
evidence. See [source coverage and founder signals](research/incubator-coverage.md)
for limits and additional programmes. The [exact discovery and scoring rules](research/discovery-rules.md) are documented in French.

## Run the engine and tests

```sh
python3 emergence.py --tu-berlin --github-limit 4 --limit 10 > founder-shortlist.json
python3 radar.py --json --limit 10
python3 -m unittest discover -v
python3 -m unittest discover -s tests -v
```

Optional environment variables for GitHub API quota are `FOUNDER_RADAR_GITHUB_TOKEN` or `GITHUB_TOKEN`. The CLI also accepts `--search-funding` with `BRAVE_SEARCH_API_KEY`. Credentials stay in environment variables. The dashboard uses the existing source-backed reviews and does not trigger Brave searches automatically.

## Evidence and scoring

1. TUM Venture Labs and Show HN use the existing main-branch collectors. TU Berlin adapts the public venture directory and carries through published team and grant evidence. GitHub searches recent repositories and samples linked commit and release metadata.
2. Qualification carries source URLs, founder evidence, claims, dated events and public funding reviews. Identity uses declared project URLs or specific GitHub repositories. GitHub profile location does not establish startup location. A directory cohort year is not an incorporation date.
3. The Founder Emergence score weighs technical execution, founding team, commercialization, early-stage signals, market evidence and evidence quality. Shortlist eligibility is evaluated separately, with funded and later-stage companies excluded. A public grant is tracked separately from an equity round. `no_funding_found` identifies a scoped review, and `unknown` calls for diligence.
4. The shared JSON envelope provides `schema_version`, `mode`, `generated_at`, `source_status`, `candidates`, `shortlist` and `manual_review`. The dashboard applies the same evaluation order to stored runs. The CSV includes the new evaluation alongside the original signal score. The older radar JSON array remains available. See [RADAR.md](RADAR.md).

Source failures are reported independently. Public directories, repository samples and funding reviews have limited coverage. The TUM autonomous-trucks announcement is a reviewed public reference, and its EXIST application does not establish a grant award. Comparing lead time against other databases requires a dated baseline. Founder Emergence scores prioritize review and do not estimate investment returns. Verify public evidence before outreach.

For the demo, run a live scan, open a lead's evidence and timeline, and explain its funding-review scope. Use the labelled snapshot if live sources are slow or unreachable.
