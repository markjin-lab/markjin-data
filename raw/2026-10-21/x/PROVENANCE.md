# X provenance (round 1, 2026-10-21)

Tool: `x.search_posts_all`; start_time=2026-10-18T20:59:00Z (now − 48h at round start), fixed end_time=2026-10-20T20:59:00Z (round start, 04:59 SGT); post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
The tool moved end_time to at least 10 s in the past for the first-page calls of A01 (effective 2026-10-20T20:58:36Z) and A02 (effective 2026-10-20T20:58:38Z); their later pages reused the same effective end_time. All other calls used 2026-10-20T20:59:00Z.
Queries: main `improve/x-queries.md` (v2, 24 queries); snapshot in `../x-queries.md`. Pagination via `next_token`: A batches up to 4 pages, B topics up to 2 pages; every query either reached its page cap or the end of results, so none was stopped early.
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, end_time notice, quota, media and video notice lines dropped). `hydrate-NN.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet; the tool also added its default expansions) for the filtered ids, same method.
Raw 1077 posts, 1075 unique; minus 362 ids already captured on earlier days → 713 new; filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 434 leads (all 线索). Hydrate lookup missing: 0.
Calls: search 59 + hydrate 5 = 64 (round 1).
Queries left for round-2 continuation: none (0).
Queries at page cap with results remaining (17): A03, A04, A05, A07, B02, B03, B04, B05, B06, B08, B09, B10, B12, B14, B15, B16, B17. Queries that reached the end of results (7): A01, A02, A06, B01, B07, B11, B13. First page returned 0 posts (not an error): B01, B07.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | aaebe3cb-6e68-4e6a-885b-e2d211711988.txt | 25 | yes |
| 02-accounts-02.json | A02 | 1 | 0682672f-666a-42dc-9dd4-fcd9dcf89d88.txt | 24 | yes |
| 03-accounts-03.json | A03 | 1 | 97efe1ad-0868-4a6c-9ced-f37f7b20fd5a.txt | 25 | yes |
| 04-accounts-04.json | A04 | 1 | c8cbbd4b-14f3-4404-86f2-455bce13e6dc.txt | 25 | yes |
| 05-accounts-05.json | A05 | 1 | ac302e17-38a7-4648-9cc4-87e2c2b38ba2.txt | 25 | yes |
| 06-accounts-06.json | A06 | 1 | e69bfb9b-0208-496b-b74f-c227b00ea93a.txt | 25 | yes |
| 07-accounts-07.json | A07 | 1 | 36a894e9-79fa-4b21-89bf-b4d6bbf2080b.txt | 25 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 51d3432b-4669-4ef2-b4f3-1865a5c24d68.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | cc7533d0-7761-4431-a9ab-0db52e7bb627.txt | 25 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 745f4ab3-0976-432a-b201-22cbe6a72761.txt | 25 | yes |
| 11-ai-compute.json | B04 | 1 | 732ca982-6656-4c1f-976b-1efee5112994.txt | 25 | yes |
| 12-macro-pboc.json | B05 | 1 | 120ad897-4888-4b96-b915-2af9d198259a.txt | 25 | yes |
| 13-macro-liquidity.json | B06 | 1 | 320abb5d-74b3-4d36-b126-cc0e5178da2b.txt | 25 | yes |
| 14-physics-arxiv.json | B07 | 1 | c820cac0-3d13-4fb6-8104-5840a2775fa8.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | 60fff85f-1035-433c-97bf-5265510db5e6.txt | 24 | yes |
| 16-stock-a-share.json | B09 | 1 | 7394a740-a0fc-4b22-9cb3-575a5d7f43f7.txt | 25 | yes |
| 17-geo-export-controls.json | B10 | 1 | 42910214-fc81-408a-b7c7-0a34809a841c.txt | 25 | yes |
| 18-ai-governance.json | B11 | 1 | b1b452d9-dc89-482c-b557-215e6be463ee.txt | 24 | yes |
| 19-energy.json | B12 | 1 | c58f2423-32fa-42ea-a1c6-20cf2f3a7fc5.txt | 25 | yes |
| 20-bio.json | B13 | 1 | ee026d4d-6e1e-4fec-97c6-92d2e5bfe5dd.txt | 24 | yes |
| 21-semis.json | B14 | 1 | 6088a50e-667f-4c3a-a519-c6dde7605e30.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 58bd79d7-fbff-4a79-9b44-6ae5940f7831.txt | 25 | yes |
| 23-population.json | B16 | 1 | 6de67de7-5ad3-4c8d-8fdb-1ca1a7008462.txt | 25 | yes |
| 24-bci.json | B17 | 1 | 3028f571-f592-4564-adaf-65641cdc2501.txt | 25 | yes |
| 01-accounts-01-p2.json | A01 | 2 | 7aec021d-9570-4bc3-a650-8e2c57ffd976.txt | 2 | yes |
| 02-accounts-02-p2.json | A02 | 2 | dce231d9-09a7-4ee1-8175-32f5626870d7.txt | 24 | yes |
| 03-accounts-03-p2.json | A03 | 2 | 33ddfd2a-c6c5-45eb-911c-e23e2bee0f63.txt | 25 | yes |
| 04-accounts-04-p2.json | A04 | 2 | 53893a7a-cb86-47e7-b573-275eb937dc7c.txt | 25 | yes |
| 05-accounts-05-p2.json | A05 | 2 | 7740239b-99a6-4282-9e7e-94b34e0c15c9.txt | 25 | yes |
| 06-accounts-06-p2.json | A06 | 2 | ec245577-4b29-43fd-ab37-be8332c3dc66.txt | 25 | yes |
| 07-accounts-07-p2.json | A07 | 2 | 81a30b62-2c8a-401d-b056-5e435fa2e3c0.txt | 25 | yes |
| 09-ai-arxiv-p2.json | B02 | 2 | 6c48592d-e304-49c7-ba18-e3a9bf8aae77.txt | 2 | yes |
| 10-ai-benchmarks-p2.json | B03 | 2 | 513030aa-41ea-4ecd-92ee-4c40012f1597.txt | 1 | yes |
| 11-ai-compute-p2.json | B04 | 2 | 3480430e-0281-45f7-976b-29dda0f3cff6.txt | 25 | yes |
| 12-macro-pboc-p2.json | B05 | 2 | 2fef1542-b4ea-493f-9d82-463d4963a062.txt | 25 | yes |
| 13-macro-liquidity-p2.json | B06 | 2 | 442b999b-1cad-4b0e-aced-ac5ed136c1ed.txt | 25 | yes |
| 15-stock-chanlun-p2.json | B08 | 2 | 64251546-2e3a-4040-85c7-cecfe55ac960.txt | 0 | yes |
| 16-stock-a-share-p2.json | B09 | 2 | 9a425200-72ba-4106-99b2-1d80a59e70c0.txt | 2 | yes |
| 17-geo-export-controls-p2.json | B10 | 2 | 996dd3a7-79e8-4623-9ae7-2bec3e339786.txt | 3 | yes |
| 18-ai-governance-p2.json | B11 | 2 | 2ec1fc63-fc36-425f-93c6-4712dbc7558d.txt | 0 | no |
| 19-energy-p2.json | B12 | 2 | 44ba8b06-fe98-4e98-ab72-0033235ebb0f.txt | 25 | yes |
| 20-bio-p2.json | B13 | 2 | b9229142-cdca-47f7-8f2e-d78075d6101b.txt | 0 | no |
| 21-semis-p2.json | B14 | 2 | 9ccc2a68-d759-4784-b232-bd9b2d5a948a.txt | 25 | yes |
| 22-quantum-p2.json | B15 | 2 | 073a2bfb-e180-4ac4-9ea5-13c64babb4e0.txt | 2 | yes |
| 23-population-p2.json | B16 | 2 | 96157882-9c5b-489b-8787-bdda1f019053.txt | 7 | yes |
| 24-bci-p2.json | B17 | 2 | e17acd83-8ec6-4776-aae7-8f8da87e9397.txt | 24 | yes |
| 01-accounts-01-p3.json | A01 | 3 | 74942cdf-1039-4674-aaee-e4d8078bd6fc.txt | 0 | no |
| 02-accounts-02-p3.json | A02 | 3 | c655a0ae-959d-499a-821b-225736ac36a4.txt | 4 | yes |
| 03-accounts-03-p3.json | A03 | 3 | 55d5668c-b8bf-4190-9333-7dcafcc6789e.txt | 25 | yes |
| 04-accounts-04-p3.json | A04 | 3 | e0ae2217-840e-4838-894a-80f41c00d767.txt | 25 | yes |
| 05-accounts-05-p3.json | A05 | 3 | 7e01dcd0-ddf4-4867-9db3-8f0ab7956ff0.txt | 25 | yes |
| 06-accounts-06-p3.json | A06 | 3 | d7efb513-52fb-4ff1-a2d0-6d018b765ede.txt | 10 | yes |
| 07-accounts-07-p3.json | A07 | 3 | 690145c8-dfc9-4db0-9848-3e8284dc7647.txt | 25 | yes |
| 02-accounts-02-p4.json | A02 | 4 | e9fccb20-ca23-4134-91bf-f4b7e326403c.txt | 0 | no |
| 03-accounts-03-p4.json | A03 | 4 | aa4ea478-eb24-4a15-bb36-7823aea5bd20.txt | 25 | yes |
| 04-accounts-04-p4.json | A04 | 4 | b4f81b45-0ddc-44ac-8288-ba83e898d6ab.txt | 25 | yes |
| 05-accounts-05-p4.json | A05 | 4 | f97ae079-f7b2-4e10-b1b9-d896d921873b.txt | 25 | yes |
| 06-accounts-06-p4.json | A06 | 4 | 87e6204c-a8ec-4b88-bb2b-0dd7e38720a1.txt | 0 | no |
| 07-accounts-07-p4.json | A07 | 4 | d9bc7df6-ee33-4a74-885a-8e5c594e066b.txt | 25 | yes |
