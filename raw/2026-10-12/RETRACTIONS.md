# 2026-10-12 撤回记录（RETRACTIONS）

本文件登记从公开仓库 main 撤回的 raw 文件。raw/ 存档原则为只追加（append-only）；以下撤回为**合规例外**，
由 Grok Bot 批准（compliance exception to append-only），经 markjin 审查与治理 复核。
原始文件已按原字节移至本机私有存档（不公开），sha256 校验未变。MANIFEST.sha256 中的原登记行按只追加原则保留不改；
scripts/verify-raw.sh 依据本表（路径 + sha256 均匹配）将其视为已撤回。

| path | source_url | sha256 | removed_at | reason |
|---|---|---|---|---|
| raw/2026-10-12/nasa-news/20261011T210721Z.xml | https://www.nasa.gov/news-release/feed/ | b679a2bca7a2288610630aa58206fd62c551df09a901e869c5d0a5543dd0bb6f | 2026-10-12 07:17 SGT (UTC+8) | NASA 新闻源可能包含第三方图片/署名素材，版权归属不明 |
| raw/2026-10-12/nasa-news/20261011T210943Z.xml | https://www.nasa.gov/news-release/feed/ | b679a2bca7a2288610630aa58206fd62c551df09a901e869c5d0a5543dd0bb6f | 2026-10-12 07:17 SGT (UTC+8) | NASA 新闻源可能包含第三方图片/署名素材，版权归属不明 |
| raw/2026-10-12/round2/nasa-news/20261011T215332Z.xml | https://www.nasa.gov/news-release/feed/ | b679a2bca7a2288610630aa58206fd62c551df09a901e869c5d0a5543dd0bb6f | 2026-10-12 07:17 SGT (UTC+8) | NASA 新闻源可能包含第三方图片/署名素材，版权归属不明 |
| raw/2026-10-12/prx-quantum/20261011T210721Z.xml | https://feeds.aps.org/rss/recent/prxquantum.xml | f73b8a6960bbed91b2da07606c1f4b313623a699fa0f013766d9471363e8e3d8 | 2026-10-12 07:17 SGT (UTC+8) | PRX Quantum 源含出版方（APS）论文摘要，非开放授权 |
| raw/2026-10-12/prx-quantum/20261011T210943Z.xml | https://feeds.aps.org/rss/recent/prxquantum.xml | f73b8a6960bbed91b2da07606c1f4b313623a699fa0f013766d9471363e8e3d8 | 2026-10-12 07:17 SGT (UTC+8) | PRX Quantum 源含出版方（APS）论文摘要，非开放授权 |
| raw/2026-10-12/round2/prx-quantum/20261011T215332Z.xml | https://feeds.aps.org/rss/recent/prxquantum.xml | f73b8a6960bbed91b2da07606c1f4b313623a699fa0f013766d9471363e8e3d8 | 2026-10-12 07:17 SGT (UTC+8) | PRX Quantum 源含出版方（APS）论文摘要，非开放授权 |
| raw/2026-10-12/openfda-510k/20261011T210721Z.json | https://api.fda.gov/device/510k.json?sort=decision_date:desc&limit=20 | 7f2d759dbe5f5832a66111367a16f1efb125a2f3633f1739f1e156eb80040c63 | 2026-10-12 07:17 SGT (UTC+8) | openFDA 510(k) 记录含个人信息 |
| raw/2026-10-12/openfda-510k/20261011T210943Z.json | https://api.fda.gov/device/510k.json?sort=decision_date:desc&limit=20 | 7f2d759dbe5f5832a66111367a16f1efb125a2f3633f1739f1e156eb80040c63 | 2026-10-12 07:17 SGT (UTC+8) | openFDA 510(k) 记录含个人信息 |
| raw/2026-10-12/round2/openfda-510k/20261011T215332Z.json | https://api.fda.gov/device/510k.json?sort=decision_date:desc&limit=20 | 7f2d759dbe5f5832a66111367a16f1efb125a2f3633f1739f1e156eb80040c63 | 2026-10-12 07:17 SGT (UTC+8) | openFDA 510(k) 记录含个人信息 |

来源 URL 出处：nasa-news 见 query-log.jsonl 第19/43行；round2/query-log.jsonl 第19行；prx-quantum 见 query-log.jsonl 第22/46行；round2/query-log.jsonl 第22行；openfda-510k 见 query-log.jsonl 第24/48行；round2/query-log.jsonl 第24行。

批准：Grok Bot（合规例外，append-only 的例外）。复核：markjin 审查与治理。

## 保留说明（本机路径）

query-log.jsonl 第 19、22、24、43、46、48 行的 stored 字段、dedup-evidence.json 第 4 行，以及 raw/2026-10-11/x/ 下的相关文件，
含有采集机器上的本地绝对路径。经审查：这些只是本机目录路径，不是凭据，也不含个人信息，因此按只追加原则原样保留，不做修改。
今后新增的 raw 文件不得包含此类本地绝对路径（已由 scripts/check-public.py 新规则 E-PUBLIC-LOCAL-PATH 拦截）。

## RETRACTIONS.md 自身的例外规则

`RETRACTIONS.md` 为只追加（append-only）文件：每次追加内容后，须在同日 `MANIFEST.sha256` 末尾再追加一行，登记其新的 sha256。MANIFEST 对本文件只校验最后一条，历史版本靠前缀不变保证；此例外仅适用于 RETRACTIONS.md。

## 2026-10-18 FRED 撤回（王总决定）

本节登记从公开仓库 main 撤回的 FRED 原始文件。

| path | source_url | sha256 | removed_at | reason |
|---|---|---|---|---|
| raw/2026-10-12/fred/CPIAUCSL.json | https://api.stlouisfed.org/fred/series/observations?series_id=CPIAUCSL&file_type=json | c80fd707af1f416c6a00f1d184fef78259ffa2a56d097dcd79860793719fd078 | 2026-10-18 18:16 SGT (UTC+8) | FRED 条款第 (p) 项与原样存档要求冲突；王总 2026-10-18 18:13 SGT 决定停用 FRED 渠道、改从原始发布机构取数，按 RETRACTIONS 撤回 |
| raw/2026-10-12/fred/DGS10.json | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json | e8fb3d750da627f024cf8e7fcc8a6826fe14bbe6c07b18d6aa56a7e6a3e280fe | 2026-10-18 18:16 SGT (UTC+8) | FRED 条款第 (p) 项与原样存档要求冲突；王总 2026-10-18 18:13 SGT 决定停用 FRED 渠道、改从原始发布机构取数，按 RETRACTIONS 撤回 |
| raw/2026-10-12/fred/FEDFUNDS.json | https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&file_type=json | 906725ead8a2dc13cd0acafc57405cd9a944a97f674059f384103a310e090a6e | 2026-10-18 18:16 SGT (UTC+8) | FRED 条款第 (p) 项与原样存档要求冲突；王总 2026-10-18 18:13 SGT 决定停用 FRED 渠道、改从原始发布机构取数，按 RETRACTIONS 撤回 |
| raw/2026-10-12/fred/T10Y2Y.json | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json | 1b231d86db788e077ae30db4025ec28c7cc2e3fcc620b3ffb51b7ad8adc23fe5 | 2026-10-18 18:16 SGT (UTC+8) | FRED 条款第 (p) 项与原样存档要求冲突；王总 2026-10-18 18:13 SGT 决定停用 FRED 渠道、改从原始发布机构取数，按 RETRACTIONS 撤回 |
| raw/2026-10-12/fred/UNRATE.json | https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&file_type=json | 20838d843a5b9ec99c9d28b7fc690a4f5ee4dffa6ce601b35554e72c2b31a4d9 | 2026-10-18 18:16 SGT (UTC+8) | FRED 条款第 (p) 项与原样存档要求冲突；王总 2026-10-18 18:13 SGT 决定停用 FRED 渠道、改从原始发布机构取数，按 RETRACTIONS 撤回 |

来源 URL 出处：fred/CPIAUCSL.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；fred/DGS10.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；fred/FEDFUNDS.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；fred/T10Y2Y.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；fred/UNRATE.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）。

批准：王总 2026-10-18 18:13 SGT 决定（经 Grok Bot 转达）：不再经 FRED，改从原始机构取数；已有 FRED 文件按 RETRACTIONS 撤回。复核与合并状态见 markjin-data PR #83。
MANIFEST.sha256 中的原登记行按只追加原则保留不改；scripts/verify-raw.sh 依据本表（路径 + sha256 均匹配）将其视为已撤回。
同目录下的 PROVENANCE.md、query-log.jsonl 等说明/日志文件不属本次撤回范围，原样保留（见 PR 描述）。

2026-10-18 勘误：上文「复核与合并状态见 markjin-data PR #83」应为 markjin-data PR #87（取代 #85、#83），合并提交 c0d788c；PR #83、#85 均已关闭、未合并。上文「见 PR 描述」中的「PR」同样指 PR #87。原句按只追加原则保留不改。
