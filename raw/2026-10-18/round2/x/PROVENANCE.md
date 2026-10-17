# X provenance (round 2, 2026-10-18)

Tool: `x.search_posts_all`; start_time=2026-10-17T20:53:00Z (round-1 run start ≈04:53 SGT); post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username; max_results=25; A batches recency, B topics relevancy.
Queries: main `improve/x-queries.md` (v2, 24 queries, approved 2026-10-17 07:46 SGT); same set as round 1, snapshot in `../x-queries.md`.
Pagination (round-2 cap = half of round 1): A batches ≤2 pages, B topics ≤1 page. All 5 A page-2 requests (A02/A03/A04/A05/A07) returned 0; A01/A06 returned 0 on page 1. B topics with a remaining next_token were not paged further (cap).
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media-notice lines dropped). `hydrate-01.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet) for the 13 filtered ids, same method; spot-check in `verify.md` uses it.
Dedup by post id against the seen-ids store ∪ round-1 files (`../x/`) ∪ 2026-10-15/16/17 raw files: raw 100 posts, 1 duplicate within round, 0 vs round 1, 0 vs seen-ids, 0 vs earlier days → 99 new. Filter like≥20 / retweet≥5 / A-batch whitelist (120 accounts) → 13 leads in `leads.json` (all 线索). Hydrate lookup missing: 0.
Calls: search 29 (24 page-1 + 5 A page-2) + hydrate 1 = 30 (round 2). Quota after hydrate: 937 of 1000 today (resets 2026-10-18T00:00:00Z = 08:00 SGT); day total 63.

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 11380316-c260-4305-98f7-0cd0d8552f7d.txt | 0 | no |
| 02-accounts-02.json | A02 | 1 | 537eaaf2-e8b9-478a-aaa0-09d5e2fb0af7.txt | 1 | yes |
| 03-accounts-03.json | A03 | 1 | ffc802c3-04f2-4e2a-b444-6d7957908a26.txt | 1 | yes |
| 04-accounts-04.json | A04 | 1 | e494664b-7ea3-4f77-be28-ec514b2a3227.txt | 2 | yes |
| 05-accounts-05.json | A05 | 1 | 341c52d3-9b1c-4101-b2df-88d830392ddc.txt | 3 | yes |
| 06-accounts-06.json | A06 | 1 | 3de88912-3bc6-46d2-873a-b7cf5588f451.txt | 0 | no |
| 07-accounts-07.json | A07 | 1 | 2f032ad0-894b-48d9-af28-6c3886793fd6.txt | 1 | yes |
| 08-ai-tech-reports.json | B01 | 1 | fc2ff96c-bcc3-40c5-a9dc-f76bc25fc7f0.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | 1b429bed-daa5-40aa-ad12-c35b09e54996.txt | 1 | yes |
| 10-ai-benchmarks.json | B03 | 1 | fa043533-5900-4e4e-9cf8-8890d48f68c7.txt | 1 | yes |
| 11-ai-compute.json | B04 | 1 | 66356acf-79ff-453f-ac7c-6ba801eeec0f.txt | 3 | yes |
| 12-macro-pboc.json | B05 | 1 | 43b79453-ee98-4b6e-b97c-96448cc57716.txt | 3 | yes |
| 13-macro-liquidity.json | B06 | 1 | c923b3a8-3cdd-4f2b-a314-0afe9eaa0349.txt | 3 | yes |
| 14-physics-arxiv.json | B07 | 1 | 7ebb0150-d767-495b-9579-d27f1dd10750.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | 62ff8757-b048-4208-827b-0062854ce0b6.txt | 1 | yes |
| 16-stock-a-share.json | B09 | 1 | bc8118d2-2e6c-43fe-8e7a-6ce6d9b75961.txt | 0 | no |
| 17-geo-export-controls.json | B10 | 1 | 72116a69-0fe9-47f4-b48b-69380d1eb7b9.txt | 3 | yes |
| 18-ai-governance.json | B11 | 1 | 210eaf93-0830-48b8-8802-07356e76564f.txt | 9 | yes |
| 19-energy.json | B12 | 1 | 831e7d74-7335-4ce7-80ab-adc4e633653a.txt | 24 | yes |
| 20-bio.json | B13 | 1 | 66c1795f-cfb6-459f-9e08-b2d291d9171e.txt | 1 | yes |
| 21-semis.json | B14 | 1 | 3833f269-db2f-43d3-9f92-34c06102398f.txt | 25 | yes |
| 22-quantum.json | B15 | 1 | ce78a93c-8fcf-4cfa-9587-222701cd87a3.txt | 0 | no |
| 23-population.json | B16 | 1 | 96b6ed8a-93cd-43b6-b834-019e0b6b915f.txt | 12 | yes |
| 24-bci.json | B17 | 1 | 3a387644-bdb9-4f73-a592-5ce3443a67cf.txt | 6 | yes |
| 02-accounts-02-p2.json | A02 | 2 | 62f9dd50-25b4-476e-a32a-11993cde0fe7.txt | 0 | no |
| 03-accounts-03-p2.json | A03 | 2 | 7d8c3dbb-a20c-41bb-a604-750909734c35.txt | 0 | no |
| 04-accounts-04-p2.json | A04 | 2 | db2243fa-6ff2-4ca6-931d-326dc4cbfba6.txt | 0 | no |
| 05-accounts-05-p2.json | A05 | 2 | 50255e39-5085-40b1-91e8-e75c83841706.txt | 0 | no |
| 07-accounts-07-p2.json | A07 | 2 | b727b098-4653-4a71-9482-10e4a737eebf.txt | 0 | no |

| hydrate file | spill file |
|---|---|
| hydrate-01.json | 3bb82c52-9b8a-4e19-9c06-f86fb89d1f44.txt |
