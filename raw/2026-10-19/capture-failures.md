# 2026-10-19 round-1 capture failures

- Mode: baseline only (arXiv API, X). PR #3/#6 are not merged into main (both closed unmerged), so fetch_primary and scrapers were not run; no other sources captured.
- FRED: permanently discontinued; no FRED requests made and no FRED data this round.
- Scheduled ~04:50 SGT run; capture ~04:55–05:00 SGT.
- arXiv API: 5/5 categories HTTP 200 (cs.AI, cs.LG, cs.CL, stat.ML, q-bio.QM), 50 entries each.
- X: 24/24 queries ok (main v2 query set), 35 search calls incl. pagination + 2 hydrate calls = 37. B01 ai-tech-reports and B06 macro-liquidity returned 0 posts (not an error). A01, A04, A06, A07 reached the end of results (no next_token).
- Pagination stopped early to finish inside the 05:15 window; 18 queries left for round-2 continuation: A02, A03, A05, B02, B03, B04, B05, B07, B08, B09, B10, B11, B12, B13, B14, B15, B16, B17.
- X leads: 154, all marked 线索; no primary-source verification this round.
- X spot-check 3/3 matched (see x/verify.md).
- Internal query set: not run (no internal query file found).
