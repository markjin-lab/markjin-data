# X PROVENANCE — 2026-11-12 round1

- Mode: baseline (arXiv API + X only). improve/sources.yaml not on main; no fetch_primary/scrapers/FRED.
- Window: start_time=2026-11-09T20:56:42Z end_time=2026-11-11T20:56:42Z (48h ending at capture start UTC)
- Query set: x-queries.md (snapshot copied into raw/DATE/)
- Tool: x.search_posts_all (namespace `x`); pagination via next_token; hydrate via x.get_posts_by_ids
- Rate: ≤25/min; day budget ≤400
- Note: PR 未合并，按基线采

## Call counts

- Search calls: 47
- Hydrate calls: 10
- Discarded non-query tool call (not archived): 0
- Total X calls this round: 57

## Results

- raw posts (sum over search pages): 928
- unique ids: 927
- filtered (like≥20 OR retweet≥5 OR A-batch whitelist): 410
- leads: 410 (all label=线索; no primary-source verification)
- spot-check: 3/3 matched (seed 20261112); see verify.md

## Pagination

- Early-stop queries left for round-2 continuation (schedule stop before page_cap): **7** (A01, A02, A03, A04, A05, A06, A07)
- At page_cap with next_token remaining (not continued this round): B02, B04, B05, B06, B08, B09, B10, B11, B12, B13, B14, B15, B16, B17
- First page empty (not an error): B01
- Completed this round (no leftover token): B01, B03, B07
- #109 account page samples: compared=true none; compared=false schedule skip A01 p2 (14, interval 11-15), A07 p2 (20, interval 16-20); private ledger only
- Public redaction: none
- 新增对照写入前快照与近几日 raw（seen-ids 在 MANIFEST 最终核验后登记）
