# FirstTrace walkthrough and priorities

## How the prototype works

1. `scout.py` reads the public UnternehmerTUM prototype-grant directory, deduplicates project names and tags descriptions against a Munich software and infrastructure thesis.
2. `data/reviews.json` holds analyst-verified founder and product links, repository associations and reasons to hold a lead. The engine fetches release dates from GitHub for associated repositories. The evidence score rewards source coverage.
3. The script generates a browsable HTML report with ranked leads, primary evidence, funding uncertainty, held candidates and a retrospective date comparison. The same renderer works with `data/demo-snapshot.json` offline.

The tested capture contains 130 projects, 14 keyword matches and 6 held candidates. Bevel has two dated GitHub release records and a TUM founder source. Its first equity round and date of database visibility remain unverified.

## Technical priorities

1. **Improve candidate identity.** Prefer reciprocal repository and company-domain links or an explicit institutional link. Queue ambiguous matches for review. Check a labeled set of competing names, agencies, funded teams and independent startups, and measure precision among the first five leads.
2. **Track changes and dates.** Store project and evidence IDs, source publication time, first observed time and funding checks in SQLite. Upsert on stable IDs, log per-source failures and mark stale results. Add an incremental scan with bounded retries and pagination. Test that reruns generate zero duplicate signals.
3. **Separate fit, evidence and timing.** Rank buyer and thesis fit independently from evidence coverage. Keep funding status explicit. Compare early signals against a named, dated press or database baseline only when available. Run a time-cutoff evaluation and record which leads a reviewer would contact.
4. **Add a second discovery feed.** Try dated local competition rosters or university collaboration posts. GitHub currently enriches pre-matched repositories. Measure whether the new feed surfaces leads the cohort alone misses.

## Product and design priorities

- **Make the day’s best find obvious.** Use a calm canvas, generous spacing, large typography and one accent for evidence and actions. Give the strongest verified lead a compact feature card with one sentence on why it matters and a clear **Review evidence** button. Borrow the hierarchy of Apple’s product sections. [Apple](https://www.apple.com/)
- **Build an inbox with a detail pane.** Keep the queue visible on the left and show the team, reason to meet, dated evidence and funding status on the right. Add search, keyboard navigation, and **Save**, **Pass** and **Needs verification**. Stack the panes on small screens and keep source links one click away.
- **Make the first question easy.** Take inspiration from OpenAI’s prominent single prompt and grouped content. Offer one search box with suggestions such as “New developer tools in Munich.” Start with filters over indexed evidence, then consider sourced natural-language queries. [OpenAI](https://openai.com/)
- **Give analysts a reason to return.** Show what changed in each saved search, such as a new release from a watched team or a funding update. Offer an optional digest of meaningful changes. Measure time to the first evidence-backed decision and whether analysts return to review new signals.
