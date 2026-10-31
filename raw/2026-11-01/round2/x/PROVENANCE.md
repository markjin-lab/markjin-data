# X provenance (round 2, 2026-11-01)

Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities,referenced_tweets; expansions=author_id; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: same set as round 1 (x-queries.md v2, 24 queries); snapshot already at day-level `../x-queries.md`.

## Part 1: round-1 continuation

Private pagination record for 2026-11-01 listed 14 continuations, all already at R1 page_cap (account 4 / topic 2). Continuation fetched 0 pages and 0 new posts; entries marked completed. No `*-round1-cont-pN.json` files.

## Part 2: round-2 new window

start_time=2026-10-31T20:54:43Z end_time=2026-10-31T22:00:04Z (R2 start UTC). Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. First page returned 0 posts (not an error): 01-accounts-01, 02-accounts-02, 08-ai-tech-reports, 10-ai-benchmarks, 14-physics-arxiv, 15-stock-chanlun, 16-stock-a-share, 17-geo-export-controls, 22-quantum. 29 search calls, 112 posts (raw; 111 unique within round).

## Files and dedup

Each search file = the JSON object of the tool return (wrapper and quota lines dropped). `hydrate-01.json` is `x.get_posts_by_ids` for the 11 filtered lead ids (post.fields=entities,created_at,note_tweet,text,author_id,public_metrics; expansions=author_id,attachments.media_keys); 2 hydrate calls (1 mistyped-id batch kept 5 valid + 1 remaining-6, merged); hydrate lookup missing: 0.
Dedup by post id against round-1 files (`../x/`) ∪ the seen-ids store ∪ earlier raw days: raw 112 posts, 1 duplicate(s) within round, 0 vs round 1, 0 vs seen-ids (beyond R1), 0 vs earlier days → 111 new. Filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) on **new** ids → 11 leads in `leads.json` (all 线索).
Calls this round: search 29 (24 page-1 + 5 A page-2) + hydrate 2 = 31. Day total with round 1 (62): 93 of the 400/day budget. One discarded wrong-query B06 search not counted in search_calls.

| file | query | page | result_count | next_token left |
|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 0 | no |
| 02-accounts-02.json | A02 | 1 | 0 | no |
| 03-accounts-03-p2.json | A03 | 2 | 0 | no |
| 03-accounts-03.json | A03 | 1 | 4 | yes |
| 04-accounts-04-p2.json | A04 | 2 | 0 | no |
| 04-accounts-04.json | A04 | 1 | 1 | yes |
| 05-accounts-05-p2.json | A05 | 2 | 0 | no |
| 05-accounts-05.json | A05 | 1 | 1 | yes |
| 06-accounts-06-p2.json | A06 | 2 | 0 | no |
| 06-accounts-06.json | A06 | 1 | 3 | yes |
| 07-accounts-07-p2.json | A07 | 2 | 0 | no |
| 07-accounts-07.json | A07 | 1 | 1 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | 2 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 0 | no |
| 11-ai-compute.json | B04 | 1 | 9 | yes |
| 12-macro-pboc.json | B05 | 1 | 3 | yes |
| 13-macro-liquidity.json | B06 | 1 | 2 | yes |
| 14-physics-arxiv.json | B07 | 1 | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | 0 | no |
| 16-stock-a-share.json | B09 | 1 | 0 | no |
| 17-geo-export-controls.json | B10 | 1 | 0 | no |
| 18-ai-governance.json | B11 | 1 | 4 | yes |
| 19-energy.json | B12 | 1 | 25 | yes |
| 20-bio.json | B13 | 1 | 8 | yes |
| 21-semis.json | B14 | 1 | 19 | yes |
| 22-quantum.json | B15 | 1 | 0 | no |
| 23-population.json | B16 | 1 | 22 | yes |
| 24-bci.json | B17 | 1 | 8 | yes |

| hydrate file | notes | posts returned |
|---|---|---|
| hydrate-01.json | 11 leads (2 get_posts_by_ids calls, merged) | 11 |

## #109 phase1 (R2_new / R2_cont)

Account pages with page_count≤20: several A page-1 had ≤20 and next_token; R2 page_cap=2 so page-2 was fetched (all returned 0). No account page stopped at R2 page_cap still holding next_token → R2_new compared=0 / not_compared=0. R2_cont: 0 (continuation pages not fetched). Stop-flip switch off. Ledger is private (account-page-samples).

