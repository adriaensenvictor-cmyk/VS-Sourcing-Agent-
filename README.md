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

Choose **Live discovery**, select sources, and click **Run sourcing engine**. The lookback controls Show HN. TUM and TU Berlin use their current public directories, and GitHub uses its bounded search windows. Start with the shortlist, or turn off the shortlist filter to inspect excluded and lower-confidence candidates. The table and dossier show funding status, original sources, score components, evidence confidence and dated traces. JSON exports keep the shared contract and CSV exports provide a screening view.

**Verified research snapshot** loads the original manually researched examples for Simra AI, TerraTask and Jouly. The UI and exports label this mode. The independently captured PR #3 shortlist is in `research/founder-shortlist.json`.

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
4. The shared JSON envelope provides `schema_version`, `mode`, `generated_at`, `source_status`, `candidates`, `shortlist` and `manual_review`. Dashboard labels derive from this record without reranking. The older radar JSON array remains available. See [RADAR.md](RADAR.md).

Source failures are reported independently. Public directories, repository samples and funding reviews have limited coverage. The TUM autonomous-trucks announcement is a reviewed public reference, and its EXIST application does not establish a grant award. Comparing lead time against other databases requires a dated baseline. Founder Emergence scores prioritize review and do not estimate investment returns. Verify public evidence before outreach.

For the demo, run a live scan, open a lead's evidence and timeline, and explain its funding-review scope. Use the labelled snapshot if live sources are slow or unreachable.
