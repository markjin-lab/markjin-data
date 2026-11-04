# X PROVENANCE — 2026-11-05 round1

- Mode: baseline (arXiv API + X only). improve/sources.yaml not on main; no fetch_primary/scrapers/FRED.
- Window: start_time=2026-11-02T20:50:00Z end_time=2026-11-04T20:50:00Z (48h ending at capture start UTC)
- Query set: x-queries.md (snapshot copied into raw/DATE/)
- Tool: x.search_posts_all (namespace `x`); pagination via next_token; hydrate via x.get_posts_by_ids
- Rate: ≤25/min; day budget ≤400
- Note: PR/improve/sources.yaml 未在 main，按基线采

## Call counts

- Search calls: 48
- Hydrate calls: 4
- Total X calls this round: 52

## Results

- raw posts (sum over search pages): 895
- unique ids: 892
- new vs seen-ids: (filled after merge)
- filtered (like≥20 OR retweet≥5 OR A-batch whitelist): 390
- leads: 390 (all label=线索; no primary-source verification)
- spot-check: 3/3 matched (seed 20261105); see verify.md

## Pagination

- Early-stop queries left for round-2 continuation (schedule stop before page_cap): **6** (A02, A03, A04, A05, A06, A07)
- At page_cap with next_token remaining (not continued this round): B02, B04, B05, B06, B08, B09, B10, B11, B12, B13, B14, B16, B17
- First page empty (not an error): B01
- #109 account page samples (compared=true): A01 p2 (private ledger only)

## Per-query pages

| id | slug | pages | cap | final_next | status | files |
|---|---|---|---|---|---|---|
| A01 | accounts-01 | 3 | 4 | no | under | 01-accounts-01.json, 01-accounts-01-p2.json, 01-accounts-01-p3.json |
| A02 | accounts-02 | 2 | 4 | yes | early_stop | 02-accounts-02.json, 02-accounts-02-p2.json |
| A03 | accounts-03 | 2 | 4 | yes | early_stop | 03-accounts-03.json, 03-accounts-03-p2.json |
| A04 | accounts-04 | 2 | 4 | yes | early_stop | 04-accounts-04.json, 04-accounts-04-p2.json |
| A05 | accounts-05 | 2 | 4 | yes | early_stop | 05-accounts-05.json, 05-accounts-05-p2.json |
| A06 | accounts-06 | 2 | 4 | yes | early_stop | 06-accounts-06.json, 06-accounts-06-p2.json |
| A07 | accounts-07 | 2 | 4 | yes | early_stop | 07-accounts-07.json, 07-accounts-07-p2.json |
| B01 | ai-tech-reports | 1 | 2 | no | empty | 08-ai-tech-reports.json |
| B02 | ai-arxiv | 2 | 2 | yes | cap | 09-ai-arxiv.json, 09-ai-arxiv-p2.json |
| B03 | ai-benchmarks | 2 | 2 | no | under | 10-ai-benchmarks.json, 10-ai-benchmarks-p2.json |
| B04 | ai-compute | 2 | 2 | yes | cap | 11-ai-compute.json, 11-ai-compute-p2.json |
| B05 | macro-pboc | 2 | 2 | yes | cap | 12-macro-pboc.json, 12-macro-pboc-p2.json |
| B06 | macro-liquidity | 2 | 2 | yes | cap | 13-macro-liquidity.json, 13-macro-liquidity-p2.json |
| B07 | physics-arxiv | 2 | 2 | no | under | 14-physics-arxiv.json, 14-physics-arxiv-p2.json |
| B08 | stock-chanlun | 2 | 2 | yes | cap | 15-stock-chanlun.json, 15-stock-chanlun-p2.json |
| B09 | stock-a-share | 2 | 2 | yes | cap | 16-stock-a-share.json, 16-stock-a-share-p2.json |
| B10 | geo-export-controls | 2 | 2 | yes | cap | 17-geo-export-controls.json, 17-geo-export-controls-p2.json |
| B11 | ai-governance | 2 | 2 | yes | cap | 18-ai-governance.json, 18-ai-governance-p2.json |
| B12 | energy | 2 | 2 | yes | cap | 19-energy.json, 19-energy-p2.json |
| B13 | bio | 2 | 2 | yes | cap | 20-bio.json, 20-bio-p2.json |
| B14 | semis | 2 | 2 | yes | cap | 21-semis.json, 21-semis-p2.json |
| B15 | quantum | 2 | 2 | no | under | 22-quantum.json, 22-quantum-p2.json |
| B16 | population | 2 | 2 | yes | cap | 23-population.json, 23-population-p2.json |
| B17 | bci | 2 | 2 | yes | cap | 24-bci.json, 24-bci-p2.json |
