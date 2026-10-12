# 2026-10-13 round-2 capture failures

- Mode: baseline only (arXiv API, FRED 5 series, X). PR #3/#6 still not merged into main; fetch_primary and scrapers not run; no other sources captured.
- Scheduled 05:50 SGT run started late (~06:02 SGT); capture 06:04–06:09 SGT.
- arXiv API: 5/5 categories HTTP 200; 250 entries, 0 new after dedup (same listing as round 1) — blank for round 2.
- FRED: 5/5 HTTP 200; 0 new observations — blank for round 2.
- X: 27/27 search calls ok (24 page-1 + 3 A-batch page-2), 0 errors; 129 posts, 2 duplicates, 127 new, 12 leads; hydrate 1 call. 14 B topics hit the 1-page cap with next_token remaining.
- X leads: all marked 线索; no primary-source verification this round.
- X spot-check 3/3 matched.
- Internal query set: not run (no internal query file found).
