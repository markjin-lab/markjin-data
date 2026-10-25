# X provenance (round 2, 2026-10-26)


Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries); same set as round 1, snapshot in `../../x-queries.md`.

## Part 1: round-1 continuation

None. No private pagination record exists for 2026-10-26 (`x-pagination/2026-10-26.json` absent), so continuation was skipped: 0 queries, 0 pages, 0 new posts. No `*-round1-cont-pN.json` files.

## Part 2: round-2 new window

start_time=2026-10-25T20:55:33Z (round-1 times.env END / round-1 run end), no end_time. Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. A02/A03/A04/A05/A06 had a next_token after page 1 and page 2 returned 0 posts for every one; A01 and A07 returned 0 posts on page 1 (no next_token). B topics were not paged (cap). First page returned 0 posts (not an error): accounts-01, accounts-07, ai-tech-reports, physics-arxiv, stock-chanlun, stock-a-share. 29 search calls, 119 posts (raw; 119 unique).

## Files and dedup

Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media/video notice lines dropped). `hydrate-01.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet,text,author_id,public_metrics; expansions=author_id,attachments.media_keys) for the 10 filtered ids, same method; spot-check in `verify.md` uses it.
Dedup by post id against round-1 files (`../../x/`) ∪ the seen-ids store ∪ all earlier raw days: raw 119 posts, 0 duplicate(s) within round, 0 vs round 1, 0 vs seen-ids, 0 vs earlier days → 119 new. Filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 10 leads in `leads.json` (all 线索). Hydrate lookup missing: 0.
Calls this round: search 29 (24 page-1 + 5 A page-2) + hydrate 1 = 30. Day total with round 1 (60): 90 of the 400/day budget.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | ?.txt | 0 | no |
| 02-accounts-02.json | A02 | 1 | ?.txt | 1 | yes |
| 03-accounts-03.json | A03 | 1 | ?.txt | 1 | yes |
| 04-accounts-04.json | A04 | 1 | ?.txt | 2 | yes |
| 05-accounts-05.json | A05 | 1 | ?.txt | 4 | yes |
| 06-accounts-06.json | A06 | 1 | ?.txt | 1 | yes |
| 07-accounts-07.json | A07 | 1 | ?.txt | 0 | no |
| 08-ai-tech-reports.json | B01 | 1 | ?.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | ?.txt | 1 | yes |
| 10-ai-benchmarks.json | B03 | 1 | ?.txt | 1 | yes |
| 11-ai-compute.json | B04 | 1 | ?.txt | 8 | yes |
| 12-macro-pboc.json | B05 | 1 | ?.txt | 5 | yes |
| 13-macro-liquidity.json | B06 | 1 | ?.txt | 4 | yes |
| 14-physics-arxiv.json | B07 | 1 | ?.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | ?.txt | 0 | no |
| 16-stock-a-share.json | B09 | 1 | ?.txt | 0 | no |
| 17-geo-export-controls.json | B10 | 1 | ?.txt | 1 | yes |
| 18-ai-governance.json | B11 | 1 | ?.txt | 13 | yes |
| 19-energy.json | B12 | 1 | ?.txt | 25 | yes |
| 20-bio.json | B13 | 1 | ?.txt | 2 | yes |
| 21-semis.json | B14 | 1 | ?.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | ?.txt | 3 | yes |
| 23-population.json | B16 | 1 | ?.txt | 21 | yes |
| 24-bci.json | B17 | 1 | ?.txt | 1 | yes |
| 02-accounts-02-p2.json | A02 | 2 | c06feeac-5916-4aa4-8328-f99ff037da78.txt | 0 | no |
| 03-accounts-03-p2.json | A03 | 2 | 64562427-96f1-4e45-8a2f-f8365a436e2d.txt | 0 | no |
| 04-accounts-04-p2.json | A04 | 2 | 2d5b2ebb-5817-4802-8e1d-89ac4813e5db.txt | 0 | no |
| 05-accounts-05-p2.json | A05 | 2 | c03fdb81-18f4-4e44-a339-1c4a5d7893d6.txt | 0 | no |
| 06-accounts-06-p2.json | A06 | 2 | 9d54dbee-7aa4-402e-80ce-0c2cc272e1d0.txt | 0 | no |

| hydrate file | spill file | posts returned |
|---|---|---|
| hydrate-01.json | 79427fcb-9cc3-4fca-b41c-a24923263fbd.txt | 10 |
