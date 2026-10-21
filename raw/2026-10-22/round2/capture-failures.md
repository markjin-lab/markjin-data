# capture-failures (round 2, 2026-10-22)

- Mode: baseline only (arXiv API 5 cats, X main v2 24 queries). PR #3/#6 not merged into main, so fetch_primary and scrapers were not run; no other sources captured. Internal query set not run.
- FRED: permanently discontinued; no FRED requests made and no FRED data this round.
- Schedule: round 2 started ~05:58 SGT (push deadline 06:30 SGT). arXiv ~05:59:36–05:59:48 SGT; X new window ~06:00–06:01 SGT; hydrate ~06:01 SGT.
- X round-1 continuation: none needed (round-1 pagination record lists 0 unfinished queries); 0 calls.
- X new window (start 2026-10-21T20:58:41Z): 24 page-1 + 6 A page-2 = 30 calls, 166 posts. All 6 A page-2 calls returned 0 posts. First page returned 0 posts (not an error): A01, B01, B07, B15.
- arXiv: HTTP 200 ×5; 250 entries / 220 unique; **0 new** vs seen-ids ∪ round 1 → blank day for new ids. Errors: 0.
- X: search 30 + hydrate 1 = 31 (day total 95 with round 1's 64; budget 400). Raw 166 / unique 165 / new 165 / filtered leads 26 (all 线索). Spot-check 3/3 matched. Blank day? No. Errors: 0.
- Primary-source: not run; all leads marked 线索.
