# Product prompt: from a list of links to an analyst that does the first 25 minutes

## Whose job changes

Lena is an active sourcing analyst in HTGF's Digital Tech team in Munich. Every week she brings the investment managers a short list of teams worth a first call. Today she:

1. checks Dealroom and Crunchbase, which only show teams once they are already visible to every other investor;
2. scrolls university, competition and event pages by hand;
3. researches every name: website, Impressum, register entry, managing directors, what the product does, pilot or launch, funding news. That is 20–30 minutes and a dozen browser tabs per name;
4. copies what she found into the CRM and forgets to check back when a team moves forward.

The brief asks us to find founders "before everyone else" (MAIN p. 21) and to show "the team, not just the product" (HTGF one-pager). The bottleneck is not finding more names. It is the research per name and knowing *when* to call.

## What FirstTrace must do

Build the analyst's first 25 minutes into the engine, and change her week from "search and copy" to "decide and call".

1. **Ask in plain words.** One search box that understands a thesis such as "AI for doctors in Bavaria, not funded yet". It searches everything FirstTrace has read: roster and grant descriptions in German and English, company websites, legal notices and evidence titles. Show what it understood (place, stage, signals) and why each result matched.
2. **Automatic company research for every lead.** Find the company website, then read the legally required German Impressum. It gives the legal entity and form (GmbH, UG, "i.G." = being incorporated), the register court and number (proof of a German base), the managing directors named in the legal notice, and what the website says (pilot, beta, waitlist, demo, hiring, investors). Identity rule: an automatic match needs the company name in the Impressum *and* a matching city or German postcode. Otherwise it stays unresolved. Analyst-verified domains always win.
3. **The investment window.** Place every lead on the brief's own timeline: early traces (our window), then first round, then everyone knows. A confirmed round or an investor named on the site closes the window. A young legal entity, a recent trace and no investor signal mean it is open. Always show the reasons.
4. **HTGF readiness with receipts.** Score each lead out of 100 on HTGF's stated criteria: German base, legal entity, named people, digital tech fit, product signal, independent validation (jury progression, grant, second source) and no equity signal yet. Every point links to its source. It is a readiness-to-contact score, not a prediction.
5. **A Monday call list.** The top teams with an open window, a one-line "why now", three first-call questions generated from the gaps, and one-click exports: a weekly brief (Markdown), a CRM-ready CSV and an outreach draft the analyst decides whether to send.
6. **A radar that remembers.** Every rescan diffs evidence: a new roster, a jury round, a release, an Impressum change (UG to GmbH, "i.G." dropped, new managing director) or a hiring page appearing. New signals open first.

## Non-negotiables

- Real data only. Missing stays "Unknown". Every fact shows its source and date type.
- Works offline from a labeled replay, and live from `python3 scout.py --serve`.
- No paid API is required. Bounded, parallel, cached requests with timeouts. Failures are shown, never hidden.
- The analyst decides who to contact. FirstTrace drafts, it never sends.

## Pitch line

"FirstTrace does the first 25 minutes of research on every early team in Bavaria, every night, and tells the analyst who to call this week and why."

## What was built and what it found (live scan, 20 November 2026)

- 167 projects read from UnternehmerTUM and 7 BayStartUP roster pages; 18 companies researched automatically from their websites and legal notices; 15 dated footprints.
- **The brand is often not the company.** Bevel is legally *Bevelites GmbH* (HRB 303590, Munich) and Aproxymade is run by *Cetect UG (haftungsbeschränkt)* (HRB 310338). A database search for the brand can miss both. FirstTrace finds the entity through the legal notice.
- **Earlier than incorporation.** CAELIA Health's legal notice describes a venture team at Fraunhofer EMFT that is not incorporated yet, funded by EXIST Research Transfer, with a page for investors. Deskbot.io is run by two named people with no company form yet.
- **Managing directors from the legal notice**, e.g. Venedy GmbH: Lukas Hügle and Armin Skollik; meda AI GmbH: Andrei Mancu and Pei-Ning Hung.

## Three-minute demo path

1. **0:00 Problem.** "An HTGF analyst spends 20–30 minutes researching each new team, and databases only show teams once every investor sees them."
2. **0:20 Live.** `python3 scout.py --serve`, press **Run live scan**. FirstTrace reads the grant directory, every competition roster, GitHub and each company's legal notice.
3. **0:50 Ask.** Type "API security in Munich" → Venedy first, with the German roster sentence highlighted. Then "Talking to investors now" → CAELIA Health.
4. **1:20 The brief.** Open Venedy: why now (finalist, GmbH registered), window open, readiness 100 with every point sourced, managing directors from the Impressum, first-call questions. Press **Copy outreach draft**.
5. **2:00 Creative signal.** Open Bevel: "Bevelites GmbH — different from the brand, so a database search can miss it." Open CAELIA: not incorporated yet, EXIST Research Transfer, investor page.
6. **2:30 Workflow.** **Weekly brief** and **Export to CRM**. Rescan: new rosters, jury rounds and legal-notice changes appear under **New signals**.
7. **2:50 Close.** "FirstTrace does the first 25 minutes of research on every early team in Bavaria, every night, and tells the analyst who to call this week and why."
