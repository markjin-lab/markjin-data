# X raw provenance — 2026-10-11 round2 (08:15 SGT)
Tool: dynamic `x` namespace `search_posts_all`. Same 12 query strings/max_results/sort as x-queries.md; start_time=2026-10-10T23:00:00Z (=07:00 SGT, only new since round1). Fields per x-queries.md (2026-10-11): post.fields=created_at,author_id,public_metrics,entities; expansions=author_id,attachments.media_keys; user.fields=username. Each call used write_to_file; spill file copied byte-for-byte → NN-slug.agent-tools.txt (**copied-file**); NN-slug.json = JSON line extracted unchanged (extracted-from-copied-file).

| file | provenance | source agent-tools file | result_count |
|---|---|---|---|
| 01-ai-labs.agent-tools.txt | copied-file | 55e7766c-6cea-4f37-85ec-9eb26601c163.txt | 0 |
| 01-ai-labs.json | extracted-from-copied-file | 01-ai-labs.agent-tools.txt | 0 |
| 02-openai-google.agent-tools.txt | copied-file | a67c7752-a267-4d81-80e4-d505576b899d.txt | 0 |
| 02-openai-google.json | extracted-from-copied-file | 02-openai-google.agent-tools.txt | 0 |
| 03-science-journals.agent-tools.txt | copied-file | 94f424a5-bb71-436c-90b8-3613913931cb.txt | 1 |
| 03-science-journals.json | extracted-from-copied-file | 03-science-journals.agent-tools.txt | 1 |
| 04-official-econ.agent-tools.txt | copied-file | 124232c8-9cf7-435f-bb84-b0c9ee50a6f4.txt | 1 |
| 04-official-econ.json | extracted-from-copied-file | 04-official-econ.agent-tools.txt | 1 |
| 05-arxiv-llm.agent-tools.txt | copied-file | e05eba8b-72f7-4d39-a4b0-047c4ec75c18.txt | 1 |
| 05-arxiv-llm.json | extracted-from-copied-file | 05-arxiv-llm.agent-tools.txt | 1 |
| 06-ai-math-proofs.agent-tools.txt | copied-file | ae34fc75-e159-4acb-bf93-ad3190bb65f9.txt | 2 |
| 06-ai-math-proofs.json | extracted-from-copied-file | 06-ai-math-proofs.agent-tools.txt | 2 |
| 07-ai-researchers.agent-tools.txt | copied-file | c30e5e1f-2eb2-40c5-857e-0d02b6f7b7e5.txt | 0 |
| 07-ai-researchers.json | extracted-from-copied-file | 07-ai-researchers.agent-tools.txt | 0 |
| 08-macro-economists.agent-tools.txt | copied-file | cd4a4656-6ced-4ebe-b691-7c3989ef3863.txt | 0 |
| 08-macro-economists.json | extracted-from-copied-file | 08-macro-economists.agent-tools.txt | 0 |
| 09-bond-yields.agent-tools.txt | copied-file | e1f6a8d2-5c48-4e0d-acbb-b0de2c066d2b.txt | 3 |
| 09-bond-yields.json | extracted-from-copied-file | 09-bond-yields.agent-tools.txt | 3 |
| 10-physics-space.agent-tools.txt | copied-file | 3a3f5659-7210-4e2c-bc2d-e53c7bae49db.txt | 0 |
| 10-physics-space.json | extracted-from-copied-file | 10-physics-space.agent-tools.txt | 0 |
| 11-zh-ai-research.agent-tools.txt | copied-file | 4fede6c3-4e97-47b1-af02-c9604572bf05.txt | 10 |
| 11-zh-ai-research.json | extracted-from-copied-file | 11-zh-ai-research.agent-tools.txt | 10 |
| 12-ai-evals-policy.agent-tools.txt | copied-file | 636f3c15-2ec1-429b-b8f8-4ce19f7b4821.txt | 0 |
| 12-ai-evals-policy.json | extracted-from-copied-file | 12-ai-evals-policy.agent-tools.txt | 0 |
