# 批准记录与发布状态 schema（v1）

协调决定 2026-10-10。`scripts/route.py` 只从 markjin-data **main 分支**的 git 对象读取以下文件（不读工作树、其他分支、本机内部目录或公开台账），用**稿件内容 sha256** 绑定。
记录不含内部信息，可以公开。公开台账白名单（`review/ledger/`）不管这里。实现：`scripts/markjin/approvals.py`；审计：`scripts/audit-approvals.py`（已接进 GitHub Actions `.github/workflows/audit-approvals.yml`，不接 pre-push）。

所有 bot 共用 GitHub 账号 `jinguomax`，脚本无法按账号区分写入方；写入方约束靠流程，脚本保证“只追加、可审计、内容绑定、严格 schema”。

> **现行规则以本节为准（整体验收 r1，2026-10-11）**：发布入口只有 `scripts/route.py --pr <编号>`（`route_pr`）；没有自动批准，所有稿件都要有效 Codex APPROVED，宏观、医疗、宗教、tongyi、信号卡另需王总 v2 批准；Codex 与王总批准都在当天 06:55（SGT）前，07:00 截止（更正稿除外）；route_pr 一律检查来源链接、不能关闭，打不开或没检查都 HOLD（网络问题重试一次）；路由不读 `low_risk`。下文各轮“rN 变更”是历史记录，与本节冲突的以本节和最新一轮为准。
>
> **整体验收 r2 起（王总定）**：`route_pr(repo, pr_number, date, card_type, *, site_repo=None)` 不收 `now`、`link_checker`——时间只用真实时钟，链接只用内置检查（测试里 monkeypatch `_real_now` / `_http_probe`）；CLI `--now` 只在 `--dry-run` 下可用，演练永远 `publishable=false`；免责声明逐字匹配（含句末标点）；更正日期须写在标题行（`# …` 行）；路由末次核对要求 PR 仍为 OPEN；front matter 的键不是字符串 → HOLD `E-ROUTE-FRONT-MATTER`。

## 威胁模型（协调决定 (c)，2026-10-10）

- 第 1 阶段只防误操作和 bot 绕过流程。**凡是要求防伪造的问题（共用账号、同一 OS 用户、记录来源无法证明），一律降级为 follow-up，指向 markjin-data#30（第 2 阶段用王总 Mac 上的密钥签名），审查时不判为 BLOCKER。**
- **信号卡和真实发信必须使用带 `quote_ref` 的 v2 王总批准记录**（见下文）；v1 记录只对日报类审查稿有效。

## 通用规则

- `content_sha256`：稿件文件原始字节的 SHA-256，64 位小写十六进制。稿件改动后哈希变化，旧记录自动失效。
- 每个 JSON 文件是一个对象，**键必须恰好是下表所列**；缺键、多键、`null`、类型不对、非法 JSON、UTF-8 解码失败 → 该类记录全部不采信（`E-ROUTE-RECORD-INVALID`）。
- 文件名（整体验收 r12/r13，与「整体验收 r12/r13 修复」两节一致）：Codex 与王总记录各有两种，文件名里的 sha 都必须与记录里的 `content_sha256` 相同：
  - 首日记录 `approvals/codex/<content_sha256>.json`、`approvals/wang/<content_sha256>.json`：首日发布只认这两份；
  - 顺延稿在可发布日 D（SGT）的重审 / 重新批准记录 `approvals/codex/<content_sha256>.<D>.json`、`approvals/wang/<content_sha256>.<D>.json`：顺延到 D 日只认这两份；文件名日期须是真实日期，且等于记录里 `reviewed_at`（Codex）/ `recorded_at`（王总）的 SGT 日期，否则判失败。
  - 写重审记录时**追加新的带日期文件**，绝不改写首日文件；同一 sha 同一日期只能有一份。
- **只追加**：`approvals/codex/`、`approvals/wang/` 下已有文件不得修改、删除、改名。route 读取时与 `audit-approvals.py` 都用 `git log --no-renames --diff-filter=MDT` 检查，发现任何一次 → `E-ROUTE-APPROVALS-REWRITTEN`，全部记录不采信。
- **英文稿 draft_id 写入检查**（Grok Bot 2026-10-17）：写 Codex 记录用 `scripts/write-codex-record.py`（`approvals.write_codex_record`）。英文稿（`--draft` 路径以 `.en.md` 结尾，或 `--lang en`）的 `draft_id` 必须以 `-en` 结尾，否则拒绝写入 `E-APPROVALS-EN-DRAFT-ID`；语言缺失或与路径矛盾也拒绝。只查新写入：已有记录不追溯，audit-approvals 不受影响。已知写错的 3 条（`6f3cf57b…`、`2e7da2ac…`、`b0264fec…`）按只追加规则保持原样，更正见 review/2026-10-16.md。
- 时间一律 ISO 8601 且带时区（如 `2026-10-10T06:30:00+08:00`）。

## Codex 审查记录：`approvals/codex/<content_sha256>.json`（顺延日 `<content_sha256>.<D>.json`）

写入方：审查与治理 bot。

| 键 | 类型 | 约束 |
|---|---|---|
| `content_sha256` | string | `^[0-9a-f]{64}$`，等于文件名 |
| `draft_id` | string | **r4 新增，必填**。被审稿件的 draft_id（见“稿件路径与 draft_id”），`^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$`；路由要求等于当前稿件，否则 `E-ROUTE-RECORD-MISMATCH` |
| `codex_session` | string | UUID，`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`（小写） |
| `verdict` | string | `"APPROVED"` 或 `"REJECTED"` |
| `log_path` | string | 仓库相对路径，`^[A-Za-z0-9._/-]{1,200}$`，不以 `/` 开头，不含 `..` 段 |
| `reviewed_at` | string | Codex 审查完成时间，ISO 8601 且必须带时区；须不晚于路由时间、不早于稿件日期（SGT）、不晚于可发布日 06:55（SGT），否则 `E-ROUTE-RECORD-EXPIRED` / `E-ROUTE-RECORD-LATE`；顺延稿须落在可发布日当天（前一日记录作废，r7） |
| `category` | string | **r7 新增，可选**。Codex 判定的类别：`"medical"` / `"religion"` / `"macro"`；任一 → 需王总批准。其他取值 → 记录非法 |

```json
{"content_sha256": "3b7c…(64 hex)", "draft_id": "daily-2026-10-10", "codex_session": "01a125bd-02b5-7df2-9964-827ba9708316",
 "verdict": "APPROVED", "log_path": "review/codex/2026-10-10-d01.log",
 "reviewed_at": "2026-10-10T06:20:00+08:00"}
```

## 王总批准记录：`approvals/wang/<content_sha256>.json`

写入方：协调 bot（转达王总本人原话）。字段与站点门禁的 `wang_approval` 一致（以 `content_sha256` 代替 `head_sha`）。
**只有王总本人的原话、由协调 bot 回传写入的记录才有效；任何 bot 自己生成的“批准”无效。**

| 键 | 类型 | 约束 |
|---|---|---|
| `content_sha256` | string | `^[0-9a-f]{64}$`，等于文件名 |
| `recorded_at` | string | ISO 8601 带时区；**当天有效**：须 `≤ 当前时间`，且换算到 Asia/Singapore 后与当前时间是同一日历日，否则 `E-ROUTE-RECORD-EXPIRED` |
| `channel` | string（类型严格检查，非字符串 → 记录非法） | `"direct"`（王总在生产 bot 对话中直接确认）或 `"via-grok-bot"`（经协调 bot 转达）；信号卡只接受 `"direct"` |
| `quote` | string | 王总原话，去空白后非空 |

```json
{"content_sha256": "3b7c…(64 hex)", "recorded_at": "2026-10-10T06:40:00+08:00",
 "channel": "via-grok-bot", "quote": "同意发布"}
```

### v2（信号卡与真实发信必需）

在 v1 的四个键之外**恰好**再加三个键（r4 起 `draft_id` 必填）：

| 键 | 类型 | 约束 |
|---|---|---|
| `schema_version` | int | 恒为 `2` |
| `draft_id` | string | **r4 新增**。被批准稿件的 draft_id，须等于当前稿件，否则 `E-ROUTE-RECORD-MISMATCH` |
| `quote_ref` | string | 指向王总原话所在消息的引用，`^[A-Za-z0-9._:/#@-]{1,200}$`（如 `coord-bot:msg/12345`） |

```json
{"schema_version": 2, "content_sha256": "3b7c…(64 hex)", "draft_id": "cards-2026-10-11-c03", "recorded_at": "2026-10-11T06:40:00+08:00",
 "channel": "direct", "quote": "同意发布", "quote_ref": "coord-bot:msg/12345"}
```

信号卡用 v1 记录 → `E-ROUTE-RECORD-V2-REQUIRED`；信号卡另需 `channel == "direct"`。真实发信（newsletter）当前不经 route，接入时同样必须要求 v2。

## 批准判定

APPROVED 需要同一 `content_sha256` 的 Codex 记录 `verdict == "APPROVED"`；**需要王总批准的稿件**（宏观 `macro-*`、tongyi、信号卡 `cards-*`，以及标为中医/佛学即 `flags.medical`/`flags.religion` 或宏观 `flags.macro` 的稿件）还须有合规、当天（Asia/Singapore 日历日）的王总记录。普通日报（含中英配对）只需 Codex APPROVED（用户决定）。日报稿 `channel` 接受 `direct` 与 `via-grok-bot`；信号卡须 v2 且 `channel == "direct"`。
缺 Codex 记录或 `REJECTED` → `E-ROUTE-NO-CODEX`；缺王总记录（仅限需要王总批准的稿件）→ `E-ROUTE-NO-WANG`。

## 发布状态：`state/publish-state.json`

写入方：生产 bot。读不到或不合法 → 路由 `HOLD` + `E-ROUTE-STATE`。

| 键 | 类型 | 约束 |
|---|---|---|
| `version` | int | 恒为 `1` |
| `updated_at` | string | ISO 8601 带时区，`≤ 当前时间`。即 Mac 心跳时间。**心跳只对需要 Codex 审查的稿件生效**：超过 30 分钟未更新 → Mac 状态未知 → **一律 HOLD**（`E-ROUTE-MAC-STALE`，可重试，不归档）。（t161u 后已没有自动批准路径；不需要王总批准的日报一旦已有有效 Codex APPROVED，不再因心跳过期 HOLD） |
| `mac_online` | bool | 只有心跳新鲜（≤ 30 分钟）且明确为 `false` 时，需审查稿才按离线当天归档（`A-MAC-OFFLINE`）；不需要王总批准的日报已有有效 Codex APPROVED 时不受 `mac_online` 影响（t161u 后没有低风险稿） |
| `wang_present` | bool | |
| `codex_in_production` | bool | `true` → 需审查稿归档 `A-NO-REVIEW-PATH` |
| `drafts` | object | 键为 draft_id（`^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$`），值见下 |

`drafts.<draft_id>`：恰好 `status`（`"archived"`/`"deferred"`）、`reason`（archived 时为 `A-MAC-OFFLINE`/`A-NOT-APPROVED`/`A-OVERDUE-TWICE`/`A-NO-REVIEW-PATH`，deferred 时为 `I-DEFERRED`）、`at`（ISO 带时区）、`date`（`YYYY-MM-DD` 真实日期）、`content_sha256`（r4 新增，64 位小写 hex，该稿字节的 sha256）。
任一已归档条目的 `content_sha256` 等于当前稿件 → `ARCHIVED`（`E-ROUTE-ARCHIVED-REUSE`）：已归档稿改名（换 draft_id）也不能复活。
归档不可逆：历史中已归档条目被修改或删除 → `E-ROUTE-STATE`。Mac 离线（心跳新鲜且 `mac_online: false`）时需审查稿当天归档，不顺延。

初始文件模板（生产 bot 首次提交时使用）：

```json
{"version": 1, "updated_at": "2026-10-11T08:00:00+08:00", "mac_online": true, "wang_present": true,
 "codex_in_production": false, "drafts": {}}
```

## 稿件路径与 draft_id

稿件必须位于 markjin-data 仓库内 `<section>/<name>.md`（恰好两级目录）。`name` 只含小写字母、数字和连字符（`^[a-z0-9]+(?:-[a-z0-9]+)*$`），`section` 只含小写字母与数字（`^[a-z0-9]+$`，r11 起不得含 '-'），
**`draft_id = <section>-<name>`**，总长不超过 64 个字符。例：`daily/2026-10-11.md` → `daily-2026-10-11`，`digest/2026-10-10.md` → `digest-2026-10-10`，
`cards/2026-10-11-c03.md` → `cards-2026-10-11-c03`（协调决定：卡片统一 `cards-<name>`，与站点仓库实际路径 `content/cards/<name>.md` 一致：站点 `content/cards/<name>.md` ↔ data 侧 `cards/<name>.md` ↔ `cards-<name>`；`card_type=signal` 必须位于 `cards/`，`cards/` 下只能是 signal，否则 `E-ROUTE-DRAFT-PATH`）。不符合规则 → 路由 `HOLD` + `E-ROUTE-DRAFT-PATH`。`route.py` 从路径推出 draft_id，不接受手填。

## 状态写回接口

门禁（`scripts/route.py`）**本身不写任何文件**。需要改状态时，它在输出 JSON 的 `state_change` 字段给出一条变更；由生产 bot 应用到 `state/publish-state.json` 并提交。
Mac 心跳用同一接口。实现：`scripts/markjin/statechange.py`；命令行：`scripts/state-change.py`。

变更对象（键必须恰好如下）：

```json
{"schema": "markjin.state-change/v1", "kind": "draft", "draft_id": "daily-2026-10-11", "date": "2026-10-11",
 "content_sha256": "<64 hex>", "status": "archived", "reason": "A-MAC-OFFLINE", "at": "2026-10-11T10:05:00+08:00"}
```

```json
{"schema": "markjin.state-change/v1", "kind": "heartbeat", "mac_online": true, "updated_at": "2026-10-11T10:05:00+08:00"}
```

| kind | 何时产生 | 应用时改动的字段 | 拒绝条件 |
|---|---|---|---|
| `draft` | 路由结果为 `ARCHIVED`（新归档）或 `DEFERRED` | 只写 `drafts[draft_id] = {status, reason, at, date, content_sha256}` | 该稿已归档（`E-ROUTE-ARCHIVED-REUSE`）；已有条目时再顺延（只顺延一次）；`status`/`reason` 不配对（archived 配 `A-*`，deferred 配 `I-DEFERRED`） |
| `heartbeat` | 每次在王总 Mac 上跑完命令后 | 只改 `updated_at` 与 `mac_online` | `updated_at` 早于文件现有值（`E-STATE-CHANGE-STALE`）；`mac_online` 不是布尔 |

其余字段（`version`、`wang_present`、`codex_in_production`、其他 drafts）一律不动。格式不合法 → `E-STATE-CHANGE-INVALID`，文件不变。
`APPROVED`、`NEEDS_REVIEW`、`HOLD`、`REJECTED` 以及已归档稿再次路由时 `state_change` 为 `null`。

示例：

```sh
# 1) 路由，取出 state_change 并写回（生产 bot）
out=$(python3 scripts/route.py --pr <编号> --repo . --site-repo <站点仓库> --date 2026-10-11 --card-type daily)   # 只接受 PR 编号；链接检查不能关闭
change=$(printf '%s' "$out" | python3 -c 'import json,sys; c=json.load(sys.stdin)["state_change"]; print(json.dumps(c) if c else "")')
[ -n "$change" ] && python3 scripts/state-change.py apply --state state/publish-state.json --change "$change"

# 2) Mac 心跳：每次在王总 Mac 上跑完命令后执行，只改 updated_at（取当前时间）与 mac_online
python3 scripts/state-change.py heartbeat --state state/publish-state.json --mac-online true
git add state/publish-state.json && git commit -m "state: heartbeat" && git push
```


## 时限、ref 与解析规则（r3 审查后补充）

- **只读 main**（r13 起 CLI 已没有 `--ref`，批准与状态固定从 `origin/main` 读；以下为历史写法）：`load_from_ref` 对 `origin/main`、`main` 以外的 ref 一律返回无状态 → HOLD（`E-ROUTE-STATE`）。
- **审查截止 06:55（SGT）**：王总批准记录的 `recorded_at` 晚于当天 06:55 → `E-ROUTE-RECORD-LATE`，不采信。
- **可发布日**：普通稿 = 稿件日期；顺延稿 = 顺延记录 `date` 的次日。06:55 / 07:00 截止、王总记录的“当天”、Codex `reviewed_at` 的上限都按可发布日计算。
- **发布截止 07:00（SGT，协调决定）**：路由时已过可发布日 07:00 → `E-ROUTE-PUBLISH-LATE`；首次逾期一律顺延到次日（`DEFERRED`），顺延稿再次逾期 → `ARCHIVED`（仍缺有效批准 → `A-NOT-APPROVED`；已获批但未发布 → `A-OVERDUE-TWICE`）。顺延稿次日仍须有效 Codex APPROVED（及按类型要求的王总批准）才可发布（t161u：没有自动批准）；**前一天的 Codex 记录作废**，须有 `reviewed_at` 落在可发布日（SGT）当天的新记录，否则 `E-ROUTE-RECORD-EXPIRED`（整体验收 r7 HIGH，路线图第 89 行“顺延稿重新走当日审批路径”）。
- **approvals 读取失败**：`approvals/codex|wang` 只有在 ref 可读且该目录确实不存在时才视为“没有记录”；其他读取失败 → `E-ROUTE-STATE`（HOLD）。记录校验失败（非法、被改写、命中内部清单）→ 需审查稿 HOLD（不再当作“没有批准”继续走 NEEDS_REVIEW/顺延）。
- **顺延只在次日生效**：已顺延稿在同一 SGT 日（或更早）再路由 → HOLD（`E-ROUTE-DEFERRED-SAMEDAY`），不产生状态变更。
- **心跳与离线**（t161u 后）：没有自动批准路径。不需要王总批准的日报一旦已有有效 Codex APPROVED，不再因心跳过期或 `mac_online=false` HOLD/归档；需要王总批准的稿件照旧。状态文件本身不合规仍 HOLD，已归档仍不复活。
- **严格 JSON**：approvals 记录与状态文件出现重复键 → 拒绝；`version`、`schema_version` 必须是 JSON 整数（`1.0`、`true` 无效）。
- **git 失败不跳过**：历史审计中任何 git 子调用失败 → HOLD（`E-ROUTE-STATE`）；“文件不存在”用 `ls-tree` 判定，与 git 失败区分。
- **写回接口先校验旧状态**：`apply_change` 在旧 `state/publish-state.json` 不合规时拒绝（`E-ROUTE-STATE`），不借写回悄悄修复。

## r4 变更（生产 bot 需对齐）

1. Codex 记录新增必填键 `draft_id`。
2. 王总 v2 记录新增必填键 `draft_id`（v1 不变；v1 的稿件身份由同一 sha 的 Codex 记录绑定）。
3. `state/publish-state.json` 的 `drafts.<draft_id>` 条目新增必填键 `content_sha256`；`state_change`（kind=draft）本来就带 `content_sha256`，应用时现在写入条目。
4. 卡片 draft_id 前缀为 `cards-`（`cards/<name>.md`）。
5. 记录的 `quote`、`quote_ref`、`log_path`、`draft_id` 用本机内部清单扫描：命中 → 该类记录全部不采信（`E-ROUTE-RECORD-INTERNAL`）；清单读不到 → 不采信（`E-INTERNAL-LIST-MISSING`）。

## r5 变更（生产 bot 需对齐）

1. Codex 记录新增必填字段 `reviewed_at`（ISO 8601，带时区）：缺失或格式不对 → 记录非法；时间规则见上。
2. Wang 记录 `channel` 严格类型检查（必须是字符串且取值合法）。
3. 07:00 首次逾期一律顺延（含低风险稿）；顺延稿按次日计算全部截止时间。
4. approvals 目录读取失败 → HOLD（`E-ROUTE-STATE`）；记录校验失败 → 需审查稿 HOLD。
5. 卡片路径：站点 `content/cards/<name>.md`，draft_id `cards-<name>`。

## r6 变更（生产 bot 需对齐）

1. 低风险判定改为结构白名单（王总 10-11 定）：日报稿正文每个非空行只能是 固定栏目标题 / 原文直引 `> 「<原文>」 — `raw/…` · <URL>`（逐字核对为该条目原文连续子串）/ 来源链接 `来源：`raw/…` · <URL>`。其他任何块 → `R-STRUCTURE`，走 Codex；直引核对不通过 → `R-QUOTE-UNVERIFIED`。详见 `scripts/README.md`。
2. （历史，已被 t161u 取代）当时路由由 `compute_low_risk()` 重新计算 `low_risk`；现在路由**不读取** `low_risk`，见下文 t161u 一节。

## r7 变更（生产 bot 需对齐）

1. 路由顺序：输入/状态校验 → 已归档 → 顺延同日 HOLD → 内部命中 REJECTED → 自检 FAIL HOLD → **approvals 读取/校验错误 HOLD**（先于任何可发布出口）→ **未到可发布日 HOLD（`E-ROUTE-NOT-YET`）** → **需审查稿且心跳新鲜、`mac_online=false` → 当天 `ARCHIVED`（`A-MAC-OFFLINE`），优先于 07:00 顺延** → 07:00 逾期：首次顺延 / 顺延稿归档（其余情况一律顺延，含心跳过期）→ 心跳过期 HOLD → …（原“低风险 `AUTO_APPROVED`”一步已按 t161u 删除；日报 Codex 快通道见下文，排在 codex_in_production 检查之后）
2. 王总记录 `recorded_at` 不得早于 Codex 记录 `reviewed_at`（`E-ROUTE-RECORD-ORDER`）。
3. 自检：无来源的转述/判断段落是硬错误 `E-REPLAY-001`，即使有批准记录也 HOLD；直引里带判断词不算低风险；直引须为完整句或前后不紧邻否定/限定词；arXiv/X 直引按自身 id 字段（arXiv 含版本）精确选条目；counts 注释不得低风险；raw 符号链接拒绝（`E-REPLAY-SYMLINK`）。

## 第 8 轮补充（2026-10-11 02:32 / 02:34 决定）

- **tongyi 审查类型**：tongyi 系列稿件位于站点 `content/posts/tongyi/<name>.md`（data 侧 `tongyi/<name>.md`），`draft_id = tongyi-<name>`。这一类**永远不算低风险**（即使结构白名单通过），必须有 Codex APPROVED 记录，并取得王总 **v2、channel=direct** 的批准记录；批准**逐篇**：记录的 `content_sha256` 与 `draft_id` 都必须等于本篇，别篇的批准不能复用。v1 记录 → `E-ROUTE-RECORD-V2-REQUIRED`；via-grok-bot 或 draft_id 不符 → `E-ROUTE-RECORD-MISMATCH`。
- **顺延记录绑定**：`state/publish-state.json` 里 `deferred` 条目的 `content_sha256` 与 `date`（稿件原日期）必须等于当前稿件，否则 HOLD + `E-ROUTE-DEFER-MISMATCH`。顺延不能挪给改过的内容或别的日期，也不能借此绕过未来日期 HOLD。
- **无来源事实段落**：由 #20 的无来源块规则实现：不命中词表、也没有来源的普通段落，自检判 UNCLEAR（`E-INFER-UNCLEAR`），路由 HOLD（Mac 离线时归档），有批准记录也不得发布；含数字或推断 → FAIL（`E-REPLAY-001`）。

## 第 8 轮补充：二次逾期原因码（2026-10-11）

顺延稿在可发布日（顺延日次日，SGT）07:00 仍未发布时归档，原因码分两种：
- 需要审查、且此时仍没有有效批准记录 → `A-NOT-APPROVED`（同时带具体的批准缺失码）；
- 低风险稿，或已有有效批准记录却仍未在 07:00 前发布 → `A-OVERDUE-TWICE`（二次逾期）。

`state/publish-state.json` 的 archived `reason` 允许值相应加入 `A-OVERDUE-TWICE`；生产 bot 写回时按门禁输出原样写入。

## 日报时间表（2026-10-11 08:37 王总定，quote_ref grok-bot:t130u）

每天 07:00 发布（SGT）。门禁只用两个时间常量，定义在 `scripts/markjin/route.py`：

| 常量 | 时间 | 含义 |
|---|---|---|
| `CUTOFF` | 06:55 | Codex `reviewed_at` 与王总 `recorded_at` 的上限（晚于此时不采信） |
| `PUBLISH_DEADLINE` | 07:00 | 发布截止：需审查稿赶不上即首次顺延到次日；顺延稿再次逾期归档 |

成稿截止（06:30）只在站点侧定义，本门禁不使用。（t161u：没有自动批准，所有稿件都须 Codex APPROVED。）原 13:30 / 14:00 已全部改为 06:55 / 07:00。

## 双语稿（第 10 轮；出处 t141u、t145u，经 Grok Bot 转达）

- `R-TRANSLATION`：稿件含“译文：”行，或文件名为 `*.en.md`，一律不算低风险，须 Codex 审查。
- draft_id：`<section>/<name>.en.md` → `<section>-<name>-en`；`<name>-en.md` 会与之撞号，路径非法（E-ROUTE-DRAFT-PATH）。
- 一个 PR 只允许：单篇 `<name>.md`；或同一 section、同一 name 的 `<name>.md` + `<name>.en.md`。其他组合 `E-ROUTE-PR-FILES`；只有 `.en.md` 没有 `.md` → `E-ROUTE-PAIR-MISSING`。
- 配对稿各自一条 Codex 记录（各对应自己的 content_sha256 与 draft_id），新增可选字段 `pair_sha256` = 另一版的 content_sha256（64 位小写十六进制，不得等于自身）。两条必须互相引用、`reviewed_at` 完全相同、都 APPROVED；否则 `E-ROUTE-PAIR-MISMATCH` / `E-ROUTE-PAIR-INCOMPLETE`。单篇稿不得使用带 `pair_sha256` 的记录。
- 配对稿两版都须各自的 Codex APPROVED（t161u：没有自动批准）。两版必须一起发布：`route.route_pr` 中任一版不可发布，另一版改判 HOLD `E-ROUTE-PAIR-INCOMPLETE`。
- 王总批准记录仍按各自 content_sha256 逐条存在。

## 第 11 轮补充（10-11 09:57 协调决定）

- **一律走 route_pr**（r12/r13）：发布入口 `scripts/route.py --pr <编号>`，只接受 PR 编号。`route.route_pr` 自己用 `gh pr view` 取 baseRefOid、headRefOid、state 与文件列表，PR 须为 open，取到的 head 须是 PR 当前 head；gh 的文件列表须与 `git diff --name-status --no-renames base...head` 完全一致。PR 中任何删除、改名、类型变更的文件一律 `ValueError(E-ROUTE-PR-FILES)`，CLI 输出 HOLD（退出码 1）。
- **自检结果绑定稿件**（r12）：私有的 `_decide_full()` 核对自检结果的 `content_sha256` 与稿件一致，不一致或缺失即 HOLD `E-ROUTE-INPUT`。
- **r13（王总 2026-10-11 定）**：`_decide_full()` 为私有函数，不对外调用；Codex 与王总记录只从 `origin/main` 的 `approvals/` 读取（调用方不能指定 ref），记录缺任一字段或格式不合 → HOLD `E-ROUTE-RECORD-INVALID`。稿件、`raw/` 与 `MANIFEST` 全部从 PR head 提交（`git archive`）读取，不读工作树。免责声明与其他检查先去掉 HTML 注释（含未闭合注释）与围栏代码块再判断。日报类稿件放在 `daily/` 或 `digest/` 都查固定免责声明，只对 2026-10-12 的稿件执行，更早的历史稿不追溯；2026-10-13 起改为只用站点页脚免责声明（见下条）。
- **日报免责声明**（r12；2026-10-16 王总／Grok Bot 修订）：
  - **2026-10-12 的日报**（含其更正稿）：`daily/`、`digest/` 下的稿件正文必须有单独成行的固定免责声明——中文稿「本文不含投资建议。」，英文稿（`.en.md`）"This article does not constitute investment advice."——缺失、改写或中英互换即 HOLD `E-ROUTE-DISCLAIMER-MISSING`。2026-10-12 之前的日报不查（历史稿不追溯）；更早日期的日报类更正稿仍按原规则查正文免责声明。
  - **2026-10-13 起的日报**（含其更正稿，按稿件日期判断）：**只用站点页脚免责声明**（i18n `footer_disclaimer`：中「本站内容不构成投资建议。」／英 "Content on this site does not constitute investment advice."），由站点 smoke（site #56 起，`smoke_check.py` 页脚规则）检查。正文**不得**再加免责声明；`route_pr` 对这些稿件不再报 `E-ROUTE-DISCLAIMER-MISSING`；审查员（Codex 或人工）**不得**因正文没有免责声明判 BLOCKER 或任何严重度问题。
- **关于页链接不算触碰内核**（Grok Bot 2026-10-16 约 06:41、约 07:07）：日报链接到公开关于页（`/about/`、`/en/about/`）上的定位与概括定义（如「统一系统观是什么，见关于页」）**不算**触碰或展开内核，审查员不得因此判 BLOCKER。BLOCKER 只针对：在公开稿件中展开私有内核内容，或链接、引用私有材料（如 `/workspace/markjin-core/` 一类本机私有路径）。
- **王总记录只收 v2**（r12）：需要王总批准的稿件（宏观、医疗、宗教、tongyi、信号卡）只接受绑定 `draft_id` 的 v2 记录；v1 记录一律 `E-ROUTE-RECORD-V2-REQUIRED`。
- **快通道顺序**（r12）：日报 Codex 快通道排在 `codex_in_production`（`A-NO-REVIEW-PATH`）检查之后。
- **section 不得含 '-'**：`<section>` 只允许小写字母与数字（`^[a-z0-9]+$`），name 规则不变；draft_id 仍为 `<section>-<name>`（分隔符不变）。因此 `a-b/c.md` 非法（E-ROUTE-DRAFT-PATH），`a/b-c.md` → `a-b-c`，不会碰撞。现有 section（daily、digest、cards、tongyi）都不含 '-'，生产 bot 无需改 draft_id 格式。

## 取消低风险自动批准（王总 t161u，经 Grok Bot 转达，2026-10-11）

王总原话：「1、行；2、按新写法，每天过codex」。口径：所有稿件都须 Codex APPROVED；宏观、tongyi、信号卡另须王总批准（日报只要 Codex）。中医/佛学稿另须王总批准一条是 bot 补写，**待王总确认**，确认前从严临时执行。

- 王总定：日报一律按新写法写，**每天都要过 Codex**，取消低风险自动批准。
- （历史：原 `route._decide`，现为 `route_pr` 内部的 `_diagnose_from_git` / `_diagnose`）AUTO_APPROVED 路径已取消：任何稿件（日报、卡片、tongyi、中英配对稿）没有有效的 Codex APPROVED 记录（及按类型要求的王总批准记录）就不得发布；不再产生 `AUTO_APPROVED` / `I-AUTO-APPROVED`。
- selfcheck 的 `low_risk` 与 `R-*` 保留，只作审查参考；路由不再读取。
- （当时的写法，**已被下文“日报 Codex 快通道”与决定 52 修订**：普通日报已有有效 Codex APPROVED 时不受心跳与离线影响）心跳与离线规则因此对所有稿件生效：心跳过期 → HOLD（E-ROUTE-MAC-STALE，可重试）；心跳新鲜且 mac_online=false → 当天归档（A-MAC-OFFLINE），优先于 07:00 顺延。顺延稿二次逾期：仍缺有效批准 → A-NOT-APPROVED；已获批但未发布 → A-OVERDUE-TWICE。
- 保留：硬拦（E-BLOCK-*）、一律走 route_pr、section 不含 '-'、中英配对规则（t145u）、R-TRANSLATION（t141u）。

## 日报只需 Codex；王总在场只对需王总批准的稿件生效（第 12 轮，用户决定）

- `route.needs_wang(draft, card_type, flags)`：宏观（`macro-*` 或 `flags.macro`）、tongyi（`tongyi-*`）、信号卡（`card_type == "signal"` / `cards-*`）、中医/佛学（`flags.medical` / `flags.religion`；bot 补写，**待王总确认**，从严临时执行）→ 需要王总批准，走严格路径。
- 普通日报已有有效 Codex APPROVED（06:55 前、绑定内容与配对、自检 PASS）且未过 07:00 → 直接 `APPROVED`，**不因 Mac 离线（A-MAC-OFFLINE）、心跳过期（E-ROUTE-MAC-STALE）或王总不在场而 HOLD/归档**；没有有效 Codex APPROVED 时，心跳与离线规则照旧。
- 普通日报（含 zh+en 配对）：Codex APPROVED（配对规则照旧）即 `APPROVED`，不读王总记录，**不看 `wang_present`**；06:55 前未获 Codex 批准 → `NEEDS_REVIEW`，不因王总缺席顺延。
- 需王总批准的稿件：仍需王总记录；未获批且王总不在场（`wang_present=false`）→ 顺延（顺延稿 → 归档）。
- 顺延（路线图 v1.8）只用两个截止：06:55（批准）与 07:00（发布）。“06:25 仍无 PR”不是顺延条件，门禁不读取也不实现该规则（测试 `R12Rollover` 断言 06:25 无 PR 不触发顺延、模块内只有这两个时间常量）。

## 更正稿 correction（Grok Bot 定，2026-10-11）

规则原文（经 Grok Bot 转达）：更正稿只要 Codex 批准就可以发布，不受当天 07:00 的限制，页面上要注明更正日期。

- **识别**：front matter 同时有 `corrects: <原 draft_id>` 与 `corrected_at: <SGT 日期 YYYY-MM-DD>`；只有一项或为空 → HOLD `E-ROUTE-CORRECTION-INVALID`。两字段须是精确格式，selfcheck 才不把它们当断言。
- **防误用**：
  - `corrects` 必须等于本稿 draft_id（与原稿 section、name 一致）。**“已发布”的凭据（王总 r15 定）：站点仓库 origin/main 上确实有这篇**——按 section、name 映射到站点 `content/posts/<section>/<name>[.en].md`，用 `git show origin/main:<路径>` 查；本地站点 origin/main 须等于远端当前 main；查不到、没给站点仓库（CLI `--site-repo`）或内容未变 → `E-ROUTE-CORRECTION-TARGET`。不用发布状态里的记录，不重跑自检。
  - 原稿的日期和类别取站点 main 上那一版的 front matter 和路径：front matter 无合法 `date` → `E-ROUTE-CORRECTION-TARGET`；`date` 须等于 `--date`；路径 section 为 macro / tongyi / cards，或 front matter 的 categories / tags / type / series 含宏观、医疗、中医、佛学、宗教、tongyi、信号卡等 → 仍须王总批准（v2 记录）。本稿自检命中宏观/医疗/宗教同样须王总批准。
  - `corrected_at` 不早于原稿日期、不晚于实际发布当天（SGT）→ 否则 `E-ROUTE-CORRECTION-DATE`；Codex `reviewed_at` 不得早于 `corrected_at`。
  - **更正区格式（站点 Issue #71，Grok Bot 2026-10-18 批准）**：每页一个「## 更正」（英文稿 `## Corrections`）标题，下面每次更正一行「`**YYYY-MM-DD**：说明`」（英文 `**YYYY-MM-DD**: …`，半角冒号加空格），按日期升序，其他行（如 2026-10-12 日报的正文免责声明）可以跟在后面。判定：只认渲染后可见的 Markdown 行（注释、代码块、隐藏元素里的不算；块级 HTML 元素如 `<div>`、`<ul>`、`<table>` 里的，以及以行首 HTML 标签开头、到下一个空行为止的 HTML 块里的同形标题与条目也不算；缩进代码块里的日期示例不算条目）；全页（不分语言）恰好一个该标题，二级、文字完全一致，且是本稿语言的那个（中文稿「更正」、英文稿 "Corrections"）；不得同时有旧格式带日期的更正标题；更正区（到下一个标题为止，ATX 或 Setext 标题都算；列表项、引用、缩进代码后的 `---` 是分隔线，不算标题）里形如日期条目的行（可带列表、引用、任务列表前缀；加粗的年月日或年月后紧跟冒号或行尾，或不加粗的年月日或年月后紧跟冒号）都须是本语言的合法条目（中文全角冒号，英文半角冒号加空格）、日期真实；「**2026-10-18**以来，…」之类叙述不算；条目按日期升序，且有日期等于 `corrected_at` 的条目 → 否则 `E-ROUTE-CORRECTION-NOTE`。页面里出现了新格式标题就按新格式判，不能与旧格式混用。
  - **规范写法（失败关闭，王总 / Grok Bot 2026-10-18 定）**：新格式更正区只接受规范写法——标题行原文正好是「`## 更正`」/「`## Corrections`」（二级 #，单独一行，不加尾部 #、HTML 或其他符号）；标题前必须空一行（或为正文第一行），紧挨着的上一段不能有以 HTML 标签或注释开头的行；更正区（到下一个 # 标题为止）内不得有 HTML 标签或注释、缩进代码（4 空格或 Tab 开头的行）、Setext 标题（文字行下直接接 `===` 或 `---`）或单独的 `===` 行（分隔线 `---` 前须空一行）。全页任何位置，包括隐藏块，只要出现第二个更正标题行，就算不合规范，按失败关闭拦下（Grok Bot 2026-10-18 定，PR #52 r12）；这里的隐藏块指被 `hidden`、`aria-hidden`、`style`、`<details>`、`<template>` 等 HTML 元素包住的内容，HTML 注释和代码块（围栏或缩进）里的文字是注释或代码示例，不算标题行。不合规范一律 `E-ROUTE-CORRECTION-NOTE`，站点检查结果的 `hints` 列出具体行号和改写方法；这些写法不再做精确的 Markdown 解析（例如紧贴 HTML 块的标题、HTML 块与注释或代码块交错、列表后直接接 `---` 等），合规范却被拒才算缺陷。改写方法：正文末尾空一行写「`## 更正`」，再空一行，每次更正顶格一行「`**YYYY-MM-DD**：说明`」，按日期升序，其后如需免责声明等文字，空一行后用普通段落。已发布页面不合规范的只报告，由站点 PR 另行改写。实现：`route.correction_format_problems`。
  - **过渡期旧格式仍接受**：没有新格式标题时，须有渲染后可见的旧格式更正标题（`## 更正 YYYY-MM-DD…` / `## Correction YYYY-MM-DD…`，标题级别不限），其日期等于 `corrected_at`（链接目标、图片、HTML 属性里的日期不算；「## 数据截至 2026-10-17」之类带日期的其他标题不算；整体验收 r2/r3，PR #52 r3） → 否则 `E-ROUTE-CORRECTION-NOTE`。实现：`route.correction_heading_ok`（route_pr 与站点页面检查共用）。
  - 免责声明（日报类更正稿：原稿日期早于 2026-10-13 的都查正文免责声明；2026-10-13 起只用站点页脚，不查正文）、自检、配对审查、`codex_in_production` 照常；只跳过 06:55 / 07:00 的截止与顺延（以及 Mac 心跳/在岗检查）。`codex_in_production` 为真时只 HOLD（`E-ROUTE-CORRECTION` + `A-NO-REVIEW-PATH`），不归档已发布的原稿。
  - 获批 → `APPROVED` + `I-CORRECTION`；未获批 → `NEEDS_REVIEW`，不顺延、不归档。
- markjin-data #31（10-10 更正稿）由 Grok Bot 破例处理，不等本脚本。

## r14（r13 审查后的修复）

- 免责声明与更正日期只在正文认：front matter 先剔除（r13 H-1）。
- 日期命名的 daily/digest 稿，路径日期必须等于 `--date`，否则 HOLD `E-ROUTE-INPUT`（r13 H-4）。
- 路由结束时再取一次 PR，head/base 变化即失败；输出带 `head_sha`，发布端须按该提交取字节（r13 H-2）。
- CLI 的 `--now` 只允许与实际时钟相差 5 分钟以内（r13 H-5）。
- 批准记录必须是 `load_from_ref` 从 `origin/main` 读出的对象（带来源），内存构造的 dict 或其他 ref → HOLD `E-ROUTE-RECORD-SOURCE`（r13 BLOCKER）。
- 路由前用 `git ls-remote` 核对本地 `origin/main` 等于远端当前 main，不一致即失败（r13 H-3）。

## r15（王总定，2026-10-11）

- 批准记录与状态不接受任何内存里传进来的对象：发布入口 `_decide_full(sc, draft, repo, now, …)` 只在函数内部用 `load_from_ref(repo, origin/main)`（git show origin/main:approvals/…、state/publish-state.json）读取；规则求值 `_evaluate` 是供它和单元测试使用的纯函数，不是发布入口。
- 只允许已知栏目 daily、digest、macro、tongyi、cards；其他栏目一律 HOLD `E-ROUTE-DRAFT-PATH`。
- 时间：`route_pr` 与 CLI 都取传入时间与实际时钟中较晚者，`--now` 的容差不能跨过 06:55 / 07:00 回拨。
- 更正稿“已发布”凭据与原稿日期、类别，见上文“更正稿 correction”。

## r16（王总定，2026-10-11，修 r15 的 2 条 BLOCKER 和 1 条 HIGH）

- 生产代码里不再有能凭内存记录给出 `publishable=True` 的函数：规则求值 `_diagnose` 只给诊断（state、codes），`publishable` 只在唯一发布入口 `_decide_full` 里设置，而且只对它自己从 origin/main 读到的记录求值后设置。测试用的组合函数放在 `tests/helpers.py`（`evaluate_for_tests`），生产代码不导入。
- front matter 用 `yaml.safe_load` 解析（依赖 PyYAML）。categories、tags 等支持多行列表、行内列表和标量写法。解析失败或顶层不是映射的，稿件 HOLD `E-ROUTE-FRONT-MATTER`；更正稿的原稿解析失败则判 `E-ROUTE-CORRECTION-TARGET`。
- 更正稿原稿的类别按最严处理：只有 daily、digest 栏目，并且 categories / category / tags / type / series 的每个值都在日报标签表（daily、digest、日报、每日信号、摘要、daily signals）里时，才不需要王总批准。其他情况（命中宏观、医疗、宗教等标签，有识别不出的标签，或值是映射、嵌套这类结构）一律须王总批准。
- 站点仓库只接受 origin remote 为 `markjin-lab/markjin-lab.github.io`（GitHub 的 https 或 ssh 写法）的。脚本先 `git fetch origin main`，再要求本地 origin/main 等于 `git ls-remote` 给出的远端 main，然后才在 origin/main 上查原稿。自建仓库或其他 remote 一律 `E-ROUTE-CORRECTION-TARGET`。

## r17（王总定，2026-10-11，修 r16 的 2 条 BLOCKER）

- 发布入口只有 `route_pr`。原 `_decide_full` 改名为 `_diagnose_from_git`，只给诊断和状态变更，不设 `publishable`。`route_pr` 在确认 PR head 没变之后，才对它自己取到的稿件设置 `publishable`。README 已写明：直接 import 内部函数得到的结果不算发布依据；有意绕过按威胁模型 (c) 记 FOLLOW-UP，归 #30。
- 原稿的 categories / category / tags / type / series 只要字段存在，值为 null、空列表、空串或无法解释，一律须王总批准。
- YAML 有重复键就判失败：本稿 `E-ROUTE-FRONT-MATTER`，原稿 `E-ROUTE-CORRECTION-TARGET`。

## 整体验收 r1 修复（王总定，2026-10-11）

- **链接检查（HIGH 2，做法一）**：`route_pr` 一律检查已通过回放的来源链接，不能关闭。`link_checker=None` 时用内置 HTTP 检查（先 HEAD，不行再 GET，状态码 < 400 算能打开）。网络问题（异常、超时、DNS）重试一次，仍不通判 HOLD `E-ROUTE-LINK-UNREACHABLE`；HTTP 错误码不重试，直接 HOLD。没检查判 HOLD `E-ROUTE-LINK-UNCHECKED`。`detail` 写明每个 URL 和原因。REJECTED、ARCHIVED 的结论不被覆盖。CLI 的 `--no-link-check` 已取消，传入即 HOLD `E-ROUTE-INPUT`。
- **信号卡更正稿**：站点原稿路径为 `content/cards/<name>[.en].md`，其他栏目为 `content/posts/<section>/<name>[.en].md`。
- 测试：补了更正稿经 `route_pr` 的端到端测试（规范 remote 之外的仓库判失败、原稿未发布判失败），以及 Codex 审查时间恰为 06:55:00 可发布、06:55:01 不可发布的边界测试。


## 结论有效期与发布前再确认（r6/r7，协调方 Grok Bot 定）

- `route_pr` 的可发布结论**只在 60 秒内有效**（`route.VALIDITY`）。输出带 `decided_at`（判定时间，SGT）、`valid_until`（= decided_at + 60 秒）与 `head_sha`（所判定的 PR head）。
- 判定方式：第一遍按开始时间、第二遍按结束时的真实时间 `end` 各算一遍，两遍结论（state、codes）必须相同；开始到 `end` 之间跨过 06:55 / 07:00 / SGT 午夜 → 整批 `E-ROUTE-RETRY`（06:55 前开始的路由按原有规则处理）。`decided_at = end`，**先记下判定时间，再做外部核对**：PR（仍为 OPEN、base/head 未变）与远端 main（`git ls-remote` 等于路由开始时的值）；有任何变化 → 整批 HOLD（`E-ROUTE-PR-FILES` / `E-ROUTE-RETRY`）。r7 起不再按 `end + 120 秒` 做第三遍，截止仍是 07:00。
- **生产 bot 必须在 `valid_until` 之前发布**（可用 `route.still_valid(decision)` 判断），发布前用 `gh pr merge <PR> --match-head-commit <head_sha>`（或等价的 head 比对）再确认一次 head 与 PR 状态；超时、head 不符或 PR 已非 OPEN → 不发布，重新路由。
- 因为外部核对都在 `decided_at` 之后，**decided_at 之后到实际发布之间的空档**（有效期内心跳过期、PR/记录/状态的并发变化等，由 60 秒有效期与 `--match-head-commit` 收口）**记为 FOLLOW-UP，不算 BLOCKER**。审查提示的分级规则同此（68A）。

## 整体验收 r7 修复（王总定，2026-10-11）

1. **稿件 PR 准入（B4）**：稿件 PR 只能改稿件本身（`<section>/<name>.md`）以及白名单数据与证据文件（`raw/<YYYY-MM-DD>/` 下的文件，含 `MANIFEST.sha256`）。只要碰到规则、代码、路线图、模板或配置（`scripts/`、`docs/`、`review/`、`approvals/`、`state/`、`tests/`、`layouts/`、`.github/`、词表、根目录文件等任何其他路径），`route_pr` 对 PR 内全部稿件给 `HOLD` + `E-ROUTE-PR-SCOPE`，不可发布；这些改动单独走 PR。批准记录与发布状态也必须先由各自的 PR 进入 main，不能夹在稿件 PR 里。
2. **医疗类从严**：词表补常见简称与英文（TCM、herbal、acupuncture、qigong、针灸、方剂、中成药…）；兜底：front matter 分类键（categories / tags / section / type / topics…）含医疗、中医、health、medicine 等标记，或稿件路径在医疗栏目（medical/、health/、tcm/、zhongyi/…）下，一律按医疗类处理 → 需王总批准。**脚本只拦已知的词和标记，其余由 Codex 判**；Codex 判为医疗类时在审查记录里写可选字段 `"category": "medical"`（取值 medical / religion / macro），路由据此要求王总批准。
3. **pre-push**：只有当次推送的目标远端 URL 就是 markjin-lab/markjin-data、且远端 main 等于本地基线时，才只扫新增提交；其他情况一律全量扫描（见 review/README.md）。
4. **顺延稿**：顺延到第二天后，前一天的 Codex 记录作废，须按可发布日重新取得 Codex 记录（`reviewed_at` 在可发布日当天、06:55 前）。

## 整体验收 r8 修复（王总定，2026-10-11）

1. front matter 分类统一按 `yaml.safe_load` 解析结果判定；出现 YAML 锚点、别名、合并键或解析失败 → `E-SELFCHECK-FM-ALIAS`（硬错误）并按医疗类处理（fail-closed）。
2. **中英配对稿取两版审批类型的并集（从严）**：只要有一版需要王总批准，两版都按需王总批准重判，**各自**都必须有绑定自身 `content_sha256` 的王总 v2 记录；不采用“一条绑定 pair_sha256 的记录覆盖两版”的方式。
3. pre-push：只有目标远端是 markjin-lab/markjin-data 且远端 main 等于基线时才只扫增量；新分支、已有分支都一样，其他情况一律全量扫描。
4. 英文 allocation / weight / exposure 比例句：同一句出现资产或仓位词才算仓位。路由可见文本的代码围栏与台账同一口径（闭围栏同字符、长度不小于开围栏）。

## 整体验收 r9 修复
- **BLOCKER（王总定）**：front matter 用 YAML 解析出的类别全部参与审批类型判定（`route.labels_need_wang`，本稿与更正原稿共用）。categories / category / tags / type / series / section / topics 等里出现 macro、religion、medical、tongyi、card、信号卡等需王总批准的类别 → 按对应类型处理、须王总批准；未知类别、null、空列表照旧须王总批准。最终审批类型 = 路径（栏目）∪ categories ∪ 正文词表（selfcheck 标记）∪ Codex category。
- **MEDIUM**：`state-change.py` 读取状态文件与变更 JSON 时遇重复键判 `E-STATE-CHANGE-INVALID`，文件不改动。

## 整体验收 r10 修复

- **BLOCKER（分类键共用）**：front matter 分类键只在 `scripts/markjin/fmkeys.py:FM_CATEGORY_KEYS` 定义一次（categories、category、tags、tag、keywords、keyword、type、series、section、sections、topics、topic、kind、subject、subjects），selfcheck 与 `route.labels_need_wang` 共用同一对象。`keywords: [AI]` 这类未知类别因此同样须王总批准；中英配对稿取两版并集，两版须各有王总记录。
- **MEDIUM**：front matter 的 macro 类别先于整篇宏观判定置位，启用整篇宏观观点硬拦；PyYAML 写入 `requirements.txt`，缺失时 selfcheck 记 `E-DEP-PYYAML`、`route_pr` / CLI 给结构化 HOLD（`{"state": "HOLD", "codes": ["E-DEP-PYYAML"]}`，退出码 1），不抛 `ModuleNotFoundError`。

## 整体验收 r12 修复

### 顺延稿重审记录（王总定）

- **命名**：顺延稿在可发布日 D（SGT）重审的 Codex 记录写到 `approvals/codex/<content_sha256>.<YYYY-MM-DD>.json`，日期为 D。原来的 `approvals/codex/<content_sha256>.json` 保持不变。
- **读取**：首日发布只认 `<sha>.json`，其 `reviewed_at` 必须是当天（不早于稿件日期、不晚于当天 06:55 SGT）。顺延到 D 日时只认 `<sha>.<D>.json`，其 `reviewed_at` 也必须是 D 日；首日的 `<sha>.json` 与其他日期的文件一律不用（缺 → `E-ROUTE-NO-CODEX`）。
- **校验**：文件名日期须为真实日期并等于 `reviewed_at` 的 SGT 日期，否则整类记录判失败（`E-ROUTE-RECORD-INVALID`）。（r13 起王总目录也使用带日期文件，见下节。）
- **只追加**：两种文件都只追加、不改写（`git log --diff-filter=MDT` 检查，违反 → `E-ROUTE-APPROVALS-REWRITTEN`）。同一 sha 同一日期只能有一份；若出现重复，判失败（`E-ROUTE-RECORD-INVALID`）。
- **中英配对**：两版都用同一个 D 的 `<sha>.<D>.json`，`pair_sha256` 互相引用、`reviewed_at` 相同。
- 读取时记录在内存中附带 `_for_date`（文件名日期，无日期文件为 null），不属于记录 schema，不写入文件。

### 其他

- **可见性（BLOCKER）**：`route.visible_text` 先去注释与围栏代码块，再用 HTML 解析器（`html.parser`）按整篇正文追踪隐藏范围：hidden、aria-hidden="true"、style、class 属性的元素及 template/script/style/noscript 等不渲染元素，其整个子树（可跨多行）不算可见；未闭合的隐藏元素隐藏到文末。免责声明与更正标题日期只在可见文本里认。日报与更正稿均有经 `route_pr` 的测试。
- **数字核对范围**：只在被引用的那一条（arXiv/X 条目 id 及版本；FRED 按 series_id 绑定的单一系列文件）里核对。（FRED 已于 2026-10-18 停用，改从原始机构取数；FRED 部分为历史口径。）
- **check-public**：不带参数只查 HEAD 提交对象；全史审计用 `--rev`。
- 算式（第二段格式错误）与 FRED 重复键均补了经 `route_pr` 的测试。

## 整体验收 r13 修复

### 顺延稿王总重新批准记录（审查与治理 bot 定的技术方案，与 Codex 对称）

顺延到第二天要重新走当天审批是现有规则；本节只定重新批准的记录写在哪里。

- 顺延稿在 D 日的王总批准记录写到 `approvals/wang/<content_sha256>.<D>.json`。首日只认 `<sha>.json`，顺延后只认 `<sha>.<D>.json`（首日记录不复用，缺 → `E-ROUTE-NO-WANG`）。
- 文件名日期必须等于记录里 `recorded_at` 的 SGT 日期，否则 `E-ROUTE-RECORD-INVALID`。v2、`channel: direct`（信号卡、tongyi）、`quote`、`quote_ref` 的要求不变，当天 06:55 前、不早于当日 Codex 审查等时间规则也不变。
- 只追加（改写 → `E-ROUTE-APPROVALS-REWRITTEN`），同一 sha 同一日期不得重复（→ `E-ROUTE-RECORD-INVALID`）；中英配对稿两版用同一个 D。

### 审批类型取类别并集（BLOCKER）

`needs_wang` 用 `codex_categories()`：取该内容全部 Codex 记录（首日 `<sha>.json`、批准校验选中的当日 `<sha>.<D>.json`，以及其他日期文件）里 `category` 的并集，从严判定是否需要王总批准；不再取“最后一条”，防止当日判出的医疗 / 宗教 / 宏观类别被首日记录盖掉。经 route_pr 的测试：D+1 重审判医疗、无王总批准 → 不可发布。

### 数字核对范围

- FRED（历史口径：FRED 已于 2026-10-18 停用，改从原始机构取数，原始文件已按 `raw/2026-10-11/RETRACTIONS.md` 撤回）：断言写明观测日期（YYYY-MM-DD 或 YYYY-MM）时，只用该日期的观测值核对；同时带 `realtime_start`/`realtime_end` 的存档，断言写了 vintage 日期则只用该 vintage 内的观测。没写日期 → 不算“来源支持”（`R-SUPPORT-UNVERIFIED`）。
- 其他来源入口（带来源段落、非结构化行）调用 `check_pair` 时一律带上断言原文。

## 整体验收 r15 修复（审查与治理 bot 定的技术方案）

- **front matter 解析**：selfcheck 统一用 `yaml.safe_load` 解析 front matter，更正稿元数据（`corrects`、`corrected_at`）和日期字段都按解析后的值判断；`corrects: "x"`、`corrected_at: "2026-10-11"` 与不带引号等价。
- **tongyi 长文不套日报断言格式**：front matter `type: tongyi` 且路径为 `tongyi/<name>.md`（站点 `content/posts/tongyi/<name>.md`）的稿件及其更正稿，不跑日报专用的断言句式检查（`E-INFER-UNCLEAR`、`E-REPLAY-001`）。
  - 硬拦照旧：买卖建议、仓位、宏观观点、内部词表、免责声明、隐藏内容（可见文本判定）、X-only。真名靠本机内部词表（`E-BLOCK-INTERNAL`）拦，公开仓库不写真名。
  - 审批照旧从严：必须有 Codex APPROVED，并有王总 v2 `channel: direct` 单篇批准。
  - 豁免只看 `type` 与路径，两者必须一致；只有一方是 tongyi → `E-TONGYI-MISMATCH`（fail-closed，照常跑日报检查）。
  - 理由：长文由 Codex 加王总逐篇把关，日报句式检查对长文只产生误报。
- 测试使用合成样本：自检无 E 类错误；经 route_pr 缺王总记录 → 不可发布（`E-ROUTE-NO-WANG`），有 v2 direct 记录 → 可发布；日报把 type 写成 tongyi 而路径不对 → `E-TONGYI-MISMATCH` 失败。

## 站点 PR 页面检查（Grok Bot 2026-10-18）

`route_pr` 只看数据仓库顶层的 `daily/`、`digest/` 等稿件；站点 PR 直接改 `content/posts/`（或 `content/cards/`）页面时，更正规则原先没人检查。`scripts/check-site-corrections.py` 补上这一处，判断复用 route.py 的同一份逻辑（front matter 解析、日期解析、`correction_heading_ok` 更正区判定）。`--head/--base` 只读取仓库；`--pr` 会 fetch 并更新本地 Git 对象和引用，不改站点工作树或远端。需要本机 hugo（版本与站点部署一致）。

- 用法：`python3 scripts/check-site-corrections.py --site-repo <站点克隆> --pr <编号>`（origin 须为 `markjin-lab/markjin-lab.github.io`，fetch main 与 `refs/pull/N/head`），或 `--head <ref> [--base <ref>]`（默认 base `origin/main`）。输出 JSON，退出码 0 通过、1 不通过或输入无效（`E-SITE-INPUT`，含参数错误、读取失败、非 UTF-8 路径或内容、hugo 缺失或版本不符、构建失败）。
- 范围：`merge-base(base, head)..head` 中改动的 `content/posts/<section>/<name>[.en].md` 与 `content/cards/<name>[.en].md`；列表页（`_index.md`）、模板、配置、静态文件不查。改名按删除 + 新增处理。
- 新增页面（base 上没有）且不带更正字段：不查，新稿走日报流程。
- 删除或改名 base 上**已发布**的页面 → `E-SITE-PAGE-DELETED`。
- 改动 base 上**已发布**的页面（包括只改 front matter、空白、行尾）：除下文纯格式迁移例外和只改 `lastmod` 的例外，front matter 必须有 `corrects` 和 `corrected_at`，否则 `E-SITE-CORRECTION-MISSING`；且须新增本次日期的更正条目（见下）。
- **只改 `lastmod` 不算更正（Grok Bot 2026-10-18 定）**：正文逐字节相同、front matter 原文去掉顶层 `lastmod:` 单行后逐字节相同时，不要求更正字段和条目。只豁免这一项：`lastmod` 加任何其他字节改动仍须新增更正条目；`lastmod2`、`lastmodified`、嵌套在其他字段下的 `lastmod`、带引号的键、正文里的 `lastmod` 字样都不豁免。不要求 `corrected_at` 等于当天；脚本只证明新增了条目，条目日期与实际改动是否相符由审稿人核对。实现：`sitecheck.lastmod_only`。
- “已发布”按 Hugo 判定（PR #52 r1）：把 merge-base 与 head 各自导出（`git archive`，不动工作树），用站点部署所用版本的 Hugo（按 YAML 解析 merge-base 上站点 `.github/workflows/hugo.yml` 的 `jobs.build.env.HUGO_VERSION`（没有则取顶层 `env.HUGO_VERSION`，注释不算），两版都用它；工作流缺失、读不出版本、本机 hugo 版本不符，或 head 更改了部署 Hugo 版本（须另行验证版本升级）→ `E-SITE-INPUT`）以同一时钟（默认当前时间）构建；PR 里只要有任何文件改动就构建；`hugo list published` 里 kind=page、且构建输出里确有对应 HTML 的页面才算已发布。草稿、未来 `date`/`publishDate`、过期 `expiryDate`、`build.render: never` 以及 cascade 继承的同类设置都不算已发布。
- base 上未发布的页面（含首次发布前的草稿、未来稿）不带更正字段时不查；带了更正字段 → `E-ROUTE-CORRECTION-TARGET`。
- base 上已发布的页面在 head 上不再生成或 permalink 改变（例如加 `draft: true`、改 `url`；permalink 按完整 URL 比较，只改 `baseURL` 主机名也算），与删除同样判 `E-SITE-PAGE-DELETED`。比较覆盖 base 上全部已发布页面：只改栏目或根 `_index.md` 的 cascade、`hugo.toml`（如 permalinks）或模板而间接使页面消失的，也给该页面报 `E-SITE-PAGE-DELETED`（结果里 status 为 `indirect`）。
- 带更正字段的页面，规则与 route 的更正稿相同：
  - 缺一项、为空或不是字符串 → `E-ROUTE-CORRECTION-INVALID`；
  - `corrects` 必须等于由路径推出的 draft_id（`<section>-<name>[-en]`，卡片为 `cards-<name>[-en]`；`a-en.md` 这类推不出合法 draft_id 的路径不算），页面在 base 上已发布，且 base 版有合法 `date`，否则 → `E-ROUTE-CORRECTION-TARGET`；
  - `corrected_at` 不是 YYYY-MM-DD、早于页面日期、晚于今天（SGT）、早于 base 版已有的 `corrected_at`，或者 head 版 `date` 与 base 版不完全相同（同日改时间、改时区写法都算） → `E-ROUTE-CORRECTION-DATE`；
  - 更正区须符合上文「更正区格式」（新格式，或过渡期旧格式），否则 → `E-ROUTE-CORRECTION-NOTE`；
  - 再次更正：无论同日或跨日，写有本次 `corrected_at` 的更正次数必须比 base 版多（新格式页只数更正区里该日期的条目，其他带日期的标题不算；旧格式页取带该日期的旧格式更正标题数与更正说明行数中较大者，其他带日期的标题不算）；沿用旧条目或旧标题，或复用 base 上已预先写好的同日期条目 → `E-ROUTE-CORRECTION-NOTE`。纯格式迁移例外见下。
- **纯格式迁移例外（Grok Bot 2026-10-18，Issue #71）**：只把旧格式更正区改成新格式、不动其他内容的改动，不算新更正，不要求 `corrected_at` 变化或新增条目；只豁免这一条，迁移后的页面仍须通过 `corrects`/`corrected_at` 字段与新格式更正区的全部校验（一页一个本语言标题等）。脚本 `sitecheck.format_migration_only` 逐项核对，任何一项不满足就按普通更正处理（通常因同日未新增条目判 `E-ROUTE-CORRECTION-NOTE`）：
  - front matter 原文逐字节相同；
  - 旧版更正区：从第一条到最后一条旧格式更正行（`*更正说明（YYYY-MM-DD）：…*` / `*Correction note (YYYY-MM-DD): …*` 与 `## 更正 YYYY-MM-DD…` / `## Correction YYYY-MM-DD…` 标题），中间只能有这两种行和空行；新版更正区：唯一的 `## 更正` / `## Corrections` 标题及紧随其后的条目行和空行；两个更正区以外的正文逐字节相同；
  - 旧版每条更正说明的（日期, 说明文字）与新版条目一一对应、文字完全相同，新版条目按日期升序；某日期有更正说明行时，该日期的旧格式标题不多于说明行，旧标题如有通用句（「本次修订的具体内容见下方更正说明。」/ "The note below lists the changes in this revision."）以外的实质说明，须原样出现在同日期的更正说明里；某日期只有旧格式标题、没有说明行时，标题日期后的实质说明即该次更正的说明，须迁成同日期、同文字的条目（说明为空或只是通用句则不算迁移）；新旧更正区都只认渲染后可见的行（代码块、注释、隐藏元素里的不算）；
  - 页首一行的白名单：只允许在「`*本文于 <日期列表> 更正，说明见文末。*`」与「`*本文于 <日期列表> 更正，说明见文末「更正」。*`」之间互换，英文稿在「`… see the note(s) at the end.*`」与「`… see Corrections at the end.*`」之间互换；日期列表必须一字不差。只适用于第一个标题（ATX 或 Setext）之前唯一的那一行页首提示，正文里其他同形句不在白名单内。
- **人工运行（Grok Bot 2026-10-18 定，不接站点必需 CI）**：这个脚本不替代 `route_pr`、Codex 审查或站点 smoke；每个改动 `content/` 的站点 PR，审稿人必须运行它，并在审查记录里写明四项：脚本所在 markjin-data 提交 SHA、完整命令、站点 base/head SHA、完整 JSON 结果。缺任何一项不得批准该站点 PR。
