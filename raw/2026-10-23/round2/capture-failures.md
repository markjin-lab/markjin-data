# capture-failures (round 2, 2026-10-23)

- Mode: baseline only (arXiv API 5 cats, X main v2 24 queries). PR #3/#6 not merged into main, so fetch_primary and scrapers were not run; no other sources captured. Internal query set not run.
- FRED: permanently discontinued; no FRED requests made and no FRED data this round.
- Schedule: round 2 started ~05:58 SGT (push deadline 06:30 SGT). arXiv ~05:59:00–05:59:13 SGT; X new window ~05:59–06:01 SGT; hydrate ~06:01 SGT.
- X round-1 continuation: none needed (round-1 pagination record lists 0 unfinished queries); 0 calls.
- X new window (start 2026-10-22T20:58:00Z): 24 page-1 + 6 A page-2 = 30 calls, 151 posts. All 6 A page-2 calls returned 0 posts. First page returned 0 posts (not an error): A07, B01, B07, B08.
- arXiv: HTTP 200 ×5; 250 entries / 207 unique; **0 new** vs seen-ids ∪ round 1 → blank day for new ids. Errors: 0.
- X: search 30 + hydrate 1 = 31 (day total 95 with round 1's 64; budget 400). Raw 151 / unique 151 / new 151 / filtered leads 25 (all 线索). Spot-check 3/3 matched. Blank day? No. Errors: 0.
- Primary-source: not run; all leads marked 线索.
