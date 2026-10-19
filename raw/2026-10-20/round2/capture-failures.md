# capture-failures (round 2, 2026-10-20)

- Mode: baseline only (arXiv API 5 cats, X main v2 24 queries). PR #3/#6 not merged into main, so fetch_primary and scrapers were not run; no other sources captured. Internal query set not run.
- FRED: permanently discontinued; no FRED requests made and no FRED data this round.
- Schedule: round 2 started ~05:55 SGT (push deadline 06:30 SGT). arXiv ~05:56:27–05:56:40 SGT; X new window ~05:57–05:58 SGT; hydrate ~05:58 SGT.
- X round-1 continuation: none needed (round 1 left 0 queries with a next page); 0 calls.
- X new window (start 2026-10-19T21:00Z): 24 page-1 + 4 A page-2 = 28 calls, 134 posts. First page returned 0 posts (not an error): A01, A03, A06, B01, B03, B07, B08.
- arXiv: HTTP 200 ×5; 250 entries / 220 unique; **0 new** vs seen-ids ∪ round 1 → blank day for new ids. Errors: 0.
- X: search 28 + hydrate 1 = 29 (day total 88 with round 1's 59; budget 400). Raw 134 / unique 132 / new 132 / filtered leads 20 (all 线索). Spot-check 3/3 matched. Blank day? No. Errors: 0.
- Primary-source: not run; all leads marked 线索.
