# data#26 历史标签存量回填 · 2026-11-08（新加坡时间）

对应 Issue：[markjin-data#26](https://github.com/markjin-lab/markjin-data/issues/26)（已关闭，本轮不重开、不改状态）。  
前件：[improve/2026-11-01-issue26-closure-rate.md](https://github.com/markjin-lab/markjin-data/blob/main/improve/2026-11-01-issue26-closure-rate.md)（11-01 已补齐两仓库标签定义，并给 data #24–#29 打上 `feedback` + `bot:反馈与改进`；当时计划本日完成存量回填）。  
互链：[improve/2026-11-08-issue29-traffic.md](https://github.com/markjin-lab/markjin-data/blob/main/improve/2026-11-08-issue29-traffic.md)。

核对：2026-11-08 约 18:10 SGT 用 `gh issue list --state all` 拉取两仓库 Issue（data 39 条、站点 91 条）及标签定义；约 18:10–18:14 SGT 用 `gh issue edit N --add-label` **只追加、不移除**已有标签。未打 `approved` / `rejected`。

---

## 一、口径

只在标题、正文、已有标签能清楚判断责任时补标，不猜测。

| 情形 | 本次做法 |
|---|---|
| 明显是反馈／改进／闭环率／发布率／流量诊断类 | 11-01 已处理 data #24–#29；本轮没有新发现需补 `feedback` 的卡片 |
| 已有 `proposal` 但缺 `bot:*` | 正文或标题写明单一负责 bot 时，只补对应 `bot:*` |
| 第 1 阶段任务卡或审查 follow-up 写明「负责：…」 | 只补对应 `bot:*`（不因此补 `proposal` / `feedback`） |
| 已有 `qa` 且标题或正文写明「负责：反馈与改进」或「负责：生产与发布」 | 只补对应 `bot:*`（`qa` 标签保留；不另打 `bot:审查与治理`） |
| 标题与正文责任冲突，或「会同／若…则归…」等条件分叉 | 跳过并记缺口 |
| `approved` / `rejected` | **不打**（只保留定义，由审查 bot 打） |

---

## 二、本日追加（76 个 Issue，全部成功）

### 2.1 markjin-data（12 个）

**`bot:审查与治理`（6）**

- [#22](https://github.com/markjin-lab/markjin-data/issues/22)、[#23](https://github.com/markjin-lab/markjin-data/issues/23)：标题与正文均写「负责：审查与治理」
- [#34](https://github.com/markjin-lab/markjin-data/issues/34)、[#35](https://github.com/markjin-lab/markjin-data/issues/35)、[#36](https://github.com/markjin-lab/markjin-data/issues/36)、[#37](https://github.com/markjin-lab/markjin-data/issues/37)：正文写「负责：审查与治理」

**`bot:生产与发布`（1）**

- [#30](https://github.com/markjin-lab/markjin-data/issues/30)：标题与正文写「负责：生产与发布」

**`bot:反馈与改进`（1）**

- [#81](https://github.com/markjin-lab/markjin-data/issues/81)：已有 `proposal` + `approved`；正文写「负责：反馈与改进 bot」。只追加 `bot:反馈与改进`，未改 `approved`

**`bot:采集`（4）**

- [#101](https://github.com/markjin-lab/markjin-data/issues/101)：正文写明依据是「致采集 bot」的书面裁定
- [#108](https://github.com/markjin-lab/markjin-data/issues/108)：已有 `proposal`；正文写「负责方是采集 bot」
- [#109](https://github.com/markjin-lab/markjin-data/issues/109)、[#110](https://github.com/markjin-lab/markjin-data/issues/110)：已有 `proposal`；同批周提案，正文写提案草稿来自采集 bot，并写「王总确认之前，不改采集脚本」

### 2.2 markjin-lab.github.io（64 个）

**`bot:反馈与改进`（11）**

- qa 且标题写「负责：反馈与改进」：[#7](https://github.com/markjin-lab/markjin-lab.github.io/issues/7)、[#8](https://github.com/markjin-lab/markjin-lab.github.io/issues/8)、[#9](https://github.com/markjin-lab/markjin-lab.github.io/issues/9)、[#10](https://github.com/markjin-lab/markjin-lab.github.io/issues/10)、[#92](https://github.com/markjin-lab/markjin-lab.github.io/issues/92)、[#109](https://github.com/markjin-lab/markjin-lab.github.io/issues/109)
- 正文写「负责：反馈与改进 bot」：[#77](https://github.com/markjin-lab/markjin-lab.github.io/issues/77)
- 已有 `proposal`，正文写「负责：反馈与改进 bot」：[#81](https://github.com/markjin-lab/markjin-lab.github.io/issues/81)、[#82](https://github.com/markjin-lab/markjin-lab.github.io/issues/82)、[#83](https://github.com/markjin-lab/markjin-lab.github.io/issues/83)、[#84](https://github.com/markjin-lab/markjin-lab.github.io/issues/84)

站点 [#165](https://github.com/markjin-lab/markjin-lab.github.io/issues/165) 此前已有 `proposal` + `bot:反馈与改进`，本轮未改。

**`bot:生产与发布`（53）**

- 第 1 阶段任务卡（标题与正文写「负责：生产与发布」）：[#41](https://github.com/markjin-lab/markjin-lab.github.io/issues/41)–[#44](https://github.com/markjin-lab/markjin-lab.github.io/issues/44)
- 正文写「部署流程归生产 bot 负责」：[#98](https://github.com/markjin-lab/markjin-lab.github.io/issues/98)
- 已有 `proposal`，正文写「建议改动（负责：生产与发布）」：[#163](https://github.com/markjin-lab/markjin-lab.github.io/issues/163)、[#164](https://github.com/markjin-lab/markjin-lab.github.io/issues/164)
- qa／正文写明「负责：生产与发布」（[#99](https://github.com/markjin-lab/markjin-lab.github.io/issues/99) 标题为「负责：生产与发布，会同审查」，只补了生产侧，未另打审查标签）：[#13](https://github.com/markjin-lab/markjin-lab.github.io/issues/13)–[#17](https://github.com/markjin-lab/markjin-lab.github.io/issues/17)、[#20](https://github.com/markjin-lab/markjin-lab.github.io/issues/20)、[#21](https://github.com/markjin-lab/markjin-lab.github.io/issues/21)、[#23](https://github.com/markjin-lab/markjin-lab.github.io/issues/23)、[#24](https://github.com/markjin-lab/markjin-lab.github.io/issues/24)、[#27](https://github.com/markjin-lab/markjin-lab.github.io/issues/27)、[#28](https://github.com/markjin-lab/markjin-lab.github.io/issues/28)、[#34](https://github.com/markjin-lab/markjin-lab.github.io/issues/34)、[#35](https://github.com/markjin-lab/markjin-lab.github.io/issues/35)、[#39](https://github.com/markjin-lab/markjin-lab.github.io/issues/39)、[#45](https://github.com/markjin-lab/markjin-lab.github.io/issues/45)、[#67](https://github.com/markjin-lab/markjin-lab.github.io/issues/67)–[#75](https://github.com/markjin-lab/markjin-lab.github.io/issues/75)、[#89](https://github.com/markjin-lab/markjin-lab.github.io/issues/89)–[#91](https://github.com/markjin-lab/markjin-lab.github.io/issues/91)、[#99](https://github.com/markjin-lab/markjin-lab.github.io/issues/99)、[#103](https://github.com/markjin-lab/markjin-lab.github.io/issues/103)、[#106](https://github.com/markjin-lab/markjin-lab.github.io/issues/106)–[#108](https://github.com/markjin-lab/markjin-lab.github.io/issues/108)、[#110](https://github.com/markjin-lab/markjin-lab.github.io/issues/110)、[#115](https://github.com/markjin-lab/markjin-lab.github.io/issues/115)、[#118](https://github.com/markjin-lab/markjin-lab.github.io/issues/118)、[#136](https://github.com/markjin-lab/markjin-lab.github.io/issues/136)、[#139](https://github.com/markjin-lab/markjin-lab.github.io/issues/139)、[#144](https://github.com/markjin-lab/markjin-lab.github.io/issues/144)、[#148](https://github.com/markjin-lab/markjin-lab.github.io/issues/148)、[#150](https://github.com/markjin-lab/markjin-lab.github.io/issues/150)、[#154](https://github.com/markjin-lab/markjin-lab.github.io/issues/154)、[#155](https://github.com/markjin-lab/markjin-lab.github.io/issues/155)、[#161](https://github.com/markjin-lab/markjin-lab.github.io/issues/161)、[#169](https://github.com/markjin-lab/markjin-lab.github.io/issues/169)、[#171](https://github.com/markjin-lab/markjin-lab.github.io/issues/171)、[#173](https://github.com/markjin-lab/markjin-lab.github.io/issues/173)

---

## 三、跳过（责任不清晰，未猜测）

### 3.1 markjin-data（19 个仍无 `bot:*`）

安全／校验／脚本类 follow-up，正文未写明单一负责 bot：[#10](https://github.com/markjin-lab/markjin-data/issues/10)、[#11](https://github.com/markjin-lab/markjin-data/issues/11)、[#16](https://github.com/markjin-lab/markjin-data/issues/16)、[#17](https://github.com/markjin-lab/markjin-data/issues/17)、[#18](https://github.com/markjin-lab/markjin-data/issues/18)、[#19](https://github.com/markjin-lab/markjin-data/issues/19)、[#32](https://github.com/markjin-lab/markjin-data/issues/32)、[#88](https://github.com/markjin-lab/markjin-data/issues/88)、[#92](https://github.com/markjin-lab/markjin-data/issues/92)、[#94](https://github.com/markjin-lab/markjin-data/issues/94)、[#96](https://github.com/markjin-lab/markjin-data/issues/96)、[#98](https://github.com/markjin-lab/markjin-data/issues/98)、[#99](https://github.com/markjin-lab/markjin-data/issues/99)、[#104](https://github.com/markjin-lab/markjin-data/issues/104)、[#112](https://github.com/markjin-lab/markjin-data/issues/112)、[#114](https://github.com/markjin-lab/markjin-data/issues/114)、[#123](https://github.com/markjin-lab/markjin-data/issues/123)。

已有 `proposal`、但未写单一负责 bot：

- [#131](https://github.com/markjin-lab/markjin-data/issues/131)（EIA 非现货试采；正文提到「由采集填执行清单」，但仍待王总勾选，未写成单一负责字段）
- [#132](https://github.com/markjin-lab/markjin-data/issues/132)（统计局发布页数字纳入公开 industry-data；跨越采集与公开写作）

### 3.2 markjin-lab.github.io（26 个仍无 `bot:*`）

正文未写明负责 bot 的跟进项：[#1](https://github.com/markjin-lab/markjin-lab.github.io/issues/1)、[#2](https://github.com/markjin-lab/markjin-lab.github.io/issues/2)、[#3](https://github.com/markjin-lab/markjin-lab.github.io/issues/3)、[#4](https://github.com/markjin-lab/markjin-lab.github.io/issues/4)、[#5](https://github.com/markjin-lab/markjin-lab.github.io/issues/5)、[#18](https://github.com/markjin-lab/markjin-lab.github.io/issues/18)、[#96](https://github.com/markjin-lab/markjin-lab.github.io/issues/96)、[#97](https://github.com/markjin-lab/markjin-lab.github.io/issues/97)、[#101](https://github.com/markjin-lab/markjin-lab.github.io/issues/101)、[#113](https://github.com/markjin-lab/markjin-lab.github.io/issues/113)、[#121](https://github.com/markjin-lab/markjin-lab.github.io/issues/121)、[#123](https://github.com/markjin-lab/markjin-lab.github.io/issues/123)、[#126](https://github.com/markjin-lab/markjin-lab.github.io/issues/126)、[#127](https://github.com/markjin-lab/markjin-lab.github.io/issues/127)。

已有 `qa`、未写负责：[#58](https://github.com/markjin-lab/markjin-lab.github.io/issues/58)、[#124](https://github.com/markjin-lab/markjin-lab.github.io/issues/124)、[#129](https://github.com/markjin-lab/markjin-lab.github.io/issues/129)。

条件分叉，未猜：[#137](https://github.com/markjin-lab/markjin-lab.github.io/issues/137)（正文写「负责：生产与发布（若由模板自动拼接前缀则归反馈与改进）」）。

标题与正文冲突，未猜：[#46](https://github.com/markjin-lab/markjin-lab.github.io/issues/46)–[#53](https://github.com/markjin-lab/markjin-lab.github.io/issues/53)（标题写「负责：Grok Bot 协调」，正文写「负责 bot：反馈与改进 bot（路线图维护）」）。

---

## 四、仍缺什么

1. 上列 19（data）+ 26（站点）个 Issue 仍无 `bot:*`。等标题／正文写清单一责任，或由对应 bot 自行补标后再回填。
2. `approved` / `rejected` 仍只保留定义，不由反馈 bot 打。本轮没有改动这两类已有标签。
3. 站点 #46–#53 需相关方统一「协调」与「反馈与改进（路线图）」口径后再标。
4. 11-01 完成的标签**定义**与 data #24–#29 的 `feedback` + `bot:反馈与改进` 保持不动。

对照 11-01「历史 Issue 标签回填计划于 2026-11-08 18:00 SGT 前分批完成」：责任清晰者已尽量补完；剩余均为故意跳过的不清晰项，不是漏打。本条完成标准仍受上述缺口限制，但是否把 #26 视为可接受的「部分完成」由 Grok Bot 判断——本 bot 不重开、不关闭该 Issue。
