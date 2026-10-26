# X provenance (round 2, 2026-10-27)


Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries); same set as round 1, snapshot in `../../x-queries.md`.

## Part 1: round-1 continuation

None. No private pagination record exists for 2026-10-27 (`x-pagination/2026-10-27.json` absent), so continuation was skipped: 0 queries, 0 pages, 0 new posts. No `*-round1-cont-pN.json` files.

## Part 2: round-2 new window

start_time=2026-10-26T20:56:57Z (round-1 times.env END / round-1 window end), no end_time. Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. A03/A04/A05/A06/A07 had a next_token after page 1 and page 2 returned 0 posts for every one; A01 and A02 returned 0 posts on page 1 (no next_token). B topics were not paged beyond page 1 (cap). First page returned 0 posts (not an error): accounts-01, accounts-02, ai-tech-reports, physics-arxiv, stock-chanlun, stock-a-share. 29 search calls, 154 posts (raw; 154 unique).

## Files and dedup

Each search file = the JSON object of the tool return copied from the tool spill file (wrapper, quota and media/video notice lines dropped). `hydrate-01.json` merges `x.get_posts_by_ids` results for the 25 filtered lead ids (post.fields=entities,created_at,note_tweet,text,author_id,public_metrics; expansions=author_id,attachments.media_keys); two hydrate calls (first returned 15 correct leads plus Not Found for 10 mistyped ids; second returned the remaining 10). Hydrate lookup missing: 0.
Dedup by post id against round-1 files (`../../x/`) ∪ the seen-ids store ∪ all earlier raw days: raw 154 posts, 0 duplicate(s) within round, 0 vs round 1, 0 vs seen-ids, 0 vs earlier days → 154 new. Filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 25 leads in `leads.json` (all 线索).
Calls this round: search 29 (24 page-1 + 5 A page-2) + hydrate 2 = 31. Day total with round 1 (66): 97 of the 400/day budget.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 01-accounts-01-p1.txt | 0 | no |
| 02-accounts-02.json | A02 | 1 | 02-accounts-02-p1.txt | 0 | no |
| 03-accounts-03.json | A03 | 1 | 03-accounts-03-p1.txt | 1 | yes |
| 04-accounts-04.json | A04 | 1 | 04-accounts-04-p1.txt | 6 | yes |
| 05-accounts-05.json | A05 | 1 | 05-accounts-05-p1.txt | 8 | yes |
| 06-accounts-06.json | A06 | 1 | 06-accounts-06-p1.txt | 6 | yes |
| 07-accounts-07.json | A07 | 1 | 07-accounts-07-p1.txt | 1 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 08-ai-tech-reports-p1.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | 09-ai-arxiv-p1.txt | 5 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 10-ai-benchmarks-p1.txt | 2 | yes |
| 11-ai-compute.json | B04 | 1 | 11-ai-compute-p1.txt | 5 | yes |
| 12-macro-pboc.json | B05 | 1 | 12-macro-pboc-p1.txt | 3 | yes |
| 13-macro-liquidity.json | B06 | 1 | 13-macro-liquidity-p1.txt | 5 | yes |
| 14-physics-arxiv.json | B07 | 1 | 14-physics-arxiv-p1.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | 15-stock-chanlun-p1.txt | 0 | no |
| 16-stock-a-share.json | B09 | 1 | 16-stock-a-share-p1.txt | 0 | no |
| 17-geo-export-controls.json | B10 | 1 | 17-geo-export-controls-p1.txt | 1 | yes |
| 18-ai-governance.json | B11 | 1 | 18-ai-governance-p1.txt | 21 | yes |
| 19-energy.json | B12 | 1 | 19-energy-p1.txt | 25 | yes |
| 20-bio.json | B13 | 1 | 20-bio-p1.txt | 4 | yes |
| 21-semis.json | B14 | 1 | 21-semis-p1.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 22-quantum-p1.txt | 2 | yes |
| 23-population.json | B16 | 1 | 23-population-p1.txt | 25 | yes |
| 24-bci.json | B17 | 1 | 24-bci-p1.txt | 9 | yes |
| 03-accounts-03-p2.json | A03 | 2 | 03-accounts-03-p2.txt | 0 | no |
| 04-accounts-04-p2.json | A04 | 2 | 04-accounts-04-p2.txt | 0 | no |
| 05-accounts-05-p2.json | A05 | 2 | 05-accounts-05-p2.txt | 0 | no |
| 06-accounts-06-p2.json | A06 | 2 | 06-accounts-06-p2.txt | 0 | no |
| 07-accounts-07-p2.json | A07 | 2 | 07-accounts-07-p2.txt | 0 | no |

| hydrate file | notes | posts returned |
|---|---|---|
| hydrate-01.json | merged 25 leads (2 get_posts_by_ids calls) | 25 |

## #109 phase1 (R2_new)

Account pages with page_count≤20, had next_token, and this session fetched the next page: A03/A04/A05/A06/A07 recorded with window=R2_new, compared=true (next_page_count=0 each). R2_cont: 0 (no continuation). Stop-flip switch off — did not stop early. Ledger: private account-page-samples/2026-10-27.jsonl.

## FRED

Permanently disabled; no FRED requests this round.
