# X provenance (round 2, 2026-11-02)

Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities,referenced_tweets; expansions=author_id; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: same set as round 1 (x-queries.md v2, 24 queries); snapshot already at day-level `../x-queries.md`.

## Part 1: round-1 continuation

Private pagination record for 2026-11-02 listed 11 continuations, all already at R1 page_cap (account 4 / topic 2). Continuation fetched 0 pages and 0 new posts; entries marked completed. No `*-round1-cont-pN.json` files.

## Part 2: round-2 new window

start_time=2026-11-01T20:55:42Z end_time=2026-11-01T21:57:33Z (R2 start UTC). Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. First page returned 0 posts (not an error): 03-accounts-03, 04-accounts-04, 07-accounts-07, 08-ai-tech-reports, 10-ai-benchmarks, 14-physics-arxiv, 15-stock-chanlun, 16-stock-a-share. 28 search calls, 126 posts (raw; 124 unique within round).

## Files and dedup

Each search file = the JSON object of the tool return (wrapper and quota lines dropped). `hydrate-01.json` is `x.get_posts_by_ids` for filtered lead ids (post.fields=entities,created_at,note_tweet). Dedup against seen-ids ∪ R1 raw ∪ earlier raw; leads = new ∩ (whitelist ∪ like≥20 ∪ rt≥5), all label=线索. User profile fields beyond id/name/username not retained in public files.
