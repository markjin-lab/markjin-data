# capture-failures — 2026-10-26 round1

## Mode
- **baseline only** (arXiv API + X). PR #3 / #6 未合并 main → 不跑 capture_sources.py / fetch_primary / scrapers。
- FRED 永久停用：本轮无任何 FRED 请求与数据。
- 原始机构源（BLS、美联储、财政部、Census、BEA、EIA 等）本轮不请求；不跑 FRB G.17。
- 内部查询集：无内部查询文件 → 跳过（与昨日相同）。

## arXiv
- 5 类目均 HTTP 200、各 50 entries；unique 211；new vs seen-ids（仅报告、未更新）0。
- 详见 `arxiv/PROVENANCE.md`。

## X
- search 调用 56；hydrate 调用 4；合计 60。
- raw posts（各页合计）781；unique 779；new vs seen-ids 410（仅报告）。
- filtered 342；leads 342（全部「线索」）。
- Early-stop 续翻查询数：**0**（本轮在 page_cap 内翻完或自然结束）。
- At page_cap 仍有 next_token（本轮不续）：A05, B02, B03, B04, B05, B11, B12, B13, B14, B15, B16, B17。
- 详见 `x/PROVENANCE.md`。

## 续翻
- 无提前停翻；未写 private x-pagination 文件。
