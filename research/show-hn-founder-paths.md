# Reviewing a founder's previous projects

Run the standalone public-source scout from the repository root.

~~~sh
python founder_sourcing.py --days 365 > founder-paths.json
python -m unittest discover -s tests -p test_founder_sourcing.py -v
~~~

The JSON contains research candidates, the scan time, and coverage warnings. An empty successful scan and an unavailable source produce distinct statuses; total failure also exits with code 1. This command can be used independently of the dashboard.

The scout queries public Show HN launches through the Algolia API. It searches for explicit founder-team location or prior-employer wording plus a first-person building statement. It samples the newest 100 hits per query with three concurrent requests. For up to six accounts, it checks up to 20 earlier Show HN posts and keeps up to three distinct project links with earlier timestamps and first-person attribution. These are public account-level claims. Verify the person's identity, employment, ownership, country of operation and financing before outreach. Location and language coverage are limited. No employer bonus or shortlist promotion is applied.

A March 2026 [CRM launch](https://news.ycombinator.com/item?id=47314724) mentions prior employment at Goldman Sachs. The same account previously described building [NitroQR](https://news.ycombinator.com/item?id=44854878). This gives a scout a concrete product to inspect. Both employment and authorship are self-reported, and the CRM post leaves company location unresolved.

## Simra AI review for the demo

On the research dossier dated 20 November 2026, the two evaluators agreed on nine of twelve assessed criteria, Founder Potential 85 and Venture Potential 65. PR #6 recognized a founder-led opportunity at 85. The PR #9 team/project weighting produced a provisional 77 (51 team points and 26 project points). These are diligence heuristics. The separate Early Signal Score was 2.

The comparison used the Simra snapshot, PR #6 revision 756655d and PR #9 revision ad1ac8d. It ran both with their native reviews and again with identical source observations. The additional source about Tacit in PR #9 supported a criterion already counted, so neither axis changed.

**Suggested first call.** Ask about the team’s analog circuit work and prior operating responsibilities, then request a customer reference and a demonstration on a customer circuit. Market opportunity and customer validation are still open. The dossier records public grant support; external equity financing and the legal formation date need verification. [TU Berlin profile](https://www.tu.berlin/entrepreneurship/startup-support/tu-startups/container-profile/startups-2026-simra-ai) · [Team and product demos](https://www.simratech.com/)
