# 2026-10-14 撤回记录（RETRACTIONS）

本文件登记从公开仓库 main 撤回的 raw 文件。raw/ 存档原则为只追加（append-only）；以下撤回为**合规例外**（compliance exception to append-only）。

## 2026-10-18 FRED 撤回（王总决定）

| path | source_url | sha256 | removed_at | reason |
|---|---|---|---|---|
| raw/2026-10-14/fred/CPIAUCSL.json | https://api.stlouisfed.org/fred/series/observations?series_id=CPIAUCSL&file_type=json | c80fd707af1f416c6a00f1d184fef78259ffa2a56d097dcd79860793719fd078 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-14/fred/DGS10.json | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json | 64dd60652cee1412ca2e4e70654f38d64552eb654ab83c087978622c3c30168c | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-14/fred/FEDFUNDS.json | https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&file_type=json | 906725ead8a2dc13cd0acafc57405cd9a944a97f674059f384103a310e090a6e | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-14/fred/T10Y2Y.json | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json | 1b231d86db788e077ae30db4025ec28c7cc2e3fcc620b3ffb51b7ad8adc23fe5 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-14/fred/UNRATE.json | https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&file_type=json | 20838d843a5b9ec99c9d28b7fc690a4f5ee4dffa6ce601b35554e72c2b31a4d9 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-14/round2/fred/CPIAUCSL.json | https://api.stlouisfed.org/fred/series/observations?series_id=CPIAUCSL&file_type=json | c80fd707af1f416c6a00f1d184fef78259ffa2a56d097dcd79860793719fd078 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-14/round2/fred/DGS10.json | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json | 64dd60652cee1412ca2e4e70654f38d64552eb654ab83c087978622c3c30168c | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-14/round2/fred/FEDFUNDS.json | https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&file_type=json | 906725ead8a2dc13cd0acafc57405cd9a944a97f674059f384103a310e090a6e | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-14/round2/fred/T10Y2Y.json | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json | 52cdab134e4d18d38a863b2ffafbdfb42d59279be43d027254b23f118462b669 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |
| raw/2026-10-14/round2/fred/UNRATE.json | https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&file_type=json | 20838d843a5b9ec99c9d28b7fc690a4f5ee4dffa6ce601b35554e72c2b31a4d9 | 2026-10-18 18:16 SGT (UTC+8) | 来源条款不允许转载和存储，改从原始机构取数 |

来源 URL 出处：fred/CPIAUCSL.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；fred/DGS10.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；fred/FEDFUNDS.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；fred/T10Y2Y.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；fred/UNRATE.json 见 fred/PROVENANCE.md（URL 模板，api_key 已去掉）；round2/fred/CPIAUCSL.json 见 round2/fred/PROVENANCE.md（URL 模板，api_key 已去掉）；round2/fred/DGS10.json 见 round2/fred/PROVENANCE.md（URL 模板，api_key 已去掉）；round2/fred/FEDFUNDS.json 见 round2/fred/PROVENANCE.md（URL 模板，api_key 已去掉）；round2/fred/T10Y2Y.json 见 round2/fred/PROVENANCE.md（URL 模板，api_key 已去掉）；round2/fred/UNRATE.json 见 round2/fred/PROVENANCE.md（URL 模板，api_key 已去掉）。

批准：王总（2026-10-18 18:13 SGT 决定：不再经 FRED 取数，已有 FRED 原始文件按 RETRACTIONS 撤回）。复核：待 markjin 审查 bot 审查；合并需王总批准记录。
MANIFEST.sha256 中的原登记行按只追加原则保留不改；scripts/verify-raw.sh 依据本表（路径 + sha256 均匹配）将其视为已撤回。
同目录下的 PROVENANCE.md、query-log.jsonl 等说明/日志文件不属本次撤回范围，原样保留（见 PR 描述）。

## RETRACTIONS.md 自身的例外规则

`RETRACTIONS.md` 为只追加（append-only）文件：每次追加内容后，须在同日 `MANIFEST.sha256` 末尾再追加一行，登记其新的 sha256。MANIFEST 对本文件只校验最后一条，历史版本靠前缀不变保证；此例外仅适用于 RETRACTIONS.md。
