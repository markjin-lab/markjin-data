# 2026-10-11 撤回记录（RETRACTIONS）

本文件登记从公开仓库 main 撤回的 raw 文件。raw/ 存档原则为只追加（append-only）；以下撤回为**合规例外**（compliance exception to append-only）。

## 2026-10-18 FRED 撤回（王总决定）

| path | source_url | sha256 | removed_at | reason |
|---|---|---|---|---|
| raw/2026-10-11/fred/CPIAUCSL.json | https://api.stlouisfed.org/fred/series/observations?series_id=CPIAUCSL&file_type=json&sort_order=desc&limit=30 | 8145e734b209a76de538334527e369ee4e0bea1e3b59c84cc3b25565242bfc01 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-11/fred/DGS10.json | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=30 | 2983c4bc7a0a1f5bc8bb2225f9d846e0fe6cd74903f7d4b5424180d42bb798cd | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-11/fred/FEDFUNDS.json | https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&file_type=json&sort_order=desc&limit=30 | 40918299a8e6fa8c72fb8c186b9764d983a08cfc45b70c3e01a408f6e4b9c01b | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-11/fred/T10Y2Y.json | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=30 | b8eb9bb7773767e26832922dce6bc45eae55745f02131f5ed0ac4491752e15dd | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-11/fred/UNRATE.json | https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&file_type=json&sort_order=desc&limit=30 | 1768afdc2324d98e079bdc7f9bd879042931c3fde9de23e72c9f41957deda90b | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-11/round2/fred/CPIAUCSL.json | https://api.stlouisfed.org/fred/series/observations?series_id=CPIAUCSL&file_type=json&sort_order=desc&limit=30 | 8145e734b209a76de538334527e369ee4e0bea1e3b59c84cc3b25565242bfc01 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-11/round2/fred/DGS10.json | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=30 | 2983c4bc7a0a1f5bc8bb2225f9d846e0fe6cd74903f7d4b5424180d42bb798cd | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-11/round2/fred/FEDFUNDS.json | https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&file_type=json&sort_order=desc&limit=30 | 40918299a8e6fa8c72fb8c186b9764d983a08cfc45b70c3e01a408f6e4b9c01b | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-11/round2/fred/T10Y2Y.json | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=30 | b8eb9bb7773767e26832922dce6bc45eae55745f02131f5ed0ac4491752e15dd | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-11/round2/fred/UNRATE.json | https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&file_type=json&sort_order=desc&limit=30 | 1768afdc2324d98e079bdc7f9bd879042931c3fde9de23e72c9f41957deda90b | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-11/nbs-gdp/fred-CHNGDPNQDSMEI.csv | https://fred.stlouisfed.org/graph/fredgraph.csv?id=CHNGDPNQDSMEI | 2d30945bea56739c985dd34a9b6e0d0b58b52e8b0fee2e8de98dee96dd951dfb | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |

来源 URL 出处：fred/CPIAUCSL.json 见 fred/query-log.jsonl 第2行（已去掉 api_key 参数）；fred/DGS10.json 见 fred/query-log.jsonl 第1行（已去掉 api_key 参数）；fred/FEDFUNDS.json 见 fred/query-log.jsonl 第4行（已去掉 api_key 参数）；fred/T10Y2Y.json 见 fred/query-log.jsonl 第5行（已去掉 api_key 参数）；fred/UNRATE.json 见 fred/query-log.jsonl 第3行（已去掉 api_key 参数）；round2/fred/CPIAUCSL.json 见 round2/fred/query-log.jsonl 第2行（已去掉 api_key 参数）；round2/fred/DGS10.json 见 round2/fred/query-log.jsonl 第1行（已去掉 api_key 参数）；round2/fred/FEDFUNDS.json 见 round2/fred/query-log.jsonl 第4行（已去掉 api_key 参数）；round2/fred/T10Y2Y.json 见 round2/fred/query-log.jsonl 第5行（已去掉 api_key 参数）；round2/fred/UNRATE.json 见 round2/fred/query-log.jsonl 第3行（已去掉 api_key 参数）；nbs-gdp/fred-CHNGDPNQDSMEI.csv 见 nbs-gdp/query-log.jsonl 第20行。

批准：王总（2026-10-18 18:13 SGT 决定：不再经 FRED 取数，已有 FRED 原始文件按 RETRACTIONS 撤回）。复核：待 markjin 审查 bot 审查；合并需王总批准记录。
MANIFEST.sha256 中的原登记行按只追加原则保留不改；scripts/verify-raw.sh 依据本表（路径 + sha256 均匹配）将其视为已撤回。
同目录下的 PROVENANCE.md、query-log.jsonl 等说明/日志文件不属本次撤回范围，原样保留（见 PR 描述）。

## RETRACTIONS.md 自身的例外规则

`RETRACTIONS.md` 为只追加（append-only）文件：每次追加内容后，须在同日 `MANIFEST.sha256` 末尾再追加一行，登记其新的 sha256。MANIFEST 对本文件只校验最后一条，历史版本靠前缀不变保证；此例外仅适用于 RETRACTIONS.md。

## 2026-10-18 FRED 撤回补充：nbs-gdp 年度对账表（FRED 数值的衍生）

| path | source_url | sha256 | removed_at | reason |
|---|---|---|---|---|
| raw/2026-10-11/nbs-gdp/annual-reconciliation.csv | 无（本地衍生文件，所用 FRED 值来自 https://fred.stlouisfed.org/graph/fredgraph.csv?id=CHNGDPNQDSMEI） | e35f34350120967564606eddc8f804985ceb9987cc983894f11de7ca6ac4ca88 | 2026-10-18 18:27 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-11/nbs-gdp/annual-reconciliation.md | 无（本地衍生文件，所用 FRED 值来自 https://fred.stlouisfed.org/graph/fredgraph.csv?id=CHNGDPNQDSMEI） | c9e83c3c7bf0cee34102db3a6f7ab421fcb26d1240113d2c8089497bc59f0cc5 | 2026-10-18 18:27 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |

批准：Grok Bot 定（王总 2026-10-18 FRED 撤回决定的延伸）。同目录 PROVENANCE.md、query-log.jsonl、README.md 保留不改。复核：待 markjin 审查 bot 审查；合并需王总批准记录。
