# X provenance (round 2, 2026-10-20)

Tool: `x.search_posts_all`; post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries); same set as round 1, snapshot in `../../x-queries.md`.

## Part 1: round-1 continuation

None. Round 1 stopped no query before its page cap (see `../capture-failures.md` and `../x/PROVENANCE.md`), so no query was left with a next page; no continuation calls were made and there are no `*-round1-cont-pN.json` files this day.

## Part 2: round-2 new window

start_time=2026-10-19T21:00:00Z (round-1 run start and round-1 end_time, 05:00 SGT), no end_time. Pagination cap halved vs round 1: A batches ≤2 pages, B topics 1 page. A02/A04/A05/A07 had a next_token after page 1 and page 2 returned 0 posts; other A batches had no next_token after page 1; B topics were not paged (cap). First page returned 0 posts (not an error): A01, A03, A06, B01, B03, B07, B08. 28 calls, 134 posts.

## Files and dedup

Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media-notice lines dropped). `hydrate-01.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet; the tool also added its default expansions) for the 20 filtered ids, same method; spot-check in `verify.md` uses it.
Dedup by post id against the seen-ids store ∪ round-1 files (`../x/`) ∪ all earlier raw days: raw 134 posts, 2 duplicates within round, 0 vs round 1, 0 vs seen-ids, 0 vs earlier days → 132 new. Filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 20 leads in `leads.json` (all 线索). Hydrate lookup missing: 0.
Calls this round: search 28 (24 page-1 + 4 A page-2) + hydrate 1 = 29. Day total with round 1 (59): 88 of the 400/day budget.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 474ee3cb-b09e-479b-85ac-88a951cb50dd.txt | 0 | no |
| 02-accounts-02.json | A02 | 1 | 14307299-418f-4045-a585-501a88bb07a3.txt | 1 | yes |
| 03-accounts-03.json | A03 | 1 | 2b8b1217-d174-443a-8783-5737d076b111.txt | 0 | no |
| 04-accounts-04.json | A04 | 1 | ebdadd5f-6e92-46d3-b974-876f2d146fbd.txt | 3 | yes |
| 05-accounts-05.json | A05 | 1 | 60cff6b6-6411-475e-9302-a595be0f68d7.txt | 8 | yes |
| 06-accounts-06.json | A06 | 1 | a12e29a6-a506-43d8-802a-d5bc20c3f961.txt | 0 | no |
| 07-accounts-07.json | A07 | 1 | b8881863-5fb5-47fc-a09d-bd9c313969ca.txt | 3 | yes |
| 08-ai-tech-reports.json | B01 | 1 | 5b718330-82d1-45e9-b6ac-97641a679e4e.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | 5cfb8770-1bc4-4638-875a-333d9f4381b4.txt | 1 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 5cbb31d2-0104-4596-b36e-c5f01b0f7f9f.txt | 0 | no |
| 11-ai-compute.json | B04 | 1 | 1713c969-638a-4486-98e8-9fa37e94ec64.txt | 8 | yes |
| 12-macro-pboc.json | B05 | 1 | d56d2909-26a2-47ed-94a9-e95e50a11afb.txt | 3 | yes |
| 13-macro-liquidity.json | B06 | 1 | f3f7f859-6839-4d4d-8896-232376f49f5a.txt | 4 | yes |
| 14-physics-arxiv.json | B07 | 1 | d2f50187-bbc3-4c92-b0b8-58a1c2535447.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | a140b3ce-3a5d-4bbc-ad04-308f8e4d56ef.txt | 0 | no |
| 16-stock-a-share.json | B09 | 1 | f6629ff0-5573-49b6-914a-0ed72b0a165d.txt | 2 | yes |
| 17-geo-export-controls.json | B10 | 1 | c33efb2f-5465-4c9a-945b-42cd3d64326f.txt | 6 | yes |
| 18-ai-governance.json | B11 | 1 | 6964b1d0-03c8-47d0-8489-7c6b48629f4c.txt | 11 | yes |
| 19-energy.json | B12 | 1 | 2509ae51-297f-4c1a-b3a2-1a3ac51afb0f.txt | 25 | yes |
| 20-bio.json | B13 | 1 | 2abf65cb-1c66-439a-8b7a-4fcacdb5118b.txt | 4 | yes |
| 21-semis.json | B14 | 1 | 44094d4f-680a-47fb-9c71-82f8ea9fda36.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | 8ffc0d59-76e3-4546-8d43-07f76fc077e1.txt | 3 | yes |
| 23-population.json | B16 | 1 | a6c779d8-bb73-431e-9300-c687e621a9dc.txt | 21 | yes |
| 24-bci.json | B17 | 1 | b0ae30a8-be00-488a-bb09-f2c793b0965e.txt | 6 | yes |
| 02-accounts-02-p2.json | A02 | 2 | c49fadd0-f421-4ca8-83ee-d5239f03b21c.txt | 0 | no |
| 04-accounts-04-p2.json | A04 | 2 | 9a77fc58-d401-4de5-96cf-5ee262f644c6.txt | 0 | no |
| 05-accounts-05-p2.json | A05 | 2 | a9b2f311-d28e-4472-a97b-d83b39359044.txt | 0 | no |
| 07-accounts-07-p2.json | A07 | 2 | 2ee5f08c-eb4a-426b-94aa-d7884f9a0945.txt | 0 | no |

| hydrate file | spill file | posts returned |
|---|---|---|
| hydrate-01.json | 4c7754d4-0f12-41f0-8fdd-49bb79f3545a.txt | 20 |
