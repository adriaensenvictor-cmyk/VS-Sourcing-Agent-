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
