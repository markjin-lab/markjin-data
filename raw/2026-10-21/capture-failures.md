# 2026-10-21 round-1 capture failures

- Mode: baseline only (arXiv API, X). PR #3/#6 are not merged into main (both closed unmerged), so fetch_primary and scrapers were not run; no other sources captured.
- FRED: permanently discontinued; no FRED requests made and no FRED data this round.
- Scheduled 04:50 SGT run; capture ~04:58–05:06 SGT.
- arXiv API: 5/5 categories HTTP 200 (cs.AI, cs.LG, cs.CL, stat.ML, q-bio.QM), 50, 50, 50, 50, 50 entries.
- X: 24/24 queries ok (main v2 query set), 59 search calls incl. pagination + 5 hydrate calls = 64. First page returned 0 posts (not an error): B01, B07.
- Pagination: no query was stopped early; queries left for round-2 continuation: none (0). Queries at their page cap with results remaining: A03, A04, A05, A07, B02, B03, B04, B05, B06, B08, B09, B10, B12, B14, B15, B16, B17.
- X leads: 434, all marked 线索; no primary-source verification this round.
- X spot-check 3/3 matched (see x/verify.md).
- Internal query set: not run (no internal query file found).
