# X provenance (round 2, 2026-10-23)


Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries); same set as round 1, snapshot in `../../x-queries.md`.

## Part 1: round-1 continuation

None. The round-1 pagination record for this day lists no unfinished query (every round-1 query reached its page cap or the end of results; see `../../x/PROVENANCE.md`), so no continuation calls were made and there are no `*-round1-cont-pN.json` files this day.

## Part 2: round-2 new window

start_time=2026-10-22T20:58:00Z (round-1 run start and round-1 end_time, 04:58 SGT), no end_time. Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. A01–A06 had a next_token after page 1 and page 2 returned 0 posts for every one; A07 returned 0 posts on page 1; B topics were not paged (cap). First page returned 0 posts (not an error): A07, B01, B07, B08. 30 calls, 151 posts.

## Files and dedup

Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media/video notice lines dropped). `hydrate-01.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet; the tool also added its default expansions) for the 25 filtered ids, same method; spot-check in `verify.md` uses it.
Dedup by post id against round-1 files (`../../x/`) ∪ the seen-ids store ∪ all earlier raw days: raw 151 posts, 0 duplicate(s) within round, 0 vs round 1, 0 vs seen-ids, 0 vs earlier days → 151 new. Filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 25 leads in `leads.json` (all 线索). Hydrate lookup missing: 0.
Calls this round: search 30 (24 page-1 + 6 A page-2) + hydrate 1 = 31. Day total with round 1 (64): 95 of the 400/day budget.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | ed741e22-4e8b-4fc5-969f-319bb0ee5dd6.txt | 1 | yes |
| 02-accounts-02.json | A02 | 1 | faf08229-5d12-4eea-b62d-4a50b96197b8.txt | 1 | yes |
| 03-accounts-03.json | A03 | 1 | 933b8d4d-52ff-4a06-98a6-6aabd7801360.txt | 1 | yes |
| 04-accounts-04.json | A04 | 1 | d1e4d151-7bdb-4807-8c73-fa4fc248838d.txt | 7 | yes |
| 05-accounts-05.json | A05 | 1 | db1ede32-d227-49be-8f1a-65f6bce22953.txt | 7 | yes |
| 06-accounts-06.json | A06 | 1 | 0b5f3f87-8646-492c-ad43-36254f4f2e93.txt | 2 | yes |
| 07-accounts-07.json | A07 | 1 | 63596759-7af7-48af-98c7-0eaf7aab7e41.txt | 0 | no |
| 08-ai-tech-reports.json | B01 | 1 | 858c1c9e-b6c5-4f8d-9c5a-657b7c42ee96.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | d8e3a9ac-149f-40eb-bb07-9aecd6fc629d.txt | 3 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 92156209-c301-497b-985d-e6077253f5a0.txt | 2 | yes |
| 11-ai-compute.json | B04 | 1 | ef42f498-b14f-40d4-ac76-6614ff946881.txt | 13 | yes |
| 12-macro-pboc.json | B05 | 1 | 3db5c4d5-269f-40d1-9da0-1f2a23fc3138.txt | 5 | yes |
| 13-macro-liquidity.json | B06 | 1 | 49bcb4dc-3b71-4e2e-890a-0a44c44c5000.txt | 1 | yes |
| 14-physics-arxiv.json | B07 | 1 | 85caf38f-95e2-4c87-95de-9759e3265c0f.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | 03f42694-ca6e-43de-95ed-f4553bd75dba.txt | 0 | no |
| 16-stock-a-share.json | B09 | 1 | e272d00f-7107-4c99-85db-6304f4989268.txt | 1 | yes |
| 17-geo-export-controls.json | B10 | 1 | e91b6d90-5237-4dd5-b45f-886e623ebf1e.txt | 4 | yes |
| 18-ai-governance.json | B11 | 1 | 98dc1898-e7cf-4814-b94f-afdedd1e1d62.txt | 20 | yes |
| 19-energy.json | B12 | 1 | 76e4c907-ed38-4092-94a0-9a45f92e3f8c.txt | 25 | yes |
| 20-bio.json | B13 | 1 | f345ce6b-4041-4931-b9bc-c3f11903d9df.txt | 9 | yes |
| 21-semis.json | B14 | 1 | 445d8487-19e4-4ada-b59b-7ea94f23a03d.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 564bfcfb-f55a-42be-a30f-bda4c17e5776.txt | 1 | yes |
| 23-population.json | B16 | 1 | b2948561-6053-436f-8104-abe4afe8cfee.txt | 20 | yes |
| 24-bci.json | B17 | 1 | 764b782b-ae6e-44ee-843e-9f59534a4d28.txt | 3 | yes |
| 01-accounts-01-p2.json | A01 | 2 | bec22922-cd44-4b95-9fd3-5530885c680a.txt | 0 | no |
| 02-accounts-02-p2.json | A02 | 2 | fc815a12-e738-409b-afa3-da973690b4fc.txt | 0 | no |
| 03-accounts-03-p2.json | A03 | 2 | ab26cc23-ddd4-4037-b875-fdab4b88ba96.txt | 0 | no |
| 04-accounts-04-p2.json | A04 | 2 | d861cb34-ffe6-4da9-a712-9a4ad7a8a37e.txt | 0 | no |
| 05-accounts-05-p2.json | A05 | 2 | fad1a5e0-1f45-4ce1-81eb-9d183f005fba.txt | 0 | no |
| 06-accounts-06-p2.json | A06 | 2 | 75b5949b-6402-4b62-a53a-373ffd75603c.txt | 0 | no |

| hydrate file | spill file | posts returned |
|---|---|---|
| hydrate-01.json | f3963376-33b6-4e33-b215-f63d7d1fe092.txt | 25 |
