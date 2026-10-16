# capture-failures (round 2, 2026-10-17)

- Mode: quota-saving baseline only (arXiv API 5 cats, FRED 5 series, X trimmed x-queries.md). PR #3/#6 not merged → no capture_sources.py / fetch_primary.py / scrapers / other sources. Internal queries not run.
- Schedule: round2 started ~05:57 SGT (deadline push by 06:30 SGT). arXiv ~05:58:35–05:58:49 SGT; FRED ~05:58:5x SGT; X searches ~05:59–06:01 SGT; hydrate+spot ~06:0x SGT.
- arXiv: HTTP 200 ×5; 250 entries / 207 unique; **0 new** vs seen-ids ∪ round1 → blank-day for new ids. Errors: 0.
- FRED: HTTP 200 ×5; no api_key in files; **1 new** observation (T10Y2Y:2026-10-16); other series 0 new vs seen∪r1. Errors: 0.
- X: search 26 (6 A page1 + 3 A page2 + 17 B; A06 paused per 2026-10-17 trim) + hydrate 1 + spot-check 1 = 28. Raw 116 / unique 114 / new 114 / filtered leads 6 (all 线索). Spot-check 3/3 found, created_at+text match. Blank-day? No (leads>0). Errors: 0.
- Primary-source: not run; all leads marked 线索.
- Issues: #1/#2 still open; events.jsonl/watchdog and leads-status/primary verify blocked until PR #3/#6.
