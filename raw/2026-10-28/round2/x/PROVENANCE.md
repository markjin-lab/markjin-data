# X provenance (round 2, 2026-10-28)

Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities,referenced_tweets; expansions=author_id; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: same set as round 1 (x-queries.md v2, 24 queries); snapshot already at day-level `../x-queries.md`.

## Part 1: round-1 continuation

Private pagination record for 2026-10-28 listed 13 continuations, all already at R1 page_cap (account 4 / topic 2). Continuation fetched 0 pages and 0 new posts; entries marked completed. No `*-round1-cont-pN.json` files.

## Part 2: round-2 new window

start_time=2026-10-25T20:58:22Z end_time=2026-10-27T21:55:29Z (R2 start UTC). Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. First page returned 0 posts (not an error): ai-tech-reports. 31 search calls, 704 posts (raw; 704 unique within round).

## Files and dedup

Each search file = the JSON object of the tool return (wrapper and quota lines dropped). `hydrate-01.json` is `x.get_posts_by_ids` for the 25 filtered lead ids (post.fields=entities,created_at,note_tweet,text,author_id,public_metrics; expansions=author_id,attachments.media_keys); 1 hydrate call; hydrate lookup missing: 0.
Dedup by post id against round-1 files (`../x/`) ∪ the seen-ids store ∪ earlier raw days: raw 704 posts, 0 duplicate(s) within round, 659 vs round 1, 1 vs seen-ids (beyond R1), 0 vs earlier days → 44 new. Filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 25 leads in `leads.json` (all 线索).
Calls this round: search 31 (24 page-1 + 7 A page-2) + hydrate 1 = 32. Day total with round 1 (65): 97 of the 400/day budget.

| file | query | page | result_count | next_token left |
|---|---|---|---|---|
| 01-accounts-01-p2.json | A01 | 2 | 1 | yes |
| 01-accounts-01.json | A01 | 1 | 25 | yes |
| 02-accounts-02-p2.json | A02 | 2 | 24 | yes |
| 02-accounts-02.json | A02 | 1 | 25 | yes |
| 03-accounts-03-p2.json | A03 | 2 | 25 | yes |
| 03-accounts-03.json | A03 | 1 | 25 | yes |
| 04-accounts-04-p2.json | A04 | 2 | 25 | yes |
| 04-accounts-04.json | A04 | 1 | 25 | yes |
| 05-accounts-05-p2.json | A05 | 2 | 25 | yes |
| 05-accounts-05.json | A05 | 1 | 25 | yes |
| 06-accounts-06-p2.json | A06 | 2 | 25 | yes |
| 06-accounts-06.json | A06 | 1 | 25 | yes |
| 07-accounts-07-p2.json | A07 | 2 | 25 | yes |
| 07-accounts-07.json | A07 | 1 | 25 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | 24 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 25 | yes |
| 11-ai-compute.json | B04 | 1 | 25 | yes |
| 12-macro-pboc.json | B05 | 1 | 25 | yes |
| 13-macro-liquidity.json | B06 | 1 | 25 | yes |
| 14-physics-arxiv.json | B07 | 1 | 5 | yes |
| 15-stock-chanlun.json | B08 | 1 | 25 | yes |
| 16-stock-a-share.json | B09 | 1 | 25 | yes |
| 17-geo-export-controls.json | B10 | 1 | 25 | yes |
| 18-ai-governance.json | B11 | 1 | 25 | yes |
| 19-energy.json | B12 | 1 | 25 | yes |
| 20-bio.json | B13 | 1 | 25 | yes |
| 21-semis.json | B14 | 1 | 25 | yes |
| 22-quantum.json | B15 | 1 | 25 | yes |
| 23-population.json | B16 | 1 | 25 | yes |
| 24-bci.json | B17 | 1 | 25 | yes |

| hydrate file | notes | posts returned |
|---|---|---|
| hydrate-01.json | 25 leads (1 get_posts_by_ids call) | 25 |

## #109 phase1 (R2_new / R2_cont)

Account pages with page_count≤20: A01 page 2 had 1 post and next_token but stopped at R2 page_cap → recorded window=R2_new, compared=false, skip_reason=page_cap. No compared=true in R2_new (page-1 account sizes were 25, out of 1–20 bins). R2_cont: 0 (continuation pages not fetched). Stop-flip switch off. Ledger is private (account-page-samples).

## FRED

Permanently disabled; no FRED requests this round.

## arXiv

Skipped by design (#110 plan-r2 action=skip_all; sample day 2026-10-27 not today). No arXiv files this round.
