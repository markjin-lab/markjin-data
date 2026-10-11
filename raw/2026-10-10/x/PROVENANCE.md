# X raw provenance — 2026-10-10

Tool: dynamic `x` namespace, `search_posts_all` (schema checked with GetDynamicTools first). 12 queries from x-queries.md, query strings/start_time/max_results unchanged; sort recency for from: lists, relevancy for topic queries; output fields added: post.fields=created_at,author_id,public_metrics, expansions=author_id, user.fields=username.
Captured 2026-10-10 16:37–16:43 SGT.

After every call /workspace/agent-tools/ was listed: no new file appeared (newest remained 278781d8-….txt, 15:43 SGT, which predates this run). Therefore **all 12 files are `tool-return-transcribed`, 0 are `copied-file`.**

Transcription method: the inline JSON returned by the tool was written verbatim (quoted heredoc, trailing newline removed) — every field kept, JSON escapes (\n, \", &amp;) kept as-is, non-ASCII kept as UTF-8. Only the trailing "X reads left…" quota line was excluded. Files are NOT byte-for-byte captures of the transport; their hashes in ../MANIFEST.sha256 fix the transcribed bytes, not the wire bytes. No U+00A0/U+2028 occurred in the returns as rendered; whitespace runs (e.g. 11-zh post 2108833699886485927) were reproduced and confirmed equal against get_posts_by_ids (see verify.md).

| file | provenance | result_count |
|---|---|---|
| 01-ai-labs.json | tool-return-transcribed | 4 |
| 02-openai-google.json | tool-return-transcribed | 6 |
| 03-science-journals.json | tool-return-transcribed | 25 |
| 04-official-econ.json | tool-return-transcribed | 25 |
| 05-arxiv-llm.json | tool-return-transcribed | 25 |
| 06-ai-math-proofs.json | tool-return-transcribed | 10 |
| 07-ai-researchers.json | tool-return-transcribed | 10 |
| 08-macro-economists.json | tool-return-transcribed | 10 |
| 09-bond-yields.json | tool-return-transcribed | 10 |
| 10-physics-space.json | tool-return-transcribed | 10 |
| 11-zh-ai-research.json | tool-return-transcribed | 10 |
| 12-ai-evals-policy.json | tool-return-transcribed | 10 |

Derived (not raw): filtered-ids.json (rule in x-queries.md), query-log.jsonl, verify.md. Old *.ids.json index files removed.
