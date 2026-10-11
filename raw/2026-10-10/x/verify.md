# Spot-check — 2026-10-10 16:44 SGT

Method: x.get_posts_by_ids for 4 posts; compared `id` and `text` with Python string equality against the raw files.

| id | raw file | id match | text exact match |
|---|---|---|---|
| 2108833699886485927 | 11-zh-ai-research.json (whitespace-heavy zh post) | yes | yes |
| 2108575761640607764 | 03-science-journals.json | yes | yes |
| 2108124820357460200 | 06-ai-math-proofs.json | yes | yes |
| 2108630834169385310 | 04-official-econ.json | yes | yes |

Result: 4/4 PASS. Caveat: both sides were transcribed from inline tool output, so this confirms consistency between two independent API calls, not wire-level bytes.
