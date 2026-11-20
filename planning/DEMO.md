# Demo and hand-in

All numbers and examples come from the live scan of 20 November 2026 (`data/demo-snapshot.json`): 167 projects read, 18 companies researched automatically from their websites and legal notices, 40 leads in the inbox, 7 held aside with a reason.

## Demo path

1. Run `python3 scout.py --serve` (or `run-mac.command` / `run-windows.bat`). The desk opens on the latest capture; press **Run live scan** and narrate while it reads the grant directory, every BayStartUP roster, GitHub and each company's legal notice.
2. Type **API security in Munich** in the search box. The search shows what it understood (Munich, "api security") and returns Venedy, Aproxymade and QOODA, with the German roster sentence highlighted.
3. Open **Venedy** from the call list: why now, the investment window, HTGF readiness 100/100 with every point sourced, the legal entity and managing directors from the Impressum, and three first-call questions. Press **Copy outreach draft**.
4. Type **Talking to investors now** to surface **CAELIA Health**, then open **Bevel** to show "legal entity differs from the brand".
5. Press **Weekly brief** and **Export to CRM**. A second scan lists what changed under **New signals**.

If the network fails, open `FirstTrace-offline.html`. It is labeled *Snapshot replay* and keeps search, call list, briefs and exports.

## Best find: Venedy, Munich

**What it is.** Autonomous AI security testing for APIs. The organizer describes it as "KI findet Schwachstellen in digitalen Schnittstellen"; the company site says it tests APIs like a real attacker and finds the logic and authorization flaws scanners miss.

**The signals behind it.**

- **2 March 2026:** nominated in Phase 1 of the Munich business plan competition 2026. [Roster](https://www.baystartup.de/startupdate/die-nominierten-im-muenchener-businessplan-wettbewerb-2026-phase-1)
- **29 July 2026:** one of eight finalists. [Finalists](https://www.baystartup.de/startupdate/acht-startups-im-finale-des-muenchner-businessplan-wettbewerbs-2026)
- **Legal notice:** Venedy GmbH, HRB 313583, Amtsgericht München, 80796 Munich. Managing directors Lukas Hügle and Armin Skollik. [Impressum](https://venedy.io/en/impressum.html)
- **Website:** a pilot program before public launch, no investors named. [Pilot program](https://venedy.io/en/pilot-program.html)
- **Footprint:** no Internet Archive capture and no Hacker News post linking venedy.io at the time of the scan.

**Why HTGF should take a look.** Security tooling for developer infrastructure sits in HTGF's Digital Tech focus. The team is in Munich, has two named managing directors, runs pilots and has no equity round in the sources checked. FirstTrace scores it 100/100 on readiness with the window open.

**What remains unverified.** Funding is unconfirmed: no round found in the checked sources is not proof that none exists. Pilot conversion and revenue are unknown. First question: what turns a pilot into a paid contract?

## Other leads worth showing

- **Bevel, Munich.** Surfaced by the UnternehmerTUM prototype grant directory. The legal notice names **Bevelites GmbH** (HRB 303590, Munich), so a database search for "Bevel" can miss it. 32 public GitHub releases since 19 April 2025. Dealroom lists a spinout with no confirmed equity round. [Impressum](https://www.bevel.software/impressum) · [Release](https://github.com/Bevel-Software/bevel-language-server-releases/releases/tag/bevel-0.6.0)
- **CAELIA Health, Munich.** The legal notice describes a venture team at Fraunhofer EMFT that is not incorporated yet, funded by EXIST Research Transfer, with a page for investors. Life sciences, so a lead for HTGF's Life Sciences team rather than Digital Tech. [Impressum](https://caelia-health.com/impressum/)
- **QOODA, Munich.** Phase 1 nominee, then finalist, then 1st place in the Munich business plan competition 2026: independent juries re-validated the team over five months. [Winners](https://www.baystartup.de/startupdate/das-sind-die-sieger-im-muenchner-businessplan-wettbewerb-2026) · [Impressum](https://www.qooda.io/impressum)

**Exclusions to show.** nuno.ai is held because a database reports a June 2026 seed round. DASH e.V. is held as a registered association, typical of student initiatives. Valuemize is held after its public pre-seed round.

**Historical comparison.** BayStartUP listed Valuemize on 23 February 2024; coverage of its pre-seed round appeared on 16 July 2026, 874 days later. The interval is between two public sources selected retrospectively; it does not measure FirstTrace's own discovery advantage. [BayStartUP](https://www.baystartup.de/startupdate/wettbewerbs-updates/die-nominierten-im-muenchener-businessplan-wettbewerb-2024-phase-1) · [Pre-seed coverage](https://www.startbase.de/news/valuemize-erhaelt-siebenstellige-pre-seed-finanzierung/)

## Three-minute pitch

| Time | What the viewer sees | Narration |
| --- | --- | --- |
| 0:00–0:20 | Title, then the brief's window | "Once a startup is in a database, every investor knows it. HTGF's window is earlier: grants, competition rosters, code, legal notices." |
| 0:20–0:40 | The analyst's manual checks | "Finding names is easy. Researching each one takes an analyst about 25 minutes by our estimate: website, legal notice, register, directors, product, funding." |
| 0:40–1:05 | Desk, **Run live scan** | "FirstTrace does those first 25 minutes for every early team in Bavaria. It reads grants, every competition roster, GitHub and each company's legal notice, and ranks teams on HTGF's criteria." |
| 1:05–1:30 | Search "API security in Munich" | "The analyst asks in plain words. Venedy comes first, with the German roster sentence highlighted." |
| 1:30–2:15 | Venedy brief | "Nominated in March, finalist in July. FirstTrace read its legal notice: Venedy GmbH, two managing directors. A pilot program, no investors named, not even archived yet. We would ask what turns a pilot into a paid contract." |
| 2:15–2:40 | Bevel and CAELIA | "Signals databases miss: Bevel is legally Bevelites GmbH, and CAELIA Health is a Fraunhofer team that is not incorporated yet and already has a page for investors." |
| 2:40–3:00 | Weekly brief, CRM export, closing line | "FirstTrace does the first 25 minutes of research on every early team in Bavaria, every night, and tells the analyst who to call this week and why." |

## BuilderBase checklist

- Project name: **FirstTrace**.
- Code: the zip made with `git archive --format=zip --prefix=FirstTrace/ -o FirstTrace-code.zip HEAD` from the exact commit used in the video, or the public repository link at that commit.
- Upload the three-minute pitch video via **Hand in** or **My team → Open hand-in**. Check playback and repository access.
- Deadline: **Saturday 21 November 2026, 10:30 CET**, Maastricht time. Target 10:00 with the upload confirmed.

## Verification and PR handoff

- **Changed** Live desk with a scan button and background first scan, automatic BayStartUP roster discovery and jury progression, company research from websites and legal notices, HTGF readiness, investment window, natural-language search, call list, briefs and exports, plus a jury package (offline HTML and launchers).
- **Verified** 16 offline tests pass. From a clean copy without caches, the desk opened in about one second on the labeled demo capture and reloaded with live data after 67 seconds: 167 projects, 18 companies researched, same ranking, no browser errors. Replay and the offline file show the same data.
- **Evidence** [Run instructions](../README.md) · [Captured scan](../data/demo-snapshot.json) · [Analyst checks](../data/reviews.json) · [Product prompt and findings](PRODUCT.md).
- **Next** Confirm Venedy's equity status from a primary source, time the manual research for one lead to back the 25-minute estimate, record the pitch on the final commit and verify BuilderBase acceptance.
