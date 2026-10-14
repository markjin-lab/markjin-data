# X provenance (round 2, 2026-10-15)

Tool: `x.search_posts_all`; start_time=2026-10-14T20:59:00Z (round-1 capture start ≈04:59 SGT); same fields/expansions/sort as round 1 (`../../x-queries.md`).
Pagination: A batches ≤2 pages, B topics ≤1 page. A03 had no next_token (0 results) so no page-2; other A page-2 returned 0. B topics with a next_token were not paged further (round2 cap).
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper and quota lines dropped). `hydrate-01.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet) for the 24 filtered ids.
Dedup: by post id against the local seen-ids store ∪ round-1 files (`../x/`). Raw 145 posts, 0 duplicates, 145 unique/new; 24 pass the like/retweet/whitelist filter → `leads.json` (all 线索). Hydrate lookup missing: 0.
Calls: search 30 + hydrate 1 + spot-check 1 = 32 (round 2). Day total (markjin rounds 1+2): 66 (r1=34 + r2=32). Grok Bot X quota after hydrate: X reads left for this user: 29 of 30 this minute, 935 of 1000 today (resets at 2026-10-15T00:00:00.000Z).

| file | query | page | spill file | result_count |
|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | fbf1d529-2600-46e2-86ef-b583226e8b88.txt | 1 |
| 02-accounts-02.json | A02 | 1 | 1252b84c-7023-410b-88fa-ad58bf9c00bf.txt | 2 |
| 03-accounts-03.json | A03 | 1 | 49fbf0c0-5d7b-4538-b648-25fc4e8dd4c1.txt | 0 |
| 04-accounts-04.json | A04 | 1 | 4407566e-2784-496c-a271-086238a4b516.txt | 8 |
| 05-accounts-05.json | A05 | 1 | 800a5958-89e2-4214-b776-5bb9ee628504.txt | 6 |
| 06-accounts-06.json | A06 | 1 | 2d7c01b2-5938-4da9-8e75-3e52d982a423.txt | 1 |
| 07-accounts-07.json | A07 | 1 | 67e0f3fb-71f7-45db-bd9c-5c0dc696a8b9.txt | 3 |
| 08-ai-tech-reports.json | B01 | 1 | 07ae7786-691f-4e4e-838a-6cdda7a8c592.txt | 0 |
| 09-ai-arxiv.json | B02 | 1 | 0e313800-f6ad-426b-8118-ae27bf104997.txt | 4 |
| 10-ai-benchmarks.json | B03 | 1 | 60eb2aef-dfef-41ab-9839-f198e049e31a.txt | 2 |
| 11-ai-compute.json | B04 | 1 | c10365d6-cd8d-4225-b13c-e2b04bea2178.txt | 10 |
| 12-macro-pboc.json | B05 | 1 | e8c07497-a07b-415c-8e36-d8c8e893c8b5.txt | 6 |
| 13-macro-liquidity.json | B06 | 1 | 2bc5f590-25d3-4086-8543-d0d7e4b95b86.txt | 4 |
| 14-physics-arxiv.json | B07 | 1 | ac57ef77-962d-4ee9-92c0-818057ca54a3.txt | 0 |
| 15-stock-chanlun.json | B08 | 1 | 76645fef-f3db-492a-9051-7ea9a110e4cb.txt | 1 |
| 16-stock-a-share.json | B09 | 1 | c199a0f5-945a-48ce-90b1-170f851292d8.txt | 1 |
| 17-geo-export-controls.json | B10 | 1 | f3fa8899-7bdd-41ac-b485-8ee7ea6a969c.txt | 0 |
| 18-ai-governance.json | B11 | 1 | b7b7628e-7777-432c-abb2-46887292b2ab.txt | 11 |
| 19-energy.json | B12 | 1 | 6c8576c2-6146-4229-a4d1-6019e0011222.txt | 25 |
| 20-bio.json | B13 | 1 | 173e6a69-3ed7-4f0e-bd43-c3a2d261bf9f.txt | 2 |
| 21-semis.json | B14 | 1 | 33b7710c-0d7f-48c3-ae54-f0cb6210e937.txt | 25 |
| 22-quantum.json | B15 | 1 | f7c9cb07-7404-4c42-ac1c-2453958d8935.txt | 2 |
| 23-population.json | B16 | 1 | 858c735b-38dc-41ce-8299-dbdf03a52195.txt | 25 |
| 24-bci.json | B17 | 1 | 9e46a074-5673-4915-84cd-64992bd50711.txt | 6 |
| 01-accounts-01-p2.json | A01 | 2 | 8d5fb5ac-06bd-4ca0-9c86-fcebb2b8c814.txt | 0 |
| 02-accounts-02-p2.json | A02 | 2 | d57a69fb-06fe-4b24-b28b-ab9bf7719027.txt | 0 |
| 04-accounts-04-p2.json | A04 | 2 | 498f3040-a2c7-4f29-be26-1b21bc0b3e54.txt | 0 |
| 05-accounts-05-p2.json | A05 | 2 | 8ec72adb-4f40-4303-9e9f-bcbf4208e6ef.txt | 0 |
| 06-accounts-06-p2.json | A06 | 2 | e7b74557-58cb-4ca1-9e76-fb3df88de2b7.txt | 0 |
| 07-accounts-07-p2.json | A07 | 2 | 05fd6390-8159-4957-bb8d-b58258e4ede6.txt | 0 |

| hydrate file | spill file |
|---|---|
| hydrate-01.json | 00324b2b-724e-44ac-99ec-189f28bf4f1b.txt |

Spot-check spill: `aff704e5-a6d6-4270-84b9-7dd4a538f32a.txt` (3 ids; not archived as a numbered hydrate file).
