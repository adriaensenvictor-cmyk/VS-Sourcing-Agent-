# German early-stage startup radar

Run from the repository with Python 3.9 or newer. TUM Venture Labs and Show HN still run live.

```sh
python3 radar.py --json --limit 10
python3 -m unittest discover -v
```

The JSON remains an array with the legacy lead fields. Use **funding.status** for the current qualification and **scores** for the five independent 0–5 assessments. Scores are rules for shortlisting, not predictions. A named founder, documented domain experience and evidence of execution matter. School prestige earns no points. The ranking places known funded leads after other leads.

- **founders** gives names and public source URLs. TUM's explicit founder field is extracted live. Reviewed cases also link to public LinkedIn profiles and official project information. Other leads retain a LinkedIn search link for manual review.
- **claims** contains a source URL and either `verified` for a reviewed fact or `hypothesis` for a machine-detected cue. A cue mentioning a pilot, hiring or waitlist can reflect an intention and should be checked against its linked source.
- **funding.status** is `funded` when a round is confirmed, `no_funding_found` when a scoped search yielded no announcement, and `unknown` when no check ran or the available evidence is ambiguous. Public grants and ambiguous financing are recorded separately. A negative search cannot establish that a company has never raised.
- **timeline** shows dated public events in chronological order. **earliest_verified_public_signal** is the oldest observed event in that timeline. It is null when none is available. A sitemap update is retained as page metadata.
- **sources** lists the discovery URLs merged by shared project URL or exact GitHub repository identity. The match does not rely on names. Public GitHub release enrichment checks up to three linked repositories per lead and requests up to 30 releases each. API errors can make the timeline incomplete.

Use `--source-json university.json` to import additional university or GitHub discovery records. Supply an array of records with `id`, `title`, `source_url`, and `evidence` entries containing `signal` and `excerpt`. Optional fields include `source`, `project_url`, `published_at`, `links.github`, and `links.linkedin`. Prefer linking the full GitHub repository URL or the exact project homepage.

For a live funding search, set `BRAVE_SEARCH_API_KEY` and run `python3 radar.py --search-funding --json`. Public search hits require review and are returned as leads for verification. Coverage is limited to public search results. LinkedIn links come from public sources and indexed pages reviewed during sourcing. The script makes no LinkedIn requests.

## Optional AI investment analysis

The optional evaluator accepts the current First Trace JSON envelope, a candidate array, or a single candidate object. It writes a separate AI report and does not change the shared candidate schema or scrape LinkedIn. The example uses the current discovery engine and limits the run to one candidate to control API use.

On Windows PowerShell, from the repository folder:

~~~powershell
$env:OPENAI_API_KEY = Read-Host "OpenAI API key"
python emergence.py --limit 1 --github-limit 0 | python ai_score.py - --output ai_evaluations.json
~~~

The key remains in the current PowerShell session; do not add it to a file or commit it. The evaluation calls the OpenAI Responses API and uses Structured Outputs. A default model can be changed with OPENAI_MODEL.

To compare against a fund profile, pass a JSON object containing the fund's known geography, sectors, stage, and exclusions:

~~~powershell
python ai_score.py candidates.json --investor-profile investor-profile.json --output ai_evaluations.json
~~~

If no investor profile is supplied, investor_fit remains unassessed. The investment score uses these weights: founder/team 25, technical differentiation 20, market opportunity 20, commercialization signals 15, venture intent 10, and investor fit 10. Each dimension is scored 0–5 only when the model cites a source URL present in the candidate dossier. Missing dimensions are excluded from the weighted average and reported through score_coverage; no total score is returned below 60% coverage.

The report separately includes early-stage confidence, evidence confidence, thesis, founder background relevance, positive signals, risks, missing information, Germany focus, and funding status. Funding is copied from the supplied qualification data. no_funding_found describes only the checked sources and never proves that a startup is unfunded. Responses are cached in a local SQLite file for seven days; use --no-cache to bypass the cache.

The evaluator only analyzes evidence supplied by the discovery pipeline or a reviewer. LinkedIn profile links remain pointers for permitted human review; the workflow does not request or scrape LinkedIn.

