# capture-failures (round 2, 2026-10-21)

- Mode: baseline only (arXiv API 5 cats, X main v2 24 queries). PR #3/#6 not merged into main, so fetch_primary and scrapers were not run; no other sources captured. Internal query set not run.
- FRED: permanently discontinued; no FRED requests made and no FRED data this round.
- Schedule: round 2 started ~05:59 SGT (push deadline 06:30 SGT). arXiv ~06:00:12–06:00:25 SGT; X new window ~06:00–06:01 SGT; hydrate ~06:02 SGT.
- X round-1 continuation: none needed (round-1 pagination record lists 0 unfinished queries); 0 calls.
- X new window (start 2026-10-20T20:59Z): 24 page-1 + 7 A page-2 = 31 calls, 182 posts. All 7 A page-2 calls returned 0 posts. First page returned 0 posts (not an error): B01.
- arXiv: HTTP 200 ×5; 250 entries / 205 unique; **0 new** vs seen-ids ∪ round 1 → blank day for new ids. Errors: 0.
- X: search 31 + hydrate 1 = 32 (day total 96 with round 1's 64; budget 400). Raw 182 / unique 179 / new 179 / filtered leads 27 (all 线索). Spot-check 3/3 matched. Blank day? No. Errors: 0.
- Primary-source: not run; all leads marked 线索.
