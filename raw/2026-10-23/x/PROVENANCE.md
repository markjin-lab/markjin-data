# X provenance (round 1, 2026-10-23)

Tool: `x.search_posts_all`; start_time=2026-10-20T20:58:00Z (now − 48h at round start), fixed end_time=2026-10-22T20:58:00Z (round start, 04:58 SGT); post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries); snapshot in `../x-queries.md`. Pagination via `next_token`: A batches up to 4 pages, B topics up to 2 pages; every query either reached its page cap or the end of results, so none was stopped early.
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper and quota lines dropped). `hydrate-NN.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet; the tool also added its default expansions) for the filtered ids, same method.
Raw 1008 posts, 1003 unique; minus 387 ids already captured on earlier days → 616 new; filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 371 leads (all 线索). Hydrate lookup missing: 0.
Calls: search 60 + hydrate 4 = 64 (round 1).
Queries left for round-2 continuation: none (0).
Queries at page cap with results remaining (14): A03, A04, A05, B04, B05, B06, B08, B10, B11, B12, B13, B14, B16, B17. Queries that reached the end of results (10): A01, A02, A06, A07, B01, B02, B03, B07, B09, B15. First page returned 0 posts (not an error): B01.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 0d3e7f63-4a18-43a7-935b-f38b33b87304.txt | 25 | yes |
| 01-accounts-01-p2.json | A01 | 2 | 845b7691-35c2-4b7d-8d61-26b9697d9e71.txt | 4 | yes |
| 01-accounts-01-p3.json | A01 | 3 | 4860fad6-ecb7-43e1-b469-082efb6f2246.txt | 0 | no |
| 02-accounts-02.json | A02 | 1 | 6f60c437-8f45-48f1-901d-9e47ae24451d.txt | 24 | yes |
| 02-accounts-02-p2.json | A02 | 2 | 53450a25-5ad0-4040-9449-60d9702a1446.txt | 25 | yes |
| 02-accounts-02-p3.json | A02 | 3 | 0d0f947c-295c-428a-88f2-93fa1dc312c0.txt | 3 | yes |
| 02-accounts-02-p4.json | A02 | 4 | 7e0fa03e-69c5-4a1c-b8bc-2d3a2634ffff.txt | 0 | no |
| 03-accounts-03.json | A03 | 1 | 7c1751c8-3730-44ea-926d-350b57c87e7a.txt | 25 | yes |
| 03-accounts-03-p2.json | A03 | 2 | 2cc74db3-a2a5-46aa-92a5-41fd42132759.txt | 25 | yes |
| 03-accounts-03-p3.json | A03 | 3 | 2229336d-6414-4097-822f-c357ebe7f915.txt | 25 | yes |
| 03-accounts-03-p4.json | A03 | 4 | cac97c31-eb29-4936-a1f5-540ed85fd0ee.txt | 25 | yes |
| 04-accounts-04.json | A04 | 1 | ba2a7fea-3023-42dc-b912-86710ba59c30.txt | 25 | yes |
| 04-accounts-04-p2.json | A04 | 2 | 67fbc4bf-307d-4446-b851-9c1fd3f1cf22.txt | 25 | yes |
| 04-accounts-04-p3.json | A04 | 3 | 39101200-430f-41ac-b3e9-4ad6b0894a91.txt | 25 | yes |
| 04-accounts-04-p4.json | A04 | 4 | aebe19a7-5c69-4541-bf3a-4a4993be443c.txt | 25 | yes |
| 05-accounts-05.json | A05 | 1 | df61d43c-b3aa-4dc9-a1c4-342bde78b29f.txt | 25 | yes |
| 05-accounts-05-p2.json | A05 | 2 | c79be2f6-b0c7-4d25-8a9e-2a6de9e8b987.txt | 25 | yes |
| 05-accounts-05-p3.json | A05 | 3 | 87766e75-25bc-422e-93fa-a1663e9325e6.txt | 25 | yes |
| 05-accounts-05-p4.json | A05 | 4 | 358a3086-abf1-4109-9989-6f7d2c4cd21a.txt | 25 | yes |
| 06-accounts-06.json | A06 | 1 | 9b83ee63-4b39-4e30-8477-c5c64962804c.txt | 25 | yes |
| 06-accounts-06-p2.json | A06 | 2 | 8be4fbeb-24ce-4e90-8d39-b3e453c0ec94.txt | 25 | yes |
| 06-accounts-06-p3.json | A06 | 3 | 7fff0b32-774d-4547-8e1f-2e6f6ca523b5.txt | 22 | yes |
| 06-accounts-06-p4.json | A06 | 4 | 583b2218-4b43-48fa-b774-a03efe6f52ce.txt | 0 | no |
| 07-accounts-07.json | A07 | 1 | abf5169d-9401-44fd-bbe6-98e7f1e887bb.txt | 25 | yes |
| 07-accounts-07-p2.json | A07 | 2 | f71dec01-6c39-40f4-a23a-f931ccdb0171.txt | 25 | yes |
| 07-accounts-07-p3.json | A07 | 3 | 6c5452a7-c9f0-41b2-9420-397c965706f3.txt | 12 | yes |
| 07-accounts-07-p4.json | A07 | 4 | 0c792e44-f72b-4d41-961c-638006f1a8f8.txt | 0 | no |
| 08-ai-tech-reports.json | B01 | 1 | 88095507-b720-4786-8a35-adb009a4e9e8.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | ebf408d7-aeb5-4bcb-a8d3-bdac188b6bc1.txt | 25 | yes |
| 09-ai-arxiv-p2.json | B02 | 2 | 466820a4-37a6-484d-8099-447a223fb33c.txt | 0 | no |
| 10-ai-benchmarks.json | B03 | 1 | ac8c3d49-9340-4722-a947-e31a5dd61798.txt | 25 | yes |
| 10-ai-benchmarks-p2.json | B03 | 2 | 53eb9f72-f4d4-4436-a188-fe3d35f1c417.txt | 0 | no |
| 11-ai-compute.json | B04 | 1 | dfc231f8-bac7-4848-9f13-49bfbc9fdff3.txt | 25 | yes |
| 11-ai-compute-p2.json | B04 | 2 | ca7f668a-d528-4fa1-9a4a-54d54ad2c95d.txt | 8 | yes |
| 12-macro-pboc.json | B05 | 1 | 7c5058ed-6b2d-491b-9b93-fcb23f9f50e4.txt | 25 | yes |
| 12-macro-pboc-p2.json | B05 | 2 | 22a5d26d-1f72-448c-8b75-c7fe1a1ec20e.txt | 22 | yes |
| 13-macro-liquidity.json | B06 | 1 | 065114d7-27e0-434c-a3a8-85eb80387692.txt | 25 | yes |
| 13-macro-liquidity-p2.json | B06 | 2 | 56be727c-5142-47f6-a083-45b98a5a6608.txt | 3 | yes |
| 14-physics-arxiv.json | B07 | 1 | 6d6f7f96-afb8-4602-8f0e-1852d1bf140c.txt | 9 | yes |
| 14-physics-arxiv-p2.json | B07 | 2 | a69e2cee-c4d4-4e30-b6d3-f793871587b5.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | fbb6b764-f1d5-4901-a679-1c7c056ae0a4.txt | 25 | yes |
| 15-stock-chanlun-p2.json | B08 | 2 | 8cd14db5-77e8-42c7-9d60-968fee55f4fc.txt | 1 | yes |
| 16-stock-a-share.json | B09 | 1 | 204a5b47-890b-4a0b-8ab8-336ada0eebd4.txt | 25 | yes |
| 16-stock-a-share-p2.json | B09 | 2 | 8e8fa32d-b80a-4e34-9f09-edd709b72ccc.txt | 0 | no |
| 17-geo-export-controls.json | B10 | 1 | 42bec768-c6bd-4b17-8812-54afca28319c.txt | 25 | yes |
| 17-geo-export-controls-p2.json | B10 | 2 | 1b14a7a3-4984-4996-8a4f-597583e0a516.txt | 7 | yes |
| 18-ai-governance.json | B11 | 1 | 47386ca9-c143-40fe-8e4d-938a49147763.txt | 25 | yes |
| 18-ai-governance-p2.json | B11 | 2 | 177f282a-70a8-4640-9714-a82e60ebd11d.txt | 11 | yes |
| 19-energy.json | B12 | 1 | 4c1f3af0-66cc-4cf7-9869-b826bd2fb2f1.txt | 24 | yes |
| 19-energy-p2.json | B12 | 2 | a63b6de2-258c-4c3a-9c91-0e1b540e9ec3.txt | 19 | yes |
| 20-bio.json | B13 | 1 | 69d8cb2d-6e29-4251-abb0-4210763cbc84.txt | 25 | yes |
| 20-bio-p2.json | B13 | 2 | ed75525e-53ed-4418-8710-d2258af6dc6e.txt | 9 | yes |
| 21-semis.json | B14 | 1 | 7991f093-36f8-4dfd-9fd9-350ea0623faa.txt | 25 | yes |
| 21-semis-p2.json | B14 | 2 | e5066459-66c0-47e0-9066-60618ed94b7a.txt | 20 | yes |
| 22-quantum.json | B15 | 1 | 1c00e749-ee20-481a-a745-98519fcb1cfd.txt | 25 | yes |
| 22-quantum-p2.json | B15 | 2 | 9db62a8a-507a-4ecc-acc5-61c998e9110d.txt | 0 | no |
| 23-population.json | B16 | 1 | e76fae11-9afa-4d9a-97a4-933df097f647.txt | 25 | yes |
| 23-population-p2.json | B16 | 2 | e34d1528-7aa1-469a-bcbc-3ce88a788819.txt | 4 | yes |
| 24-bci.json | B17 | 1 | c04f1fc6-4d35-413b-a545-ddef71f04211.txt | 24 | yes |
| 24-bci-p2.json | B17 | 2 | 16bea76b-e9fa-474e-936a-2c5ef7e07392.txt | 7 | yes |
