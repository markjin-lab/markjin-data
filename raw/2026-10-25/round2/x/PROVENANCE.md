# X provenance (round 2, 2026-10-25)


Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries); same set as round 1, snapshot in `../../x-queries.md`.

## Part 1: round-1 continuation

None. The round-1 pagination record for this day lists `continued: []` (no query was stopped early under page_cap with remaining next_token; at-cap remainders are not continued in round2), so no continuation calls were made and there are no `*-round1-cont-pN.json` files this day.

## Part 2: round-2 new window

start_time=2026-10-24T20:59:39Z (round-1 run start / round-1 end_time), no end_time. Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. A02/A04/A05/A06/A07 had a next_token after page 1 and page 2 returned 0 posts for every one; A01 and A03 returned 0 posts on page 1 (no next_token). B topics were not paged (cap). First page returned 0 posts (not an error): accounts-01, accounts-03, ai-tech-reports, ai-arxiv, ai-benchmarks, physics-arxiv, stock-a-share. 29 search calls, 143 posts (raw; 142 unique).

## Files and dedup

Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media/video notice lines dropped). `hydrate-01.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet,text,author_id,public_metrics; expansions=author_id,attachments.media_keys) for the 12 filtered ids, same method; spot-check in `verify.md` uses it. One extra mistaken hydrate call with wrong ids was discarded (counted toward quota; spill kept only in stage as hydrate-mistaken-discard.json, not committed).
Dedup by post id against round-1 files (`../../x/`) ∪ the seen-ids store ∪ all earlier raw days: raw 143 posts, 1 duplicate(s) within round, 0 vs round 1, 0 vs seen-ids, 0 vs earlier days → 142 new. Filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 12 leads in `leads.json` (all 线索). Hydrate lookup missing: 0.
Calls this round: search 29 (24 page-1 + 5 A page-2) + hydrate 2 (1 mistaken discarded + 1 hydrate-01) = 31. Day total with round 1 (66): 97 of the 400/day budget.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 6b7d7fe0-82c3-4555-990d-e03108d873c7.txt | 0 | no |
| 02-accounts-02.json | A02 | 1 | bedbc1f1-b41b-49ef-9891-e9512e9d0ba6.txt | 1 | yes |
| 03-accounts-03.json | A03 | 1 | b55afd5a-6220-4a28-9c7e-d06e85458153.txt | 0 | no |
| 04-accounts-04.json | A04 | 1 | 38023911-0211-4bf2-b0ff-b6c993b7c1e7.txt | 2 | yes |
| 05-accounts-05.json | A05 | 1 | db312db5-1190-4650-8985-42891f9a2a89.txt | 4 | yes |
| 06-accounts-06.json | A06 | 1 | 3a387c97-821a-45c3-8730-4926b397f6e7.txt | 1 | yes |
| 07-accounts-07.json | A07 | 1 | 3c6b9207-dd6d-4f9c-8856-d0bcaf0f76a8.txt | 2 | yes |
| 08-ai-tech-reports.json | B01 | 1 | be365e82-6a35-4520-8ef6-413e8ddeff37.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | 7d69e62b-88b8-4b7e-b556-259f86a561fe.txt | 0 | no |
| 10-ai-benchmarks.json | B03 | 1 | 3ec0b9ea-c422-4156-a83f-d154281aa104.txt | 0 | no |
| 11-ai-compute.json | B04 | 1 | 9be48be9-0802-43b1-807f-8b4e062a50a3.txt | 17 | yes |
| 12-macro-pboc.json | B05 | 1 | e0cf2b69-4f03-49f7-bf9a-8503b7f5053b.txt | 6 | yes |
| 13-macro-liquidity.json | B06 | 1 | 6caa65e9-4b34-4c94-b0a3-7e0ab5664834.txt | 3 | yes |
| 14-physics-arxiv.json | B07 | 1 | e4616a84-07c0-46cd-8d88-1d967f09f6a7.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | b5a464c5-9cf9-45c3-bf27-59a03f8ef6bf.txt | 1 | yes |
| 16-stock-a-share.json | B09 | 1 | d7c5d480-6445-44ff-ac20-7b5ef8a73565.txt | 0 | no |
| 17-geo-export-controls.json | B10 | 1 | d342e385-93b7-4895-93f1-eb69ae1345f3.txt | 2 | yes |
| 18-ai-governance.json | B11 | 1 | 82e0846e-00be-43d8-b514-de72560e62dc.txt | 19 | yes |
| 19-energy.json | B12 | 1 | b262452a-c21d-40a9-ab1a-3ab57c917705.txt | 25 | yes |
| 20-bio.json | B13 | 1 | 280cf055-9ba0-46ee-b62e-2d12ccdf54f3.txt | 5 | yes |
| 21-semis.json | B14 | 1 | 703cadd3-466e-4d9e-a0a6-9b7acc13b89b.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | de8fc86e-1c9f-4265-887d-c15963b1cae8.txt | 4 | yes |
| 23-population.json | B16 | 1 | 314d745d-2204-4ee5-83f0-724809e98d99.txt | 24 | yes |
| 24-bci.json | B17 | 1 | a999f627-533a-46ea-8361-f21f8235c3c7.txt | 2 | yes |
| 02-accounts-02-p2.json | A02 | 2 | 0efd0561-726c-4f51-91ba-8a8fa04ecd7f.txt | 0 | no |
| 04-accounts-04-p2.json | A04 | 2 | cc39388f-2336-4c52-920a-fb88d2862288.txt | 0 | no |
| 05-accounts-05-p2.json | A05 | 2 | 2f59f7a3-90d8-4c2f-baea-18869fd1a958.txt | 0 | no |
| 06-accounts-06-p2.json | A06 | 2 | ea4ef2d5-5935-43cd-bb39-4083e13520cf.txt | 0 | no |
| 07-accounts-07-p2.json | A07 | 2 | 14d5696f-ead1-4690-8c43-9c5bd86a09da.txt | 0 | no |

| hydrate file | spill file | posts returned |
|---|---|---|
| hydrate-01.json | 3f33be54-2209-447a-b7dd-3ccf15779c10.txt | 12 |
