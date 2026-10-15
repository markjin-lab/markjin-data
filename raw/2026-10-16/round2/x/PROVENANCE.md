# X provenance (round 2, 2026-10-16)

Tool: `x.search_posts_all`; start_time=2026-10-15T21:02:00Z (round-1 capture start ≈05:02 SGT); same fields/expansions/sort as round 1 (`../../x-queries.md`).
Pagination: A batches ≤2 pages, B topics ≤1 page. A02 and A06 had no next_token (0 results) so no page-2; other A page-2 returned 0. B topics with a next_token were not paged further (round2 cap).
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper and quota lines dropped). `hydrate-01.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet) for the 20 filtered ids.
Dedup: by post id against the local seen-ids store ∪ round-1 files (`../x/`). Raw 156 posts, 2 duplicates within round, 154 unique/new; 20 pass the like/retweet/whitelist filter → `leads.json` (all 线索). Hydrate lookup missing: 0.
Calls: search 29 (7 A page1 + 5 A page2 + 17 B; A02/A06 no p2) + hydrate 1 + spot-check 1 = 31 (round 2). Day total (markjin rounds 1+2): 66 (r1=35 + r2=31).

| file | query | page | spill file | result_count |
|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 43402972-de69-48d4-afe4-4992821284cc.txt | 3 |
| 02-accounts-02.json | A02 | 1 | 3a7bbb09-a515-41e9-815c-35547ec084b8.txt | 0 |
| 03-accounts-03.json | A03 | 1 | 110d500f-b8b9-4669-87dc-59fcb844bf76.txt | 3 |
| 04-accounts-04.json | A04 | 1 | 4307f081-792e-4d65-bc0d-d638ea198148.txt | 5 |
| 05-accounts-05.json | A05 | 1 | 57473c46-b0fd-4426-86b0-fda2f2a8a7d0.txt | 5 |
| 06-accounts-06.json | A06 | 1 | 1eb0f416-1b9b-40a4-8d28-5de2013d5305.txt | 0 |
| 07-accounts-07.json | A07 | 1 | 8cbe4f73-8d14-456e-8f8b-78d00c1aded5.txt | 1 |
| 08-ai-tech-reports.json | B01 | 1 | aeb5f22e-5eea-4e97-9b0d-66fc1af0a7e4.txt | 0 |
| 09-ai-arxiv.json | B02 | 1 | 0c2df2b0-3e55-434e-8d9e-d79e841c7c8c.txt | 1 |
| 10-ai-benchmarks.json | B03 | 1 | 6267d347-9468-4f1b-b8f3-ccfcfaf96b14.txt | 0 |
| 11-ai-compute.json | B04 | 1 | cd1ce795-d26a-40c8-979e-26140260ff00.txt | 7 |
| 12-macro-pboc.json | B05 | 1 | 587f38cf-76ec-4363-85a3-b216b5976b55.txt | 4 |
| 13-macro-liquidity.json | B06 | 1 | 6e5b1ab1-4111-413c-b09b-cb240fc5beb4.txt | 9 |
| 14-physics-arxiv.json | B07 | 1 | 94ebaddd-4590-46f5-89ff-8e2c164299d7.txt | 0 |
| 15-stock-chanlun.json | B08 | 1 | f691dd75-0972-4f28-926d-eb2a5e25d754.txt | 2 |
| 16-stock-a-share.json | B09 | 1 | 00b38bb6-861e-4798-97c2-192f06286246.txt | 1 |
| 17-geo-export-controls.json | B10 | 1 | ceccf846-ab25-44be-b745-1d676ed8de07.txt | 3 |
| 18-ai-governance.json | B11 | 1 | b9513dfe-a250-4d5f-8e87-e65eaf385bd5.txt | 22 |
| 19-energy.json | B12 | 1 | 9e0328d2-8d3a-4f56-b631-f37f43a15948.txt | 25 |
| 20-bio.json | B13 | 1 | 37aeaa8b-c693-4994-8b82-afe0d29ae5eb.txt | 6 |
| 21-semis.json | B14 | 1 | c5f94098-dbca-4cc3-8bdb-a8ae7eb975aa.txt | 25 |
| 22-quantum.json | B15 | 1 | ec4c324c-202d-4036-a8b7-2f7524e081dd.txt | 3 |
| 23-population.json | B16 | 1 | ab5f07f4-2ac2-4429-b8d2-6c90819ac2bf.txt | 25 |
| 24-bci.json | B17 | 1 | 95ecb173-315f-4496-91cd-e1f72bdd1dfd.txt | 6 |
| 01-accounts-01-p2.json | A01 | 2 | c9cd8340-8175-46a6-b5bf-fdb7cd667f91.txt | 0 |
| 03-accounts-03-p2.json | A03 | 2 | 6e08a936-e7d9-4577-99fc-f5a8cdc30b02.txt | 0 |
| 04-accounts-04-p2.json | A04 | 2 | 4361959e-ac65-429b-a5cb-e38621dc84ff.txt | 0 |
| 05-accounts-05-p2.json | A05 | 2 | 302d78e8-138e-4adb-a2b7-39b3e9eeb5e0.txt | 0 |
| 07-accounts-07-p2.json | A07 | 2 | a5894057-779c-4a08-a5ec-f03e4be478f7.txt | 0 |

| hydrate file | spill file |
|---|---|
| hydrate-01.json | 902110e1-ae0c-409b-8218-7522b99cc1d8.txt |

Spot-check spill: `eebfced4-5b84-4b09-b557-2edc82faf4c7.txt` (3 ids; not archived as a numbered hydrate file).
