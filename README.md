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

## Founder–Venture Fit

The queue and shortlist still use the original six-part Founder Emergence calculation, now displayed as **Early Signal Score**. New runs include the additive alias `early_signal_score` and a separate `founder_venture_fit` object on each candidate. Both travel with the JSON and CSV exports. Archived JSON is exported as originally recorded. The dashboard can evaluate its available evidence using the archived run date.

**Reading the assessment.** Both axes measure documented strengths on a 100-point rubric. Founder budgets are domain expertise 20, relevant achievements 15, technology built 20, operating or entrepreneurial experience 20, complementary capabilities 10 and research contributions 15. Venture budgets are problem significance 15, differentiation 15, market opportunity 15, feasibility 20, commercial path 15 and customer validation 20. A student's delivered technology or research can qualify on exactly the same terms as an experienced operator's. A university, employer, academic title, founder name or GitHub star count alone earns zero points.

A criterion earns its budget once when supported. Explicit limiting evidence earns zero and is recorded separately. Opposing observations suspend that criterion and the combined judgment pending review. Missing evidence stays open. An entirely unassessed axis is null. A partially documented axis gives a lower bound on supported criteria. Coverage and citations explain how to read it.

| Evidence pattern | Fit assessment |
| --- | --- |
| Both axes reach 70 | Strong on both dimensions. Use the stronger axis plus 10, capped at 100. |
| One axis reaches 70 | Founder-led or venture-led review at the stronger score, even when the other axis is unknown. |
| Neither reaches 70, fewer than three criteria assessed on either side | Insufficient evidence. Combined score is null. |
| Both axes at most 35 with sufficient coverage | Low priority on reviewed evidence. Use the weaker score. |
| Other sufficiently assessed cases | Developing fit. Use the weaker score to prioritize diligence. |

The budgets and thresholds are hackathon diligence heuristics. They have no calibration against HTGF decisions or investment outcomes. Source confidence remains the legacy evidence-quality score out of ten. Fit coverage counts reviewed criteria and does not measure source independence. Several strengths may rely on one team's own account. Verify them before outreach.

**Evidence intake.** The evaluator consumes verified typed project claims and an optional `fit_evidence` list on a source record. A reviewed observation has `criterion`, `text`, `source_url`, `status: verified` and optionally `direction: supports|limits`, `subject`, `reviewed_on` and `date`. Founder observations require an attributed person or named team. The small public-source review in `research/fit_evidence.json` matches exact university profile URLs and records the review date. It supplies attributed research, operating experience, technologies built and venture evidence. LinkedIn profiles are never fetched by this layer. Keyword hypotheses and unsupported biographies stay outside the assessment.

**Three-year review.** Supply an explicitly sourced `legal_formation` fact with an exact ISO date or a sourced `unincorporated` observation. The third calendar anniversary is included. Leap-day anniversaries use the last day of February. Missing, conflicting or future dates require verification. Grants, cohort years, repository timestamps and registration publication notices alone cannot establish founding. University candidates with unresolved legal age receive a separate review flag. Age and fit are advisory and leave the original shortlist intact.

**Optional AI diligence.** Set `OPENAI_API_KEY` in the launch environment and click **Generate AI diligence assessment** in a dossier. The dashboard sends up to 30 cited public excerpts to OpenAI once per assessment per session. The model selects a diligence focus, an existing evidence ID and a follow-up question using strict JSON. The UI renders the original excerpt and URL separately. It accepts no generated biographies or numerical scores. Without credentials, on network failure or after a refusal, the deterministic assessment remains available.

## Secondary-school project watchlist

Open **Student projects** in the Streamlit sidebar. The initial view loads five reviewed dossiers offline: AeroOne, Heuwind Lagertechnik, Moore UB, LIPIGO and GlioScope. Each gives the school country, source-linked evidence and one follow-up question. Use **Check public school and event sources** for fresh listings, then disable **Reviewed dossiers only** to inspect newly discovered teams. JSON export includes the full watchlist and source diagnostics.

~~~sh
python founder_sourcing.py --student-watchlist --snapshot
python founder_sourcing.py --student-watchlist > students-first.json
python founder_sourcing.py --student-watchlist --previous students-first.json > students-next.json
~~~

A live run reads five public sources: the Baden-Württemberg regional student-company results, JUGEND GRÜNDET finalists, Gen-E upper-secondary awards, the Bruchsal school's Heuwind news feed, and the Košice school's news index for LIPIGO. Competition adapters cover the linked 2026 editions. Update the roster URLs and selectors for later editions. School news monitoring is bounded to those two schools; the Košice index shows its current page. German roster entries require identifiable secondary-school wording. School country describes affiliation; company headquarters, legal formation and equity funding require separate evidence.

Run again with a previous live export to identify newly listed projects or follow-up articles. The first run sets the baseline. Earlier observations retain their last-seen dates during source failures. The dashboard compares successive refreshes in the current session. The CLI can run under an existing scheduler. Exit status is nonzero if every live source fails, and reviewed dossiers are still exported.

Reviewed evidence distinguishes awards, competition listings, pitches, source-reported customer work and scheduled events. Live listings are research observations, with first/last observation timestamps separate from published dates. An award or new article never assigns commercial traction, investment eligibility, or a score. Dated school announcements can precede public awards: for Heuwind the dossier includes the school's March Berlin pitch report and July coverage of the national win.
