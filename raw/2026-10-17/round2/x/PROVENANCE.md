# X provenance (round 2, 2026-10-17)

Tool: `x.search_posts_all`; start_time=2026-10-16T20:55:00Z (round-1 capture start ≈04:55 SGT); same fields/expansions/sort as round 1.
Queries: trimmed local working copy of x-queries v2 (2026-10-17 05:02 SGT, Grok Bot rule): from: batches keep only accounts already in main's 12-query `improve/x-queries.md`; A06 paused (no approved account); B01 limited to OpenAI/AnthropicAI/GoogleDeepMind. Round 1 ran before the trim on the full v2 set. 23 queries this round (A01–A05, A07, B01–B17).
Pagination (round-2 cap = half of round 1): A batches ≤2 pages, B topics ≤1 page. A01/A03/A04 page 2 returned 0; A02/A05/A07 had 0 results and no next_token. B topics with a next_token were not paged further (cap).
Each file = the JSON line of the tool return copied byte-for-byte from the tool spill file (wrapper, quota and media-notice lines dropped). `hydrate-01.json` = `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet) for the 6 filtered ids.
Dedup: by post id against the local seen-ids store ∪ round-1 files (`../../x/`). Raw 116 posts, 2 duplicates within round, 0 vs round 1, 0 vs seen-ids → 114 unique/new; 6 pass the like≥20 / retweet≥5 / whitelist filter (whitelist = trimmed A-batch accounts) → `leads.json` (all 线索). Hydrate lookup missing: 0.
Calls: search 26 (6 A page1 + 3 A page2 + 17 B) + hydrate 1 + spot-check 1 = 28 (round 2). Day total (markjin rounds 1+2): 62 (r1=34 + r2=28). Quota after spot-check: 938 of 1000 today (resets 2026-10-17T00:00:00Z = 08:00 SGT).

| file | query | page | spill file | result_count | next_token left |
|---|---|---|---|---|---|
| 01-accounts-01.json | A01 | 1 | 2ae5465f-2923-4a5d-90b0-140b8884fcd0.txt | 1 | yes |
| 02-accounts-02.json | A02 | 1 | b2047f78-4501-4495-a849-7c54b71a90d3.txt | 0 | no |
| 03-accounts-03.json | A03 | 1 | e7f7c38a-04d4-486a-976a-b9447ea7741e.txt | 2 | yes |
| 04-accounts-04.json | A04 | 1 | 5c0ee67f-5fc9-4653-a22a-ea9290a778ad.txt | 3 | yes |
| 05-accounts-05.json | A05 | 1 | 5d16cd35-f497-496e-9e34-6428e9296430.txt | 0 | no |
| 07-accounts-07.json | A07 | 1 | 951f4a73-6ad9-46ff-a50d-2a7d2a7c741d.txt | 0 | no |
| 08-ai-tech-reports.json | B01 | 1 | b1199f00-dba9-4040-8000-57def902352c.txt | 0 | no |
| 09-ai-arxiv.json | B02 | 1 | c516cb9b-028e-4b36-8988-0c4d5dc85c1b.txt | 4 | yes |
| 10-ai-benchmarks.json | B03 | 1 | 7ee14703-1d9e-43ac-816b-a3fee150bd5d.txt | 1 | yes |
| 11-ai-compute.json | B04 | 1 | 1949722a-724d-473c-805c-0622bb8e58d8.txt | 6 | yes |
| 12-macro-pboc.json | B05 | 1 | 2cf7d61c-1cdc-46a8-bbd0-ec0e2725943d.txt | 1 | yes |
| 13-macro-liquidity.json | B06 | 1 | f7c0e2a1-8497-41f0-95bb-0585b4a6c4a0.txt | 4 | yes |
| 14-physics-arxiv.json | B07 | 1 | 7da3f6ea-6790-4bd5-9d5b-420a9f1d4af2.txt | 0 | no |
| 15-stock-chanlun.json | B08 | 1 | 9e5a3b4d-cfab-4df1-bda9-760ceb34e8db.txt | 0 | no |
| 16-stock-a-share.json | B09 | 1 | e1d781e9-0198-4544-8c58-98440287c0a4.txt | 0 | no |
| 17-geo-export-controls.json | B10 | 1 | 55722a67-543e-4de2-805e-b9994c1ec5cf.txt | 7 | yes |
| 18-ai-governance.json | B11 | 1 | 5dd6d662-42f4-4054-8eac-5bd8de238c5a.txt | 12 | yes |
| 19-energy.json | B12 | 1 | e9c11529-c105-4486-a6a3-b8eb03509e74.txt | 25 | yes |
| 20-bio.json | B13 | 1 | 0ccec86a-47f0-4ccd-88a6-ad6e0e4488ff.txt | 2 | yes |
| 21-semis.json | B14 | 1 | 34a92ec4-53b3-456c-b104-1dc2519884ff.txt | 24 | yes |
| 22-quantum.json | B15 | 1 | 304fdc57-359e-43f9-b33c-2ddd5ad088c4.txt | 3 | yes |
| 23-population.json | B16 | 1 | 7f6670ee-b81f-4d4b-9ef7-38d033780132.txt | 17 | yes |
| 24-bci.json | B17 | 1 | 3c6aa362-e913-4d45-a707-07c34feffb3e.txt | 4 | yes |
| 01-accounts-01-p2.json | A01 | 2 | 6bbdcbc1-347d-415d-9675-df553c27751c.txt | 0 | no |
| 03-accounts-03-p2.json | A03 | 2 | d244ed50-f608-41c8-90e5-18ff29b63f40.txt | 0 | no |
| 04-accounts-04-p2.json | A04 | 2 | e3c84c90-5fc2-41ec-bf7d-65d4ebfcc0b9.txt | 0 | no |

| hydrate file | spill file |
|---|---|
| hydrate-01.json | 65fb0994-4904-4907-b9cf-e692b98f9c03.txt |

Spot-check spill: `581ee5c2-7ce3-419c-9d6c-bc74348da26f.txt` (3 ids; not archived as a numbered hydrate file).
