# 2026-10-12 round-1 capture failures

- Scheduled 05:00 SGT run did not land; manual rerun started ~05:07 SGT.
- capture_sources.py: ok=24 failed=0 (invocation needed explicit --sources/--date flags).
- FRED: 5/5 ok.
- X: 24/24 public queries ok; B01 ai-tech-reports returned 0 posts (not an error). No pagination fetched (next_token present on A batches; not followed this run).
- X spot-check 3/3 matched.

## LZ-4 支撑页抓取（2026-10-12 08:20 SGT）

- vandenberg-lz4-sonic-boom — https://www.vandenberg.spaceforce.mil/News/Article-Display/Article/1652283/central-california-residents-may-experience-sonic-boom/
  - 2026-10-12T00:20:09Z（08:20:09 SGT）：HTTP 403 "Access Denied"（Akamai edge，errors.edgesuite.net）；robots.txt 同样 403（00:19:44Z）。UA: markjin-collector/0.1。
  - 按规则未绕过（未换 UA、未用无头浏览器、未用缓存/镜像），本页未存。
