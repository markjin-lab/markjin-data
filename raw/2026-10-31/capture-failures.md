# capture-failures — 2026-10-31 round1

## Baseline mode
- improve/sources.yaml 未合入 main → 本轮公开仅采 arXiv API + X；不跑 fetch_primary、不跑公开 scrapers。
- FRED 永久停用：零 FRED 请求。
- 原始机构/EIA 业务 API 本轮不请求；海关 BLOCKED。
- 操作版 sources 仅用于 NEA 私有 + MIIT（Mac-only）。

## #110 arXiv R1 validate
- all_valid=true
- invalid=[]

## X pagination (no tokens in public)
- early-stop (schedule): 0
- page_cap with next_token (R2): A02, A03, A04, A05, B02, B04, B05, B06, B09, B10, B11, B12, B13, B14, B16, B17
- private x-pagination recorded under private/x-pagination/ (tokens not public)

## Other
- B01 first page empty (not an error)
- FRED: permanently off
