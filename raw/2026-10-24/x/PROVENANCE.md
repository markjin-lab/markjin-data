# X provenance (round 1, 2026-10-24)

Tool: `x.search_posts_all`; start_time=2026-10-21T20:59:05Z (now − 48h at round start), fixed end_time=2026-10-23T20:59:05Z (round start, 04:59 SGT); post.fields=created_at,author_id,public_metrics,entities,referenced_tweets; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `x-queries.md` (v2, 24 queries); snapshot in `../x-queries.md`. Pagination via `next_token`: A batches up to 4 pages, B topics up to 2 pages; every query either reached its page cap or the end of results, so none was stopped early.
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper and quota lines dropped). `hydrate-NN.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet,text,author_id,public_metrics; the tool also added its default expansions) for the filtered ids, same method.
Raw 1054 posts, 1053 unique; minus 405 ids already captured on earlier days → 648 new; filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 374 leads (all 线索). Hydrate lookup missing: 0.
Calls: search 60 (+1 discarded wrong-query A07 retry) + hydrate 4 = 65 (round 1).
Queries left for round-2 continuation: none (0).
Queries at page cap with results remaining (15): A03, A04, A05, B04, B05, B06, B08, B09, B10, B12, B13, B14, B15, B16, B17. Queries that reached the end of results (9): A01, A02, A06, A07, B01, B02, B03, B07, B11. First page returned 0 posts (not an error): B01.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 17033e91-8673-46c2-98e4-852bc69c1e31.txt | 25 | yes |
| 01-accounts-01-p2.json | A01 | 2 | a109123d-d06e-4e38-87de-279921242d17.txt | 8 | yes |
| 01-accounts-01-p3.json | A01 | 3 | 5b9e4ee2-8b91-462f-ae28-bf41cedb94a3.txt | 0 | no |
| 02-accounts-02.json | A02 | 1 | e72f0feb-4b19-4fab-8f8c-8dfc970bcb51.txt | 25 | yes |
| 02-accounts-02-p2.json | A02 | 2 | ef655fdb-fee7-493f-a2f6-e75e7594ed4c.txt | 24 | yes |
| 02-accounts-02-p3.json | A02 | 3 | 93ff400f-0d11-401a-93e4-2471512afd95.txt | 14 | yes |
| 02-accounts-02-p4.json | A02 | 4 | bdbb8c39-6152-4721-b866-2e07d359e385.txt | 0 | no |
| 03-accounts-03.json | A03 | 1 | aedce0d9-f509-4563-9b97-42a45f107e46.txt | 25 | yes |
| 03-accounts-03-p2.json | A03 | 2 | 96b45f80-0e1f-4eba-bfa9-f9d57aa8a7a1.txt | 25 | yes |
| 03-accounts-03-p3.json | A03 | 3 | cb42f588-7295-4d66-9f8f-c7e8e499bbc3.txt | 25 | yes |
| 03-accounts-03-p4.json | A03 | 4 | b44c6e48-25b0-42a3-a05d-2ddda85a3a57.txt | 25 | yes |
| 04-accounts-04.json | A04 | 1 | cc5022a8-c3b7-48eb-b9ea-f29ecba96bdc.txt | 25 | yes |
| 04-accounts-04-p2.json | A04 | 2 | ea7e7caa-5411-4454-8c00-21778ae2912c.txt | 25 | yes |
| 04-accounts-04-p3.json | A04 | 3 | bd811186-1bd6-4fba-aab6-82e4f4d3f17b.txt | 25 | yes |
| 04-accounts-04-p4.json | A04 | 4 | 22e52001-2a05-437c-b9af-463ba4070942.txt | 25 | yes |
| 05-accounts-05.json | A05 | 1 | f920de43-769b-436b-9bd9-11a80dd70d6f.txt | 25 | yes |
| 05-accounts-05-p2.json | A05 | 2 | cf0f70a0-770e-481b-b0f0-c3ae4729d151.txt | 25 | yes |
| 05-accounts-05-p3.json | A05 | 3 | c7f0872b-be8d-4dcb-b183-50d68fa5cc7e.txt | 25 | yes |
| 05-accounts-05-p4.json | A05 | 4 | bbdba4a4-a891-415b-9b4d-c236281bc2f9.txt | 25 | yes |
| 06-accounts-06.json | A06 | 1 | 2eb1202a-69df-4d9e-b77d-5225a962e8d0.txt | 25 | yes |
| 06-accounts-06-p2.json | A06 | 2 | 56e76b71-b4c8-4e7c-9067-4b7fd6943029.txt | 25 | yes |
| 06-accounts-06-p3.json | A06 | 3 | 976df409-fd26-4580-b412-ce4cf24adff3.txt | 7 | yes |
| 06-accounts-06-p4.json | A06 | 4 | a919ba97-d23f-4dcf-b961-36f393aca1c8.txt | 0 | no |
| 07-accounts-07.json | A07 | 1 | 697f9bb3-75d7-4a08-aeac-5ca166280dc7.txt | 25 | yes |
| 07-accounts-07-p2.json | A07 | 2 | f23fa369-c264-424a-8978-d9574d331e53.txt | 25 | yes |
| 07-accounts-07-p3.json | A07 | 3 | eb8fb060-8a10-423f-8e82-45634e116aa7.txt | 7 | yes |
| 07-accounts-07-p4.json | A07 | 4 | e43d8e75-94df-48f8-ac7d-4e9ac236f4b6.txt | 0 | no |
| 08-ai-tech-reports.json | B01 | 1 | 1ffe79d0-b86e-4e3f-a4e5-3eb7c60f39d5.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | acd5d8e4-6e35-4048-92e9-1f8d66a242b4.txt | 25 | yes |
| 09-ai-arxiv-p2.json | B02 | 2 | 00f190d3-6630-413c-86e3-6024bf23e47e.txt | 0 | no |
| 10-ai-benchmarks.json | B03 | 1 | 93ee9a07-667f-454a-ac52-737a14f539c8.txt | 25 | yes |
| 10-ai-benchmarks-p2.json | B03 | 2 | 299b07cf-e9b2-48de-8c73-a0786e907489.txt | 0 | no |
| 11-ai-compute.json | B04 | 1 | c55510ff-ffa4-402a-a36b-0ae8409929c7.txt | 25 | yes |
| 11-ai-compute-p2.json | B04 | 2 | 55a37031-d150-43df-8aae-2708c13606cd.txt | 6 | yes |
| 12-macro-pboc.json | B05 | 1 | 58269d98-4195-4726-a633-18c62c1ecf7f.txt | 25 | yes |
| 12-macro-pboc-p2.json | B05 | 2 | 2b01d87c-47c2-4d63-9f5f-525993510003.txt | 10 | yes |
| 13-macro-liquidity.json | B06 | 1 | c70c900c-d6d4-4041-a27b-dc75670c856c.txt | 25 | yes |
| 13-macro-liquidity-p2.json | B06 | 2 | 7b6d3bfc-4903-4fb9-b6b3-5ce62b46ed36.txt | 1 | yes |
| 14-physics-arxiv.json | B07 | 1 | 2a81b53d-9f95-4fe1-86ec-b99bcbf365f8.txt | 5 | yes |
| 14-physics-arxiv-p2.json | B07 | 2 | 301b4160-11f0-4012-bac9-53762a706d94.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | 96fcbb01-6928-48b4-8765-9643a0470217.txt | 25 | yes |
| 15-stock-chanlun-p2.json | B08 | 2 | 51b9ef48-a96e-4f2d-adb9-204a10b19c31.txt | 3 | yes |
| 16-stock-a-share.json | B09 | 1 | 214d6371-6d96-4069-b10f-bb1d64e5c552.txt | 25 | yes |
| 16-stock-a-share-p2.json | B09 | 2 | ca74dcaa-cace-4696-adf0-beefabb5b824.txt | 3 | yes |
| 17-geo-export-controls.json | B10 | 1 | dbe362ea-858a-4a3f-98c6-b6dc7db43d13.txt | 25 | yes |
| 17-geo-export-controls-p2.json | B10 | 2 | 4c32a458-3072-4a42-9757-fdeef49cedc9.txt | 15 | yes |
| 18-ai-governance.json | B11 | 1 | 1078eb28-0410-4751-ae15-7bf3771cb90c.txt | 25 | yes |
| 18-ai-governance-p2.json | B11 | 2 | bfa49848-5c00-4a0e-a87e-d4fd2ef3e924.txt | 0 | no |
| 19-energy.json | B12 | 1 | ec5e2b13-98d8-4fb6-a9c2-bd14ed2a50aa.txt | 25 | yes |
| 19-energy-p2.json | B12 | 2 | b3a51397-cc2f-4e2a-8161-df4761d6a42b.txt | 24 | yes |
| 20-bio.json | B13 | 1 | 1c931490-9799-4254-abea-0165bcd5013b.txt | 25 | yes |
| 20-bio-p2.json | B13 | 2 | fb635e01-3c80-42fd-b977-c44297aaab68.txt | 25 | yes |
| 21-semis.json | B14 | 1 | 7c1aaae1-2a3f-4964-a931-4bfbf7348926.txt | 25 | yes |
| 21-semis-p2.json | B14 | 2 | 74fcd8a4-87a5-402b-994b-8def03a95dd6.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | f90199bd-37ab-4c83-a8f0-7916b3929db0.txt | 25 | yes |
| 22-quantum-p2.json | B15 | 2 | e72eb3fd-8f97-4d12-b80c-30d965293243.txt | 4 | yes |
| 23-population.json | B16 | 1 | 2461b44f-4cde-4f93-83bd-c1cee3a60b7e.txt | 25 | yes |
| 23-population-p2.json | B16 | 2 | aec24d7d-76df-4882-b69f-4960f0cc5791.txt | 24 | yes |
| 24-bci.json | B17 | 1 | 24959b0d-4161-43be-807a-5ccd22a87008.txt | 24 | yes |
| 24-bci-p2.json | B17 | 2 | 14d156a6-4028-4b71-bb3c-1805bda2d41e.txt | 25 | yes |
