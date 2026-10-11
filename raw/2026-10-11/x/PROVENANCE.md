# X raw provenance — 2026-10-11

Tool: dynamic `x` namespace `search_posts_all` (schema checked via GetDynamicTools). 12 queries from x-queries.md with query strings and max_results unchanged; start_time kept at the same relative lookback as 2026-10-10 (2 days; 4 days for 04/12) → 2026-10-09 / 2026-10-07. Fields: post.fields=created_at,author_id,public_metrics; expansions=author_id; user.fields=username. Captured 2026-10-11 07:10–07:12 SGT.

Calls used write_to_file, so each call produced a new file in /workspace/agent-tools/. Each was copied byte-for-byte to `NN-slug.agent-tools.txt` (**copied-file**; includes the tool wrapper lines and the quota line exactly as written). `NN-slug.json` is the JSON line extracted unchanged from that file (wrapper + quota line dropped) — derived from copied-file. Note: copied-file here = bytes of the tool spill file, not wire bytes of the X API.

| file | provenance | source agent-tools file | result_count |
|---|---|---|---|
| 01-ai-labs.agent-tools.txt | copied-file | f01abd98-4888-4b67-b89a-08b31510df8c.txt | 1 |
| 01-ai-labs.json | extracted-from-copied-file | 01-ai-labs.agent-tools.txt | 1 |
| 02-openai-google.agent-tools.txt | copied-file | ae160032-e8ed-4313-8fd0-6c6ee3bc0122.txt | 4 |
| 02-openai-google.json | extracted-from-copied-file | 02-openai-google.agent-tools.txt | 4 |
| 03-science-journals.agent-tools.txt | copied-file | 0723b96f-130a-46f5-a48c-05c410fa3dbb.txt | 25 |
| 03-science-journals.json | extracted-from-copied-file | 03-science-journals.agent-tools.txt | 25 |
| 04-official-econ.agent-tools.txt | copied-file | 296f8446-73ca-4af3-9f09-80ee2e575814.txt | 25 |
| 04-official-econ.json | extracted-from-copied-file | 04-official-econ.agent-tools.txt | 25 |
| 05-arxiv-llm.agent-tools.txt | copied-file | ffb276dc-da70-48c8-a7f0-f71ce8d31cda.txt | 25 |
| 05-arxiv-llm.json | extracted-from-copied-file | 05-arxiv-llm.agent-tools.txt | 25 |
| 06-ai-math-proofs.agent-tools.txt | copied-file | 761120b4-bd82-4d6b-8351-17c180aaee9b.txt | 10 |
| 06-ai-math-proofs.json | extracted-from-copied-file | 06-ai-math-proofs.agent-tools.txt | 10 |
| 07-ai-researchers.agent-tools.txt | copied-file | 64a969b0-15e0-419a-a01e-1346a5eb2425.txt | 10 |
| 07-ai-researchers.json | extracted-from-copied-file | 07-ai-researchers.agent-tools.txt | 10 |
| 08-macro-economists.agent-tools.txt | copied-file | 4b5ed479-e0af-4ed4-a67d-b38cb6fcadfd.txt | 10 |
| 08-macro-economists.json | extracted-from-copied-file | 08-macro-economists.agent-tools.txt | 10 |
| 09-bond-yields.agent-tools.txt | copied-file | a1b01d93-7d56-4f0b-917b-34dfd10f0492.txt | 10 |
| 09-bond-yields.json | extracted-from-copied-file | 09-bond-yields.agent-tools.txt | 10 |
| 10-physics-space.agent-tools.txt | copied-file | cf5aa1c6-c48d-4129-81da-c155c68049f2.txt | 10 |
| 10-physics-space.json | extracted-from-copied-file | 10-physics-space.agent-tools.txt | 10 |
| 11-zh-ai-research.agent-tools.txt | copied-file | d6f2e316-7594-4d44-9ac5-2384bcfabb8a.txt | 10 |
| 11-zh-ai-research.json | extracted-from-copied-file | 11-zh-ai-research.agent-tools.txt | 10 |
| 12-ai-evals-policy.agent-tools.txt | copied-file | 0d204260-b918-4c33-8ef5-dfedc9fa66dd.txt | 10 |
| 12-ai-evals-policy.json | extracted-from-copied-file | 12-ai-evals-policy.agent-tools.txt | 10 |
| verify-get_posts_by_ids.agent-tools.txt | copied-file | 441733e8-f6a9-47ff-8a09-ab6a52e12f5e.txt | 3 |
