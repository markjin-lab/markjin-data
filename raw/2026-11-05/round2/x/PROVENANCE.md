# X provenance (round 2, 2026-11-05)

Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities,referenced_tweets; expansions=author_id; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: same set as round 1 (x-queries.md v2, 24 queries); snapshot already at day-level `../x-queries.md`.

## Part 1: round-1 continuation

Private pagination for 2026-11-05 listed 6 early_stop (A02–A07) and 13 page_cap (B02,B04,B05,B06,B08,B09,B10,B11,B12,B13,B14,B16,B17).
- early_stop: fetched 12 pages (A02 p3=13 then p4 empty; A06 p3=2 then p4 empty; A07 p3=6 then p4 empty; A03/A04/A05 through p4/cap); 171 posts; files `*-round1-cont-pN.json`.
- page_cap: already at R1 page_cap → 0 pages / 0 new posts; marked completed.
No next_token values written here.

## Part 2: round-2 new window

start_time=2026-11-04T20:50:00Z end_time=2026-11-04T22:00:03Z (R2 start UTC). Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. First page returned 0 posts (not an error): 06-accounts-06, 08-ai-tech-reports, 14-physics-arxiv, 15-stock-chanlun, 16-stock-a-share. 30 search calls in new window (24 p1 + 6 p2), plus 12 continuation search = 42 search; 2 hydrate; 352 posts raw (351 unique within round).

## Files and dedup

Each search file = the JSON object of the tool return (wrapper and quota lines dropped). `hydrate-01.json` / `hydrate-02.json` are `x.get_posts_by_ids` for filtered lead ids (post.fields=entities,created_at,note_tweet). Dedup against seen-ids ∪ R1 raw ∪ earlier raw; leads = new ∩ (whitelist ∪ like≥20 ∪ rt≥5), all label=线索. User profile fields beyond id/name/username not retained in public files.

Dedup: raw 352, dup_within 1, in_round1 1, in_seen 34, in_earlier 0 → new 316. Filter → 170 leads.
