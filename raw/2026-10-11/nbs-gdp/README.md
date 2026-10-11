# nbs-gdp：中国季度名义 GDP 存档说明（2026-10-11 抓取）

单位：亿元人民币，现价。本 README 为新增文件，不修改任何已提交文件；文件哈希见 `../MANIFEST.sha256`，抓取记录见 `query-log.jsonl`、`PROVENANCE.md`。

## 三个口径（务必区分）

**(a) 2015Q1–2022Q4（以及 2023Q1–Q2）：FRED `CHNGDPNQDSMEI`**
- 文件：`fred-CHNGDPNQDSMEI.csv`（OECD MEI 来源，单位为元，÷1e8 得亿元；序列止于 2023Q3）。
- 口径：国家统计局（NBS）**第五次全国经济普查修订前**的口径。与当前 NBS 年度数（年鉴 2025 表 3-1）不可直接比较。
- 来源：https://fred.stlouisfed.org/graph/fredgraph.csv?id=CHNGDPNQDSMEI

**(b) 2023Q3 起：NBS 季度初步核算（初值）**
- 取自 stats.gov.cn 每季度“国内生产总值初步核算结果”发布页（单季值；只发布累计值时由累计值差分）。均为首次发布数，未用后续修订值替换。
- 2023Q3 319992（https://www.stats.gov.cn/sj/zxfb/202310/t20231019_1943720.html）
- 2023Q4 347890（https://www.stats.gov.cn/sj/zxfb/202401/t20240118_1946691.html）
- 2024Q1 296299（https://www.stats.gov.cn/sj/zxfb/202404/t20240429_1948771.html）
- 2024Q2 320537（https://www.stats.gov.cn/sj/zxfb/202407/t20240716_1955649.html）
- 2024Q3 332910（https://www.stats.gov.cn/sj/zxfb/202410/t20241019_1957083.html）
- 2024Q4 373726（https://www.stats.gov.cn/sj/zxfb/202501/t20250118_1958363.html）
- 2025Q1 318758（https://www.stats.gov.cn/sj/zxfb/202504/t20250417_1959334.html）
- 2025Q2 341778（https://www.stats.gov.cn/sj/zxfb/202507/t20250716_1960426.html）
- 2025Q3 354500（https://www.stats.gov.cn/sj/zxfb/202510/t20251021_1961646.html）
- 2025Q4 387911（https://www.stats.gov.cn/sj/zxfb/202601/t20260120_1962349.html）
- 2026Q1 334193（https://www.stats.gov.cn/sj/zxfb/202604/t20260417_1963336.html）
- 2026Q2 361511（https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html）

**(c) 2024Q1–Q3 初值同样是修订前口径**
- NBS 于 2024-12-27 发布《关于修订2023年国内生产总值数据的公告》（https://www.stats.gov.cn/sj/zxfb/202412/t20241227_1957915.html），2023 年 GDP 由 1260582 修订为 1294272（+33690，其中五经普 +20257、自有住房核算改革 +13433）。
- 2024Q1–Q3 初值发布于该修订之前，属**修订前口径**；2023Q3–Q4 初值亦然。2024Q4 及以后的初值为修订后口径。因此 2024 年四个季度初值之和（1323472）明显低于 2024 年全年初值（1349084）。

## 年度参照
- 统计年鉴 2025 表 3-1（`nbs-yearbook2025-C03-01.jpg`，https://www.stats.gov.cn/sj/ndsj/2025/html/C03-01.jpg）：1978–2024 年度 GDP，当前修订口径。
- 2023 年统计公报 https://www.stats.gov.cn/sj/zxfb/202402/t20240228_1947915.html ；2024 年 https://www.stats.gov.cn/sj/zxfb/202502/t20250228_1958817.html ；2025 年 https://www.stats.gov.cn/sj/zxfb/202602/t20260228_1962662.html
- 最终核实：2022 年 https://www.stats.gov.cn/sj/zxfb/202312/t20231229_1946058.html ；2024 年 https://www.stats.gov.cn/sj/zxfb/202512/t20251226_1962144.html
- 对账表：`annual-reconciliation.csv` / `annual-reconciliation.md`。

## NBS 数据库不可用
NBS 数据库 data.stats.gov.cn（easyquery，https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgjd&...）在 box 与用户 Mac 上均返回 **HTTP 403（WAF reason: UrlACL）**；box 端响应存档为 `nbs-easyquery-A0101-403.html`。未尝试任何验证码/鉴权绕过。故季度修订后口径的完整序列暂缺，以上 (a)(b)(c) 为替代方案。
