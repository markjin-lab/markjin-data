# capture-failures — 2026-10-28 round1

## Mode
- **baseline only** (arXiv API + X). improve/sources.yaml 不在 main → 不跑 capture_sources.py / fetch_primary / 公开 scrapers。
- FRED 永久停用：本轮无任何 FRED 请求与数据。
- 原始机构源（BLS、美联储、财政部、Census、BEA、EIA 等）本轮不请求；不跑 FRB G.17。
- 内部查询集：跳过。

## arXiv
- 5 类目均 HTTP 200、各 50 entries；#110 validate-r1 全部 valid（private 报告）。
- 无效分类：无。

## X
- search 调用 59；hydrate 调用 6；合计 65。
- raw posts（各页合计）1070；unique 1070。
- filtered 551；leads 551（全部「线索」）。
- Early-stop 续翻查询数（排期提前停）：**0**。
- At page_cap 仍有 next_token（本轮不续，留 R2）：A03, A04, A05, B04, B06, B09, B10, B11, B12, B13, B14, B16, B17。
- First page empty: B01。
- 详见 `x/PROVENANCE.md`。

## 续翻
- 无排期提前停翻；page_cap 续翻 token 私存于 private/x-pagination/2026-10-28.json（公开不写 token）。
