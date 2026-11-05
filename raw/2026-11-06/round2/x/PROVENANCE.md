# X provenance (round 2, 2026-11-06)

Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities,referenced_tweets; expansions=author_id; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: same set as round 1 (x-queries.md v2, 24 queries); snapshot already at day-level `../x-queries.md`.

## Part 1: round-1 continuation

Private pagination for 2026-11-06 listed 6 early_stop (A02–A07) and 14 page_cap (B02,B04,B05,B06,B08–B17).
- early_stop: fetched 11 pages (A02 p3=23 then p4 empty; A06 p3=1 then p4 empty; A07 p3 empty; A03/A04/A05 through p4/cap); 174 posts; files `*-round1-cont-pN.json`.
- page_cap: already at R1 page_cap → 0 pages / 0 new posts; marked completed.
No next_token values written here.

## Part 2: round-2 new window

start_time=2026-11-05T20:50:00Z end_time=2026-11-05T21:59:50Z (R2 start UTC). Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. First page returned 0 posts (not an error): 01-accounts-01, 08-ai-tech-reports, 10-ai-benchmarks, 14-physics-arxiv, 15-stock-chanlun, 16-stock-a-share. 30 search calls in new window (24 p1 + 6 p2), plus 11 continuation search = 41 search; 2 hydrate; 352 posts raw (352 unique within round).

## Files and dedup

Each search file = the JSON object of the tool return (wrapper and quota lines dropped). `hydrate-01.json` / `hydrate-02.json` are `x.get_posts_by_ids` for filtered lead ids (post.fields=entities,created_at,note_tweet). Dedup against seen-ids ∪ R1 raw ∪ earlier raw; leads = new ∩ (whitelist ∪ like≥20 ∪ rt≥5), all label=线索. User profile fields beyond id/name/username not retained in public files.

Dedup: raw 352, dup_within 0, in_round1 0, in_seen 61, in_earlier 0 → new 291. Filter → 150 leads.
