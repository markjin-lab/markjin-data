# raw/ 原始存档（只追加）

## 路径
`raw/YYYY-MM-DD/<source>/<文件>`，source ∈ arxiv | fred | x；采集时间：自 2026-10-12 起为 05:00（round1）与 06:00（round2）SGT，日报 07:00 SGT 发布；2026-10-11 及以前为 07:00 与 08:15 SGT（历史目录保持原样）。


另有以下子目录（同样逐字节保存、在当天 MANIFEST.sha256 登记）：
- `raw/YYYY-MM-DD/fulltext/`：许可允许转载的全文（遮盖联系邮箱后的公开版）；未获转载授权的只记 URL 与 sha256。说明见目录内 `PROVENANCE.md`。
- `raw/YYYY-MM-DD/nbs-gdp/`：国家统计局 GDP 公开页面与对账表，说明见目录内 `PROVENANCE.md`、`README.md`。
- `raw/YYYY-MM-DD/round2/<source>/`：当天第二轮（round2）采集，结构与第一轮的 arxiv / fred / x 相同。

## 只追加规则
- 逐字节保存，**已提交文件永不编辑、永不覆盖、永不删除/改名**。
- 更正以新文件追加（如 `cs.AI.r2.xml`），并在 MANIFEST 追加新行；旧行保留。
- `MANIFEST.sha256` 是唯一允许变更的已提交文件，且只能追加行。
- 规则自 `scripts/verify-raw.sh` 引入的提交起强制执行（此前 2026-10-10 目录在 d0dbcaf、6189d95 中有删改，已按当时状态作为基线）。

## MANIFEST 格式
每天目录下 `MANIFEST.sha256`，`sha256sum` 标准格式，一行一个文件：
```
<64位小写 sha256>  ./<source>/<文件>
```
目录内除 MANIFEST 自身外的每个文件都必须登记。可另附 `manifest.json`（同样须登记）记录来源 URL、抓取时间（ISO 8601，+08:00）与来源标签。

## 来源标签（provenance）
- `copied-file`：直接从 API/HTTP 响应落盘的原始字节（如 arXiv Atom XML、FRED JSON）。
- `tool-return-transcribed`：由工具调用返回内容转录写入的文件（如 X/Grok 搜索结果 JSON）。非原始字节，只能作为线索，断言须回放到 `copied-file` 一手来源（见 issue #4）。
标签记录在 `manifest.json` 或各 source 的 `query-log.jsonl` 中，按文件路径对应。

## 证据链引用
证据链“存档”字段直接写：`raw/YYYY-MM-DD/<source>/<文件> sha256:<哈希>`，哈希即 MANIFEST 对应行，可用下列命令回放。

## 校验
```
scripts/verify-raw.sh            # 全部日期 sha256sum -c + 对照 git 历史检查只追加
cd raw/YYYY-MM-DD && sha256sum -c MANIFEST.sha256   # 单日
```
