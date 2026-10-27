# arXiv R1 2026-10-28

- Timezone: Asia/Singapore
- UA: markjin-capture/1.0
- Endpoint: https://export.arxiv.org/api/query
- Categories: cs.AI, cs.LG, cs.CL, stat.ML, q-bio.QM
- Each: start=0 max_results=50 sortBy=submittedDate sortOrder=descending
- Inter-category sleep ~3s
- Stored as raw Atom XML (cs.AI.xml … q-bio.QM.xml)
- query-log.jsonl: per-request url, http_status, timestamp (UTC), entry_count

All five categories returned HTTP 200 with 50 entries each.
