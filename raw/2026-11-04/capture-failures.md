# capture-failures — 2026-11-04 round1

- Mode: PR/improve/sources.yaml 未在 main，按基线采（仅公开 arXiv API + X）。
- FRED: permanently off（零请求、不存档）。
- 海关: BLOCKED；EIA: 不请求业务 API。
- #110 arXiv validate-r1: all_valid=true; invalid=[]。
- X early-stop（排期停翻，留给 R2 续翻）: A02, A03, A04, A05, A06（各停于 p2，next_page=3）。
- X page_cap 留给 R2: B04, B06, B08, B09, B10, B11, B12, B13, B14, B16, B17。
- X first page empty: B01（非错误）。
- X 续翻 token 仅存 private x-pagination（不进公开）。
