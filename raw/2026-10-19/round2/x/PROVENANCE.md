# X provenance (round 2, 2026-10-19)

Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries); same set as round 1, snapshot in `../../x-queries.md`.

## Part 1: round-1 continuation (files `*-round1-cont-pN.json`)

Round 1 stopped paging early (see `../../capture-failures.md`); 18 queries were left with a next page. Each was continued with exactly the round-1 query string, sort order, start_time=2026-10-16T20:55:00Z and end_time=2026-10-18T20:55:00Z, passing the next_token recorded at the end of round 1 (token values not recorded here). Page numbers continue round 1's count: A02/A03/A05 page 4 (cap 4, round 1 had done 3), B02–B05 and B07–B17 page 2 (cap 2, round 1 had done 1). All 18 queries are now complete (page cap reached or no further results). 18 calls, 165 posts.

## Part 2: round-2 new window

start_time=2026-10-18T20:55:00Z (round-1 run start, 04:55 SGT), no end_time. Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. A01/A02/A04/A05 page 2 returned 0; other A batches had no next_token after page 1; B topics were not paged (cap). 28 calls, 130 posts.

## Files and dedup

Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media-notice lines dropped). `hydrate-01.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet) for the 42 filtered ids, same method; spot-check in `verify.md` uses it.
Dedup by post id against the seen-ids store ∪ round-1 files (`../../x/`) ∪ 2026-10-16/17/18 raw files: raw 295 posts, 2 duplicates within round, 0 vs round 1, 75 vs seen-ids, 0 vs earlier days → 218 new (89 of them from the continuation pages). Filter like≥20 / retweet≥5 / A-batch whitelist → 42 leads in `leads.json` (all 线索). Hydrate lookup missing: 0.
Calls this round: search 46 (18 continuation + 24 page-1 + 4 A page-2) + hydrate 1 = 47. Day total with round 1 (37): 84 of the 400/day budget.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 02-accounts-02-round1-cont-p4.json | A02 | 4 | e91df4a6-defe-4617-a299-998c05db5ee3.txt | 0 | no |
| 03-accounts-03-round1-cont-p4.json | A03 | 4 | af8e1171-ff27-4f68-8161-d6cd7415d36f.txt | 0 | no |
| 05-accounts-05-round1-cont-p4.json | A05 | 4 | a2982238-87d9-4579-bd12-e9cd1dae34e7.txt | 25 | yes |
| 09-ai-arxiv-round1-cont-p2.json | B02 | 2 | b4690d1c-e0c3-41f0-a2ce-83e49b4b1b3a.txt | 0 | no |
| 10-ai-benchmarks-round1-cont-p2.json | B03 | 2 | fbbf33df-e74a-463c-998c-67c8c3304030.txt | 0 | no |
| 11-ai-compute-round1-cont-p2.json | B04 | 2 | e6f5a66c-5246-475f-bae9-5f0848615f81.txt | 25 | yes |
| 12-macro-pboc-round1-cont-p2.json | B05 | 2 | f684c75b-ac0d-4020-8109-72461606ab9f.txt | 13 | yes |
| 14-physics-arxiv-round1-cont-p2.json | B07 | 2 | 6b6e32b6-79ea-4575-b4d8-e56cef6891a0.txt | 0 | no |
| 15-stock-chanlun-round1-cont-p2.json | B08 | 2 | c2603f1d-3a11-457f-89e9-a416fc9bb48b.txt | 0 | no |
| 16-stock-a-share-round1-cont-p2.json | B09 | 2 | a45bf4e7-fd9d-4c98-b557-40bd8d08b212.txt | 0 | no |
| 17-geo-export-controls-round1-cont-p2.json | B10 | 2 | 94990eea-ccdd-478b-b408-f552e76def62.txt | 14 | yes |
| 18-ai-governance-round1-cont-p2.json | B11 | 2 | b5661d1f-b666-4e33-9002-47eb60216004.txt | 3 | yes |
| 19-energy-round1-cont-p2.json | B12 | 2 | 51bfddd8-a37f-4d39-851f-3544bfe483e2.txt | 25 | yes |
| 20-bio-round1-cont-p2.json | B13 | 2 | e9dadae3-9ae8-4f48-9ddf-b16044acf873.txt | 1 | yes |
| 21-semis-round1-cont-p2.json | B14 | 2 | 9b573f14-e91a-4d0b-9e4a-04df0bebbc8c.txt | 24 | yes |
| 22-quantum-round1-cont-p2.json | B15 | 2 | bd56853e-6d21-47e5-9d87-a6d0d221cea5.txt | 0 | no |
| 23-population-round1-cont-p2.json | B16 | 2 | e9729b36-ea77-45da-b53a-f75c4dd29ba3.txt | 25 | yes |
| 24-bci-round1-cont-p2.json | B17 | 2 | 093969bb-43f9-4bc6-a3ad-5fa74fc3621c.txt | 10 | yes |
| 01-accounts-01.json | A01 | 1 | 9153b7b3-f768-45ab-8b3c-ec5f92449855.txt | 1 | yes |
| 02-accounts-02.json | A02 | 1 | 2c10f115-2aa4-4461-87a7-3432b117358f.txt | 2 | yes |
| 03-accounts-03.json | A03 | 1 | 9f1b504f-23b8-485d-802b-1ea774044596.txt | 0 | no |
| 04-accounts-04.json | A04 | 1 | 58748a30-72e9-4a4c-a086-fa9206b9488a.txt | 4 | yes |
| 05-accounts-05.json | A05 | 1 | d62ca3f3-bc9e-43e4-843d-5325c0b2f1b5.txt | 7 | yes |
| 06-accounts-06.json | A06 | 1 | 94f67b70-666a-443f-9e60-0169089e1948.txt | 0 | no |
| 07-accounts-07.json | A07 | 1 | f532d573-905f-4667-a072-c8e3a6df8204.txt | 0 | no |
| 08-ai-tech-reports.json | B01 | 1 | 63d7dbf4-e65e-48a6-8ec7-60cb7d7cd574.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | e0989589-b342-4381-9b1a-2bda6a1275c1.txt | 4 | yes |
| 10-ai-benchmarks.json | B03 | 1 | f81aa06b-8d7d-44ab-98e0-b6377515c3de.txt | 0 | no |
| 11-ai-compute.json | B04 | 1 | 4259b753-0d21-4630-bee8-325259393f6e.txt | 11 | yes |
| 12-macro-pboc.json | B05 | 1 | 7e806508-a056-41ae-9359-8d5d3adfab55.txt | 3 | yes |
| 13-macro-liquidity.json | B06 | 1 | acdda8e4-7fb4-4167-a59d-4fee6fb945b2.txt | 4 | yes |
| 14-physics-arxiv.json | B07 | 1 | b7e9087c-6b76-4f13-a6cd-55de2a16ec6a.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | f49fcaff-630d-49dd-97ac-07dae4ab1696.txt | 0 | no |
| 16-stock-a-share.json | B09 | 1 | 072443ea-7da7-401e-8b3c-364196958180.txt | 1 | yes |
| 17-geo-export-controls.json | B10 | 1 | 7502aeba-5207-4e9c-b47a-b483cc4622c8.txt | 2 | yes |
| 18-ai-governance.json | B11 | 1 | 75a57ecb-09e9-44e7-8be6-8adf6bb011c2.txt | 16 | yes |
| 19-energy.json | B12 | 1 | b858f2ea-08de-4e29-b399-73edf4db7b95.txt | 25 | yes |
| 20-bio.json | B13 | 1 | fa16dfd8-edf1-4742-826e-ac424c06de70.txt | 2 | yes |
| 21-semis.json | B14 | 1 | 1b1dc427-35e6-4636-8932-0e14b92fda3d.txt | 24 | yes |
| 22-quantum.json | B15 | 1 | fc617a84-e433-4849-aa2b-e18c119aacaf.txt | 1 | yes |
| 23-population.json | B16 | 1 | 0360570d-f406-4202-aa4b-d6c9dd947f9e.txt | 18 | yes |
| 24-bci.json | B17 | 1 | eca504f6-460d-4337-b55f-68a0ae0176e9.txt | 5 | yes |
| 01-accounts-01-p2.json | A01 | 2 | 4840096b-b7ac-423a-8cc0-95dee0878591.txt | 0 | no |
| 02-accounts-02-p2.json | A02 | 2 | f4fd03a7-3502-4971-b5d5-d9256aaf2a4f.txt | 0 | no |
| 04-accounts-04-p2.json | A04 | 2 | fc719bae-040c-4403-816f-fd3587a515a6.txt | 0 | no |
| 05-accounts-05-p2.json | A05 | 2 | 5d8ede8e-657e-408f-a16a-6bf58a45e57a.txt | 0 | no |

| hydrate file | spill file |
|---|---|
| hydrate-01.json | a4ab0168-7fa9-4e8e-bf97-ef90699cdab0.txt |
