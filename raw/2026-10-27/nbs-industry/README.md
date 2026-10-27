# nbs-industry：国家统计局工业 / 能源 / 固投发布页公开摘录（#132）

路径：`raw/2026-10-27/nbs-industry/`。本 README 为新增文件；文件哈希见 `../MANIFEST.sha256`；抓取与授权见 `PROVENANCE.md`、`query-log.jsonl`、`INDEX.json`。

## 批准范围（不可扩）
1. **工增同比·环比** — `nbs-t20261019_1965617.html` + `.excerpt.md`
2. **能源四项同比**（原煤 / 原油 / 天然气 / 发电量）— `nbs-t20261019_1965613.html` + `.excerpt.md`
3. **固投设备工器具同比** — `nbs-t20261019_1965616.html` + `.excerpt.md`

**占比不写**：固投设备工器具占比正文无分项数字，公开稿不摘、不引用占比数字。

汇总：`PUBLIC-EXCERPTS.md`。索引：`INDEX.json`（占比项 `found:false` 且 `public:false`）。

## 来源标注
每篇摘录显著注明：引自国家统计局网站（中国统计信息网）www.stats.gov.cn，并给出原文 URL。条款要点见 `PROVENANCE.md`。

## 证据链引用
存档字段写：
```
raw/2026-10-27/nbs-industry/<文件> sha256:<哈希>
```
哈希即当天 `../MANIFEST.sha256` 对应行。industry-data 短代码只引用本目录批准指标文字/同比环比，勿扩占比或 data.stats。

## 不做
- 不复测 data.stats.gov.cn（A4）
- 不改 eia-api / miit / nea sources
- 不把内部私有试摘录绝对路径写入公开文件
