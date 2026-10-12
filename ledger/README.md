# ledger/：分支台账

`branches.csv` 是分支台账，一个分支占一行。分支不只用于宏观：日报里的 AI、能源、太空、生物等条目，只要做了完整分类（写出全部后续分支和触发条件），都要登记，用 domain 列区分领域。
生产与发布 bot 在发布时登记；观测窗口到期后，审查与治理 bot 追加对账行。
字段和规则以站点路线图 `docs/roadmap.md` 第六节“分支台账”、第十三节 13.1 为准；本 PR 的扩展（domain、row_id、更正行、整库校验码、门禁只算第一行）为协调 bot 已定（2026-10-12），路线图同步见站点 PR #38。
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
| row_id | 行标识，生成规则：`<draft_id>-b<branch_order>-r<n>`，n 是这个分支在文件中的第几行（从 1 起，按文件顺序）。脚本按此规则复算 |
| corrects_row_id | 更正行填被更正行的 row_id（必须是同一分支、已经存在的行）；其他行留空 |
| reason | 更正理由，更正行必填；其他行留空 |
| draft_id | 稿件编号（小写字母、数字和连字符） |
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
| window_start / window_end | 观测窗口的起止日期；window_end 就是到期日 |
| branch_order | 同一篇稿件内的分支序号，从 1 开始 |
| interval_low / interval_high | 区间型分支的下沿和上沿，留空表示无穷。按季读数型分支、没有数值区间的定性条件，四个区间字段一律填 `NA` |
| interval_low_closed / interval_high_closed | 端点是否包含在区间内，填 `true` 或 `false`；不适用填 `NA` |
| trigger_condition | 触发条件的文字写法。必须和区间字段等价，判定以区间字段为准 |
| n_quarters | 按季读数型分支需要连续观察的季度数 N。其他分支填 `NA` 或留空，下面四个按季字段同理 |
| window_quarters | 参与判定的 N 个季度，按时间顺序用英文分号分隔，如 `2026Q4;2027Q1` |
| lu_basis_date | 计算下沿 L、上沿 U 所依据的基准日期 |
| l_value / u_value | 所用下沿 L 和上沿 U 的数值 |
| lu_evidence | 计算 L 和 U 用到的每个读数，用英文分号分隔，每个写成 `季度:读数@vintage#raw 路径:sha256\|来源链接`，vintage 写 YYYY-MM-DD |
| registered_by / registered_at | 登记人（bot 名）和登记时间 |

**到期对账**：window_end 之后由审查与治理 bot 填写。

| 字段 | 含义 |
|---|---|
| actual_value | 实际取值（区间型分支） |
| quarter_readings | 每个季度的读数，写成 `季度:读数@vintage#raw 路径:sha256`，用英文分号分隔，季度须在 window_quarters 内并按顺序（按季读数型分支） |
| actual_branch | 是否为实际发生的那一支，填 `是`、`否` 或留空 |
| check_result | 对账结果：`PENDING`（未到期）、`HIT`、`MISS`、`NONE_HIT`、`MULTI_HIT`、`TRIGGER_UNOBSERVABLE`、`DATA_UNAVAILABLE` |
| error_source | 错在哪一环，只能填 `采集`、`解读`、`框架`。有多个原因时用英文分号分隔，主因写在最前。只在对账结果为 NONE_HIT、MULTI_HIT 或 TRIGGER_UNOBSERVABLE 时填写 |
| checked_by / checked_at | 核对人和核对时间 |
| evidence | 复算依据：raw 路径和 sha256、计算脚本的路径和 commit、取值时间 |

## framework_sha256 和 framework_commit

对内核整库清单算 sha256，并记录内核提交号：framework_sha256 是登记时内核已提交版本的整库清单的 sha256，framework_commit 是对应的内核提交号。具体算法写在内核自己的文档里，内核不公开；经王总同意，才向指定审阅人出示内核，由审阅人按同一算法复核。

## 登记和对账的规则

1. **只追加，不改已有行。** 已提交的行一个字节都不改，也不删，新内容一律追加在文件末尾。CI 用 `--base` 检查新文件是否以原文件开头（push 取 before，PR 取 base 与 head 的 merge-base）。
2. **第一行是登记行。** 每个分支（draft_id + branch_order）的第一行 check_result 必须是 `PENDING`，registered_at 不得晚于 window_end 当天。
3. **事先登记字段写了不改。** 同一分支后追加的对账行，事先登记字段必须和该分支当前的登记行（第一行，或最近一条更正行）完全一致。
4. **对账时追加一行，不改原行。** 事先登记字段照抄，再填对账字段；checked_at 必须晚于 window_end。数据未发布（DATA_UNAVAILABLE）可以等数据发布后再追加一行。每个分支只能有一个最终结论（HIT、MISS、NONE_HIT、MULTI_HIT、TRIGGER_UNOBSERVABLE）；要改结论，只能追加更正行，此后另算。
5. **更正行。** 填 corrects_row_id（指向同一分支已存在的 row_id）和 reason，check_result 为 `PENDING`，其余字段写更正后的值。原行保留不动。
6. **PENDING 行**不得填 actual_value、actual_branch、error_source、evidence、checked_by、checked_at。按季读数型分支可以在 PENDING 行先登记 quarter_readings。
7. **按季读数型分支**：王总确认判定规则前，结论只允许 `PENDING`、`TRIGGER_UNOBSERVABLE`、`DATA_UNAVAILABLE`，error_source 留空。
8. **门禁计数。** 统计“至少 20 条可到期分支”时，每个分支只算第一行：第一行 window_end 不晚于 2026-12-31、check_result 为 PENDING 的计 1；对账行和更正行都不重复计数。门禁不限于宏观。
9. **登记校验**（从严临时执行），任一条不满足就不登记，退回生产与发布 bot：N ≥ 1；L ≤ U；window_quarters 恰好是 N 个连续季度，最后一个不晚于 window_end 所在季度；lu_evidence 非空且每个读数格式正确；按季读数型分支四个区间字段填 `NA`。
10. **公开口径。** 台账只登记分支条件、校验码和提交号，不写框架正文，也不写推导。

## 校验

```sh
python3 scripts/check-branches.py --repo . --ref HEAD                                # 格式与登记规则
python3 scripts/check-branches.py --repo . --ref HEAD --base origin/main             # 另查只追加
python3 scripts/check-branches.py --repo . --ref HEAD --count-gate [--domain ai]     # 门禁计数
```

脚本只输出行号、错误码和计数，不判定 HIT 或 MISS。测试在 `tests/test_branches.py`。
