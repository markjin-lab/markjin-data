# capture-failures (round 2, 2026-10-19)

- Mode: baseline only (arXiv API 5 cats, X main v2 24 queries). PR #3/#6 not merged into main, so fetch_primary and scrapers were not run; no other sources captured. Internal query set not run.
- FRED: permanently discontinued; no FRED requests made and no FRED data this round.
- Schedule: round 2 started ~06:00 SGT (push deadline 06:30 SGT). X continuation ~06:00–06:01 SGT; X new window ~06:01–06:03 SGT; arXiv ~06:03:18–06:03:32 SGT; hydrate ~06:04 SGT.
- X round-1 continuation: 18 queries, 18 pages (A02/A03/A05 page 4; 15 B topics page 2); 165 posts, 89 new after dedup; all 18 queries complete.
- X new window (start 2026-10-18T20:55Z): 24 page-1 + 4 A page-2 = 28 calls, 130 posts.
- arXiv: HTTP 200 ×5; 250 entries / 207 unique; **0 new** vs seen-ids ∪ round 1 → blank day for new ids. Errors: 0.
- X: search 46 + hydrate 1 = 47 (day total 84 with round 1's 37; budget 400). Raw 295 / unique 293 / new 218 / filtered leads 42 (all 线索). Spot-check 3/3 matched. Blank day? No. Errors: 0.
- Primary-source: not run; all leads marked 线索.
