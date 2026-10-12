# 2026-10-13 round-1 capture failures

- Mode: baseline only (arXiv API, FRED 5 series, X). PR #3/#6 are not merged into main, so fetch_primary and scrapers were not run; no other sources captured.
- Scheduled 04:50 SGT run started late (~05:04 SGT); capture 05:05–05:10 SGT.
- arXiv API: 5/5 categories HTTP 200 (cs.AI, cs.LG, cs.CL, stat.ML, q-bio.QM).
- FRED: 5/5 HTTP 200.
- X: 24/24 queries ok, 55 search calls incl. pagination + 5 hydrate calls; B01 ai-tech-reports returned 0 posts (not an error). A03 and A05 hit the 4-page cap with next_token remaining.
- X leads: all marked 线索; no primary-source verification this round.
- X spot-check 3/3 matched.
- Internal query set: not run (no internal query file found).
