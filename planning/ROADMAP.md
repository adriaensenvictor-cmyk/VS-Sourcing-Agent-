# Overnight roadmap and copy-ready prompts

FirstTrace already works. A live scan and a replay each return 152 projects, 35 inbox leads and 7 held leads. Tests pass, and the report is a single offline HTML file. The deadline is BuilderBase **Saturday 21 November 2026, 10:30 CET**, with the upload targeted for 10:00. Every step below adds to the existing repository and keeps the demo shippable after each merge.

Required by the brief (HTGF one-pager, MAIN pages 21–22, BuilderBase p. 10): a working engine that finds real leads, one best find with its signals and why HTGF should meet the team, a project name, the exact demo code and a 3-minute video. The jury scores **lead quality, earliness, creativity of signals, technical execution and scalability**. Each step names the criterion it serves.

## The idea that ties it together: "Proof of earliness"

Right now, earliness is one hand-picked comparison (Valuemize, 874 days). The biggest gain is to **measure it for every lead automatically, with free, dated, public sources**:

| Signal | What it proves | Free source | Honest label |
| --- | --- | --- | --- |
| First TLS certificate for the company domain | The website went live (an `app.` or `beta.` subdomain suggests a product) | crt.sh JSON (`?q=domain&output=json`, earliest `not_before`) | "Certificate issued", not launch |
| First Wayback capture of the company site | Public web presence existed by this date | Wayback CDX (`limit=1`) | "Archived by", not created on |
| **First Wayback capture of the Dealroom/Crunchbase page** | The latest date by which the database listed the company | Wayback CDX on the database URL | "Database page archived by". The listing may be earlier, so lead time is an upper bound |
| First Hacker News mention of the domain | First developer-community visibility | HN Algolia API | Dated post |
| GitHub org created / first release | Shipping cadence | GitHub API (already used) | Publication date |
| First "founding engineer" job post | Hiring before the round | Public Personio XML feed `{company}.jobs.personio.de/xml` | Currently open jobs only |

The headline line in the UI and pitch becomes: **"First public trace 19 Apr 2025 → database page first archived DD MMM YYYY: up to N days ahead."** This exact wording is honest and directly answers "how early compared to common databases?".

The demo's "wow" moment is a **time-machine slider**. Drag it back to 2025, and Bevel lights up from its release while the database marker stays grey. This is the `--as-of` logic you already have, moved into the browser.

---

## Paste this preamble at the top of every Codex / Claude Code prompt

```text
Repo: FirstTrace (HTGF "Find the Founders Before Everyone Else", MAIN Summit). Read README.md, AGENTS.md, planning/BUILD.md and planning/ROADMAP.md first; follow AGENTS.md strictly.
Hard rules:
- Python standard library only (no pip installs) so `python3 scout.py` runs anywhere; the report stays one self-contained offline HTML file built by report.py from ui/.
- Never invent facts. Missing values stay missing and render as "Unverified"/"Unknown". Every displayed fact carries a source URL and a date type (published / observed / archived-by / certificate-issued).
- Never infer founders from contributors, funding from a grant, or adoption from stars. Analyst decides contact.
- Replay must stay visibly labeled; new live data must be captured into the snapshot so replay shows it offline. Legacy snapshots must still replay.
- Network calls: timeouts, bounded pages, errors reported in source_status, never crash the scan.
- Add/extend offline tests in tests/test_firsttrace.py (no network in tests). Run: python3 -m unittest discover -s tests -v ; python3 scout.py --replay data/demo-snapshot.json --output report.html ; and a live run if you touched ingestion.
- Work on the named branch below. Keep the change narrow; don't reformat unrelated code. Finish with the PR handoff: Changed / Verified / Evidence / Next.
```

---

## Clock (CET) and owners

| Time | Step | Owner | Tool | Must / Should / Could |
| --- | --- | --- | --- | --- |
| now → +30 min | 0. Safe baseline | Integration | git | Must |
| +0.5 → +3.5 h | 1. Footprint signals (backend) | Ingestion | Codex | **Must** |
| +0.5 → +3.5 h | 2. Time machine + timeline UI | Product | Codex | **Must** |
| +0.5 → +3.5 h | 3. Verify domains + database URLs for top 8 | Research | human + ChatGPT/Claude | **Must** |
| +3.5 → +5.5 h | 4. Transparent score + noise filter | Ingestion | Codex | Must |
| +3.5 → +5.5 h | 5. Command bar, keyboard triage, dossier | Product | Codex | Should |
| +3.5 → +5.5 h | 6. AI corroboration (OpenAI) | Research | Codex | Should |
| +5.5 → +7.5 h | 7. Continuous run: digest JSON + GitHub Actions | Integration | Codex | Should |
| +5.5 → +7.5 h | 8. n8n alert + ElevenLabs audio brief | Integration | n8n, ElevenLabs | Could |
| **02:00** | **Scope freeze**, final snapshot, Claude Code review | all | Claude Code | Must |
| 07:00 → 09:30 | Rehearse, record, voice-over fallback | Presentation | ElevenLabs optional | Must |
| 09:30 → 10:30 | Freeze SHA, upload, verify playback | Integration | BuilderBase | Must |

Rule: if a step is not merged and green by its slot end, drop it. Never cut steps 0–3.

---

## Step 0. Safe baseline (human, 15 min)

Commit the current working tree on a branch, run tests, live and replay, and tag it `demo-safe-v1`. From now on, every merge must still run `python3 scout.py --replay data/demo-snapshot.json`. If anything breaks at 9 a.m., record from this tag.

```sh
git switch -c integration/baseline && git add -A && git commit -m "Baseline before overnight sprint"
python3 -m unittest discover -s tests -v && python3 scout.py --replay data/demo-snapshot.json --output report.html
git tag demo-safe-v1 && git push -u origin integration/baseline --tags
```

## Step 1. Footprint signals (Codex, branch `ingestion/footprint`)

*Earliness + creativity of signals + scalability*

```text
[PREAMBLE]
Branch: ingestion/footprint
Goal: add automatic, dated "footprint" evidence and a database-lag measurement for analyst-reviewed leads.
1. Data contract: in data/assessments.json "stages", allow optional "domain" (e.g. "bevel.software") and "databases": [{"label": "Dealroom", "url": "..."}]. Only leads with an explicit domain get footprint lookups (identity comes from the analyst, never from name matching).
2. New module footprint.py (stdlib, reuse sources.fetch with its retry/timeouts). For each domain, run these lookups:
   - crt.sh: https://crt.sh/?q=<domain>&output=json -> earliest not_before; also earliest cert whose name starts with app./beta./api./docs. -> "product subdomain".
   - Wayback CDX: https://web.archive.org/cdx/search/cdx?url=<domain>&output=json&limit=1&fl=timestamp,original -> first archived capture of the site.
   - For each database URL: same CDX query -> "database page archived by" date (or none).
   - HN Algolia: https://hn.algolia.com/api/v1/search_by_date?query=<domain>&restrictSearchableAttributes=url&hitsPerPage=1 with ascending check -> earliest HN post linking the domain (title, url, created_at).
   Each result row: {kind, label, date, date_type, url, source}. Use date_type values: "certificate-issued", "archived-by", "published".
   Cap total footprint requests per scan (e.g. 40), 10 s timeout, and record per-source state in source_status["footprint"] = {"state": fresh|partial|failed, "count": n}. Failures add to errors, never abort.
3. In scout.discover(), attach project["footprint"] = [...] and include it in the snapshot so --replay shows it offline. --as-of must drop footprint rows dated after the cutoff. history.record_scan should record footprint rows as kind "footprint" so "New signals" works.
4. Earliness: compute per lead earliest_trace = min(dated traces, releases, footprint excluding database rows) and database_seen = earliest database archived-by date. If both are present, lead_days = database_seen - earliest_trace, labeled "up to N days before <db> page was first archived". If database_seen is missing, return "No archived database page found (checked <urls>)". Never compute from undated evidence.
5. Tests with canned JSON fixtures (no network): earliest-date selection, missing database, cutoff filtering, legacy snapshot without footprint still replays.
6. Run a live scan with --snapshot data/demo-snapshot.json only after Research has filled domains (coordinate); otherwise keep the old snapshot and show the replay works.
```

## Step 2. Time machine and evidence timeline (Codex, branch `product/time-machine`)

*Technical execution + earliness, and the demo's hero moment*

```text
[PREAMBLE]
Branch: product/time-machine. Touch only ui/report.js, ui/report.css, ui/report.html (and report.py only if the payload needs a field).
Design references: apple.com product pages (one focal point, huge confident type, generous whitespace, subtle motion, sticky local nav) and openai.com (monochrome, single input, suggestion chips). Keep current IDs and features working.
1. Evidence timeline in the lead detail: a horizontal track from the earliest dated trace to today. Dots are colored by type: campus/competition trace, GitHub release, certificate, Wayback, HN, funding, plus a distinct hollow marker for "database page archived by". Hovering or focusing a dot shows the label, date type and source link. Under it, one big number: "Up to 412 days before Dealroom" or "Database lag unknown". Use plain SVG/CSS, no libraries.
2. Time-machine slider in the hero: a date range input from the earliest evidence date to today, with month ticks. Moving it filters, client-side, to evidence dated <= the slider date. Undated evidence and current analyst assessments are hidden in this mode, mirroring scout.apply_cutoff. The banner reads "Viewing public traces as of <date>. Identities were reviewed later." Leads with zero evidence fade out with a short animation. Add a "Play" button that animates from earliest to today in ~6 seconds for the video.
3. Respect prefers-reduced-motion, keep keyboard access (arrow keys on the slider), and keep the mobile layout stacked at 390 px.
4. Verify in a browser: replay report, drag to 2025-05-01, and confirm Bevel shows the release while the database marker is absent. Capture before/after screenshots for the PR.
```

## Step 3. Research: make the footprint real (human, with ChatGPT/Claude as cross-checkers)

*Lead quality.* This step is what turns Step 1 from code into evidence. For the top 8 leads (Bevel, Venedy, Patalyze, Meda AI, Micro Factory, Cebellum, DeepMask, ESG-X), add to `data/assessments.json`:

- `domain`: only from the team's own site, linked from an official source (roster, university page).
- `databases`: the exact Dealroom / Crunchbase / CB Insights / Startbase URLs you checked, including any where nothing was found (keep the note).
- `team`, `location` (German base?), product stage and funding status, each with a URL.

Use this prompt in ChatGPT (web search on) or Claude to cross-check, then verify every link yourself:

```text
You are a VC sourcing analyst for HTGF (pre-seed/seed, German HQ, digital tech). For the company "<NAME>" (official source: <ROSTER URL>):
1) its official website domain, 2) named founders with a primary-source URL each, 3) German operating base with URL, 4) any public equity round (date, amount, investor, primary announcement URL) — distinguish grants/EXIST/competition prizes from equity, 5) Dealroom/Crunchbase/Startbase URLs if they exist, 6) one sentence on who the buyer is.
Rules: cite a URL for every claim; write "not found" instead of guessing; flag name collisions with other companies; do not use LinkedIn-only claims as founder evidence.
```

Then pick the **best find** using the HTGF lens: a German base, a named technical team, a shipped artifact, no confirmed equity and the earliest trace well before any database page. If a lead beats Bevel on "pre-equity and more recent", it becomes the pitch lead (as DEMO.md already says).

## Step 4. Transparent score and noise filter (Codex, branch `ingestion/score`)

*Lead quality + filtering the noise (an explicit HTGF tip)*

```text
[PREAMBLE]
Branch: ingestion/score. Coordinate: this touches build_inbox() in scout.py — Product must not edit scout.py meanwhile.
Replace the opaque "evidence" count with an explainable score. Each point is a named, sourced receipt:
+ Team identified (team URL)  + German base confirmed  + Shipped artifact (release / product subdomain cert / launched)
+ Multi-source (≥2 independent traces)  + Fresh (first trace < 12 months)  + No confirmed equity (funding Unverified or Pre-equity)  + Hiring signal
- Noise: student assignment / club / agency / thesis wording, consulting "we build apps for you" language, or a confirmed Series A+ (hold with reason "Already funded — too late for first-round access")
Output lead["score"] = {"total": n, "receipts": [{"label", "points", "url"}]} and sort held last, then score desc, then name. Keep "Core fit/Adjacent/Unreviewed" as a visible label.
UI (minimal): show the score as "5 signals" with an expandable "Why this lead" list of receipts, each linking its source.
Add tests for each receipt and for agency/assignment holds using small fixtures. Report how many of the 152 projects move to Held vs before, in the PR.
```

## Step 5. "Fast as Spotlight" interaction layer (Codex, branch `product/command-bar`)

*Product experience, which wins the 5-second test in BUILD.md*

```text
[PREAMBLE]
Branch: product/command-bar. ui/ files only.
1. Single "Ask FirstTrace" bar (OpenAI-style): parse plain language locally — no API — into existing filters, e.g. "pre-seed devtools in munich", "new this week", "has release", "unverified funding", "held". Show the parsed chips under the input so the analyst sees exactly what was understood; Enter applies, Esc clears. Keep "/" to focus; add ⌘K / Ctrl+K.
2. Keyboard triage: J/K next/previous lead, W watch, P pass, V needs verification, O open primary source, ? shows a shortcut sheet. Toast confirms each action with Undo.
3. "Meeting dossier" button: a print-optimized one-page view (@media print) of the selected lead with team, signals timeline, receipts, what is unverified, three first-call questions, and all source URLs with date types. Header: "Prepared by FirstTrace · replay/live · observed <time>".
4. Copy "First-contact draft" button: generates a short, polite email draft from the dossier facts only (no claims beyond sources), copied to clipboard, labeled "Draft — analyst decides whether to send".
5. Dark mode via prefers-color-scheme, focus rings visible, contrast AA. Verify at 1440 px and 390 px; attach screenshots.
```

Codex tip: for UI tasks, run 2–3 parallel attempts in Codex cloud and merge the cleanest one. Ask Claude Code to review the diff (Step 9 prompt).

## Step 6. AI corroboration with receipts (Codex, branch `research/ai-corroboration`)

*Scalability (removes the slowest manual step) + technical execution*

```text
[PREAMBLE]
Branch: research/ai-corroboration. New file corroborate.py; do not change scout.py's default behavior.
`python3 corroborate.py --top 10` reads the latest snapshot, and for each unreviewed or Unverified lead calls the OpenAI Responses API (urllib, key from env OPENAI_API_KEY, never logged or committed) in TWO calls:
  (a) plain-text call with tools=[{"type":"web_search"}] asking for founders, German base, product stage, equity rounds, database pages — keep url_citation annotations;
  (b) structured-output call (JSON schema) over the cited text only. Every field = {value, url, quote} or null. A field without a URL that appeared in (a)'s citations is dropped.
Write data/ai_suggestions.json keyed by project id with model name, timestamp and the citations. It NEVER writes assessments.json.
The report shows suggestions in a distinct dashed style labeled "AI suggestion — not verified" with Accept / Reject buttons. Accepted suggestions are exported as a JSON patch the analyst pastes into assessments.json (keep the human in the loop and the provenance).
Budget: max 10 leads per run, print token usage. Without a key the script exits cleanly with a message. Tests mock the HTTP layer.
Measure in the PR: for 5 leads, minutes of manual research vs. time to review suggestions, and how many suggested facts survived checking.
```

## Step 7. Continuous engine: digest JSON and a nightly runner (Codex, branch `integration/continuous`)

*Scalability: "could it run continuously?"*

```text
[PREAMBLE]
Branch: integration/continuous.
1. Add `--digest PATH` to scout.py: writes JSON {observed_at, mode, new_signals: [{project_id, name, kind, label, date, date_type, url}], counts, source_status}. It is driven by history "changes", so identical reruns produce an empty list.
2. Add .github/workflows/scan.yml: daily cron (06:00 UTC) + workflow_dispatch; Python 3.11; runs tests, a live scan with --history .firsttrace/history.sqlite3 restored/saved via actions/cache, writes report.html + digest.json into a `site/` folder, uploads as an artifact. Keep it publishing nothing publicly by default; add a commented-out GitHub Pages deploy job the team can enable after deciding visibility.
3. README: "Run continuously" section (cron, cache, how to add a source adapter in one function + one test). Include parse counts and request budget per source.
4. Verify by running the workflow steps locally twice: the second digest must be empty, and must not duplicate alerts.
```

## Step 8. n8n and ElevenLabs layer (Could; time-box 90 min, only after steps 1–4 are merged)

**Architecture:** GitHub Actions (or a laptop) runs the scan → `digest.json` → **n8n** fetches it, writes a 60-second brief, sends it to the analyst channel, and calls **ElevenLabs** for an audio version. n8n never runs Python, which keeps it simple and reliable. Get the keys from BuilderBase Resources (OpenAI), Discord (ElevenLabs) and the shared n8n link.

**n8n workflow.** Paste this into n8n's AI workflow builder if your instance has it, or build the nodes by hand:

```text
Build an n8n workflow "FirstTrace Signal Brief":
1. Schedule Trigger: weekdays 08:00 Europe/Berlin (plus a Manual Trigger for the demo).
2. HTTP Request GET {{DIGEST_URL}} (the digest.json artifact/Pages URL). If new_signals is empty → stop (no alert spam).
3. OpenAI (or AI Agent) node, model with temperature 0.2, system prompt:
   "You write a 120-word briefing for an HTGF analyst. Use ONLY the JSON provided. For each new signal: company, what changed, date and date type, and the source URL. Never state a funding round, founder or traction not in the JSON. End with: 'Decide in FirstTrace whether to reach out.'"
4. HTTP Request POST https://api.elevenlabs.io/v1/text-to-speech/{{VOICE_ID}} (header xi-api-key from n8n credentials, body {text, model_id}) → binary mp3.
5. Send to Slack/Telegram/Email: the text brief + mp3 attachment + link to the report.
6. Error Trigger workflow → message "FirstTrace scan failed: <source_status>".
Test twice with the same digest: the second run must send nothing.
```

**ElevenLabs, three uses ranked by value:**

1. **Pitch voice-over fallback.** If a teammate's recording is rough at 8 a.m., generate narration from the DEMO.md script and keep the screen recording live. Tell the jury the voice is synthetic.
2. **"Signal Radio" audio brief**, as in the n8n step above. Put one 20-second clip at the end of the video ("every morning the analyst hears…"). Text-to-speech prompt:

   ```text
   [calm, confident] Good morning. FirstTrace found two new signals overnight.
   Venedy, Munich — nominated in the Munich business plan competition, published 2 March 2026; their site invites pilot customers. Funding is unverified.
   [short pause] Bevel — a new public release on GitHub. Their first public trace predates the earliest archived database page by up to <N> days.
   Open FirstTrace to decide who to call.
   ```
3. **"Ask the desk" voice agent** (stretch, only if everything else is done). An ElevenLabs Agent with one server tool `GET /leads?query=` that returns digest rows. Agent system prompt:

   ```text
   You are FirstTrace's sourcing desk for an HTGF analyst. Answer only from the get_leads tool results. Always say the date and whether it is a publication date or an archive date. If funding is not confirmed, say "funding unverified". Never recommend contacting a team; say "that's the analyst's call". Keep answers under 40 words.
   ```

   Skip it if it can't be shown in 15 seconds of video. Judges score the engine, not the voice.

## Step 9. Claude Code as reviewer and fact-checker (run after each merge and at freeze)

Paste into Claude Code:

```text
Review the diff of branch <X> against main for correctness bugs and for violations of AGENTS.md (invented facts, funding inferred from grants, unlabeled replay, secrets, network calls without timeouts, legacy snapshot breakage). Then run tests, a replay and a live scan and report the counts. List only concrete problems with file:line.
```

```text
Fact-check mode: for every URL in data/reviews.json, data/assessments.json and planning/DEMO.md, fetch it and confirm the page still supports the exact claim and date we attach to it. Output a table: claim | URL | status | supports claim? | fix. Do not edit data files; I decide.
```

```text
Devil's advocate as an HTGF partner: read the report payload for the top 5 leads and DEMO.md. Try to disqualify each lead (too late/funded, not German, agency, assignment, name collision, no team). Rank them by "would I take the meeting" and say what one check would change your mind.
```

## Step 10. Freeze, record, submit (from 02:00)

1. Merge only green branches into the recording branch. Capture the final live snapshot (`--snapshot data/demo-snapshot.json`), commit it, tag it `demo-final`, and write down the SHA.
2. Run the blind top-5 review (BUILD.md) and put the number on screen: "3 of 5 leads a second reviewer would meet."
3. Update DEMO.md narration with the measured lead-time numbers from Step 1. Use the exact phrasing "up to N days before the database page was first archived".
4. Record at 07:00 using this demo path: a live scan in the terminal → the hero time machine pressing **Play** → the best-find dossier → Venedy via the Ask bar ("pilot unverified funding") → **Watch** → one held lead with its receipt → the Actions run/digest and Signal Radio clip (5 s) → close on the best find.
5. Upload by 10:00. Check that the video plays, the repository is accessible at that SHA, and the BuilderBase receipt arrived.

## More outside-the-box ideas (only if time remains; each is a 45-minute experiment)

- **Pivot detector.** Diff the homepage `<title>`/hero text across Wayback captures. Bevel moved from legacy-code tooling to an agent control plane, and a visible pivot with continued shipping signals a team that persists.
- **Founder graph.** Show the same person across grant, competition, TUM project and GitHub (analyst-linked only). "Appears in 3 independent sources" is a strong team signal.
- **Warm-path hint.** Flag when a lead's university or programme (CDTM, UnternehmerTUM, EXIST) overlaps with HTGF portfolio founders' backgrounds, as a conversation opener rather than a claim.
- **Trademark watch.** A DPMA filing in the company's name precedes launches. DPMAconnectPlus needs a signed contract, so record DPMAregister links manually for the top leads only.
- **Research-to-company radar.** Search CORDIS/ERC Proof of Concept for German teams in AI/devtools, and follow each to an explicit spinout link.
- **Engine scorecard tab.** Show sources, parse counts, error rate, request budget, a precision@5 from blind review, and median "up to N days" lead time with coverage, so the scalability claim comes with numbers.
