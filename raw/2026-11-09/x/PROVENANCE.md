# X PROVENANCE — 2026-11-09 round1

- Mode: baseline (arXiv API + X only). improve/sources.yaml not on main; no fetch_primary/scrapers/FRED.
- Window: start_time=2026-11-06T21:01:41Z end_time=2026-11-08T21:01:41Z (48h ending at capture start UTC)
- Query set: x-queries.md (snapshot copied into raw/DATE/)
- Tool: x.search_posts_all (namespace `x`); pagination via next_token; hydrate via x.get_posts_by_ids
- Rate: ≤25/min; day budget ≤400
- Note: PR 未合并，按基线采

## Call counts

- Search calls: 47
- Hydrate calls: 4
- Discarded non-query tool call (not archived): 1
- Total X calls this round: 52

## Results

- raw posts (sum over search pages): 754
- unique ids: 753
- filtered (like≥20 OR retweet≥5 OR A-batch whitelist): 312
- leads: 312 (all label=线索; no primary-source verification)
- spot-check: 3/3 matched (seed 20261109); see verify.md

## Pagination

- Early-stop queries left for round-2 continuation (schedule stop before page_cap): **6** (A02, A03, A04, A05, A06, A07)
- At page_cap with next_token remaining (not continued this round): B02, B04, B05, B06, B08, B10, B11, B12, B13, B14, B16, B17
- First page empty (not an error): B01
- Completed this round (no leftover token): A01, B03, B07, B09, B15
- #109 account page samples: compared=true A01 p1 (9, interval 6-10) → next p2 count=0 / ids none / leads 0; compared=false schedule skip A02 p2 (10), A06 p2 (3), A07 p2 (16); private ledger only
- Public redaction: 23-population-p2.json one post text mentioned a website path token that the public-path guard treats as a local home directory. Replaced that token with `[home]` so the public tree passes the guard. Original page kept only in private (not published).
