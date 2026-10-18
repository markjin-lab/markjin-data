# review/（公开台账）

公开台账只记录 **错误码、计数、比率、日期、card_id** 五类字段（字段白名单），不写任何自由文本。

- `review/ledger/YYYY-MM-DD.jsonl`：每行一条记录，字段仅限 `date`、`error_code`、`count`、`ratio`（可省略）、`card_id`（可省略；公开稿件里的锚点，只允许小写字母/数字/连字符，如 `2026-10-10-c03`）。由 `scripts/markjin/ledger.py` 写入，白名单外字段或未登记错误码会被拒绝（`E-LEDGER-FIELD` / `E-LEDGER-VALUE`）。
- `review/error-codes.md`：错误码表，由 `scripts/gen-error-codes.py` 从 `scripts/markjin/codes.py` 生成。审查意见一律按错误码写入台账。
- **台账只是统计**：计数不是批准凭证（`I-AUTO-APPROVED` 计数已随 t161u 取消低风险自动批准而停用，不再产生）；路由不读取台账判断是否已批准。
- 台账日期按真实日历解析，且必须与文件名 `YYYY-MM-DD.jsonl` 一致（`E-LEDGER-DATE`）；`review/ledger/` 目录缺失 → `E-LEDGER-DIR`。
- 内部材料只放本机内部目录（环境变量 `MARKJIN_INTERNAL_DIR`；未设置时为仓库根目录的同级目录 `../markjin-internal`），不做 git 管理、不推送。写入只靠**操作系统身份与目录权限**：目录必须属于当前用户、权限 0700、不是符号链接、不在 git 仓库内。`write_internal()` 的 `actor` 参数只是自报标签，不做授权，**不能作为任何批准凭证**。
- 公开仓库守卫 `python3 scripts/check-public.py [--pre-push | --rev REV | --range A..B]`：检查 git 对象（默认 HEAD 提交对象），不检查工作树；逐个提交检查内部材料路径、review/ 路径白名单与格式、台账白名单（原“两个禁词”检查已于 2026-10-11 解禁撤除）。不依赖本机内部清单，CI 与本机都可跑。
- 内部主题检查只在**本机推送前**执行：`git config core.hooksPath scripts/hooks` 安装 `scripts/hooks/pre-push`，它把 stdin 原样交给 `check-internal.py --pre-push` 与 `check-public.py --pre-push`，按每个 `local_sha` 检查 git 对象：hook 把 Git 传入的远端名（$1）和本次实际推送 URL（$2）用 `--remote` / `--remote-url` 交给两个守卫。新分支（或 remote_sha 本地不存在）先核验可信上游 main：**本次推送的目标 URL** 与 origin URL（含 pushurl）都是 markjin-lab/markjin-data，且目标 URL 上的远端 main（`git ls-remote <url> refs/heads/main`）等于本地基线 `origin/main`——全部满足才只扫新引入的提交（`<local_sha> --not <上游 main>`）；推往任何其他远端、手工运行没给 `--remote-url`、或核验失败，一律扫描其可达的全部提交（r6 协调方定、r7 王总定；不依赖 `--not --remotes`）；已有分支同样先核验目标——只有上述可信条件全部满足（目标是 markjin-lab/markjin-data、远端 main 等于基线）时才扫描 `remote_sha..local_sha`，否则同样从 local_sha 全量扫描（r8 王总定），每个提交检查完整树的路径、内容与提交说明。stdin 为空或格式异常、清单缺失或结构不完整、git 出错、解码失败 → 拒绝推送（fail-closed）。报错只给提交短 SHA、文件序号与行号，不输出文件名或命中内容。CI 读不到内部清单，不跑这项检查。

历史文件 `review/YYYY-MM-DD.md` 为第 1 阶段之前的格式，保留不改。

## 台账与内部清单补充规则（r4）

- `review/ledger/` 下只允许 `.gitkeep`（须为空）与 `YYYY-MM-DD.jsonl`；其他文件名、子目录 → `E-LEDGER-FILE`；台账文件为空 → `E-LEDGER-EMPTY`。
- 台账每行 JSON 出现重复键一律拒绝（`E-LEDGER-VALUE`），防止前一个值被隐藏。
- `card_id` 必须是卡片稿件里确实存在且唯一的锚点（`E-LEDGER-CARD`）：只认 `cards/<name>.md`（对应站点 `content/cards/<name>.md`），去掉代码块与 HTML 注释后含 `{#<card_id>}` 或 `id="<card_id>"`；重复锚点不认。check-public 按同一提交树核对。
- `review/` 整体白名单（`E-REVIEW-PATH`）：`README.md`、`error-codes.md`、`ledger/.gitkeep`、`ledger/YYYY-MM-DD.jsonl`、`YYYY-MM-DD.md`、`YYYY-MM-DD-rN/{digest.md,post.md,review-prompt.md,result-rN[a-z]?.txt}`、`codex/<名>.log`。
- `check-public.py` / `check-internal.py` 显式给出的 `--rev`/`--range` 解析后没有提交 → `E-CHECK-EMPTY`（不报通过）。
- 内部清单：表格以外不允许出现任何文字（协调决定），出现即清单无效（fail-closed）。需要识别的内容一律写进表格。

### review/ 非台账记录的格式校验（`E-REVIEW-FORMAT`）

`review/YYYY-MM-DD.md`、`review/YYYY-MM-DD-rN/*`、`review/codex/*.log` 无法做字段白名单，因此：
- 公开守卫（check-public，CI 可跑）做格式校验：UTF-8、非空、大小上限（日志 4 MB，其余 512 KB）、无控制字符、不得出现内部材料路径；
  日审 md 首行须为含该日期的 `# ` 标题；轮次目录 md 首行须为 `# ` 标题，`result-*.txt` 最后一行须为纯文本 `VERDICT: APPROVED`、`VERDICT: APPROVED_WITH_FOLLOWUPS` 或 `VERDICT: REJECTED`（与下文及 ledger.py 一致）；
  Codex 日志首行须为 `OpenAI Codex v…`。
- 内部清单扫描：check-internal（本机 pre-push）对全部 blob（含上述文件）执行，命中即拒绝推送，输出不回显命中词。

### 解禁记录（2026-10-11）

王总 2026-10-11 01:14（SGT）亲口确认解除“中医”“佛学”的公开禁令（quote_ref `grok-bot:t90u`，Grok Bot 对话 t90u，01:10 SGT，原文“中医和佛学不需要回避可以公开”）。check-public 的禁词检查与 `E-PUBLIC-BANNED` 已撤除；医疗内容仍不算低风险。

### 第 8 轮补充（2026-10-11）

- pre-push 内部清单扫描另查推送的**引用名**（本地与远端分支/标签名）和**附注标签说明**（含嵌套标签）；命中报 `E-BLOCK-INTERNAL`，位置脱敏为 `push:#<行>:ref|tag`。
- `--range` 只要有一个解析为空就报 `E-CHECK-EMPTY`，不会被同时给出的 `--rev` 或其他有效区间掩盖。
- 台账 `card_id` 锚点不认行内代码（`` `…` ``）和转义文本（`\{#id}`、`\id="…"`）里的写法。

## 第 7 轮审查补充（2026-10-11 07:14）

- pre-push：已有远端分支的推送若 `remote_sha..local_sha` 为空（例如强推倒退到祖先），判 `E-CHECK-EMPTY` 并拒绝推送，不当作“检查通过”。
- 附注标签说明逐层扫描，嵌套不设深度上限（遇到环判 `E-CHECK-GIT`）。

## 第 8 轮审查补充（2026-10-11 07:45 决定）

- **提交头与标签头也扫内部清单**：除提交说明外，提交对象的 author / committer（名称、邮箱）等头部，以及每层附注标签的 tag 名、tagger（名称、邮箱）与说明，都在 pre-push 中扫描；只跳过 tree / parent / object / type 这类 SHA 与类型行。命中 → E-BLOCK-INTERNAL。
- **标签目标检查**：推送附注标签时，先把标签解析到最终指向的提交，再对该提交做台账目录等检查（E-LEDGER-DIR 不再被跳过）。
- **显式空目标**：每个 `--rev` 和 `--range` 单独要求非空；任一为空 → E-CHECK-EMPTY，不会被其他有效目标掩盖。
- **card_id 锚点**：`data-id="…"` 等带前缀属性、缩进代码块（4 空格 / Tab 开头）里的文字不算锚点；任一候选卡片读取或解码失败 → E-LEDGER-CARD（拒绝追加，不跳过）。
- **内部目录**：位于 bare 仓库（祖先目录含 HEAD + objects/ + refs/）内同样拒绝使用。

## 二进制原件与审查结论格式（整体验收 r1，2026-10-11）

- check-public / check-internal 对路径、提交说明和文件内容都按 UTF-8 解码，解码失败判 `E-CHECK-DECODE`。唯一的例外是已登记的二进制原件：路径为 `raw/<日期>/<相对路径>`，扩展名是 pdf、jpg、jpeg、png、gif 或 webp，并且同一提交树的 `raw/<日期>/MANIFEST.sha256` 里有 `<sha256>  ./<相对路径>` 一行与这份字节的 sha256 一致。这类文件的路径照常扫描，内容不作文本扫描。没登记的、字节不符的、扩展名不在单上的、不在 `raw/<日期>/` 下的，仍然判失败。
- 整体验收 r4：扩展名为 .pdf/.jpg/.jpeg/.png/.gif/.webp 的文件一律先做登记校验（不以能否按 UTF-8 解码为条件）；未登记、字节不符或不在 raw/<日期>/ 下 → `E-CHECK-DECODE`。
- review/ 下审查结果文件最后一行可以是 `VERDICT: APPROVED`、`VERDICT: APPROVED_WITH_FOLLOWUPS` 或 `VERDICT: REJECTED`，其中第二种（`APPROVED_WITH_FOLLOWUPS`）供规划文件使用。稿件批准记录（approvals/codex）仍然只认 `APPROVED`。
- `review/error-codes.md` 由 `python3 scripts/gen-error-codes.py` 生成，`--check` 用来核对是否一致，测试也会核对。合并 PR 后如果 codes.py 有变化，要重新生成。

- r6（协调方 Grok Bot 定）：上游 main 历史里已存在的提交（如 #34 的 b5cfa0a、c289cb3，`check-public --rev origin/main` 仍报 `E-CHECK-DECODE`，历史不改写）在 pre-push 核验上游 main 通过后不再重复扫描，不会拦住新分支首次推送；新引入的二进制文件仍须按 MANIFEST 严格登记。
- 台账 `card_id` 锚点：未闭合的 HTML 注释（`<!--` 没有 `-->`）视为延续到文件末尾，其中的 `{#id}` / `id="…"` 不算锚点（整体验收 r5）。
- r7（整体验收 r6 HIGH）：没有新增提交的 ref 更新（新分支或新标签指向可信上游 main 上已有的提交）不会因增量为空而跳过：至少扫描它指向的那个提交（完整树、提交说明、台账目录等树门禁）。
- r7（整体验收 r6 MEDIUM）：守卫对 raw/<日期>/MANIFEST.sha256 与自检同一口径严格解析——任一行格式不对、绝对路径或含 `..`、路径首尾空白、重复路径，或没有条目 → 整份 MANIFEST 无效，其中的二进制都不算登记（E-CHECK-DECODE）。
- r7（整体验收 r6 MEDIUM）：台账锚点按 CommonMark 围栏规则去掉代码块——闭围栏须同一字符且不短于开围栏；未闭合的围栏延续到文件末尾，其中的 `{#id}` 不算锚点。


**整体验收 r8 修复（pre-push，王总定）**：只有一种情况只扫增量——本次推送的目标远端/URL 是 markjin-lab/markjin-data，且远端 main 等于本地基线。新分支与已有分支一样处理；其他情况（推往其他远端、未给 URL、远端 main 已变）一律从 local_sha 全量扫描。已有分支强推倒退（区间为空）不论目标都判 E-CHECK-EMPTY。

- 整体验收 r11：`I-AUTO-APPROVED` 已停用（t161u），台账里这个码只许记 `count: 0`，非零值判 `E-LEDGER-VALUE`。
- 整体验收 r12：`check-public` 不带参数时只查 HEAD 这一个提交对象（不扫祖先）；要审计全部历史用 `--rev <REV>`，PR 增量用 `--range base..head`。
