# Capture failures — 2026-10-27 round2

- FRED: permanently disabled (no requests).
- X continuation (Part 1): skipped — private `x-pagination/2026-10-27.json` absent (0 queries / 0 pages / 0 new posts).
- X search: no tool errors this round (29 search calls).
- X hydrate: 2 calls; first call mixed 15 correct lead ids with 10 mistyped ids (Not Found for typos only); second call returned the remaining 10 leads. Public `hydrate-01.json` merges all 25 leads; hydrate lookup missing: 0.
- arXiv weekly sample: all 5 categories HTTP 200 / 50 entries; validate all_valid; identical to round1 (ids + entry content; feed-level `updated` ignored).
- Empty first page (not an error): accounts-01, accounts-02, ai-tech-reports, physics-arxiv, stock-chanlun, stock-a-share.
