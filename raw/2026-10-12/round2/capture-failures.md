# 2026-10-12 round-2 capture failures

- Run started ~05:52 SGT. capture_sources.py --round 2: ok=24 failed=0 (out-root mis-nested once, moved into place before commit).
- X: 24/24 queries ok, start_time 2026-10-11T20:50Z, no pagination; 117 posts, 112 new after dedup against round1 + seen-ids.
- FRED: not re-fetched in round 2 (round-1 5/5 already covers today's daily/monthly series).
