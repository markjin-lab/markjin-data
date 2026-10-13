# X provenance (round 1, 2026-10-14)

Tool: `x.search_posts_all`; start_time=2026-10-11T21:01:00Z (now − 48h at 05:01 SGT); post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: working copy x-queries v2 (main has no newer version); snapshot in `../x-queries.md`. Pagination via `next_token`: this round paged A batches to 2 pages and B topics to 1 page (below the 4/2 caps) to finish inside the 05:15 window; batches with a remaining next_token are flagged below.
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper and quota lines dropped). `hydrate-NN.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet) for the filtered ids, same method.
Raw 690 posts, 690 unique; filter like≥20 / retweet≥5 / A-batch whitelist, minus 56 ids already captured on 2026-10-12/13 → 293 leads (all 线索). Hydrate lookup missing: 0.
Calls: search 31 + hydrate 3 = 34 (round 1). Quota after round: 27 of 30 this minute (resets at 2026-10-13T21:04:00.000Z), 966 of 1000 today (resets at 2026-10-14T00:00:00.000Z).

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | f7779b0b-5a49-4236-9d8d-3520ec106537.txt | 25 | yes |
| 02-accounts-02.json | A02 | 1 | a9919e17-7189-453f-900c-9bb79b33fa0e.txt | 25 | yes |
| 03-accounts-03.json | A03 | 1 | 63a0ff09-b028-4350-9d7e-d4b0cdd184cd.txt | 25 | yes |
| 04-accounts-04.json | A04 | 1 | a5b83122-cf1e-45be-966e-2f434e4da146.txt | 25 | yes |
| 05-accounts-05.json | A05 | 1 | 05bf8a9c-6813-4fbe-bcd5-cca40ac22896.txt | 25 | yes |
| 06-accounts-06.json | A06 | 1 | d561d12a-04ff-4936-ac27-f95a909e00f5.txt | 25 | yes |
| 07-accounts-07.json | A07 | 1 | 012b2099-71d1-496c-8ee6-d7c0eea5c761.txt | 25 | yes |
| 01-accounts-01-p2.json | A01 | 2 | 008716fc-75b3-4061-a323-55779198a16f.txt | 3 | yes |
| 02-accounts-02-p2.json | A02 | 2 | 20a0e57d-7b5c-4ec3-aa3d-e17994b587c4.txt | 25 | yes |
| 03-accounts-03-p2.json | A03 | 2 | 0f987b13-b268-43fe-b125-467323717ecd.txt | 25 | yes |
| 04-accounts-04-p2.json | A04 | 2 | 0326efd4-877c-4a05-b221-a6cac75d4e61.txt | 25 | yes |
| 05-accounts-05-p2.json | A05 | 2 | 0e929b00-c6ce-42a5-9784-10d9da25f481.txt | 25 | yes |
| 06-accounts-06-p2.json | A06 | 2 | c998207a-0666-4052-bc1f-ca55bdb2dc14.txt | 12 | yes |
| 07-accounts-07-p2.json | A07 | 2 | 7eddc871-ea5a-42c8-805f-91fb0a419859.txt | 25 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 5eff321b-8e78-48bc-bcfe-5b973f014ad7.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | e3792229-2534-4fa1-aecb-5a2566c9374c.txt | 25 | yes |
| 10-ai-benchmarks.json | B03 | 1 | bd6ad1f3-eabe-4c17-be17-fc6841c93b83.txt | 25 | yes |
| 11-ai-compute.json | B04 | 1 | bad193ab-06b4-4e17-bc10-967fce02f17c.txt | 25 | yes |
| 12-macro-pboc.json | B05 | 1 | 0966e407-30cd-4743-bbcf-7a8a1f829d11.txt | 25 | yes |
| 13-macro-liquidity.json | B06 | 1 | 4d05cd16-b9be-4913-a26e-b576e35f0437.txt | 25 | yes |
| 14-physics-arxiv.json | B07 | 1 | afb294d7-7195-4e81-b372-9a2b47180994.txt | 1 | yes |
| 15-stock-chanlun.json | B08 | 1 | 01d272db-fa32-456a-afd6-1b50cd7f5191.txt | 25 | yes |
| 16-stock-a-share.json | B09 | 1 | c209e825-eaf0-4063-9382-b4ad817fd755.txt | 25 | yes |
| 17-geo-export-controls.json | B10 | 1 | 0b4d7a2b-bfbf-455d-b3d6-683c4afe39c4.txt | 25 | yes |
| 18-ai-governance.json | B11 | 1 | ba38dce0-0389-49e5-a7ab-f5f4adec5bcc.txt | 25 | yes |
| 19-energy.json | B12 | 1 | 7900b55f-321c-4bcb-bb1b-dab03b4620e0.txt | 25 | yes |
| 20-bio.json | B13 | 1 | 4a26cbc9-2ffc-406e-a4a4-be5ca264f08b.txt | 25 | yes |
| 21-semis.json | B14 | 1 | 1e8c07f0-5dd0-4195-a930-7402fc364f8f.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 2d5c3b72-1707-46eb-98fd-7ea1228b4d77.txt | 25 | yes |
| 23-population.json | B16 | 1 | c39211f6-2b56-49f5-a389-84147486c63c.txt | 24 | yes |
| 24-bci.json | B17 | 1 | ae17f6f8-813f-43b3-971e-45d27a52aa32.txt | 25 | yes |
