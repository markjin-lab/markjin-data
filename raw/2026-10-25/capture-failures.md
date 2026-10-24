# 2026-10-25 round-1 capture failures

- Mode: baseline only (arXiv API, X). PR #3/#6 are not merged into main (both closed unmerged), so fetch_primary and scrapers were not run; no other sources captured.
- FRED: permanently discontinued; no FRED requests made and no FRED data this round.
- Scheduled ~05:00 SGT run; capture ~04:59–05:07 SGT.
- arXiv API: 5/5 categories HTTP 200 (cs.AI, cs.LG, cs.CL, stat.ML, q-bio.QM), 50 entries each; 211 unique ids, 1 new.
- X: 24/24 queries ok (main v2 query set), 63 search calls incl. pagination (+5 invalid next_token retries) + 3 hydrate calls = 66. First page returned 0 posts (not an error): B01.
- Pagination: no query was stopped early; queries left for round-2 continuation: none (0). Queries at their page cap with results remaining: A03, A04, A05, B02, B03, B04, B05, B06, B09, B11, B12, B13, B14, B16, B17.
- X leads: 203, all marked 线索; no primary-source verification this round.
- X spot-check 3/3 matched (see x/verify.md).
- Internal query set: not run (no internal query file found).
