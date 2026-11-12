# X PROVENANCE — 2026-11-13 round1

- Mode: baseline (arXiv API + X only). improve/sources.yaml not on main; no fetch_primary/scrapers/FRED.
- Window: start_time=2026-11-10T20:56:01Z end_time=2026-11-12T20:56:01Z (48h ending at capture start UTC)
- Query set: x-queries.md (snapshot copied into raw/DATE/)
- Tool: x.search_posts_all (namespace `x`); pagination via next_token; hydrate via x.get_posts_by_ids
- Rate: ≤25/min; day budget ≤400
- Note: PR 未合并，按基线采

## Call counts

- Search calls: 47
- Hydrate calls: 9
- Discarded non-query tool call (not archived): 0
- Total X calls this round: 56

## Results

- raw posts (sum over search pages): 844
- unique ids: 840
- filtered (like≥20 OR retweet≥5 OR A-batch whitelist): 375
- leads: 375 (all label=线索; no primary-source verification)
- spot-check: 3/3 matched (seed 20261113); see verify.md

## Pagination

- Early-stop queries left for round-2 continuation (schedule stop before page_cap): **7** (A01, A02, A03, A04, A05, A06, A07)
- At page_cap with next_token remaining (not continued this round): B02, B03, B04, B05, B06, B08, B10, B11, B12, B13, B14, B15, B16, B17
- First page empty (not an error): B01
- Completed this round (no leftover token): B01, B07, B09
- #109 account page samples: compared=true none; compared=false schedule skip A01 p2 (5, interval 1-5); private ledger only
- Public redaction: none
- 新增对照写入前快照与近几日 raw（seen-ids 在 MANIFEST 最终核验后登记）
