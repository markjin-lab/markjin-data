# X provenance (round 2, 2026-10-21)

Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries); same set as round 1, snapshot in `../../x-queries.md`.

## Part 1: round-1 continuation

None. The round-1 pagination record for this day lists no unfinished query (round 1 stopped no query before its page cap; see `../x/PROVENANCE.md`), so no continuation calls were made and there are no `*-round1-cont-pN.json` files this day.

## Part 2: round-2 new window

start_time=2026-10-20T20:59:00Z (round-1 run start and round-1 end_time, 04:59 SGT), no end_time. Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. All 7 A batches had a next_token after page 1 and page 2 returned 0 posts for every one; B topics were not paged (cap). First page returned 0 posts (not an error): B01. 31 calls, 182 posts.

## Files and dedup

Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media/video notice lines dropped). `hydrate-01.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet; the tool also added its default expansions) for the 27 filtered ids, same method; spot-check in `verify.md` uses it.
Dedup by post id against round-1 files (`../x/`) ∪ the seen-ids store ∪ all earlier raw days: raw 182 posts, 3 duplicates within round, 0 vs round 1, 0 vs seen-ids, 0 vs earlier days → 179 new. Filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 27 leads in `leads.json` (all 线索). Hydrate lookup missing: 0.
Calls this round: search 31 (24 page-1 + 7 A page-2) + hydrate 1 = 32. Day total with round 1 (64): 96 of the 400/day budget.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 7010e4af-e56d-4dd9-a845-138fa949a1bd.txt | 2 | yes |
| 02-accounts-02.json | A02 | 1 | 2a464ac2-7bcc-45fb-a433-c1135f177e7f.txt | 2 | yes |
| 03-accounts-03.json | A03 | 1 | ee99ea8d-e6c9-4f77-aa66-931b7ed9f0de.txt | 6 | yes |
| 04-accounts-04.json | A04 | 1 | 9353d81f-af60-4be0-b388-ccf7ed369b9f.txt | 3 | yes |
| 05-accounts-05.json | A05 | 1 | 628a7b7e-fad1-4233-92cb-0145456e44a6.txt | 5 | yes |
| 06-accounts-06.json | A06 | 1 | 35b562bf-daf1-408a-ba8d-3570d3461582.txt | 1 | yes |
| 07-accounts-07.json | A07 | 1 | 33619184-a13c-41a1-bbd3-b339f672dfc0.txt | 4 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 68a7deaf-dc19-45f8-9227-037942c16428.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | af90374c-ff6c-4f5e-b5e4-e66597c8f5fb.txt | 3 | yes |
| 10-ai-benchmarks.json | B03 | 1 | ddb5ed8d-2b7d-4ca0-ad72-e0218fcc6993.txt | 3 | yes |
| 11-ai-compute.json | B04 | 1 | b71d85ca-52e9-4f12-9abd-1b0098c1a240.txt | 15 | yes |
| 12-macro-pboc.json | B05 | 1 | 5b01cdb4-2ef9-4c10-b820-fafba7855b76.txt | 7 | yes |
| 13-macro-liquidity.json | B06 | 1 | 121382c9-6eb0-4b02-9249-423954927425.txt | 5 | yes |
| 14-physics-arxiv.json | B07 | 1 | 65a44f24-accf-442a-8afc-b01f5762fd9a.txt | 1 | yes |
| 15-stock-chanlun.json | B08 | 1 | 6d1ced53-8033-48f8-abe8-b598091d58ad.txt | 1 | yes |
| 16-stock-a-share.json | B09 | 1 | 17f22518-35f9-44bf-8a7a-9d85e4ee4b00.txt | 2 | yes |
| 17-geo-export-controls.json | B10 | 1 | e235c714-4e88-47ba-af1f-14ab3b0ebd6c.txt | 7 | yes |
| 18-ai-governance.json | B11 | 1 | f7efd225-4891-43f1-8f64-a496dcb917d2.txt | 23 | yes |
| 19-energy.json | B12 | 1 | 6f4a7ae4-e13a-4f18-80b1-59ea1c89ce5d.txt | 25 | yes |
| 20-bio.json | B13 | 1 | 04002bf7-8a9b-4cb1-b49b-3eea56f82bf5.txt | 8 | yes |
| 21-semis.json | B14 | 1 | c2097035-cef6-4126-8466-51a1f9ca7ea5.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 7ef8bc81-a506-4a47-9211-b218968a506c.txt | 4 | yes |
| 23-population.json | B16 | 1 | eb221550-3eb5-4d29-891d-b29e2ec87020.txt | 21 | yes |
| 24-bci.json | B17 | 1 | 8e2e7619-b7ad-4a92-ac10-bb2beb12f91c.txt | 9 | yes |
| 01-accounts-01-p2.json | A01 | 2 | 69334142-db75-489a-9824-1f87519e27c0.txt | 0 | no |
| 02-accounts-02-p2.json | A02 | 2 | b1ccba1c-eeed-4fde-afa9-ff982c81d739.txt | 0 | no |
| 03-accounts-03-p2.json | A03 | 2 | 02f0061c-8ce3-4489-bdd4-fc3293b014a5.txt | 0 | no |
| 04-accounts-04-p2.json | A04 | 2 | f6aeebb2-dd65-4f3a-9eca-44e32f586651.txt | 0 | no |
| 05-accounts-05-p2.json | A05 | 2 | b4ecd3cc-19f6-45f9-987a-768834fd8b59.txt | 0 | no |
| 06-accounts-06-p2.json | A06 | 2 | c7c326ca-01e9-4719-a6bb-a2778a332d9c.txt | 0 | no |
| 07-accounts-07-p2.json | A07 | 2 | 7ef758e6-cbdb-4203-93fc-2a87d0c9b83f.txt | 0 | no |

| hydrate file | spill file | posts returned |
|---|---|---|
| hydrate-01.json | 5aeea0f8-0021-41b3-a535-de76dc82ba35.txt | 27 |
