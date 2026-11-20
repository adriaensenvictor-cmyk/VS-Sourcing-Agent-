# 18-hour build plan

## Clock and definition of done

BuilderBase closes at **10:30 CET on Saturday, 21 November 2026**. The team should target a successful upload by 10:00 and use 10:00–10:30 to verify the receipt, video playback and repository access. T+0 through T+18 below is the full sprint sequence. If starting after 16:00 Friday, compress optional work to protect the upload target.

The core demo runs a real public scan, presents a ranked queue, opens an early lead with dated product evidence and team provenance, explains one held candidate and works offline from an explicitly labeled snapshot. The pitch explains why the best startup deserves a call and what remains unverified. Aim for at least one candidate the reviewer would actually contact, and record the baseline result even when unavailable.

| Sprint | Ingestion | Lead evidence | Product | Integration and pitch |
| --- | --- | --- | --- | --- |
| T+0–2 | Confirm two public endpoints and source schema | Verify HTGF fit and agree what constitutes a financing round | Sketch inbox → lead → evidence | Confirm hand-in permissions, assign owners, agree exact clock |
| T+2–5 | Parse full cohort, dedupe, produce JSON and source status | Verify five candidates, check team, funding and duplicate names | Render real inbox and exclusion, link to sources | Merge minimum path and dry-run demo from clean checkout |
| T+5–8 | Join verified team-to-repository IDs, capture release dates | Choose provisional best find and strongest counterexample | Evidence timeline, visible review status and unknowns | Run live and replay, start video outline |
| T+8–12 | Test one improvement in priority order below | Cross-review top five and source dates, seek a verified comparator | Show before/after in analyst workflow | Measure quality, lock scope by T+12 |
| T+12–15 | Freeze data contract and capture final snapshot | Sign off lead dossier and fact-check narration | Test laptop, browser and viewport for recording | Rehearse, stage final version and fallback |
| T+15–18 | Help investigate failures only | Verify each material claim against its source | Fix only blockers | Record 3-minute pitch, verify exact code, upload and confirm receipt |

## Owners and merge contract

Assign one teammate to each role now. Ingestion owns fetching, capture and source errors. Research owns `data/reviews.json` and factual lead checks. Product owns lead presentation and usability. Integration owns the shared demo revision, ship checks and BuilderBase. During parallel edits, split rendering into its own module only if concurrent ownership of `scout.py` becomes an issue. Agree the interface first to avoid divergent prototypes.

- Candidate fields are project name, derived tags and noise match. Normalized names support within-source dedupe. Ambiguous cross-source identity stays under analyst review.
- A verification record holds source URL, team, product, funding status, commercial hypothesis and verified repository IDs or a hold reason. A canonical company domain or explicit org link is needed to associate developer activity.
- Capture includes observed-at UTC, candidate records, dated releases and source errors. A release date refers to GitHub publication. The collector currently reads up to 100 releases per reviewed repository and shows the earliest eligible one it observed. Archive exact provenance before changing the display.
- Integration checkpoints are T+2 contract, T+5 one live path, T+8 verified demo and T+12 scope freeze. Branches are short-lived, with narrow changes and one owner per shared file. Use PRs for review and nominate a single integrator for the recording branch or tag. Keep the event PDFs available to each teammate through the event materials or shared repo if redistribution is authorized.
- PR handoff format: **Changed** one sentence, **Verified** command and observed result, **Evidence** links, **Next** owner plus next action. Copy durable decisions to these files. Use chat for coordination and PRs for handoff.

## Improvements in order

1. **Better lead quality and identity coverage.** Review at least five ranked records. Require a public team source, confirmed German operating base, buyer hypothesis and an independent check of funding. Use primary company and investor materials and one corroborating database. Verify fewer than two ambiguous matches through names alone by requiring an explicit association for every connector. Measure top-five meet-worthiness by a second human reviewer.
2. **Earliness.** Find one dated database/press first-publication reference and an eligible source trace for the same entity. Show `baseline publication date − trace publication date` and label a public press baseline as such. Do one time-cutoff replay with only evidence available by that cutoff. Historical current metadata and a manually selected case cannot establish prospective performance. Measure comparison coverage and report unknown when the baseline is undated.
3. **Continuous use.** Run the collector at a bounded cadence, diff snapshots on entity/evidence identity and present fresh signals to a reviewer. Start with manual invocations. If deployment is already reliable by T+12, use n8n Schedule Trigger on a reachable runner and test twice with no duplicated alerts. Track parse counts, errors and request budget before adding adapters.
4. **Optional differentiation.** Try one university collaboration source or structured OpenAI corroboration with the same records. Time-box to 45 minutes and keep only if it adds a credible lead or replaces a slow manual step. Try an ElevenLabs excerpt only after the live and offline demo are rehearsed and if the pitch remains within 180 seconds.

## Checks before recording

- Run a live scan and replay. Compare lead order and evidence links for the same capture. Confirm both modes are visible, and failure reports do not masquerade as fresh results.
- Open the strongest candidate, locate their team and a dated release within five seconds, and find one held candidate and its reasoning. Check the result at the recording viewport.
- Have a second teammate review the top five blind to score, logging the number worth meeting, and time the same triage task with and without the inbox. Treat one observation as an example.
- Verify a first-round claim using primary evidence, or keep funding explicitly unconfirmed. Verify an earliness comparator only if a clear publication date exists. Disclose manual matches.
- Gate the final hand-in on actual video playback, a readable link/code artifact at the recorded revision, and BuilderBase acceptance.
