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
- 只认精确路径 `raw/<日期>/MANIFEST.sha256` 与 `raw/<日期>/RETRACTIONS.md` 为可追加文件；嵌套在子目录里的同名文件按普通 raw 文件处理（须登记、不可改、删除须撤回登记）。
- 撤回：删除文件的同一提交在 `RETRACTIONS.md` 追加一行，sha256 必须等于父提交中被删除那份 blob；登记的文件若仍存在，照常按 MANIFEST 校验 sha256（撤回行不能掩盖假 sha）。

## 可信基线（verify-raw 检查起点）
- 可信基线起点：`224fd88`（规则与 MANIFEST 登记补齐之后的 main）。`d6f88b5` 那批（2026-10-12 round1/round2 采集，含 `03ffe25`、`d6f88b5`）
  是规则生效前的历史违规：文件在后续提交 `224fd88` 才补登记，从 `03ffe25` 起扫会在 `d6f88b5` 失败，这是已知历史，不回溯、不改写。
- 日常检查只从 PR 基线或推送前的远端 sha 往后逐提交查：CI 用 PR 的 merge-base；pre-push 用远端 ref 的旧 sha；
  新分支（远端无此 ref）用 `git merge-base origin/main <target>`；本地无 origin/main 时回退 `<target>^`。不要用早于可信基线的提交作 BASE。

## 不可变 ref（pre-push 强制）
- 清单：`refs/heads/main` 与全部 `refs/tags/*`。
- 禁止删除；已有 tag 不得改指到别的提交（即使是子孙提交）；main 只能快进（基线必须是目标的祖先）。
- 推送目标不是提交（树、blob 等）或任何 git 调用失败 → 拒绝推送。

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
scripts/verify-raw.sh [BASE] [--target REV]   # 从 git 对象逐提交检查 BASE..target 的快照与只追加规则
cd raw/YYYY-MM-DD && sha256sum -c MANIFEST.sha256   # 单日
```
