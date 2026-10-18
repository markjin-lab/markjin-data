# 2026-10-10 撤回记录（RETRACTIONS）

本文件登记从公开仓库 main 撤回的 raw 文件。raw/ 存档原则为只追加（append-only）；以下撤回为**合规例外**（compliance exception to append-only）。

## 2026-10-18 FRED 撤回（王总决定）

| path | source_url | sha256 | removed_at | reason |
|---|---|---|---|---|
| raw/2026-10-10/fred/CPIAUCSL.json | https://api.stlouisfed.org/fred/series/observations?series_id=CPIAUCSL&file_type=json&sort_order=desc&limit=30 | e9a97029f4f467fd61fd6eb4640ff7c8a628b88a4d6c8e0f4381682e934fcf38 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-10/fred/DGS10.json | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=30 | 2983c4bc7a0a1f5bc8bb2225f9d846e0fe6cd74903f7d4b5424180d42bb798cd | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-10/fred/FEDFUNDS.json | https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&file_type=json&sort_order=desc&limit=30 | 03adb1e593f14d4b495352b0ebad276fe6c2186cc04ee985711e6a0957b65f6c | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-10/fred/T10Y2Y.json | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=30 | b8eb9bb7773767e26832922dce6bc45eae55745f02131f5ed0ac4491752e15dd | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-10/fred/UNRATE.json | https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&file_type=json&sort_order=desc&limit=30 | ce07b5ca2eb48e0bc8be90a69c2f572fe396df58bb154ce9250a503c98314a4d | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |

来源 URL 出处：fred/CPIAUCSL.json 见 fred/query-log.jsonl 第2行（已去掉 api_key 参数）；fred/DGS10.json 见 fred/query-log.jsonl 第1行（已去掉 api_key 参数）；fred/FEDFUNDS.json 见 fred/query-log.jsonl 第4行（已去掉 api_key 参数）；fred/T10Y2Y.json 见 fred/query-log.jsonl 第5行（已去掉 api_key 参数）；fred/UNRATE.json 见 fred/query-log.jsonl 第3行（已去掉 api_key 参数）。

批准：王总（2026-10-18 18:13 SGT 决定：不再经 FRED 取数，已有 FRED 原始文件按 RETRACTIONS 撤回）。复核：待 markjin 审查 bot 审查；合并需王总批准记录。
MANIFEST.sha256 中的原登记行按只追加原则保留不改；scripts/verify-raw.sh 依据本表（路径 + sha256 均匹配）将其视为已撤回。
同目录下的 PROVENANCE.md、query-log.jsonl 等说明/日志文件不属本次撤回范围，原样保留（见 PR 描述）。

## RETRACTIONS.md 自身的例外规则

`RETRACTIONS.md` 为只追加（append-only）文件：每次追加内容后，须在同日 `MANIFEST.sha256` 末尾再追加一行，登记其新的 sha256。MANIFEST 对本文件只校验最后一条，历史版本靠前缀不变保证；此例外仅适用于 RETRACTIONS.md。
