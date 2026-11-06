# X PROVENANCE — 2026-11-07 round1

- Mode: baseline (arXiv API + X only). improve/sources.yaml not on main; no fetch_primary/scrapers/FRED.
- Window: start_time=2026-11-04T20:50:00Z end_time=2026-11-06T20:50:00Z (48h ending at capture start UTC)
- Query set: x-queries.md (snapshot copied into raw/DATE/)
- Tool: x.search_posts_all (namespace `x`); pagination via next_token; hydrate via x.get_posts_by_ids
- Rate: ≤25/min; day budget ≤400
- Note: PR 未合并，按基线采

## Call counts

- Search calls: 48
- Hydrate calls: 4
- Total X calls this round: 52

## Results

- raw posts (sum over search pages): 821
- unique ids: 820
- filtered (like≥20 OR retweet≥5 OR A-batch whitelist): 362
- leads: 362 (all label=线索; no primary-source verification)
- spot-check: 3/3 matched (seed 20261107); see verify.md

## Pagination

- Early-stop queries left for round-2 continuation (schedule stop before page_cap): **6** (A02, A03, A04, A05, A06, A07)
- At page_cap with next_token remaining (not continued this round): B02, B04, B05, B06, B08, B09, B10, B11, B12, B13, B14, B15, B16
- First page empty (not an error): B01
- #109 account page samples (compared=true): A01 p2 (private ledger only)
