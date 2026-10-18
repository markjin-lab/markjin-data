# X provenance (round 1, 2026-10-19)

Tool: `x.search_posts_all`; start_time=2026-10-16T20:55:00Z (now − 48h at ~04:55 SGT), fixed end_time=2026-10-18T20:55:00Z (round start); post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries); snapshot in `../x-queries.md`. Pagination via `next_token`: A batches paged up to 3 pages (cap 4), B topics 1 page (cap 2), stopped early to finish inside the 05:15 window.
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media-notice lines dropped). `hydrate-NN.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet) for the filtered ids, same method.
Raw 619 posts, 618 unique; minus 274 ids already captured on 2026-10-15/16/17/18 → 344 new; filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 154 leads (all 线索). Hydrate lookup missing: 0.
Calls: search 35 + hydrate 2 = 37 (round 1).
Queries left for round-2 continuation (18): A02, A03, A05, B02, B03, B04, B05, B07, B08, B09, B10, B11, B12, B13, B14, B15, B16, B17.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | fb088563-4501-49da-96aa-ab9fa70cbf62.txt | 17 | yes |
| 02-accounts-02.json | A02 | 1 | 9a697602-cfed-48e2-81d9-7c70df8eaf60.txt | 24 | yes |
| 03-accounts-03.json | A03 | 1 | 5505f8df-9108-4e01-9f4c-8031b3402acf.txt | 25 | yes |
| 04-accounts-04.json | A04 | 1 | b7e8ec9b-61f1-44b5-a8a2-80aed4747372.txt | 25 | yes |
| 05-accounts-05.json | A05 | 1 | 89bb32b1-e958-4164-a253-1f3dfe8c9804.txt | 25 | yes |
| 06-accounts-06.json | A06 | 1 | 3559dddb-aa01-450d-8772-3d49778d93e2.txt | 17 | yes |
| 07-accounts-07.json | A07 | 1 | b32085c5-745d-4d79-bcf7-32ca401537df.txt | 8 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 50096d5a-ba8a-49a4-9048-e0bb793f484a.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | 36665ae8-da17-4c1b-8e91-73fa365c3aa8.txt | 25 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 14564012-c04e-4c53-b88e-ff0fc0300187.txt | 25 | yes |
| 11-ai-compute.json | B04 | 1 | dffafbb9-ce62-4224-adc9-4326e49e1092.txt | 24 | yes |
| 12-macro-pboc.json | B05 | 1 | e8a52ebe-bdd3-4567-b677-f0a5f932a072.txt | 25 | yes |
| 13-macro-liquidity.json | B06 | 1 | 4c4040d4-f058-42e8-b6c3-ae1f3594c7fc.txt | 0 | no |
| 14-physics-arxiv.json | B07 | 1 | 2e0047b9-53f3-491d-bf4d-284510a5dfc4.txt | 25 | yes |
| 15-stock-chanlun.json | B08 | 1 | 528ba10e-04b6-4fc5-a0a7-dbf61f0ceb4e.txt | 23 | yes |
| 16-stock-a-share.json | B09 | 1 | 67ccbeae-9d5b-40a2-a94f-5102a7936f18.txt | 17 | yes |
| 17-geo-export-controls.json | B10 | 1 | a375f8d9-3b05-49fb-8fef-634d5f81dc53.txt | 25 | yes |
| 18-ai-governance.json | B11 | 1 | 9cb905fa-910b-45f3-bd42-67e4e79add73.txt | 25 | yes |
| 19-energy.json | B12 | 1 | 4d767383-9abd-449f-a207-80d76a5bc143.txt | 24 | yes |
| 20-bio.json | B13 | 1 | 28d962f7-90a3-4ef5-bdb8-8e50c091fd2c.txt | 25 | yes |
| 21-semis.json | B14 | 1 | ccd6c987-0075-4661-8130-8698a5aa8712.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 86258ebb-bb97-43e7-b366-7ceeb358d490.txt | 25 | yes |
| 23-population.json | B16 | 1 | 93d95646-49bb-4096-9fd1-4528d9d65d81.txt | 25 | yes |
| 24-bci.json | B17 | 1 | 50b0bbe8-a009-4a67-b1dc-c07dc25e97ce.txt | 25 | yes |
| 01-accounts-01-p2.json | A01 | 2 | 1ed178d2-27d0-419d-869d-648835765674.txt | 0 | no |
| 02-accounts-02-p2.json | A02 | 2 | 9f43b9d6-6c54-4574-9271-9715fea3fc78.txt | 24 | yes |
| 03-accounts-03-p2.json | A03 | 2 | cdd74058-e5d3-40a1-bfa5-69dca88aa847.txt | 25 | yes |
| 04-accounts-04-p2.json | A04 | 2 | 997cd168-a43c-42c8-900d-1225f834cbb6.txt | 13 | yes |
| 05-accounts-05-p2.json | A05 | 2 | e71e0d83-6085-48da-ad13-ede126187e4a.txt | 25 | yes |
| 06-accounts-06-p2.json | A06 | 2 | ee0aa070-11d6-43f6-a3aa-b41e571f98d6.txt | 0 | no |
| 07-accounts-07-p2.json | A07 | 2 | 3229f951-306c-438d-bf71-2d944ba89741.txt | 0 | no |
| 02-accounts-02-p3.json | A02 | 3 | 60d81486-f868-4a75-aff6-b712b4029676.txt | 1 | yes |
| 03-accounts-03-p3.json | A03 | 3 | b3ed792d-a374-4aa5-86fb-275b1d2497c6.txt | 2 | yes |
| 04-accounts-04-p3.json | A04 | 3 | 6a163c41-d033-4487-be7e-55f3255fb532.txt | 0 | no |
| 05-accounts-05-p3.json | A05 | 3 | 00a713a2-4e49-4466-abe8-a998e8c5755f.txt | 25 | yes |

| hydrate file | spill file |
|---|---|
| hydrate-01.json | 81b11fa8-8da5-4adc-bd85-d801580d40fd.txt |
| hydrate-02.json | 47fc7605-90e8-4dc8-b2cc-1b99520940bf.txt |
