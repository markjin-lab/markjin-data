# capture-failures (round 2, 2026-10-24)

- Mode: baseline only (arXiv API 5 cats, X main v2 24 queries). PR #3/#6 not merged into main, so fetch_primary and scrapers were not run; no other sources captured. Internal query set not run.
- FRED: permanently discontinued; no FRED requests made and no FRED data this round.
- Schedule: round 2 started ~05:59 SGT (push deadline 06:30 SGT). arXiv ~05:59:33–05:59:46 UTC; X new window ~06:00–06:03 SGT; hydrate ~06:03 SGT.
- X round-1 continuation: none needed (round-1 pagination record lists 0 unfinished queries); 0 calls.
- X new window (start 2026-10-23T20:59:05Z): 24 page-1 + 6 A page-2 = 30 calls, 152 posts. All 6 A page-2 calls returned 0 posts. First page returned 0 posts (not an error): A01, B01, B09.
- arXiv: HTTP 200 ×5; 250 entries / 211 unique; **0 new** vs seen-ids ∪ round 1 → blank day for new ids. Errors: 0.
- X: search 30 + hydrate 1 = 31 (day total 96 with round 1's 65; budget 400). Raw 152 / unique 151 / new 151 / filtered leads 26 (all 线索). Spot-check 3/3 matched. Blank day? No. Errors: 0.
- Primary-source: not run; all leads marked 线索.
