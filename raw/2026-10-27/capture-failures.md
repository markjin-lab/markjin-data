# capture-failures — 2026-10-27 round1

## Mode
- **baseline only** (arXiv API + X). PR #3 / #6 未合并 main → 不跑 capture_sources.py / fetch_primary / scrapers。
- FRED 永久停用：本轮无任何 FRED 请求与数据。
- 原始机构源（BLS、美联储、财政部、Census、BEA、EIA 等）本轮不请求；不跑 FRB G.17。
- 内部查询集：无内部查询文件 → 跳过（与昨日相同）。

## arXiv
- 5 类目均 HTTP 200、各 50 entries；unique 见 arxiv/PROVENANCE.md。
- #110 R1 有效性见 private 报告（推仓后登记）。

## X
- search 调用 56；hydrate 调用 10；合计 66。
- raw posts（各页合计）925；unique 922。
- filtered 441；leads 441（全部「线索」）。
- Early-stop 续翻查询数：**0**。
- At page_cap 仍有 next_token（本轮不续）：A03, A04, A05, B02, B03, B04, B05, B06, B08, B10, B11, B12, B13, B14, B16, B17。
- First page empty: B01。
- 详见 `x/PROVENANCE.md`。

## 续翻
- 无提前停翻；未写 private x-pagination 文件。
