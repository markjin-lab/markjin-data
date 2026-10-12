# ledger/：宏观分支台账

`macro-branches.csv` 是宏观稿的分支台账，一个分支占一行。宏观稿发布时，生产与发布 bot 登记该稿的全部分支；观测窗口到期后，审查与治理 bot 对账。
字段和规则以站点路线图 `docs/roadmap.md` 第六节“分支台账”和第十三节 13.1 为准（v1.10，站点 main 95c7047）。本文与路线图不一致时，以路线图为准。

路线图中标为“bot 补写，待王总确认”的规则，凡写明“从严临时执行”的，现在就照做；写明“确认前不生效”的，现在只登记数据，不按它判定结果。

## 文件格式

- UTF-8，不带 BOM；逗号分隔，含逗号或引号的值按 CSV 规则用双引号括起；每行以换行结尾。
- 第一行是表头，列名和列序必须与下表一致。目前文件里只有表头，没有示例行，下文的示例不计入台账。
- 日期写 `YYYY-MM-DD`（SGT），时间写 `YYYY-MM-DDTHH:MM:SS+08:00`。

## 字段

**事先登记**：发布时写定，以后不改。

| 字段 | 含义 |
|---|---|
| draft_id | 稿件编号 |
| slug | 稿件的网址短名 |
| publish_date | 发布日期 |
| framework_version | 所用框架的版本号，如 `v2.4` |
| framework_sha256 | 内核校验码，即登记时所用框架正文的 sha256（64 位小写十六进制）。算法见下节 |
| observed_variable | 观测的变量 |
| unit | 单位 |
| data_source | 数据来源，如 FRED 序列号 |
| data_vintage | 取数规则，不是固定快照。默认写“每季取到期核对日（SGT）最新发布的版本” |
| window_start / window_end | 观测窗口的起止日期；window_end 就是到期日 |
| branch_order | 同一篇稿件内的分支序号，从 1 开始 |
| interval_low / interval_high | 区间型分支的下沿和上沿，留空表示无穷。按季读数型分支一律填 `NA` |
| interval_low_closed / interval_high_closed | 端点是否包含在区间内，填 `true` 或 `false`。按季读数型分支填 `NA` |
| trigger_condition | 触发条件的文字写法。必须和区间字段等价，判定以区间字段为准 |
| n_quarters | 按季读数型分支需要连续观察的季度数 N。区间型分支留空 |
| window_quarters | 参与判定的 N 个季度，按时间顺序用英文分号分隔，如 `2026Q4;2027Q1` |
| lu_basis_date | 计算下沿 L、上沿 U 所依据的基准日期 |
| l_value / u_value | 所用下沿 L 和上沿 U 的数值 |
| lu_evidence | 计算 L 和 U 用到的每个读数。每个读数都写明来源链接、data_vintage、raw 路径和 sha256 |
| registered_by / registered_at | 登记人（bot 名）和登记时间 |

**到期对账**：window_end 之后由审查与治理 bot 填写。

| 字段 | 含义 |
|---|---|
| actual_value | 实际取值（区间型分支） |
| quarter_readings | 每个季度的读数，写成 `季度:读数@data_vintage#raw 路径:sha256`，用英文分号分隔（按季读数型分支） |
| actual_branch | 是否为实际发生的那一支，填 `是`、`否` 或留空 |
| check_result | 对账结果：`PENDING`（未到期）、`HIT`、`MISS`、`NONE_HIT`、`MULTI_HIT`、`TRIGGER_UNOBSERVABLE`、`DATA_UNAVAILABLE` |
| error_source | 错在哪一环，只能填 `采集`、`解读`、`框架`。有多个原因时用英文分号分隔，主因写在最前。只在对账结果为 NONE_HIT、MULTI_HIT 或 TRIGGER_UNOBSERVABLE 时填写 |
| checked_by / checked_at | 核对人和核对时间 |
| evidence | 复算依据：raw 路径和 sha256、计算脚本的路径和 commit、取值时间 |

## framework_sha256 怎么算

只对内核里的一个文件算：宏观框架正文 `framework/macro.md`。不拼接其他文件，按字节原样计算，不做换行转换或任何规范化。
取已提交到内核 git 的版本，不取工作区里尚未提交的修改：

```sh
git -C <内核目录> show HEAD:framework/macro.md | sha256sum | cut -d' ' -f1
```

- 输出的 64 位小写十六进制串就是 framework_sha256。
- 登记前先确认 `git -C <内核目录> status --short framework/macro.md` 输出为空，确保正文没有未提交的修改。
- 内核和框架正文不公开。经王总同意，才能向指定审阅人出示内核，由审阅人用同一条命令复核。

## 登记和对账的规则

1. **只追加，不改已有行。** 已提交的行一个字节都不改，也不删。新的内容一律追加在文件末尾。CI 用 `--base` 检查改动后的文件是否以原文件开头。
2. **事先登记的字段写了不改。** 同一 `draft_id + branch_order` 下追加的每一行，事先登记字段都必须和该分支的第一行完全一致。
3. **对账时追加一行。** 到期对账时，不改原来那行 PENDING，而是追加一行：事先登记字段照抄原行，再填上对账字段。数据未发布（DATA_UNAVAILABLE）时，等数据发布后再追加一行重新核对。
4. **登记有误时追加更正行。** 原行保留。更正行该怎么写，路线图尚待王总确认（站点路线图第十三节 13.1 第 1 步）。确认之前从严处理：同一 `draft_id + branch_order` 只要有不止一行，而且这些行的事先登记字段不同，就不得追加，校验会报错。
5. **登记校验**（从严临时执行）。任一条不满足，这一期就不登记分支，退回生产与发布 bot：
   - N（n_quarters）≥ 1；
   - L（l_value）≤ U（u_value）；
   - window_quarters 恰好是 N 个连续的季度，最后一个不晚于 window_end 所在的季度；
   - lu_evidence 不能为空；
   - 按季读数型分支的四个区间字段都填 `NA`。
6. **公开口径。** 台账只登记分支条件和校验码，不写框架正文，也不写推导。稿件正文不写内部分类标签，分支和触发条件只进台账。

## 校验

```sh
python3 scripts/check-branches.py --repo . --ref HEAD                   # 格式与登记规则
python3 scripts/check-branches.py --repo . --ref HEAD --base origin/main # 另查只追加
```

脚本只输出行号和错误码，不判定 HIT 或 MISS。测试在 `tests/test_branches.py`。
