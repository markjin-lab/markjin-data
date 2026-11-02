# X provenance (round 2, 2026-11-03)

Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities,referenced_tweets; expansions=author_id; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: same set as round 1 (x-queries.md v2, 24 queries); snapshot already at day-level `../x-queries.md`.

## Part 1: round-1 continuation

Private pagination for 2026-11-03 listed 5 early_stop (A02–A06) and 7 page_cap (B04,B11,B12,B13,B14,B16,B17).
- early_stop: fetched 8 pages (A02/A06 p3 empty stop; A03/A04/A05 through p4/cap); 138 posts; files `*-round1-cont-pN.json`.
- page_cap: already at R1 page_cap → 0 pages / 0 new posts; marked completed.
No next_token values written here.

## Part 2: round-2 new window

start_time=2026-11-02T20:59:00Z end_time=2026-11-02T21:59:43Z (R2 start UTC). Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. First page returned 0 posts (not an error): 08-ai-tech-reports, 14-physics-arxiv, 15-stock-chanlun, 16-stock-a-share. 31 search calls in new window (24 p1 + 7 p2), plus 8 continuation search = 39 search; 2 hydrate; 316 posts raw (314 unique within round).

## Files and dedup

Each search file = the JSON object of the tool return (wrapper and quota lines dropped). `hydrate-01.json` / `hydrate-02.json` are `x.get_posts_by_ids` for filtered lead ids (post.fields=entities,created_at,note_tweet). Dedup against seen-ids ∪ R1 raw ∪ earlier raw; leads = new ∩ (whitelist ∪ like≥20 ∪ rt≥5), all label=线索. User profile fields beyond id/name/username not retained in public files.
