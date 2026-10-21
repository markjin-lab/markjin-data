# X provenance (round 1, 2026-10-22)

Tool: `x.search_posts_all`; start_time=2026-10-19T20:58:41Z (now − 48h at round start), fixed end_time=2026-10-21T20:58:41Z (round start, 04:58 SGT); post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries); snapshot in `../x-queries.md`. Pagination via `next_token`: A batches up to 4 pages, B topics up to 2 pages; every query either reached its page cap or the end of results, so none was stopped early.
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper and quota lines dropped). `hydrate-NN.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet; the tool also added its default expansions) for the filtered ids, same method.
Raw 1109 posts, 1105 unique; minus 459 ids already captured on earlier days → 646 new; filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 384 leads (all 线索). Hydrate lookup missing: 0.
Calls: search 60 + hydrate 4 = 64 (round 1).
Queries left for round-2 continuation: none (0).
Queries at page cap with results remaining (19): A03, A04, A05, A06, A07, B02, B04, B05, B06, B08, B09, B10, B11, B12, B13, B14, B15, B16, B17. Queries that reached the end of results (5): A01, A02, B01, B03, B07. First page returned 0 posts (not an error): B01.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | d9893cfe-342b-4a13-960d-a8b649d578c2.txt | 25 | yes |
| 02-accounts-02.json | A02 | 1 | f34de4bb-fbbe-436e-b3c5-fb170f712f06.txt | 25 | yes |
| 03-accounts-03.json | A03 | 1 | 1c7c6c56-7005-44b7-9eea-682a6e125d46.txt | 25 | yes |
| 04-accounts-04.json | A04 | 1 | ccf942f1-6b30-4dab-b28b-90d76d450d99.txt | 25 | yes |
| 05-accounts-05.json | A05 | 1 | 6e00e091-ecc1-4f72-b307-93f80d074ecc.txt | 25 | yes |
| 06-accounts-06.json | A06 | 1 | 8759339f-a9a1-4d22-8a40-dab0481d261f.txt | 25 | yes |
| 07-accounts-07.json | A07 | 1 | df356810-9326-4e35-8b4b-9ea951b27d00.txt | 25 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 2aa8f6a9-79a4-48f7-9e92-8c27ff464efa.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | 56b5bab5-0fe3-4527-993d-39c68b672a50.txt | 25 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 7ad1720f-380d-4a06-97d8-dd242af18588.txt | 25 | yes |
| 11-ai-compute.json | B04 | 1 | 712e991a-45d0-438d-afbf-18f36dc9e5fe.txt | 25 | yes |
| 12-macro-pboc.json | B05 | 1 | ef6f1440-ba89-4c97-8ca4-9e86682abeca.txt | 25 | yes |
| 13-macro-liquidity.json | B06 | 1 | a6c132ae-1605-474c-bd1f-41ab49dbedf9.txt | 25 | yes |
| 14-physics-arxiv.json | B07 | 1 | 9d8aaf05-5833-4b79-91ca-be4c1ef7cf2b.txt | 5 | yes |
| 15-stock-chanlun.json | B08 | 1 | f7f781cd-d650-4c4f-93b3-ece73eb16873.txt | 24 | yes |
| 16-stock-a-share.json | B09 | 1 | e0fa202d-57c1-4ab7-a003-5bb1a804c212.txt | 25 | yes |
| 17-geo-export-controls.json | B10 | 1 | 3e8def12-1cc2-4e54-808e-508e2ab4354d.txt | 25 | yes |
| 18-ai-governance.json | B11 | 1 | 705fb513-f892-4acc-aefa-fbf6e62bfe7e.txt | 25 | yes |
| 19-energy.json | B12 | 1 | 680f8807-2d67-4a62-ab1e-b3c97863f7c0.txt | 25 | yes |
| 20-bio.json | B13 | 1 | 160702a5-9099-44c3-8cbd-2013f86f4370.txt | 25 | yes |
| 21-semis.json | B14 | 1 | 700a1815-70cb-4185-b651-131bed6b74e7.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | ca13e648-f5bf-49a6-87a8-bc9d3696a83e.txt | 25 | yes |
| 23-population.json | B16 | 1 | 36080380-3292-4e58-8f9a-45c2e50b1df5.txt | 25 | yes |
| 24-bci.json | B17 | 1 | 3acb4ae8-cbce-4138-9306-afeeb4e9e47f.txt | 25 | yes |
| 01-accounts-01-p2.json | A01 | 2 | bda2f6b1-a33f-4080-944d-af0539704418.txt | 8 | yes |
| 02-accounts-02-p2.json | A02 | 2 | 2d7339ee-eb46-4667-9183-b86aafbed6a7.txt | 24 | yes |
| 03-accounts-03-p2.json | A03 | 2 | 8f226456-838f-4657-87a5-15345b700ec2.txt | 25 | yes |
| 04-accounts-04-p2.json | A04 | 2 | 4a9448d8-3e61-42d7-83ef-e1ad408f7411.txt | 25 | yes |
| 05-accounts-05-p2.json | A05 | 2 | 89a417f6-dc11-4d37-b647-ec615b4e7c45.txt | 25 | yes |
| 06-accounts-06-p2.json | A06 | 2 | da14b5f2-5b95-4c36-9eb0-313f6a33aa4a.txt | 25 | yes |
| 07-accounts-07-p2.json | A07 | 2 | ee539654-6755-4956-8384-1278e7319c04.txt | 25 | yes |
| 09-ai-arxiv-p2.json | B02 | 2 | 6cae33a1-047b-48d3-8862-809761e90d60.txt | 9 | yes |
| 10-ai-benchmarks-p2.json | B03 | 2 | 7c4db495-a95d-4cd7-b349-53d4e85d35d0.txt | 0 | no |
| 11-ai-compute-p2.json | B04 | 2 | dda41352-ad04-4a32-9d8d-14a489b2a447.txt | 4 | yes |
| 12-macro-pboc-p2.json | B05 | 2 | 08bc6247-3376-47fb-adc5-2e6c65f43136.txt | 25 | yes |
| 13-macro-liquidity-p2.json | B06 | 2 | 5de5f2c7-83e1-4e9f-a739-54239fd65840.txt | 9 | yes |
| 14-physics-arxiv-p2.json | B07 | 2 | ababc46a-f0b0-417d-b4f9-a7d86dfb0c10.txt | 0 | no |
| 15-stock-chanlun-p2.json | B08 | 2 | f7dae8fc-c1ca-4b9d-b48b-003183086f6e.txt | 4 | yes |
| 16-stock-a-share-p2.json | B09 | 2 | 0e17d5bb-564a-4f2c-96a4-6ff8f6f4c42b.txt | 1 | yes |
| 17-geo-export-controls-p2.json | B10 | 2 | 2545819a-b691-4ee5-a98e-80955391521f.txt | 2 | yes |
| 18-ai-governance-p2.json | B11 | 2 | abe29c46-6f67-475b-9ecf-6ac1fef0952d.txt | 4 | yes |
| 19-energy-p2.json | B12 | 2 | ab5e7c84-a62d-442a-9a90-25e6b77f9262.txt | 25 | yes |
| 20-bio-p2.json | B13 | 2 | ddf93a1e-67e6-492d-adb8-d4c895b83366.txt | 3 | yes |
| 21-semis-p2.json | B14 | 2 | c442717f-af87-4a1e-924b-ec64bd6565c1.txt | 21 | yes |
| 22-quantum-p2.json | B15 | 2 | 941b012d-e5d5-46e3-bdc0-80d987e739b1.txt | 7 | yes |
| 23-population-p2.json | B16 | 2 | 539c1b02-966c-43ac-853c-bebb5700edcd.txt | 25 | yes |
| 24-bci-p2.json | B17 | 2 | 528cbfed-f556-48ee-8f1a-9de1b69f47bf.txt | 25 | yes |
| 01-accounts-01-p3.json | A01 | 3 | 045beab0-4488-493b-aee2-9847e3382a21.txt | 0 | no |
| 02-accounts-02-p3.json | A02 | 3 | 30e513fc-5a52-4b39-9ffa-2270bdd558b4.txt | 4 | yes |
| 03-accounts-03-p3.json | A03 | 3 | ef08d0c8-f531-4bbf-97fb-02a21a970129.txt | 25 | yes |
| 04-accounts-04-p3.json | A04 | 3 | bdabbad1-3216-4bcc-8d78-bb1b8a052977.txt | 25 | yes |
| 05-accounts-05-p3.json | A05 | 3 | 2d2c02d2-5537-44a4-b25b-5c737b3f249f.txt | 25 | yes |
| 06-accounts-06-p3.json | A06 | 3 | af3da6af-630d-4fdd-b53d-97465edd8c0d.txt | 25 | yes |
| 07-accounts-07-p3.json | A07 | 3 | 89508b32-1b56-47c7-8e8a-7d1ba8aef9bd.txt | 25 | yes |
| 02-accounts-02-p4.json | A02 | 4 | 18b7adc7-5e85-433a-8d5e-8238ca0d1241.txt | 0 | no |
| 03-accounts-03-p4.json | A03 | 4 | 144a07c9-5933-43f7-bcba-7b6e99348291.txt | 25 | yes |
| 04-accounts-04-p4.json | A04 | 4 | 439f9f5e-05b5-4c2a-90f5-33a023341acc.txt | 25 | yes |
| 05-accounts-05-p4.json | A05 | 4 | 20dfdc64-7a88-4d17-89fb-0810dcb3f2e5.txt | 25 | yes |
| 06-accounts-06-p4.json | A06 | 4 | 55e58a83-2773-4cdb-9c8a-8280e5b328f4.txt | 5 | yes |
| 07-accounts-07-p4.json | A07 | 4 | 6a37c13f-9776-4b13-b13c-1bda43da4804.txt | 25 | yes |
