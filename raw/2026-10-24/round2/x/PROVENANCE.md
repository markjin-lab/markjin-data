# X provenance (round 2, 2026-10-24)


Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries); same set as round 1, snapshot in `../../x-queries.md`.

## Part 1: round-1 continuation

None. The round-1 pagination record for this day lists no unfinished query (every round-1 query reached its page cap or the end of results; see `../../x/PROVENANCE.md`), so no continuation calls were made and there are no `*-round1-cont-pN.json` files this day.

## Part 2: round-2 new window

start_time=2026-10-23T20:59:05Z (round-1 run start and round-1 end_time, 04:59 SGT), no end_time. Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. A02–A07 had a next_token after page 1 and page 2 returned 0 posts for every one; A01 returned 0 posts on page 1 (no next_token). B topics were not paged (cap). First page returned 0 posts (not an error): A01, B01, B09. 30 calls, 152 posts (raw; 151 unique).

## Files and dedup

Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media/video notice lines dropped). `hydrate-01.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet,text,author_id,public_metrics; the tool also added its default expansions) for the 26 filtered ids, same method; spot-check in `verify.md` uses it.
Dedup by post id against round-1 files (`../../x/`) ∪ the seen-ids store ∪ all earlier raw days: raw 152 posts, 1 duplicate(s) within round, 0 vs round 1, 0 vs seen-ids, 0 vs earlier days → 151 new. Filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 26 leads in `leads.json` (all 线索). Hydrate lookup missing: 0.
Calls this round: search 30 (24 page-1 + 6 A page-2) + hydrate 1 = 31. Day total with round 1 (65): 96 of the 400/day budget.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 5ac63c40-44fe-4a6c-989d-979ccd694f07.txt | 0 | no |
| 02-accounts-02.json | A02 | 1 | 96014659-0b67-4d81-9a5e-5fe6c3cd35bf.txt | 3 | yes |
| 03-accounts-03.json | A03 | 1 | 0c2fa43b-37b5-4683-b57f-ef05b7f2ebeb.txt | 3 | yes |
| 04-accounts-04.json | A04 | 1 | d5120a2d-922a-4f16-8d7f-4c59861d54ff.txt | 4 | yes |
| 05-accounts-05.json | A05 | 1 | 26f7da33-b85c-4ff7-aee2-9ba0f203bac0.txt | 4 | yes |
| 06-accounts-06.json | A06 | 1 | 04632788-d4f3-4cf6-ad0a-e730e61762cf.txt | 1 | yes |
| 07-accounts-07.json | A07 | 1 | 650548e4-acc1-4185-8f2a-cf349ab52b2b.txt | 3 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 1cc39f1b-4374-4b97-afaa-a15371e316b4.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | c1bdbaad-6167-4883-9c7d-7ff5f379d13e.txt | 2 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 8724fe5f-acd8-4e27-8fd0-2b278ef6dc8b.txt | 1 | yes |
| 11-ai-compute.json | B04 | 1 | a294d835-67cc-42ae-88ea-d5d033b59525.txt | 6 | yes |
| 12-macro-pboc.json | B05 | 1 | 44128928-4a56-4e2e-adaa-7911c4aaa2dc.txt | 3 | yes |
| 13-macro-liquidity.json | B06 | 1 | 58baa90d-2d03-4653-97f1-026de476241a.txt | 6 | yes |
| 14-physics-arxiv.json | B07 | 1 | b3a63e49-1b37-41ae-b14b-d05cf44b2336.txt | 1 | yes |
| 15-stock-chanlun.json | B08 | 1 | 36cde899-a8e1-48b0-9050-2cd9a0aab42f.txt | 1 | yes |
| 16-stock-a-share.json | B09 | 1 | f6967a5a-4986-4112-a1e6-96016ee04ea6.txt | 0 | no |
| 17-geo-export-controls.json | B10 | 1 | bebc477f-4a78-4494-80aa-6fde044e342d.txt | 2 | yes |
| 18-ai-governance.json | B11 | 1 | be53e865-8a6a-4dd3-96ec-c795bed67c73.txt | 25 | yes |
| 19-energy.json | B12 | 1 | 39a5faa3-d4e0-4e4a-b9a9-7c9c2e62580b.txt | 25 | yes |
| 20-bio.json | B13 | 1 | aca20a8c-2a01-414d-b3bc-0b6d80d02679.txt | 8 | yes |
| 21-semis.json | B14 | 1 | 381a1a43-8a42-4e5d-88f3-afe210cedd50.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 0f1b2014-4273-4cb6-a05e-8adfa0159679.txt | 1 | yes |
| 23-population.json | B16 | 1 | 6ac14fcd-d51b-42a5-90c7-4998d2b0db70.txt | 25 | yes |
| 24-bci.json | B17 | 1 | e4d4d25d-f3f0-436b-9b26-cd75a4945370.txt | 3 | yes |
| 02-accounts-02-p2.json | A02 | 2 | a93937c3-8dda-4926-8135-1de12b7ed012.txt | 0 | no |
| 03-accounts-03-p2.json | A03 | 2 | e4bfb55e-c8c2-45e5-b453-ee63acc21d96.txt | 0 | no |
| 04-accounts-04-p2.json | A04 | 2 | 1e503cdf-eeeb-40a9-a406-58b44e4d76bb.txt | 0 | no |
| 05-accounts-05-p2.json | A05 | 2 | 706578c3-f9e7-4c88-821e-8817b1f5aa2b.txt | 0 | no |
| 06-accounts-06-p2.json | A06 | 2 | 36515d3a-e92b-486f-95e2-3f80d8a8eb35.txt | 0 | no |
| 07-accounts-07-p2.json | A07 | 2 | 7fa2c7ed-f127-4413-9d67-05f445d0cb43.txt | 0 | no |

| hydrate file | spill file | posts returned |
|---|---|---|
| hydrate-01.json | 29c072fe-3d05-4e0b-a9d3-733d9a567024.txt | 26 |
