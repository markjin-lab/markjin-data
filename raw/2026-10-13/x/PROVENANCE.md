# X provenance (round 1, 2026-10-13)

Tool: `x.search_posts_all`; start_time=2026-10-10T21:06:00Z (now − 48h at 05:06 SGT); post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Pagination via `next_token` (A batches ≤4 pages, B topics ≤2 pages; stop at no next_token / 0 results). Queries: working copy x-queries v2 (main has no newer version); snapshot in `../x-queries.md`.
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper and quota lines dropped). `hydrate-NN.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet) for the filtered ids, same method.
Calls: search 55 + hydrate 5 = 60 (round 1).

| file | query | page | spill file | result_count |
|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 1e418a6d-33ae-46de-b959-24fdb99b0714.txt | 17 |
| 02-accounts-02.json | A02 | 1 | 486f355e-0326-45a0-9102-4a2dd87b6595.txt | 25 |
| 03-accounts-03.json | A03 | 1 | 3e6b6e48-87f7-4377-8631-bc40b5e0545c.txt | 25 |
| 04-accounts-04.json | A04 | 1 | 592f8cc8-3f21-440a-b5e2-88df964e4248.txt | 25 |
| 05-accounts-05.json | A05 | 1 | f086ac87-553c-4ddf-94af-debbcea6a290.txt | 25 |
| 06-accounts-06.json | A06 | 1 | ddaaff0f-88b6-4901-904d-aa88461f670f.txt | 25 |
| 07-accounts-07.json | A07 | 1 | 65a04f0c-fcbb-43fc-aee4-bd580acf8eb8.txt | 16 |
| 08-ai-tech-reports.json | B01 | 1 | 61643a15-1e5e-47e0-a413-82034af5d34f.txt | 0 |
| 09-ai-arxiv.json | B02 | 1 | da274c60-6c3a-4b82-a73b-b6c5d73778e0.txt | 25 |
| 10-ai-benchmarks.json | B03 | 1 | 8818f469-f7c0-4f4f-9d85-7bea223f5438.txt | 25 |
| 11-ai-compute.json | B04 | 1 | 71a01d1d-0340-422a-9267-81e3f345292c.txt | 25 |
| 12-macro-pboc.json | B05 | 1 | b05ca255-c371-4af2-893a-835dd7d9c0b7.txt | 25 |
| 13-macro-liquidity.json | B06 | 1 | 9a9d22d7-0fb0-4146-9119-360a66921e0b.txt | 25 |
| 14-physics-arxiv.json | B07 | 1 | 14a196ca-ff71-4911-9d91-701152fa90e7.txt | 1 |
| 15-stock-chanlun.json | B08 | 1 | d0d8a165-d415-45df-bb0f-21986e4a9c8e.txt | 25 |
| 16-stock-a-share.json | B09 | 1 | ef914e66-6f8c-4ade-87b5-f50305f562d7.txt | 25 |
| 17-geo-export-controls.json | B10 | 1 | f8778214-62e8-4384-bfe1-227a3e1240f6.txt | 25 |
| 18-ai-governance.json | B11 | 1 | 4d77ca69-77c1-4ad9-a4e8-89f8e441b535.txt | 25 |
| 19-energy.json | B12 | 1 | 878b52b5-e8f9-44a1-89e2-e99e713c01db.txt | 25 |
| 20-bio.json | B13 | 1 | 47a86a95-9a61-4168-9e0a-31d9ab49f9b5.txt | 25 |
| 21-semis.json | B14 | 1 | 04baa8e2-51b0-4672-89b8-a9f26f199491.txt | 25 |
| 22-quantum.json | B15 | 1 | 6a480bdd-db06-4dc4-a3a8-0c049ae73f91.txt | 25 |
| 23-population.json | B16 | 1 | a228c953-7327-4ad0-878b-ad4a24653b20.txt | 25 |
| 24-bci.json | B17 | 1 | 28d659bf-03f5-45e2-9750-39b85e46905e.txt | 25 |
| 01-accounts-01-p2.json | A01 | 2 | 5803fc75-0eaf-4e52-9615-7dcf4d44813b.txt | 0 |
| 02-accounts-02-p2.json | A02 | 2 | 68e4dbc9-26a6-4efe-9e1f-ea2bb6dfbbf1.txt | 13 |
| 03-accounts-03-p2.json | A03 | 2 | d396d6b4-9810-4050-81dc-aa90a3d22c04.txt | 25 |
| 04-accounts-04-p2.json | A04 | 2 | 725c31cd-5de3-4075-9c41-c89e2584bfde.txt | 25 |
| 05-accounts-05-p2.json | A05 | 2 | 1ba3b754-7ef5-4cb3-9a83-dc4765c40685.txt | 25 |
| 06-accounts-06-p2.json | A06 | 2 | 31732bbe-f2ce-40f6-895f-9d0a15d46bc0.txt | 1 |
| 07-accounts-07-p2.json | A07 | 2 | 764a0886-586b-4deb-8864-83bef81a693f.txt | 0 |
| 09-ai-arxiv-p2.json | B02 | 2 | 75b9a057-7b06-4724-9f60-2c6a129f6c4b.txt | 3 |
| 10-ai-benchmarks-p2.json | B03 | 2 | ed2222d1-5e41-45d7-b5b6-a46182424dcf.txt | 0 |
| 11-ai-compute-p2.json | B04 | 2 | 2b96a822-d792-46e5-af24-e53986dd9d13.txt | 25 |
| 12-macro-pboc-p2.json | B05 | 2 | 44804760-4b7d-4edb-9116-0d32b97cda6d.txt | 2 |
| 13-macro-liquidity-p2.json | B06 | 2 | aae80b05-4713-41a7-bf57-be13c09884dd.txt | 5 |
| 14-physics-arxiv-p2.json | B07 | 2 | 968e783d-d562-47a9-be92-8693fa9bc9fb.txt | 0 |
| 15-stock-chanlun-p2.json | B08 | 2 | f27a732f-4200-46bd-b9b0-6d2b80f26d34.txt | 0 |
| 16-stock-a-share-p2.json | B09 | 2 | 7e602b3b-b10f-44b9-8b1e-a9e82cc81ac7.txt | 1 |
| 17-geo-export-controls-p2.json | B10 | 2 | 39f51e21-30e3-4a10-a1ea-a4b1b927a129.txt | 1 |
| 18-ai-governance-p2.json | B11 | 2 | 547d7603-c245-4f1c-b3ea-750c82c1d2dd.txt | 19 |
| 19-energy-p2.json | B12 | 2 | cbeb1199-51b5-4a25-93e5-f9154e1bf415.txt | 25 |
| 20-bio-p2.json | B13 | 2 | f61aa604-7d3c-4229-b4f1-ce51a8f77c1f.txt | 23 |
| 21-semis-p2.json | B14 | 2 | 9a3b7c71-943a-487b-887c-0faf418d0974.txt | 25 |
| 22-quantum-p2.json | B15 | 2 | ea7f0f15-37c3-4a4b-b1f0-58720d1ab5cc.txt | 0 |
| 23-population-p2.json | B16 | 2 | 09ebc4cd-24fb-4508-b606-7d364e6025e5.txt | 24 |
| 24-bci-p2.json | B17 | 2 | 57698e7e-9295-468c-8109-aca832ad151c.txt | 15 |
| 02-accounts-02-p3.json | A02 | 3 | cba390a2-d225-4643-8cab-fdc0b981910a.txt | 0 |
| 03-accounts-03-p3.json | A03 | 3 | 1b90ac63-3766-493c-8056-12367cbeee75.txt | 25 |
| 04-accounts-04-p3.json | A04 | 3 | 14929e64-4576-4d40-b329-587dffb1a4c2.txt | 20 |
| 05-accounts-05-p3.json | A05 | 3 | 1baaa23f-5890-4fcf-802a-6d75efa68e2c.txt | 25 |
| 06-accounts-06-p3.json | A06 | 3 | a193acfb-159b-4dec-a84e-c4aebab2c660.txt | 0 |
| 03-accounts-03-p4.json | A03 | 4 | 10604b7a-dddb-4a39-8fed-2cbd4d4d3ee9.txt | 16 |
| 04-accounts-04-p4.json | A04 | 4 | 8c3b68a1-603c-4e38-b5b6-c0486880e2ec.txt | 0 |
| 05-accounts-05-p4.json | A05 | 4 | 3cc95fcf-4095-45ce-8479-630edb7c9943.txt | 25 |
| hydrate-01.json | lookup | - | 2be75b83-c17d-47a1-896e-153b08b59ab0.txt | 100 |
| hydrate-02.json | lookup | - | 6182ff14-7cab-4128-9475-da22f987ae8c.txt | 100 |
| hydrate-03.json | lookup | - | cf43317d-5d5e-4454-ae98-204f37fdd46e.txt | 100 |
| hydrate-04.json | lookup | - | 4ffb57f2-d6e9-4d8e-abd6-460ab69e2655.txt | 100 |
| hydrate-05.json | lookup | - | 4e83b55b-603d-4702-bd12-1fbf2e429cc6.txt | 6 |
