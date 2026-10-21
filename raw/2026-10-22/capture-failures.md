# 2026-10-22 round-1 capture failures

- Mode: baseline only (arXiv API, X). PR #3/#6 are not merged into main (both closed unmerged), so fetch_primary and scrapers were not run; no other sources captured.
- FRED: permanently discontinued; no FRED requests made and no FRED data this round.
- Scheduled 04:50 SGT run; capture ~04:58–05:05 SGT.
- arXiv API: 5/5 categories HTTP 200 (cs.AI, cs.LG, cs.CL, stat.ML, q-bio.QM), 50 entries each.
- X: 24/24 queries ok (main v2 query set), 60 search calls incl. pagination + 4 hydrate calls = 64. First page returned 0 posts (not an error): B01.
- Pagination: no query was stopped early; queries left for round-2 continuation: none (0). Queries at their page cap with results remaining: A03, A04, A05, A06, A07, B02, B04, B05, B06, B08, B09, B10, B11, B12, B13, B14, B15, B16, B17.
- X leads: 384, all marked 线索; no primary-source verification this round.
- X spot-check 3/3 matched (see x/verify.md).
- Internal query set: not run (no internal query file found).
