# X provenance (round 2, 2026-10-22)

Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries); same set as round 1, snapshot in `../../x-queries.md`.

## Part 1: round-1 continuation

None. The round-1 pagination record for this day lists no unfinished query (every round-1 query reached its page cap or the end of results; see `../../x/PROVENANCE.md`), so no continuation calls were made and there are no `*-round1-cont-pN.json` files this day.

## Part 2: round-2 new window

start_time=2026-10-21T20:58:41Z (round-1 run start and round-1 end_time, 04:58 SGT), no end_time. Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. A02–A07 had a next_token after page 1 and page 2 returned 0 posts for every one; A01 returned 0 posts on page 1; B topics were not paged (cap). First page returned 0 posts (not an error): A01, B01, B07, B15. 30 calls, 166 posts.

## Files and dedup

Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media/video notice lines dropped). `hydrate-01.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet; the tool also added its default expansions) for the 26 filtered ids, same method; spot-check in `verify.md` uses it.
Dedup by post id against round-1 files (`../../x/`) ∪ the seen-ids store ∪ all earlier raw days: raw 166 posts, 1 duplicate(s) within round, 0 vs round 1, 0 vs seen-ids, 0 vs earlier days → 165 new. Filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 26 leads in `leads.json` (all 线索). Hydrate lookup missing: 0.
Calls this round: search 30 (24 page-1 + 6 A page-2) + hydrate 1 = 31. Day total with round 1 (64): 95 of the 400/day budget.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | c0839245-a866-4cd7-96ff-53bbd0121c27.txt | 0 | no |
| 02-accounts-02.json | A02 | 1 | 1eb59b1a-a303-4a07-bcb6-b3cff19592d8.txt | 1 | yes |
| 03-accounts-03.json | A03 | 1 | 168facf8-0cc9-40b9-a25b-d7e0ddc060f5.txt | 3 | yes |
| 04-accounts-04.json | A04 | 1 | 801adb9f-d0a9-46eb-84c3-86a8dfcd9cdd.txt | 9 | yes |
| 05-accounts-05.json | A05 | 1 | da9bbbd6-a075-4019-b514-01e894b48dd9.txt | 8 | yes |
| 06-accounts-06.json | A06 | 1 | 69b27d97-b186-4ff4-8105-78b035e35c7f.txt | 1 | yes |
| 07-accounts-07.json | A07 | 1 | f7716c80-e072-4092-957f-bd8ce2b45923.txt | 1 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 2494eb82-4d10-4542-86ba-bf345bd15b01.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | e6c5e35d-1d05-4ffe-a95c-614f38ed4b44.txt | 6 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 7151b54a-c728-4310-97c5-3df0d577dafc.txt | 1 | yes |
| 11-ai-compute.json | B04 | 1 | fc84c2ac-0003-410b-b9b4-3de00742dc7d.txt | 15 | yes |
| 12-macro-pboc.json | B05 | 1 | 8105ac91-bda8-4055-a8ed-6a4bd4536b54.txt | 5 | yes |
| 13-macro-liquidity.json | B06 | 1 | 60f53fba-1747-4851-a983-59a89ccd4082.txt | 5 | yes |
| 14-physics-arxiv.json | B07 | 1 | 56c96d41-a396-4457-bffa-40e137971ff1.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | a589dd46-39a5-432b-9e1f-9097d43c51f2.txt | 1 | yes |
| 16-stock-a-share.json | B09 | 1 | 3c082b19-7993-424d-ade0-68ff2165041c.txt | 1 | yes |
| 17-geo-export-controls.json | B10 | 1 | e71635b4-fa57-4c0e-adfe-e848ea9fc554.txt | 3 | yes |
| 18-ai-governance.json | B11 | 1 | 301c9b22-b6f0-4124-888c-1bccb2785b06.txt | 19 | yes |
| 19-energy.json | B12 | 1 | 592d76a4-7f80-486d-8950-0e0cb291292e.txt | 25 | yes |
| 20-bio.json | B13 | 1 | 1ea2b8cb-683d-4fda-b8b0-1a3fa396ae51.txt | 10 | yes |
| 21-semis.json | B14 | 1 | 86e7897a-d5bd-4ebb-bf07-8e1d02994153.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 670bca2f-ba0c-4159-94bc-42628a3df896.txt | 0 | no |
| 23-population.json | B16 | 1 | 9fb19a20-caf6-413b-a671-c3e90a01cc2e.txt | 25 | yes |
| 24-bci.json | B17 | 1 | d4ad7cae-cc02-4df4-a37e-63655b42d16d.txt | 2 | yes |
| 02-accounts-02-p2.json | A02 | 2 | 62adfc0f-b128-475d-b07c-e0c3c0f060c1.txt | 0 | no |
| 03-accounts-03-p2.json | A03 | 2 | 7e9f265b-e9da-41d6-b0c5-d712fe4793f2.txt | 0 | no |
| 04-accounts-04-p2.json | A04 | 2 | 672c889e-a8fd-46ce-acb7-f7f2efb49cbc.txt | 0 | no |
| 05-accounts-05-p2.json | A05 | 2 | 0856f260-8a10-48ca-9298-059c03426bc2.txt | 0 | no |
| 06-accounts-06-p2.json | A06 | 2 | 2c10d7db-e57c-401c-846b-106ff74b25a1.txt | 0 | no |
| 07-accounts-07-p2.json | A07 | 2 | 45bf4124-fcab-459b-80b3-f42f442631d6.txt | 0 | no |

| hydrate file | spill file | posts returned |
|---|---|---|
| hydrate-01.json | b92b8adb-cbc4-4443-a4ff-fc33ed03ab7d.txt | 26 |
