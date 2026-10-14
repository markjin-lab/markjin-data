# X provenance (round 1, 2026-10-15)

Tool: `x.search_posts_all`; start_time=2026-10-12T21:01:00Z (now − 48h at ~05:00 SGT); post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: working copy x-queries v2 (main has no newer version); snapshot in `../x-queries.md`. Pagination via `next_token`: this round paged A batches to 2 pages and B topics to 1 page (below the 4/2 caps) to finish inside the 05:15 window; batches with a remaining next_token are flagged below.
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper and quota lines dropped). `hydrate-NN.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet) for the filtered ids, same method.
Raw 712 posts, 710 unique; filter like≥20 / retweet≥5 / A-batch whitelist, minus 96 ids already captured on 2026-10-13/14 → 279 leads (all 线索). Hydrate lookup missing: 0.
Calls: search 31 + hydrate 3 = 34 (round 1). Quota after round: 27 of 30 this minute (resets at 2026-10-14T21:03:00.000Z), 966 of 1000 today (resets at 2026-10-15T00:00:00.000Z).

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | c69dd312-2ba4-4395-805d-f196864ffbf4.txt | 25 | yes |
| 02-accounts-02.json | A02 | 1 | 406e4fd2-7539-44f1-9fa8-f0747aa462df.txt | 25 | yes |
| 03-accounts-03.json | A03 | 1 | 61528e60-dc05-45c7-9bf8-eacb9936fe7c.txt | 25 | yes |
| 04-accounts-04.json | A04 | 1 | 58441395-e96c-48cb-b1da-7df8ac17fc02.txt | 25 | yes |
| 05-accounts-05.json | A05 | 1 | 598f16ee-0a79-426b-b87b-cbea98fdaea8.txt | 25 | yes |
| 06-accounts-06.json | A06 | 1 | 18fedc15-b205-422c-923d-711dec1a4ce8.txt | 25 | yes |
| 07-accounts-07.json | A07 | 1 | a14a3db4-3028-431b-8f0d-09eb9071996e.txt | 25 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 29187566-4456-4233-a05d-9a20ca44f060.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | ab2d2c0c-5b5b-4317-8d18-7e36adfa4fb3.txt | 25 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 7b4e3f54-2728-4546-92e1-ba3aaf3d830d.txt | 25 | yes |
| 11-ai-compute.json | B04 | 1 | 79e7d153-046a-4bff-b180-3a8dfb012b36.txt | 25 | yes |
| 12-macro-pboc.json | B05 | 1 | 9d3e39fb-43bd-45f9-bf88-e315c5aac865.txt | 25 | yes |
| 13-macro-liquidity.json | B06 | 1 | 510d03e8-c408-4dad-ba29-ff795858398b.txt | 25 | yes |
| 14-physics-arxiv.json | B07 | 1 | 5557bf22-b1d2-441f-816e-a07f6dfface6.txt | 2 | yes |
| 15-stock-chanlun.json | B08 | 1 | 28acba88-5923-4e1d-84e3-b9871b3b1b2e.txt | 25 | yes |
| 16-stock-a-share.json | B09 | 1 | f93321b9-8e9a-469a-8a22-5b98e14212f5.txt | 25 | yes |
| 17-geo-export-controls.json | B10 | 1 | cae177b4-283f-4b98-b980-ba95a4d0cf4f.txt | 25 | yes |
| 18-ai-governance.json | B11 | 1 | 8cfeba0a-c4cd-4275-99e8-09338a0764db.txt | 25 | yes |
| 19-energy.json | B12 | 1 | 03437780-4e52-4246-8ba6-34abd53aef5b.txt | 24 | yes |
| 20-bio.json | B13 | 1 | 343ac246-2d23-4c5e-8fc3-4e382fcf1022.txt | 25 | yes |
| 21-semis.json | B14 | 1 | 6473e485-1b5a-4375-92b0-44db19348c5a.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 3f6b0207-c48f-4d0f-8bb3-d4720bcff0a9.txt | 25 | yes |
| 23-population.json | B16 | 1 | bd79cd79-f5dc-4080-b729-37c892ec0867.txt | 25 | yes |
| 24-bci.json | B17 | 1 | 2e260274-8296-45d9-a24c-4acc13f97e53.txt | 25 | yes |
| 01-accounts-01-p2.json | A01 | 2 | 24595c69-95e1-4c93-a7c0-42d0e79234a1.txt | 11 | yes |
| 02-accounts-02-p2.json | A02 | 2 | eec391e7-4ae4-458b-b25f-b4151c810e2e.txt | 25 | yes |
| 03-accounts-03-p2.json | A03 | 2 | c496f53b-5484-4798-8f1a-5e33de710d20.txt | 25 | yes |
| 04-accounts-04-p2.json | A04 | 2 | 199fc0c8-56d4-4795-b8af-f3571a8f6b3d.txt | 25 | yes |
| 05-accounts-05-p2.json | A05 | 2 | cc19abd3-14fe-461c-9e26-9ef5e3941bdc.txt | 25 | yes |
| 06-accounts-06-p2.json | A06 | 2 | b1a69996-49d7-4ed6-9dfa-75885ee9a980.txt | 25 | yes |
| 07-accounts-07-p2.json | A07 | 2 | 58ec03ab-f6c2-4f8c-bb65-0c3fd967adfe.txt | 25 | yes |

| hydrate file | spill file |
|---|---|
| hydrate-01.json | 52d40b83-f397-446c-90b2-56be5582874c.txt |
| hydrate-02.json | 1fb1416a-a72b-4a07-8bd4-a816414dad07.txt |
| hydrate-03.json | 36d82bea-4a75-4863-87dc-d64dd4551da3.txt |
