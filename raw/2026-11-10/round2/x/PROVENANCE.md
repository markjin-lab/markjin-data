# X provenance (round 2, 2026-11-10)

Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities,referenced_tweets; expansions=author_id; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: same set as round 1 (x-queries.md v2, 24 queries); snapshot already at day-level `../x-queries.md`.

## Part 1: round-1 continuation

Private pagination for 2026-11-10 listed 6 early_stop (A02–A07) and 12 page_cap (B02,B04,B05,B06,B09,B10,B11,B12,B13,B14,B16,B17). R1 file omitted the page_cap array; reconstructed from R1 public p2 next_tokens before marking complete (0 pages expected).
- early_stop: fetched 10 pages (A02 p3=11/p4=0; A03 p3=25/p4=22; A04 p3=25/p4=16; A05 p3=25/p4=25; A06/A07 p3 empty); 149 posts; files `*-round1-cont-pN.json`.
- page_cap: already at R1 page_cap → 0 pages / 0 new posts; marked completed.
No next_token values written here.

## Part 2: round-2 new window

start_time=2026-11-09T20:50:00Z end_time=2026-11-09T22:00:17Z (R2 start UTC). Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. First page returned 0 posts (not an error): 08-ai-tech-reports, 14-physics-arxiv, 15-stock-chanlun, 16-stock-a-share. 31 search calls in new window (24 p1 + 7 p2), plus 10 continuation search = 41 search; 2 hydrate; 339 posts raw (337 unique within round).

## Files and dedup

Each search file = the JSON object of the tool return (wrapper and quota lines dropped). `hydrate-01.json` and `hydrate-02.json` are `x.get_posts_by_ids` for filtered lead ids (post.fields=entities,created_at,note_tweet). Dedup against seen-ids ∪ R1 raw ∪ earlier raw; leads = new ∩ (whitelist ∪ like≥20 ∪ rt≥5), all label=线索. User profile fields beyond id/name/username not retained in public files.

Dedup: raw 339, dup_within 2, in_round1 3, in_seen 67, in_earlier 0 → new 267. Filter → 116 leads.
