# capture-failures (round 2, 2026-10-18)

- Mode: baseline only (arXiv API 5 cats, FRED 5 series, X main v2 24 queries). PR #3/#6 not merged into main, so fetch_primary and scrapers were not run; no other sources captured. Internal query set not run.
- Schedule: round 2 started ~05:56 SGT (push deadline 06:30 SGT). arXiv ~05:58:02–05:58:16 SGT; FRED ~05:58:2x SGT; X searches ~05:59–06:00 SGT; hydrate ~06:01 SGT.
- arXiv: HTTP 200 ×5; 250 entries / 207 unique; **0 new** vs seen-ids ∪ round 1 → blank day for new ids. Errors: 0.
- FRED: HTTP 200 ×5; no api_key in files; **0 new** observations → blank day. Errors: 0.
- X: search 29 (24 page-1 + 5 A page-2) + hydrate 1 = 30. Raw 100 / unique 99 / new 99 / filtered leads 13 (all 线索). Spot-check 3/3 matched. Blank day? No. Errors: 0.
- Primary-source: not run; all leads marked 线索.
