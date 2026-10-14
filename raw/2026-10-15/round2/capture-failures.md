# capture-failures (round 2, 2026-10-15)

- Mode: quota-saving baseline only (arXiv API 5 cats, FRED 5 series, X x-queries.md). PR #3/#6 not merged → no capture_sources.py / fetch_primary.py / scrapers / other sources. Internal queries not run.
- Schedule: round2 started ~05:58 SGT (deadline push by 06:30 SGT). arXiv ~05:58:50–05:59:00 SGT; FRED ~05:59 SGT; X searches ~05:59:28–06:01:30 SGT; hydrate+spot ~06:02–06:03 SGT.
- arXiv: HTTP 200 ×5; 250 entries / 200 unique; **0 new** vs seen-ids ∪ round1 → blank-day for new ids. Errors: 0.
- FRED: HTTP 200 ×5; no api_key in files; **1 new** observation (T10Y2Y:2026-10-14); other series 0 new vs seen∪r1. Errors: 0.
- X: search 30 (7 A page1 + 6 A page2 + 17 B; A03 no next_token so no p2) + hydrate 1 + spot-check 1 = 32. Raw 145 / unique 145 / new 145 / filtered leads 24 (all 线索). Spot-check 3/3 found, created_at+text match. Blank-day? No (leads>0). Errors: 0.
- Primary-source: not run; all leads marked 线索.
- Issues: #1/#2 still open; events.jsonl/watchdog and leads-status/primary verify blocked until PR #3/#6. events.jsonl not written (rounds/ path not on main for recent days).
