# capture-failures — 2026-11-08 round1

- Mode: PR 未合并，按基线采（arXiv API + X only）; FRED permanently off.
- #110 arXiv validate-r1: all_valid=true; invalid=[]
- X first-page empty (not failure): B01
- X early-stop (schedule → R2): A02, A03, A04, A05, A06, A07
- X page_cap with next_token → R2: B04, B05, B08, B10, B11, B12, B13, B14, B15, B16, B17
- No FRED requests; no fetch_primary; no public scrapers; EIA not requested; 海关 BLOCKED.
