# capture-failures (round 2, 2026-10-16)

- Mode: quota-saving baseline only (arXiv API 5 cats, FRED 5 series, X x-queries.md). PR #3/#6 not merged → no capture_sources.py / fetch_primary.py / scrapers / other sources. Internal queries not run.
- Schedule: round2 started ~05:58 SGT (deadline push by 06:30 SGT). arXiv ~05:58:51–05:59:06 SGT; FRED ~05:59:04–05:59:15 SGT; X searches ~05:59:40–06:01:10 SGT; hydrate+spot ~06:01–06:02 SGT.
- arXiv: HTTP 200 ×5; 250 entries / 206 unique; **0 new** vs seen-ids ∪ round1 → blank-day for new ids. Errors: 0.
- FRED: HTTP 200 ×5; no api_key in files; **1 new** observation (T10Y2Y:2026-10-15); other series 0 new vs seen∪r1. Errors: 0.
- X: search 29 (7 A page1 + 5 A page2 + 17 B; A02/A06 no next_token so no p2) + hydrate 1 + spot-check 1 = 31. Raw 156 / unique 154 / new 154 / filtered leads 20 (all 线索). Spot-check 3/3 found, created_at+text match. Blank-day? No (leads>0). Errors: 0.
- Primary-source: not run; all leads marked 线索.
- Issues: #1/#2 still open; events.jsonl/watchdog and leads-status/primary verify blocked until PR #3/#6. events.jsonl not written (rounds/ path not on main for recent days).
