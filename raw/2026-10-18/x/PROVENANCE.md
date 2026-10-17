# X provenance (round 1, 2026-10-18)

Tool: `x.search_posts_all`; start_time=2026-10-15T20:55:00Z (now − 48h at ~04:55 SGT); post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries, approved 2026-10-17 07:46 SGT); snapshot in `../x-queries.md`. Pagination via `next_token`: A batches paged to 2 pages, B topics 1 page (below the 4/2 caps) to finish inside the 05:15 window; queries with a remaining next_token are flagged below.
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media-notice lines dropped). `hydrate-NN.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet) for the filtered ids, same method.
Raw 683 posts, 681 unique; minus 317 ids already captured on 2026-10-15/16/17 → 364 new; filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 177 leads (all 线索). Hydrate lookup missing: 0.
Calls: search 31 + hydrate 2 = 33 (round 1). Quota after hydrate: 967 of 1000 today (resets at 2026-10-18T00:00:00Z = 08:00 SGT).

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 5c507317-0a90-44de-b93f-4eca1791589f.txt | 25 | yes |
| 02-accounts-02.json | A02 | 1 | 73c5684d-6c14-4b84-aed4-4435c8653a96.txt | 25 | yes |
| 03-accounts-03.json | A03 | 1 | 52de4b3f-d853-46cc-919b-3e240b4daba7.txt | 25 | yes |
| 04-accounts-04.json | A04 | 1 | bf4d1967-1264-46b9-9550-d545060d8c5c.txt | 25 | yes |
| 05-accounts-05.json | A05 | 1 | 52cb5564-44ab-4a26-97c7-3fe47075629b.txt | 25 | yes |
| 06-accounts-06.json | A06 | 1 | 8ee81d61-b599-4fcd-a7a6-76ee9f212285.txt | 25 | yes |
| 07-accounts-07.json | A07 | 1 | 5dd51f20-7d6d-4831-911a-4f3d735cd23a.txt | 25 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 35420dfc-c9e8-46c2-857d-0f170b576680.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | 8e278abf-92ef-4d28-88e5-cd33a9adbe1f.txt | 25 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 7d024fb1-9e46-4d3d-a78c-e67a4e718f94.txt | 25 | yes |
| 11-ai-compute.json | B04 | 1 | 300a314d-78eb-4d01-9ae6-940280c442ec.txt | 24 | yes |
| 12-macro-pboc.json | B05 | 1 | 81b0a9d2-3ef9-488f-9326-6a788b766fa3.txt | 25 | yes |
| 13-macro-liquidity.json | B06 | 1 | 780d1d93-7c7d-42eb-9518-c22225dbabc3.txt | 25 | yes |
| 14-physics-arxiv.json | B07 | 1 | ea8ad185-66a5-42d1-9201-40c9f3cd067a.txt | 6 | yes |
| 15-stock-chanlun.json | B08 | 1 | 74f336fc-43bf-472c-bf35-ffbe12ac2444.txt | 25 | yes |
| 16-stock-a-share.json | B09 | 1 | 5f391cfb-78ee-40db-84e7-a61e5cafa4cb.txt | 25 | yes |
| 17-geo-export-controls.json | B10 | 1 | c20c71fa-da2e-47ec-beb9-8f8c17259c89.txt | 25 | yes |
| 18-ai-governance.json | B11 | 1 | 6cce7e00-483b-4b84-bf0e-fe12ff9d60dc.txt | 25 | yes |
| 19-energy.json | B12 | 1 | 73e29ba9-a099-4592-89d5-1fbeeb422909.txt | 25 | yes |
| 20-bio.json | B13 | 1 | fd12e6e2-9cda-4e89-a967-c04dc0f00f49.txt | 25 | yes |
| 21-semis.json | B14 | 1 | 3180daa2-7be3-4058-8d24-c60742b4f4f0.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 2cff1b05-e97c-4232-97fd-136b22f44446.txt | 25 | yes |
| 23-population.json | B16 | 1 | 789254fb-4343-4eb9-baa9-20bf04c60455.txt | 25 | yes |
| 24-bci.json | B17 | 1 | 8ba18db9-3ca2-45a9-8d73-ef0453a46ccd.txt | 25 | yes |
| 01-accounts-01-p2.json | A01 | 2 | 093e85bd-bd33-4ff2-8e09-68fb45d01bd4.txt | 14 | yes |
| 02-accounts-02-p2.json | A02 | 2 | d1322ac6-9c00-4c05-84af-3a201aed914c.txt | 23 | yes |
| 03-accounts-03-p2.json | A03 | 2 | 7ffa390e-ecae-481e-baa0-8be1b891e129.txt | 25 | yes |
| 04-accounts-04-p2.json | A04 | 2 | 88bdbd10-e72a-46cf-894d-ffbbfa652c6f.txt | 25 | yes |
| 05-accounts-05-p2.json | A05 | 2 | 9bccf285-cb78-476f-a158-5826cabc47fd.txt | 25 | yes |
| 06-accounts-06-p2.json | A06 | 2 | d52167a2-4c34-4445-8235-eefad569c544.txt | 8 | yes |
| 07-accounts-07-p2.json | A07 | 2 | a60eb305-5590-4372-ae8f-97ab742a4a3e.txt | 8 | yes |

| hydrate file | spill file |
|---|---|
| hydrate-01.json | d98201c5-cd8f-469a-b59e-10bb51e7449b.txt |
| hydrate-02.json | 7395fdec-d8dd-44ad-9fe5-99f0f0c552b3.txt |
