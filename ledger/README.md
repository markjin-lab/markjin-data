# ledger/：分支台账

`branches.csv` 是分支台账：每个分支先有一条登记行，之后的对账和更正只追加新行。分支不只用于宏观：日报里的 AI、能源、太空、生物等条目，只要做了完整分类（写出全部后续分支和触发条件），都要登记，用 domain 列区分领域。
生产与发布 bot 在发布时登记；观测窗口到期后，审查与治理 bot 追加对账行。
字段和规则的基础是站点路线图 `docs/roadmap.md` 第六节“分支台账”和第十三节 13.1。**站点 #46–#53 对齐前以本 README 为准。** 以下扩展为协调 bot 已定（2026-10-12），路线图同步见站点 PR #38：
- domain 列；row_id 及其生成规则；classification_id；
- 判定分组：HIT 与互斥判定按 (draft_id, classification_id) 分组，每组至少 2 支，组成员在登记时固定；
- 登记更正、结论更正两类更正行；registered_at 不可改；
- 整库校验码 framework_sha256 与内核提交号 framework_commit；
- 门禁只算第一行；命中率口径见规则第 10 条；
- 按季读数行只允许 PENDING，读数严格追加；
- CI 逐提交检查只追加，并核对推送时间。
路线图中标为“bot 补写，待王总确认”的规则：写明“从严临时执行”的现在照做；写明“确认前不生效”的现在只登记，不据此判定。

稿件公开正文不写内部分类标签；分支和触发条件只进台账。
## 文件格式

- UTF-8，不带 BOM；逗号分隔，含逗号或引号的值按 CSV 规则用双引号括起；每行以换行结尾。
- 第一行是表头，列名和列序必须与 `scripts/markjin/branches.py` 的 HEADER 一致。目前文件里只有表头，没有示例行。
- `NA` 表示“本条不适用”。宏观专用字段（区间、按季、L/U）只在用到时才填，其余填 `NA` 或留空。
- 日期写 `YYYY-MM-DD`（SGT），时间写 `YYYY-MM-DDTHH:MM:SS+08:00`。

## 字段

**事先登记**：发布时写定，以后不改。

| 字段 | 含义 |
|---|---|
| row_id | 行标识，生成规则：`<draft_id>-<classification_id>-b<branch_order>-r<n>`，n 是这个分支在文件中的第几行（从 1 起，按文件顺序）。脚本按此规则复算 |
| corrects_row_id | 更正行填被更正行的 row_id（必须是同一分支、已经存在的行）；其他行留空 |
| reason | 更正理由，更正行必填；其他行留空 |
| draft_id | 稿件编号（小写字母、数字和连字符） |
| classification_id | 稿件内完成分类的条目编号，写 `c1`、`c2`……。一篇日报可以有多个条目，每个条目一个；一个分支由 draft_id + classification_id + branch_order 确定 |
| slug | 稿件的网址短名 |
| publish_date | 发布日期 |
| domain | 领域：`macro`（宏观）、`ai`、`energy`（能源）、`space`（太空）、`bio`（生物）、`other`（其他） |
| framework_version | 所用框架的版本号，如 `v2.4` |
| framework_sha256 | 内核校验码：登记时内核整库清单的 sha256（64 位小写十六进制），见下节 |
| framework_commit | 登记时内核的提交号（40 位小写十六进制） |
| observed_variable | 观测的变量 |
| unit | 单位 |
| data_source | 数据来源，如 FRED 序列号 |
| data_vintage | 取数规则，不是固定快照。宏观默认写“每季取到期核对日（SGT）最新发布的版本”；不适用填 `NA` |
| window_start / window_end | 观测窗口的起止日期；window_end 就是到期日。观测从 window_start 当日 00:00（SGT）开始，window_start 至少是 publish_date 的次日 |
| branch_order | 同一篇稿件内的分支序号，从 1 开始 |
| interval_low / interval_high | 区间型分支的下沿和上沿，留空表示无穷。按季读数型分支、没有数值区间的定性条件，四个区间字段一律填 `NA` |
| interval_low_closed / interval_high_closed | 端点是否包含在区间内，填 `true` 或 `false`；不适用填 `NA` |
| trigger_condition | 触发条件。区间型分支必须写成机器写法，与区间字段逐字一致：`L < x < U`、`L <= x < U`、`x < U`、`L <= x` 等（`<=` 表示端点闭），至少一端有限，脚本按区间字段复算比对；按季读数型和定性条件写文字 |
| n_quarters | 按季读数型分支需要连续观察的季度数 N。其他分支填 `NA` 或留空，下面四个按季字段同理 |
| window_quarters | 参与判定的 N 个季度，按时间顺序用英文分号分隔，如 `2026Q4;2027Q1` |
| lu_basis_date | 计算下沿 L、上沿 U 所依据的基准日期 |
| l_value / u_value | 所用下沿 L 和上沿 U 的数值 |
| lu_evidence | 计算 L 和 U 用到的每个读数，用英文分号分隔，每个写成 `季度:读数@vintage#raw 路径:sha256\|来源链接`，vintage 写 YYYY-MM-DD |
| registered_by / registered_at | 登记人（bot 名）和登记时间。registered_at 写完整时间 `YYYY-MM-DDTHH:MM:SS+08:00`，第一行的日期必须等于 publish_date，并且早于观测开始；登记后不可改 |

**到期对账**：window_end 之后由审查与治理 bot 填写。

| 字段 | 含义 |
|---|---|
| actual_value | 实际取值。区间型分支对账出 HIT、MISS、NONE_HIT、MULTI_HIT 时必须是数字；脚本按端点开闭算出它落在不在本支区间内，结果必须和 check_result、actual_branch 一致 |
| quarter_readings | 每个季度的读数，写成 `季度:读数@vintage#raw 路径:sha256`，用英文分号分隔，季度须在 window_quarters 内并按顺序（按季读数型分支） |
| actual_branch | 是否为实际发生的那一支，填 `是`、`否` 或留空 |
| check_result | 对账结果：`PENDING`（未到期）、`HIT`、`MISS`、`NONE_HIT`、`MULTI_HIT`、`TRIGGER_UNOBSERVABLE`、`DATA_UNAVAILABLE` |
| error_source | 错在哪一环，只能填 `采集`、`解读`、`框架`。有多个原因时用英文分号分隔，主因写在最前。只在对账结果为 NONE_HIT、MULTI_HIT 或 TRIGGER_UNOBSERVABLE 时填写 |
| checked_by / checked_at | 核对人和写入时间（完整时间戳）。对账行的 checked_at 必须晚于 window_end；按季读数行的 checked_at 是这一行的写入时间 |
| evidence | 复算依据，格式 `raw 路径:sha256[,raw 路径:sha256…]\|scripts/脚本路径@40 位 commit\|取值时间（+08:00）`；raw 路径须是 `raw/YYYY-MM-DD/…`、不得含 `..`，并与该日 MANIFEST.sha256 一致 |

## framework_sha256 和 framework_commit

对内核整库清单算 sha256，并记录内核提交号：framework_sha256 是登记时内核已提交版本的整库清单的 sha256，framework_commit 是对应的内核提交号。具体算法写在内核自己的文档里，内核不公开；经王总同意，才向指定审阅人出示内核，由审阅人按同一算法复核。

## 登记和对账的规则

**判定分组**：HIT 与互斥判定按 (draft_id, classification_id) 分组。每组至少 2 支，同组分支必须在同一个提交里、连续地一起登记，之后不得再给这一组加分支（E-BR-GROUP-LATE）。同组分支的 publish_date、registered_at 的日期、window_start、window_end、observed_variable、unit、data_source、data_vintage 必须完全相同。同组如果全是区间型分支，各区间必须两两互斥，并且合起来覆盖全部实数（按端点开闭计算）。对账时，组内组内只看各分支当前的最终结论：恰有一支 HIT、其余 MISS；全部 NONE_HIT；两支以上 MULTI_HIT、其余 MISS；或全部 TRIGGER_UNOBSERVABLE。组内结论尚未出齐时只查是否矛盾；error_source 在组内必须一致。

行分四种：**登记行**（每个分支的第一行）、**对账行**、**登记更正行**、**结论更正行**。

1. **只追加，不改已有行。** 已提交的行一个字节都不改，也不删，新内容一律追加在文件末尾。
   - CI 用 `--base` **逐个提交**检查：base..head 之间的每个提交，台账都必须以其父提交的台账开头（push 取 before，PR 取 base 与 head 的 merge-base）。同一个 PR 里先加后改也会被拦下。基线提交不存在或读不出时判失败，不放行。
   - **推送时间。** CI 用运行时间作为推送时间（`--now`）。对本次新增的登记行和登记更正行，要求推送时间与 registered_at 相差不超过 6 小时，并且早于 window_start 当日 00:00（SGT）。
2. **登记行。** check_result 必须是 `PENDING`，quarter_readings 为空；registered_at 的日期等于 publish_date，并早于观测开始（window_start 至少是发布次日）；lu_basis_date 和 lu_evidence 里每个读数的 vintage 都不得晚于 registered_at。
3. **不可改字段**：全部事先登记字段，加上 registered_at。对账行和结论更正行里，这些字段必须与当前登记（登记行，或最近一条登记更正行）完全一致。
4. **对账行**：window_end 之后追加，事先登记字段照抄，再填对账字段，checked_at 晚于 window_end。DATA_UNAVAILABLE 可以等数据发布后再追加一行。每个分支只能有一个最终结论（HIT、MISS、NONE_HIT、MULTI_HIT、TRIGGER_UNOBSERVABLE）；要改只能走结论更正。
5. **登记更正行**（观测开始前）：check_result 为 `PENDING`，corrects_row_id 指向当前登记行，reason 必填。可以改事先登记字段（draft_id、branch_order、publish_date 不能改），registered_at 写更正行自己的真实时间：必须晚于被更正行，日期早于 window_start（更正前后都要早于）。观测开始后就不能再做登记更正。
6. **结论更正行**（观测开始后）：只能改对账字段，事先登记字段和 registered_at 照抄；corrects_row_id 必须指向当前那条最终结论（第一次是那条对账行，之后是上一条结论更正行），reason 必填，check_result 是最终结论之一。“结论改过”的次数就是这个分支结论更正行的条数，由台账直接推导，不另设字段。
7. **观测开始后要改条件**，只能用新的 classification_id 另起一组重新登记（新组的登记行照第 2 条，组内至少 2 支），原组照原登记对账。不能在原组里加新的 branch_order。
8. **按季读数型分支**：王总确认判定规则前，所有行的结论都只能是 `PENDING`，error_source 留空。唯一例外是可以追加读数行：仍为 `PENDING`，填 quarter_readings 以及 checked_by、checked_at（写入时间）。quarter_readings 必须以前一条读数为前缀，并且至少多一个季度（严格变长），已有条目不改不删；季度从 window_quarters 第一个开始按顺序；每个读数写成 `季度:读数@vintage#raw 路径:sha256`，vintage 不早于该季度结束，也不晚于这一行的写入时间；raw 路径不得含 `..`，并与 MANIFEST 一致。
9. **PENDING 行**（读数行除外）不得填 actual_value、actual_branch、error_source、evidence、checked_by、checked_at。
10. **门禁计数和命中率。**
    - 分支身份和分母取每个分支的第一行。
    - 门禁只算第一行：第一行 window_end 不晚于 2026-12-31、check_result 为 PENDING 的分支计 1，对账行和更正行不重复计数；门禁不限于宏观。
    - 命中率按更正后的条件算，前提是登记更正发生在观测开始前；没有更正的，按第一行。结果取当前有效的最终结论（结论更正后的最新一条）。一组恰有一支 HIT、其余 MISS，记为对。
    - 另外单独列出做过登记更正的分支数和结论更正的次数。`--stats` 会输出这几项。
11. **登记校验**（从严临时执行），任一条不满足就不登记，退回生产与发布 bot：N ≥ 1；L ≤ U；window_quarters 恰好是 N 个连续季度，最后一个不晚于 window_end 所在季度；lu_evidence 非空，每个读数都带 vintage、raw 路径、sha256 和来源链接；按季读数型分支四个区间字段填 `NA`。
12. **公开口径。** 台账只登记分支条件、校验码和提交号，不写框架正文，也不写推导；自由文本字段（slug、reason、observed_variable、unit、data_source、data_vintage、trigger_condition、registered_by、checked_by、actual_value）不得含绝对路径、file: URI 或内部目录名，由 check-branches 检查；CI 还对 PR 或 push 的全部新增提交运行 `check-public.py --range`，检查台账全文是否含本机路径。

## 校验

```sh
python3 scripts/check-branches.py --repo . --ref HEAD                                # 格式与登记规则
python3 scripts/check-branches.py --repo . --ref HEAD --base origin/main             # 另逐提交查只追加、组成员固定
python3 scripts/check-branches.py --repo . --ref HEAD --base B --now <+08:00 时间>    # 另查推送时间
python3 scripts/check-branches.py --repo . --ref HEAD --count-gate [--domain ai] --stats  # 门禁计数与命中率
```

脚本只输出行号、提交短 SHA、错误码和计数。它会核对区间型结论与 actual_value 是否一致，但不从 raw 复算取值。测试在 `tests/test_branches.py`。

## follow-up（尚未实现）

- 从 raw 原件复算读数和 actual_value，并核对 evidence 引用的来源与 data_source 一致；核实之前，结论仍以人工复核为准。
- 推送时间以 CI 运行时间为准，仍可能受重跑影响；更可信的接收时间记录留待后续。
- 按季读数的写入时间（checked_at）目前是自报，可信记录留待后续。
