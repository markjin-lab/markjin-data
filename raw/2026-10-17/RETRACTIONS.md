# 2026-10-17 撤回记录（RETRACTIONS）

本文件登记从公开仓库 main 撤回的 raw 文件。raw/ 存档原则为只追加（append-only）；以下撤回为**合规例外**（compliance exception to append-only）。

## 2026-10-18 FRED 撤回（王总决定）

| path | source_url | sha256 | removed_at | reason |
|---|---|---|---|---|
| raw/2026-10-17/fred/CPIAUCSL.json | https://api.stlouisfed.org/fred/series/observations?series_id=CPIAUCSL&file_type=json | ff9efae1764aeb46bf39d4726843a8b006b2ff08f3310ba2ae056bca3d6fc110 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-17/fred/DGS10.json | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json | 14ed1a4a0193609ddfb09b1495badd567768e2f82616896e7cdb0807128d706c | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-17/fred/FEDFUNDS.json | https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&file_type=json | 886259a8918e4219fe047b6b0d0140218f613ab33378a2fd3b169c6f630198ed | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-17/fred/T10Y2Y.json | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json | eaf49aff643e07a31ad257f7d5a39da9506f88bc1773d27896ab78f78a5929d9 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-17/fred/UNRATE.json | https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&file_type=json | 4627995af5b83032aba575b484e9a02e84bb0231766accd552a035a190260dda | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-17/round2/fred/CPIAUCSL.json | https://api.stlouisfed.org/fred/series/observations?series_id=CPIAUCSL&file_type=json | ff9efae1764aeb46bf39d4726843a8b006b2ff08f3310ba2ae056bca3d6fc110 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-17/round2/fred/DGS10.json | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json | 14ed1a4a0193609ddfb09b1495badd567768e2f82616896e7cdb0807128d706c | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-17/round2/fred/FEDFUNDS.json | https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&file_type=json | 886259a8918e4219fe047b6b0d0140218f613ab33378a2fd3b169c6f630198ed | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-17/round2/fred/T10Y2Y.json | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json | fdfd730d458e6cba8933321a8b8e2db24117be3128db79436616c816b6d874f7 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-17/round2/fred/UNRATE.json | https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&file_type=json | 4627995af5b83032aba575b484e9a02e84bb0231766accd552a035a190260dda | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |

来源 URL 出处：fred/CPIAUCSL.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；fred/DGS10.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；fred/FEDFUNDS.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；fred/T10Y2Y.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；fred/UNRATE.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；round2/fred/CPIAUCSL.json 见 round2/fred/PROVENANCE.md（URL 模板，api_key 已去掉）；round2/fred/DGS10.json 见 round2/fred/PROVENANCE.md（URL 模板，api_key 已去掉）；round2/fred/FEDFUNDS.json 见 round2/fred/PROVENANCE.md（URL 模板，api_key 已去掉）；round2/fred/T10Y2Y.json 见 round2/fred/PROVENANCE.md（URL 模板，api_key 已去掉）；round2/fred/UNRATE.json 见 round2/fred/PROVENANCE.md（URL 模板，api_key 已去掉）。

批准：王总（2026-10-18 18:13 SGT 决定：不再经 FRED 取数，已有 FRED 原始文件按 RETRACTIONS 撤回）。复核：待 markjin 审查 bot 审查；合并需王总批准记录。
MANIFEST.sha256 中的原登记行按只追加原则保留不改；scripts/verify-raw.sh 依据本表（路径 + sha256 均匹配）将其视为已撤回。
同目录下的 PROVENANCE.md、query-log.jsonl 等说明/日志文件不属本次撤回范围，原样保留（见 PR 描述）。

## RETRACTIONS.md 自身的例外规则

`RETRACTIONS.md` 为只追加（append-only）文件：每次追加内容后，须在同日 `MANIFEST.sha256` 末尾再追加一行，登记其新的 sha256。MANIFEST 对本文件只校验最后一条，历史版本靠前缀不变保证；此例外仅适用于 RETRACTIONS.md。
