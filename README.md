# 💎 Hidden Gem — Find the founders before everyone else

A public-evidence-first pre-seed scout for **HTGF / MAIN Summit Hackathon 2026**.

**Team:** Matei · Mathia · Victor · Jinansh

## The goal

Spot German technology ventures from traces left **before their first VC round**.
Do not confuse an interesting GitHub repository with an investable startup; the engine
explicitly shows evidence, named-founder status, funding uncertainty and follow-up questions.

Three discovery adapters:
1. **TU Berlin startup ecosystem:** 2026 ventures, named teams and EXIST grants
   (university support is NOT equity financing).
2. **Hacker News Show HN:** projects with founder self-reported German location.
3. **GitHub:** recent technical builds with independently retrieved German profile locations.

The UI reports partial-source errors rather than inventing hits. The snapshot mode is
separately labelled *manually researched reference cases* and never passed off as a live scan.

## Run in five minutes

Requires Python 3.10+.

~~~bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
~~~

Optional: set a GitHub API token for a larger rate allowance: \`export GITHUB_TOKEN=...\`
(DO NOT commit your token or paste it into a demo).

Choose **Live discovery** and press **Run sourcing engine**.
The dashboard opens on **Verified research snapshot**, with Germany and an age limit of three years selected.
Choose **Other Europe** to inspect Constellate Proteomics, a Dutch historical case. Open its Timeline and reveal
the later coverage to compare the conference mention with the funding story. Simra AI, TerraTask and Jouly are
German reference cases. All four are curated. Enable **Include companies with unverified age** to review TerraTask.

Use the shortlist during screening and download the queue before closing your browser session.
The source exports retain the engine's original fields. Each dossier shows additional sourced profile details.
The Sources section links to European research and filing directories for manual follow-up.

The Analyst brief tab works offline with linked source excerpts. For optional AI summaries, set
`OPENAI_API_KEY` in the Streamlit server's environment before starting the app. Keep the key out of source control.
In the tab, submit a question or leave it blank for an overview. The button sends the question, company name
and selected public excerpts to OpenAI and uses the server account's API credits.

## Tests

~~~bash
python -m unittest discover -s tests -v
python -m compileall -q engine.py app.py
~~~

GitHub Actions runs these offline checks on pushes and PRs.

## What the score means — and does not mean

The deterministic score adds named team, German geography, relevant technology,
prototype evidence, research, explicit pilot/customer wording, and recent public traces.
It penalizes homework, agencies and hobby-language noise. Unidentified founder cases
are capped at 68/100. Every score component and evidence URL is inspectable.

**Score != success likelihood.** **No funding announcement != unfunded.** **EXIST != VC equity.**
**Directory cohort year != company incorporation date.** Press/database lead-time is
unknown until someone checks records and documents the comparison.

## Recommended 3-minute demo

- 0:00–0:25: Why HTGF needs to meet teams before funding announcements.
- 0:25–1:15: Trigger a **live** scan and show links, filter, scoring and a source warning
  if one source blocks automated access.
- 1:15–2:15: Open a lead dossier, evidence ledger, founder fit and potential disqualifiers.
- 2:15–2:45: Verify one standout case with independent contemporaneous sources.
  If using the reference snapshot, disclose that it is curated; never call it a live find.
- 2:45–3:00: Explain scaling: add university directories, scheduled scans, timestamped
  snapshots and measured lead time versus common startup databases.

## Before submitting

BuilderBase: **project name + code matching the demo + 3-minute pitch video**.
Submission deadline **Saturday 21 November 2026, 10:30 CET (Maastricht)**.
Do not merge other branches without coordinating with teammates.

## Limitations and data use

TU Berlin may block automated HTTP requests; it is reported as an error, not silently
replaced with sample data. GitHub queries are rate-limited, and Show HN has sparse
German-location disclosures. Candidate ranking is a shortlist for **human due diligence**,
not automated financial advice or permission to scrape private data. Respect third-party
terms of use; no unsolicited outreach automation is included.
