# 2026-10-12 round-1 capture failures

- Scheduled 05:00 SGT run did not land; manual rerun started ~05:07 SGT.
- capture_sources.py: ok=24 failed=0 (invocation needed explicit --sources/--date flags).
- FRED: 5/5 ok.
- X: 24/24 public queries ok; B01 ai-tech-reports returned 0 posts (not an error). No pagination fetched (next_token present on A batches; not followed this run).
- X spot-check 3/3 matched.
