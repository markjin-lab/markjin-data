# X provenance (round 1, 2026-10-17)

Tool: `x.search_posts_all`; start_time=2026-10-14T20:56:00Z (now − 48h at ~04:56 SGT); post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: working copy x-queries v2 (main has no newer v2 version; `improve/x-queries.md` on main is the older 12-query set); snapshot in `../x-queries.md`. Pagination via `next_token`: this round paged A batches to 2 pages and B topics to 1 page (below the 4/2 caps) to finish inside the 05:15 window; batches with a remaining next_token are flagged below.
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media-notice lines dropped). `hydrate-NN.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet) for the filtered ids, same method.
Raw 730 posts, 728 unique; filter like≥20 / retweet≥5 / A-batch whitelist, minus ids already captured on 2026-10-14/15/16 → 289 leads (all 线索). Hydrate lookup missing: 0.
Calls: search 31 + hydrate 3 = 34 (round 1). Quota after A-p2 search: 23 of 30 this minute (resets at 2026-10-16T20:58:00.000Z), 969 of 1000 today (resets at 2026-10-17T00:00:00.000Z).

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 4727af9a-c782-47b8-93eb-624c3f2fd725.txt | 25 | yes |
| 02-accounts-02.json | A02 | 1 | 501d44f4-4ba7-40c0-90ac-b667cd151d8e.txt | 24 | yes |
| 03-accounts-03.json | A03 | 1 | 5d8b2276-f18c-4632-a48c-d16e3b3bcdd8.txt | 25 | yes |
| 04-accounts-04.json | A04 | 1 | b696e424-1722-4184-9920-fc93ac0517f4.txt | 25 | yes |
| 05-accounts-05.json | A05 | 1 | 1c3b51e4-2bd9-486a-a7a3-5613ab93ce4b.txt | 25 | yes |
| 06-accounts-06.json | A06 | 1 | 777e278d-b8e6-4325-b109-bac185acce88.txt | 25 | yes |
| 07-accounts-07.json | A07 | 1 | 62a7ee0c-644a-4700-a99c-11714a197d76.txt | 25 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 075971f4-9de4-49f2-b083-c6255d60f6bf.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | 9d0f7431-d33d-4ed1-99a0-1e89ad95a6cb.txt | 25 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 729341e2-6e78-4373-b2e2-c710c5594de2.txt | 24 | yes |
| 11-ai-compute.json | B04 | 1 | eb12f002-b45e-42e8-a545-6a09405a6302.txt | 25 | yes |
| 12-macro-pboc.json | B05 | 1 | a195a934-e987-416c-9280-e7b4c57dcc2d.txt | 25 | yes |
| 13-macro-liquidity.json | B06 | 1 | cfec80b3-4890-427f-b737-a5f23dd8a14f.txt | 25 | yes |
| 14-physics-arxiv.json | B07 | 1 | e0fd799c-2e61-4892-be77-3e2c89301a21.txt | 11 | yes |
| 15-stock-chanlun.json | B08 | 1 | fd62a1b1-7056-42f4-8ead-2e1391eda904.txt | 24 | yes |
| 16-stock-a-share.json | B09 | 1 | 2f16fe6e-aebf-47a3-9b19-3b8358f92ab0.txt | 25 | yes |
| 17-geo-export-controls.json | B10 | 1 | 22898a59-89eb-4ced-9684-063258764a2c.txt | 25 | yes |
| 18-ai-governance.json | B11 | 1 | c7b92dfa-2339-44e8-a780-6d5ba368bdff.txt | 25 | yes |
| 19-energy.json | B12 | 1 | 3d226674-a306-44e4-83d2-0e2ca5961505.txt | 25 | yes |
| 20-bio.json | B13 | 1 | 4c203b49-e1e0-40b2-82bd-3e338997d695.txt | 24 | yes |
| 21-semis.json | B14 | 1 | 117e686b-31ac-414e-9748-511ea39cd5f8.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 0cbc6407-4e8b-4222-89d9-808761aa497d.txt | 25 | yes |
| 23-population.json | B16 | 1 | 2acdd6b4-c8d9-49f0-92fc-a3d1876fb902.txt | 24 | yes |
| 24-bci.json | B17 | 1 | 1f1646b0-217c-4014-bc25-d8c2cf4e1404.txt | 25 | yes |
| 01-accounts-01-p2.json | A01 | 2 | 8fa27d11-d1d8-4853-9ed5-317dbf1593ed.txt | 24 | yes |
| 02-accounts-02-p2.json | A02 | 2 | e2d4aef9-fc8f-4d57-88b6-f1327ce8c58c.txt | 25 | yes |
| 03-accounts-03-p2.json | A03 | 2 | b74401e0-ad92-45dd-9fc7-deb3c7a2769d.txt | 25 | yes |
| 04-accounts-04-p2.json | A04 | 2 | 1f98e970-fce5-4fad-95f6-2882e6776d60.txt | 25 | yes |
| 05-accounts-05-p2.json | A05 | 2 | 2a4a4630-1a9e-47f9-bd06-2334f919f065.txt | 25 | yes |
| 06-accounts-06-p2.json | A06 | 2 | e6758bef-7e4f-4ea7-9863-a2a66c71d38c.txt | 25 | yes |
| 07-accounts-07-p2.json | A07 | 2 | 52a708da-066d-4a83-9d8f-5a0d878c2097.txt | 25 | yes |

| hydrate file | spill file |
|---|---|
| hydrate-01.json | 20071a53-d239-445c-a4dd-245c1884de69.txt |
| hydrate-02.json | a1cb08e3-c61e-4860-aea2-c85dec30d2d4.txt |
| hydrate-03.json | c0be3cd7-ed72-4b5c-9e44-ce87568509d9.txt |
