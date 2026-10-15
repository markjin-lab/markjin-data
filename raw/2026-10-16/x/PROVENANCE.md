# X provenance (round 1, 2026-10-16)

Tool: `x.search_posts_all`; start_time=2026-10-13T21:02:00Z (now − 48h at ~05:02 SGT); post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: working copy x-queries v2 (main has no newer version); snapshot in `../x-queries.md`. Pagination via `next_token`: this round paged A batches to 2 pages and B topics to 1 page (below the 4/2 caps) to finish inside the 05:15 window; batches with a remaining next_token are flagged below.
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper and quota lines dropped). `hydrate-NN.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet) for the filtered ids, same method.
Raw 714 posts, 713 unique; filter like≥20 / retweet≥5 / A-batch whitelist, minus ids already captured on 2026-10-13/14/15 → 322 leads (all 线索). Hydrate lookup missing: 0.
Calls: search 31 + hydrate 4 = 35 (round 1). Quota after A-p2 search: 23 of 30 this minute (resets at 2026-10-15T21:05:00.000Z), 969 of 1000 today (resets at 2026-10-16T00:00:00.000Z); hydrate used 4 more reads.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 9b32546e-7fd4-446a-941e-674e969138e8.txt | 25 | yes |
| 02-accounts-02.json | A02 | 1 | c0b13747-c595-49d8-ac23-567688bc8f64.txt | 23 | yes |
| 03-accounts-03.json | A03 | 1 | 0d9a2d08-9ff9-420d-a14b-24e04cc5bb8e.txt | 25 | yes |
| 04-accounts-04.json | A04 | 1 | 74b410c9-f8cb-4f6d-8d60-54364ce3258d.txt | 25 | yes |
| 05-accounts-05.json | A05 | 1 | 18f9fca1-7464-4613-a1a3-cc51b03ff836.txt | 25 | yes |
| 06-accounts-06.json | A06 | 1 | 6c3b308a-bada-4628-9add-4d3335cbde97.txt | 25 | yes |
| 07-accounts-07.json | A07 | 1 | 1057a90b-1420-4ce3-a162-b2a833898e10.txt | 25 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 5c7466a0-3dd0-477f-8f1c-093cde1ebe80.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | d33f095b-a339-433f-b15c-451169e128fc.txt | 25 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 90797760-bcbc-444a-9853-b7891862512d.txt | 23 | yes |
| 11-ai-compute.json | B04 | 1 | 4d17cf9d-cf5f-4985-a9ef-a57937d75e5e.txt | 25 | yes |
| 12-macro-pboc.json | B05 | 1 | 584352e2-2590-470d-b83f-7852d5e9febb.txt | 25 | yes |
| 13-macro-liquidity.json | B06 | 1 | dc8d7b33-e69a-49ad-9c40-0927b338d1b8.txt | 25 | yes |
| 14-physics-arxiv.json | B07 | 1 | 8dabab3f-702e-4aa7-95e3-057ea854c0c3.txt | 6 | yes |
| 15-stock-chanlun.json | B08 | 1 | 5bd50a71-ba52-4b12-b920-580f16ceb976.txt | 24 | yes |
| 16-stock-a-share.json | B09 | 1 | 2c8d5380-7a5c-44e1-aff0-cbd81ea93f41.txt | 25 | yes |
| 17-geo-export-controls.json | B10 | 1 | 8af6848f-56ba-4b48-b2d6-54fb67e51b5c.txt | 25 | yes |
| 18-ai-governance.json | B11 | 1 | 7fa346be-84b9-42d3-8314-a9cb131014ba.txt | 25 | yes |
| 19-energy.json | B12 | 1 | 6c4183de-70fe-4f73-8424-229783aaa737.txt | 24 | yes |
| 20-bio.json | B13 | 1 | 066afc56-638a-447b-bdee-036c90e345bd.txt | 24 | yes |
| 21-semis.json | B14 | 1 | 2ab0a25f-7d47-4503-9e93-de570da73595.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 2ff96a97-29f4-443d-9ed4-29342f00f099.txt | 25 | yes |
| 23-population.json | B16 | 1 | 97af4ffe-b6e2-4402-9cfa-6bd42764f431.txt | 24 | yes |
| 24-bci.json | B17 | 1 | dcfa5157-bfb0-466c-8ac0-70710bcb43b1.txt | 25 | yes |
| 01-accounts-01-p2.json | A01 | 2 | 4be57ce1-170a-4953-b91a-eef44e8dde72.txt | 16 | yes |
| 02-accounts-02-p2.json | A02 | 2 | 65b5a497-c2bc-43e8-9a28-de6860bc9c92.txt | 25 | yes |
| 03-accounts-03-p2.json | A03 | 2 | cc050c23-5390-4c73-889b-b08920b71b15.txt | 25 | yes |
| 04-accounts-04-p2.json | A04 | 2 | d3f80eb0-2f22-4838-89fa-e29217277f17.txt | 25 | yes |
| 05-accounts-05-p2.json | A05 | 2 | 79891cdd-1930-430c-9701-aaf607fc2ac7.txt | 25 | yes |
| 06-accounts-06-p2.json | A06 | 2 | bb81d96b-991b-48e7-baa0-7d0f49a5a7f4.txt | 25 | yes |
| 07-accounts-07-p2.json | A07 | 2 | ed0ba122-aaa3-40e3-a790-10e3c410141e.txt | 25 | yes |

| hydrate file | spill file |
|---|---|
| hydrate-01.json | 54662d78-b134-43ef-8eb9-8fc8a21bf8c5.txt |
| hydrate-02.json | 3e397912-463b-40d4-bd70-1347e7843434.txt |
| hydrate-03.json | ed274612-ba65-4868-841a-67e3c5b401f6.txt |
| hydrate-04.json | 6e51284a-3cb3-4d73-9314-3500128f8848.txt |
