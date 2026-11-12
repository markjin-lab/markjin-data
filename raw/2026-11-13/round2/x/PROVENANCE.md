# X provenance (round 2, 2026-11-13)

Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities,referenced_tweets; expansions=author_id; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: same set as round 1 (x-queries.md v2, 24 queries); snapshot already at day-level `../x-queries.md`.

## Part 1: round-1 continuation

Private pagination for 2026-11-13 listed 7 early_stop (A01–A07) and 14 page_cap (B02,B03,B04,B05,B06,B08,B10,B11,B12,B13,B14,B15,B16,B17).
- early_stop: fetched 10 pages (A01 p3 empty; A02 p3=10; A03 p3=25/p4=25; A04 p3=25/p4=25; A05 p3=25/p4=25; A06 p3=14; A07 p3=7); 181 posts; files `*-round1-cont-pN.json`. A02/A06/A07 p3 had next but added no new ids, so p4 was not fetched (ingest stop).
- page_cap: already at R1 page_cap → 0 pages / 0 new posts; marked completed.
No next_token values written here.

## Part 2: round-2 new window

start_time=2026-11-12T20:50:00Z end_time=2026-11-12T22:02:45Z (R2 start UTC). Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. First page returned 0 posts (not an error): 01-accounts-01, 08-ai-tech-reports, 14-physics-arxiv, 16-stock-a-share. 30 search calls in new window (24 p1 + 6 p2), plus 10 continuation search = 40 search; 2 hydrate; 393 posts raw (391 unique within round). p2_calls=6 (A02–A07; all result_count=0). A01 p1 empty so no p2.

## Files and dedup

Each search file = the JSON object of the tool return (wrapper and quota lines dropped). `hydrate-01.json` and `hydrate-02.json` are `x.get_posts_by_ids` for filtered lead ids (post.fields=entities,created_at,note_tweet). Dedup against seen-ids ∪ R1 raw ∪ earlier raw; leads = new ∩ (whitelist ∪ like≥20 ∪ rt≥5), all label=线索. User profile fields beyond id/name/username not retained in public files.

Dedup: raw 393, dup_within 2, in_round1 0, in_seen 77, in_earlier 0 → new 314. Filter → 145 leads.
