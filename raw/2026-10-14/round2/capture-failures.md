# capture-failures (round 2, 2026-10-14)

- Mode: quota-saving baseline only (arXiv API 5 cats, FRED 5 series, X x-queries.md). PR #3/#6 not merged → no capture_sources.py / fetch_primary.py / scrapers / other sources. Internal queries not run.
- Schedule: round2 started ~05:57 SGT (deadline push by 06:30 SGT). arXiv ~05:57:40–05:57:45 SGT; FRED ~05:57:45 SGT (2026-10-13T21:57:45Z); X searches ~05:58:45–06:01:16 SGT; hydrate+spot ~06:01:45–06:02:02 SGT.
- arXiv: HTTP 200 ×5; 250 entries / 218 unique; **0 new** vs seen-ids ∪ round1 → blank-day for new ids (cs.AI/stat.ML/q-bio.QM listing hashes differ slightly vs round1, but all ids already seen). Errors: 0.
- FRED: HTTP 200 ×5; no api_key in files; **2 new** observations (T10Y2Y only); other series 0 new. Errors: 0.
- X: search 31 (7 A page1 + 7 A page2 + 17 B) + hydrate 1 + spot-check 1 = 33. Raw 149 / unique 148 / new 148 / filtered leads 21 (all 线索). Spot-check 3/3 found, created_at match. Blank-day? No (leads>0). Errors: 0.
- Primary-source: not run; all leads marked 线索.
- Issues: #1/#2 still open; events.jsonl/watchdog and leads-status/primary verify blocked until PR #3/#6.
