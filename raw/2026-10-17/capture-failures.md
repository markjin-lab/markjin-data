# 2026-10-17 round-1 capture failures

- Mode: baseline only (arXiv API, FRED 5 series, X). PR #3/#6 are not merged into main, so fetch_primary and scrapers were not run; no other sources captured.
- Scheduled ~04:50 SGT run; capture ~04:55–05:00 SGT.
- arXiv API: 5/5 categories HTTP 200 (cs.AI, cs.LG, cs.CL, stat.ML, q-bio.QM), 50 entries each.
- FRED: 5/5 HTTP 200.
- X: 24/24 queries ok, 31 search calls incl. pagination + 3 hydrate calls; B01 ai-tech-reports returned 0 posts (not an error). Pagination stopped early (A batches 2 pages, B topics 1 page) to finish inside the 05:15 window; 7 of 7 A batches and 16 of 17 B topics still had a next_token.
- X leads: 289, all marked 线索; no primary-source verification this round.
- X spot-check 3/3 matched.
- Internal query set: not run (no internal query file found).
