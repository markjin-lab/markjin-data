# X provenance (round 1, 2026-10-20)

Tool: `x.search_posts_all`; start_time=2026-10-17T21:00:00Z (now − 48h at ~04:59 SGT), fixed end_time=2026-10-19T21:00:00Z (round start, 05:00 SGT); post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
The tool moved end_time to at least 10 s in the past for the first-page calls of A01–A07 and B01–B05 (effective end_time A01 20:59:09Z, A02 20:59:12Z, A03 20:59:15Z, A04 20:59:18Z, A05 20:59:21Z, A06 20:59:24Z, A07 20:59:26Z, B01 20:59:29Z, B02 20:59:31Z, B03 20:59:33Z, B04 20:59:35Z, B05 20:59:37Z, all 2026-10-19); their later pages reused the same effective end_time. All other calls used 2026-10-19T21:00:00Z.
Queries: main `improve/x-queries.md` (v2, 24 queries); snapshot in `../x-queries.md`. Pagination via `next_token`: A batches up to 4 pages, B topics up to 2 pages; every query either reached its page cap or the end of results, so none was stopped early.
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, end_time notice, quota and media-notice lines dropped). `hydrate-NN.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet; the tool also added its default expansions) for the filtered ids, same method.
Raw 910 posts, 903 unique; minus 249 ids already captured on earlier days → 654 new; filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 344 leads (all 线索). Hydrate lookup missing: 0.
Calls: search 55 + hydrate 4 = 59 (round 1).
Queries left for round-2 continuation: none (0).
Queries at page cap with results remaining (15): A04, A05, B02, B04, B05, B06, B08, B10, B11, B12, B13, B14, B15, B16, B17. Queries that reached the end of results (9): A01, A02, A03, A06, A07, B01, B03, B07, B09. First page returned 0 posts (not an error): B01, B07.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 5ce16d33-d28e-4ea7-8be7-21752f347695.txt | 14 | yes |
| 02-accounts-02.json | A02 | 1 | ccb49036-0fd8-4856-b908-ae92d3a530fd.txt | 24 | yes |
| 03-accounts-03.json | A03 | 1 | a16acc5e-330d-4a54-ab6c-21e32295d25a.txt | 25 | yes |
| 04-accounts-04.json | A04 | 1 | 95e5af84-3ee8-498b-9f67-dd159a0f99e9.txt | 25 | yes |
| 05-accounts-05.json | A05 | 1 | df0c07ca-a0a6-44a2-8c52-1d0edd266d8b.txt | 25 | yes |
| 06-accounts-06.json | A06 | 1 | b9701175-785a-4333-b4f0-bdf2347f2f59.txt | 25 | yes |
| 07-accounts-07.json | A07 | 1 | cc3047bb-006c-4114-adcc-7a9902376f46.txt | 25 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 5f0a22f1-8d57-4a53-8709-a295d09adf13.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | 59ede983-4176-416f-9fa1-e3a33a733d54.txt | 25 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 7e8ed455-3799-494c-8a2d-487e20473bbc.txt | 25 | yes |
| 11-ai-compute.json | B04 | 1 | b61f7ea5-674b-4d9b-a580-3c40ae3ec295.txt | 25 | yes |
| 12-macro-pboc.json | B05 | 1 | a9b8ae23-c499-4ef6-ac95-ad44123e810f.txt | 25 | yes |
| 13-macro-liquidity.json | B06 | 1 | 36df61ba-4d85-4c36-8141-f5ba53907601.txt | 25 | yes |
| 14-physics-arxiv.json | B07 | 1 | 350a5efa-975d-4984-9194-09f4d329b1a9.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | 7654d247-aecf-4282-83e6-ff49364915de.txt | 24 | yes |
| 16-stock-a-share.json | B09 | 1 | ebfe5f23-12a9-4ef2-87c3-c52b365f476a.txt | 25 | yes |
| 17-geo-export-controls.json | B10 | 1 | 3aa38ea1-bc79-48d0-a9c0-6435ee8badc6.txt | 25 | yes |
| 18-ai-governance.json | B11 | 1 | a32faec5-3bac-4b7f-9b5c-44c5037e8c2d.txt | 25 | yes |
| 19-energy.json | B12 | 1 | b076f6d0-6430-407b-8510-182496f3e596.txt | 25 | yes |
| 20-bio.json | B13 | 1 | eb4eeda7-ffc2-4784-af54-0b5ee16134ab.txt | 24 | yes |
| 21-semis.json | B14 | 1 | 39631086-05a0-406f-9628-1a933a53687f.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 9999a5bd-c794-4356-940d-d6bfb04a7b0f.txt | 25 | yes |
| 23-population.json | B16 | 1 | f4876999-e16c-4efb-bf9f-bd3ff8443bad.txt | 25 | yes |
| 24-bci.json | B17 | 1 | 1788266a-76e2-4644-a3bc-3d06aa1e2a3e.txt | 25 | yes |
| 01-accounts-01-p2.json | A01 | 2 | 19329ca8-fb3f-4d59-abf9-5ab20f8ab59a.txt | 0 | no |
| 02-accounts-02-p2.json | A02 | 2 | 3b39f7d1-b9e7-4243-90c9-effa383d8794.txt | 15 | yes |
| 03-accounts-03-p2.json | A03 | 2 | f563c8da-b17e-4b1c-bb3d-6d4664f5624e.txt | 25 | yes |
| 04-accounts-04-p2.json | A04 | 2 | 665a6d81-73b9-4f51-94ca-34538db519e1.txt | 25 | yes |
| 05-accounts-05-p2.json | A05 | 2 | cc77957e-96b6-4bfc-b9ce-2e1c07feec24.txt | 25 | yes |
| 06-accounts-06-p2.json | A06 | 2 | 4ee47ca2-e246-4120-843a-a4004b64914e.txt | 6 | yes |
| 07-accounts-07-p2.json | A07 | 2 | eb68baae-18dc-427f-b697-cce359417934.txt | 15 | yes |
| 09-ai-arxiv-p2.json | B02 | 2 | 62d91332-7848-4e13-9352-ee179fb52a00.txt | 12 | yes |
| 10-ai-benchmarks-p2.json | B03 | 2 | f6426d56-f65f-4465-b076-cb3c2a393da6.txt | 0 | no |
| 11-ai-compute-p2.json | B04 | 2 | 7ecc4b38-71ab-4d08-a8ba-c7998ff0e666.txt | 22 | yes |
| 12-macro-pboc-p2.json | B05 | 2 | 93da3ed0-832a-4220-bd63-4d8f0a9cd95d.txt | 11 | yes |
| 13-macro-liquidity-p2.json | B06 | 2 | 96a1856b-7e39-438c-9b86-12e787bdc9f9.txt | 4 | yes |
| 15-stock-chanlun-p2.json | B08 | 2 | d9c94ab1-334d-4984-abe0-11fbdb77f123.txt | 1 | yes |
| 16-stock-a-share-p2.json | B09 | 2 | 2e160095-6e56-4338-b9ef-6fe2d3a1578d.txt | 0 | no |
| 17-geo-export-controls-p2.json | B10 | 2 | d0c76f17-0f91-4ee5-8ea6-5a9c26c977a3.txt | 10 | yes |
| 18-ai-governance-p2.json | B11 | 2 | 60792e4f-3d66-467e-8d41-1692c8153934.txt | 8 | yes |
| 19-energy-p2.json | B12 | 2 | 5e417af3-3b36-4441-b64d-f2388053ed0b.txt | 25 | yes |
| 20-bio-p2.json | B13 | 2 | 9bef3307-e702-466b-b001-a93950add187.txt | 5 | yes |
| 21-semis-p2.json | B14 | 2 | 62f6504d-ae41-4925-940a-f627204d3d89.txt | 25 | yes |
| 22-quantum-p2.json | B15 | 2 | 5775429d-0a7a-46ec-9781-1759dd4cd37f.txt | 4 | yes |
| 23-population-p2.json | B16 | 2 | 1e5948a1-192c-4164-9183-f2ae0c7f62db.txt | 25 | yes |
| 24-bci-p2.json | B17 | 2 | 9b65045c-3742-45b1-b16c-08d53e19e53a.txt | 4 | yes |
| 02-accounts-02-p3.json | A02 | 3 | 08a3199f-2c36-4edd-8551-349e60f78fe2.txt | 0 | no |
| 03-accounts-03-p3.json | A03 | 3 | d7f26910-4884-4740-9a60-bba409a495b1.txt | 20 | yes |
| 04-accounts-04-p3.json | A04 | 3 | ae84ce98-f011-443b-b658-e96c66f07cea.txt | 25 | yes |
| 05-accounts-05-p3.json | A05 | 3 | 3a1c3cac-b1dc-4dfd-a04b-60a19cee650f.txt | 25 | yes |
| 06-accounts-06-p3.json | A06 | 3 | c926012d-163c-4b1a-ad29-b13d3be87be3.txt | 0 | no |
| 07-accounts-07-p3.json | A07 | 3 | 18c9e097-badb-4b80-b3b6-a1617e0613d7.txt | 0 | no |
| 03-accounts-03-p4.json | A03 | 4 | 0048f14b-ef6a-45af-ae6d-626b6c22ee43.txt | 0 | no |
| 04-accounts-04-p4.json | A04 | 4 | 63ea2e3b-5475-46a8-a045-a2f50b335a85.txt | 12 | yes |
| 05-accounts-05-p4.json | A05 | 4 | 8d623445-f936-49b9-9817-d802e5d8cf74.txt | 25 | yes |

| hydrate file | spill file | posts returned |
|---|---|---|
| hydrate-01.json | 06e30f00-cece-4a9d-a135-dbf89ae7ea4c.txt | 100 |
| hydrate-02.json | 3fa6f9e2-dda5-48a9-9764-c2672be6934c.txt | 100 |
| hydrate-03.json | ebfb1a7c-c8b8-459d-b888-9a4d4f35672e.txt | 100 |
| hydrate-04.json | 50c023a6-c9d6-4baa-9d4f-0c4ef356d7a4.txt | 44 |
