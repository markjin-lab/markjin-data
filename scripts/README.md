# scripts/

## selfcheck（#9 脚本自检，第 2 轮）

> **现行口径（王总 t161u，原话“1、行；2、按新写法，每天过codex”）**：日报一律过 Codex，**不再有自动批准**（AUTO_APPROVED 已取消）。所有稿件都须取得有效 Codex APPROVED 才能发布；宏观、tongyi、信号卡另须王总批准。selfcheck 的 `low_risk` 与 `R-*` 只作审查参考，不决定能否发布。下文凡写“低风险”“非低风险 （low_risk 参考值为 False）”的段落，均只说明 `low_risk` 参考值如何计算，不是发布规则。

> **硬拦的边界（王总经 Grok Bot 转达，2026-10-11 r13）**：selfcheck 只是 Codex 之前的前置硬拦，不承担语义层面的完备拦截。词表和模式能识别的宏观观点、仓位与买卖建议直接 FAIL；**词表和模式之外的观点、评价与倾向，由每篇必过的 Codex 审查拦截**。因此 selfcheck `PASS` 不代表稿件没有观点，也不构成 B1 已满足的证明；不再为追求完备而无限加词。


`python3 scripts/selfcheck.py DRAFT.md --repo REPO_ROOT --date YYYY-MM-DD --card-type daily|signal [--json]`

- `--repo`、`--date`、`--card-type` 都必须显式给出：不退回当前目录，不默认 daily。退出码 0=PASS、1=FAIL、2=UNCLEAR。
- 输出只含错误码、行号与计数，不回显稿件文本。错误码表见 `scripts/markjin/codes.py`。

### 威胁模型与低风险参考值（结构白名单）

威胁模型以“防误操作、防 bot 绕过”为主（协调决定 2026-10-10），不追求无限加严。
词表在公开 JSON `scripts/markjin/lexicon.json`（中性文件名，便于与生产 bot 共用；每个词规范化后至少 2 个字符，禁止“称”这类单字；`exclude` 列出排除短语，如“表示学习”）。
匹配前先规范化：NFKC、去掉零宽与 Unicode 格式控制字符、压缩空白；逐行匹配，并在整篇拼接后再匹配一次（覆盖跨行与插空白写法）。

**low_risk 参考值 = 结构白名单**（2026-10-11 00:32 定；t161u 后只作参考）：日报稿正文的每个非空行都必须是下面三种之一，否则 `R-STRUCTURE`，非低风险 （low_risk 参考值为 False）。

1. **标题**：只允许固定栏目名（去掉日期后为 日报 / AI 日报 / 论文 / arXiv / 模型发布 / daily / digest，或只有日期），不含来源。
2. **原文直引**：
   ```
   > 「<原文>」 — `raw/<目标日期>/<arxiv|x|fred>/<文件>` · <来源 URL>
   ```
   （也接受 ASCII 双引号 `"…"`。）raw 与 URL 照常回放（同日、同类型、MANIFEST 哈希、ID 在存档）；引文规范化（实体解码、NFKC、去零宽、压缩空白）后
   必须是该来源条目原文的**连续子串**：arXiv 只在**自身 `<id>`** 等于该 ID 的 `<entry>` 的 `<title>`/`<summary>` 内各自找（不跨字段拼接；摘要里提到的 ID 不算；URL 带版本时版本也必须相同，v1 存档不配 v2 链接），X 只在**自身 `id` 字段**等于该 ID 的对象的 `text`/`full_text`/`note_tweet.text` 里找，FRED 为整份文件；
   引文至少 6 个非空白字符；引文必须是完整句子（前面是开头或句末标点，自身以句末标点结尾），否则原文中紧邻其前后的位置不得是否定词或限定词（not、no、never、does not、unless、only if、except、if、may… / 不、未、没有、无、非、仅、只有、除非、若、可能…）。逐字核对只用于日报（`card_type=daily`）。核对不通过（夹带原文没有的字、换了条目、太短）→ `R-QUOTE-UNVERIFIED`，非低风险。
3. **来源链接**：`来源：`raw/…` · <URL>[ ; `raw/…` · <URL>]`（可带列表符号），每对照常回放，链接必须能打开。

结构化复述断言（`- <断言> — `raw/…` · <URL>`）保留全部来源绑定与数字核对，但它是转述，不在白名单内（`R-STRUCTURE`）。

`low_risk=True`（参考值；路由不读取）当且仅当（selfcheck 内 `compute_low_risk()` 计算）：status=PASS、无硬错误、无任何审查原因（含 `R-INFERENCE`：直引里带判断词同样不算低风险，协调决定 10-11）、`card_type` 显式为 `daily`、
日期合法、至少 1 条逐字核对通过的原文直引、`other`（白名单外的块）为 0、全部来源链接能打开、非 X 单一来源、非宏观、非医疗。

**词表的角色**：只用于硬拦（投资/仓位、宏观观点、内部主题）与风险标注，不再担负低风险门槛。判断/转述词出现在原文直引里同样记 `R-INFERENCE`，不算低风险（协调决定 10-11）；出现在任何白名单外的块里，该块本来就让稿件非低风险。宏观/医疗/X 单一来源仍然非低风险（领域风险，不是措辞判断）。

| 情形 | 结果 |
|---|---|
| 白名单外的块（段落、列表、结构化断言、表格、非固定栏目标题、注释、front matter、分隔线） | `R-STRUCTURE`，非低风险 （low_risk 参考值为 False） |
| 原文直引逐字核对不通过 / 信号卡上的直引 | `R-QUOTE-UNVERIFIED`，非低风险 |
| 英文 weight / allocation / exposure + 百分比 | 只有同一句里出现资产或仓位词（stocks、equity、bonds、gold、cash、portfolio、fund、ETF、holdings、position… 或词表 assets）时才算仓位 → `E-BLOCK-INVEST`；“Memory allocation is 30%.” 等技术句不拦（r8） |
| 判断/转述措辞（可能、显然、有望、预计、声称、表示、stated、reported、according to…），含直引内 | `R-INFERENCE`，非低风险 |
| 无来源的段落（含表头、front matter 行）带判断/转述措辞 | `E-REPLAY-001` → FAIL（拿到批准记录也不得发布） |
| counts 注释（即使合法） | 计数照常核对；`R-STRUCTURE`，非低风险 |
| raw 路径（含祖先目录）或 MANIFEST 为符号链接 | `E-REPLAY-SYMLINK` → FAIL |
| 持有比例/资产权重（如“组合的股票权重为 30%”） | `E-BLOCK-INVEST`（宏观稿另 `E-BLOCK-MACRO-OPINION`）→ FAIL |
| 比较计算（“比上期高 X%”“较上月下降 X”）缺标记/算式/来源 | 按宏观算术规则 `E-BLOCK-MACRO-OPINION` → FAIL |
| 宏观算式验算不符 | `E-FORMULA-MISMATCH` → FAIL |
| 引用块、表格行等非结构化断言（有来源） | 照样回放检查；`R-UNSTRUCTURED`，非低风险 |
| 列表/引用/表格行没有来源结构 | `E-REPLAY-001` + `E-INFER-UNCLEAR` → FAIL |
| 来源 URL 类型未知（段落中另允许本组织 GitHub 链接） | `E-REPLAY-005` → FAIL |
| raw 与 URL 不成对、不在目标日期目录、类型与 URL 不一致、路径越界 | `E-REPLAY-006` → FAIL |
| raw 缺失 / 哈希不符 / 标识不在存档 / 读取或解码失败 | `E-REPLAY-002`/`003`/`004`/`E-REPLAY-READ` → FAIL |
| MANIFEST 非法行、重复路径、越界路径、为空 | `E-MANIFEST-PARSE` → FAIL |
| counts 注释多于一个、未知键、重复键、非法值、非整行 | `E-COUNT-002` → FAIL |
| 断言中的数字不能全部在 raw 中找到 | `R-SUPPORT-UNVERIFIED`，非低风险 |
| 日报中的断言（原文直引、结构化断言、带来源的行）只有 X 来源支撑 | `E-X-ONLY` 硬拦（r6 协调方定：X 只作线索）；有其他可回放来源同时支撑则不拦 |
| 只有 X 来源的纯来源链接行或信号卡 / 医疗 / 信号卡 / 没有结构化断言 | `R-X-ONLY` / `R-MEDICAL` / `R-SIGNAL-CARD` / `R-NO-ASSERTION`，非低风险；没有可重新核验断言的日报只标 `R-NO-ASSERTION`，不拦 |
| 宏观算式字段在分隔符（右括号、分号、逗号、句号、换行）或来源标记前还有未验算的后缀（如 `=0.2x≈9.99`） | `E-FORMULA-MISMATCH` 硬拦（r6） |
| 词表缺失或结构非法 | `E-SELFCHECK-LEXICON` → FAIL |
| 来源链接打不开 / 未检查（`--no-link-check` 或离线） | `R-LINK-UNREACHABLE` / `R-LINK-UNCHECKED`，非低风险 |

### 宏观按整篇判定

任一行属宏观语境（宏观词、FRED 来源）即整篇为宏观（`R-MACRO`，永不低风险）。宏观稿中任何位置（含跨行写法）出现观点、预测、判断词
（预计、看多、看涨、看好、加配、减配、建议…）或资金比例/投入建议（如“建议将三成资金投入股票”）→ `E-BLOCK-MACRO-OPINION`（FAIL）。
宏观稿中的因果判断（由于、导致、推动…）同样硬拦。转述词在宏观稿中只算 `R-INFERENCE`，不硬拦。

**宏观算术白名单**（协调决定）：只放行纯算术表述（同比、环比、差值等“由原始数据计算”类），且必须**同时**满足：
带标记（`由原始数据计算` / `按原始数据计算` / `据原始数据计算`，可前缀 `推断：`）、带算式（`算式：<表达式>=<结果>`，如 `算式：(4.2/4.0-1)×100=5%`）、
是带数据来源的结构化断言。缺任何一样仍 `E-BLOCK-MACRO-OPINION`；去掉标记与算式后剩余文字若仍有观点、预测或因果判断，照样硬拦。宏观稿永远不是低风险。资金比例/投入建议在非宏观稿中同样 `E-BLOCK-INVEST`。

### 内部主题检查

词表只从本机 `$MARKJIN_INTERNAL_DIR/topics-private.md`（默认 `/workspace/markjin-internal/`）读取，仓库内不含任何内部主题词。
清单严格解析：恰好一张三列表格，表头必须是 `名称 | 识别条件 | 来源`，各行三列非空、名称不重复；三列内容都受保护。缺失、不可读或结构不完整 → `E-INTERNAL-LIST-MISSING`（FAIL）。

## route（#10 审查路由）

`python3 scripts/route.py --pr N --repo REPO --date YYYY-MM-DD --card-type daily|signal [--site-repo DIR] [--dry-run [--now ISO]]`（整体验收 r2：时间只用真实时钟；`--now` 只在 `--dry-run` 下可用，演练结果永远不可发布；`--no-link-check` 已取消）（r13：只接受 PR 编号，base/head/文件列表由 `gh pr view` 取得；稿件、raw/、MANIFEST 从 head 提交读取）

- draft_id 由路径推出：`<section>-<name>`（如 `daily-2026-10-11`）；规则、批准记录 schema、发布状态、状态写回接口与心跳全部见 `docs/approvals.md`。
- **CLI 不接受任何自报的批准或状态**；批准与状态只从 `origin/main` 的 git 对象读取（r13 起调用方不能指定 ref），不读工作树、本机内部目录或公开台账；记录缺任一字段 → HOLD `E-ROUTE-RECORD-INVALID`。t161u 后没有自动批准，台账中历史的 `I-AUTO-APPROVED` 只是已取消路径的统计，不是批准凭证。
- 入口严格 schema（缺字段/None → `HOLD` + `E-ROUTE-INPUT`）；路由不读取 `low_risk`（t161u 后只作审查参考）。
- 门禁不写文件：`ARCHIVED`/`DEFERRED` 时输出 `state_change`，由生产 bot 用 `scripts/state-change.py apply` 写回。
- 王总批准记录只对需王总批准的稿件要求（普通日报只需 Codex）；中英配对稿取两版审批类型的并集：任一版需王总批准，两版都须各自有绑定自身 content_sha256 的王总记录（r8，从严）；当天有效（Asia/Singapore 日历日）；日报稿接受 `direct` 与 `via-grok-bot`，信号卡只接受 v2 + `direct`。

### 状态与顺延（以路线图为准）

- 状态文件读不到或不合法 → `HOLD` + `E-ROUTE-STATE`（生产 bot 提交 `state/publish-state.json` 之前，这是预期行为）。
- **日报快通道（第 12 轮用户决定，现行）**：不需要王总批准的日报（含中英配对）在 07:00 前已有有效 Codex APPROVED（06:55 前完成、绑定内容与配对）时，直接 `APPROVED`，**不受下面两条心跳/离线规则影响**（`codex_in_production` 仍归档）。
- Mac 心跳（`updated_at`）超过 30 分钟 → 其余稿件（需王总批准的稿件，以及还没有有效 Codex APPROVED 的日报）`HOLD` + `E-ROUTE-MAC-STALE`，可重试，不归档（已过 07:00 时按顺延处理）。
- 心跳新鲜且 `mac_online: false`：同上范围的稿件当天归档（`A-MAC-OFFLINE`），优先于 07:00 顺延。
- Mac 在线、需王总批准的稿件（宏观、tongyi、信号卡、中医/佛学）王总缺席或 06:55 前未获批：顺延 1 天（`I-DEFERRED`）；普通日报只需 Codex APPROVED，不看王总在场；顺延稿再次未获批 → 归档 `A-NOT-APPROVED`。
- Codex 参与生产 → 归档 `A-NO-REVIEW-PATH`。归档不可逆。

## 台账与守卫（#11，第 2 轮）

- `scripts/markjin/ledger.py`：公开台账白名单 `date`/`error_code`/`count`/`ratio`/`card_id`；真实日历日期、与文件名一致；目录缺失报错。台账计数不是批准凭证。
- `scripts/markjin/gitscan.py`：按 git 对象逐个提交扫描路径、内容、提交说明；严格解析 pre-push stdin；解码失败拒绝。
- `scripts/check-public.py`：CI 可跑，不读内部清单，检查 git 对象而非工作树。
- `scripts/check-internal.py` + `scripts/hooks/pre-push`：只在本机推送前运行，fail-closed；报错脱敏。详见 `review/README.md`。

### 第 8 轮补充（2026-10-11 02:32 决定）

- **情态词**：英文 may / could / might / suggest(s/ed/ing) / likely（按词边界）与中文 可能 / 或将 / 有望（词表 `modal`）记为推断 `R-INFERENCE`，出现在原文直引里同样挡住低风险。
- **否定/限定窗口**（**已被下文“第 8 轮审查补充（07:45）”的按句判断取代，仅留作历史**）：直引不是完整句子时，原文中引文之前、同一句内的窗口（英文向前 3 个词、中文向前 4 个字）里不得有否定或限定词，可跨过中间的副词（如 does not consistently outperform）；引文之后仍查紧邻位置。完整句子不受此限。
- **arXiv 版本**：链接带版本时须与条目自身版本一致；链接无版本而存档里该 ID 有多个版本 → `E-REPLAY-VERSION-UNCLEAR`（UNCLEAR，不发布）。
- **arXiv 条目 ID**：用 XML 解析，只认 `<entry>` 的直接子节点 `<id>`；嵌套在 `<summary>` 等里面的 `<id>` 不算。解析失败 → `E-REPLAY-READ`。
- **仓位/购买句式硬拦**：“值得购买 / 值得买 / 值得投资 …”（词表 `invest`）、“股票持有六成 / 债券持有百分之三十 / 股票持有 6 成 / 满仓持有七成”等含中文数字的持有比例 → `E-BLOCK-INVEST`。
- **医疗与宗教**：`R-MEDICAL` 覆盖中医、佛学及针灸、中药、经络、方剂、推拿、艾灸、拔罐、穴位、草药等；佛学/佛教等另记 `R-RELIGION`。两者都**可以公开、不硬拦**，但不算低风险。
- **医疗类从严（r7 BLOCKER 2，Grok Bot 定）**：词表 `medical` 补常见中文词（针刺、汤药、中成药、方药、养生、食疗、刮痧、气功…），英文简称与短词放 `medical_ascii`（TCM、herbal、herbs、acupoint、qigong、tuina、cupping、moxa），按词边界匹配（避免 “at CMU” 误中）。**兜底**：front matter 先用 `yaml.safe_load` 解析（r8：不再逐行读原文），按解析结果判定——顶层 categories / category / tags / section / type / topics / series / keywords 等分类键（大小写不敏感，含嵌套列表与映射里的任何字符串）的取值；出现 YAML 锚点（&）、别名（*）、合并键（<<）或解析失败 → `E-SELFCHECK-FM-ALIAS` 硬错误并按医疗类处理（fail-closed）。分类键取值只要含 `medical_markers`（医疗、医学、中医、中药、针灸、养生、健康、health、healthcare、medical、medicine、TCM、wellness…）或医疗词，整篇记 `R-MEDICAL`；稿件路径在医疗栏目（`medical_sections`：medical/、health/、tcm/、zhongyi/…）下同样按医疗类处理（route.needs_wang）。
- **脚本只拦已知的词和标记，其余由 Codex 判**：Codex 判为医疗类时在审查记录里写 `category: "medical"`（可选字段，取值 medical / religion / macro），路由据此要求王总批准；词表未命中不代表不是医疗类。
- **标题**：非固定栏目名的标题（含 front matter 的 `title:`）一律 `R-STRUCTURE`，并照常做推断/硬拦检查。
- **无来源块规则（段落）**：不命中词表、也没有来源的普通段落一律 `E-INFER-UNCLEAR`（UNCLEAR，不发布，有批准记录也不行）；含推断/转述词或数字 → `E-REPLAY-001`。front matter 字段、固定免责声明、表头不算事实段落（带推断仍硬错）。
- **词表误伤修正**：固定免责声明只放行精确原文“本文不含投资建议。”；连词“所以”移出因果词表；“见顶”等仍硬拦。

### 解禁记录

- **2026-10-11 01:14（SGT）**：王总亲口确认（经协调 bot 转达，并在主 bot 处亲自确认），解除“中医”“佛学”两个词的公开禁令。原话 quote_ref：`grok-bot:t90u`（Grok Bot 对话 t90u，01:10 SGT），原文：“中医和佛学不需要回避可以公开”。
- 影响：撤除公开守卫 check-public 的禁词检查（原 `E-PUBLIC-BANNED`）、相关测试与文档。词表 lexicon.json 中“中医”“佛学”只作风险标注（`R-MEDICAL` / `R-RELIGION`，非低风险、需王总批准），不再有任何硬拦。
- 不变：医疗内容仍然不算低风险（`R-MEDICAL`）；内部主题清单检查（check-internal）不受影响。

## 第 7 轮审查补充（2026-10-11 07:14 协调决定）

- **完整句子**只认句号、问号、叹号结尾（`。.！!？?`）；分号、逗号不算句末。截掉“; only if …”“；仅在…”等限定语的直引不是完整句，按否定/限定窗口检查，命中即非低风险（R-QUOTE-UNVERIFIED）。
- **推测动词与情态词类表**（lexicon.json）：`spec_en_verbs`（seem、appear、suggest、indicate、imply、hint、signal、point to、tend to，自动覆盖 -s/-ed/-ing 变形）、`spec_en_words`（may、might、could、would、likely、probably、possibly、perhaps、apparently 等，按词边界）、`spec_zh`（似乎、看来、表明、好像、疑似、或许、也许、大概、可能、或将、有望、预示、暗示、意味着等）。命中即 R-INFERENCE，直引里也挡住低风险。新增词只改词表，不改代码。
- **资产仓位与建议句式硬拦**（E-BLOCK-INVEST，宏观稿另记 E-BLOCK-MACRO-OPINION）：资产词表 `assets`（至少股票、债券、美债、国债、黄金、美元、房产、基金）与两类句式组合：`<资产> + 应当/应该/值得/建议/宜… + 持有/买/购买/配置…`（含倒装“应当持有美债”），`<资产> + 持有/占/占比/权重/仓位… + 比例`（半数、一半、六成、百分之三十、30%）。宏观评价词补“有吸引力”“被低估/高估”等。
- **front matter 与表头里无来源的数字**一律硬错（E-REPLAY-001）；值整体为日期/时间的 front matter 字段（date、publishDate 等）除外。

## 第 8 轮审查补充（2026-10-11 07:45 决定）

- **否定/限定按句判断**：直引不是完整句子时，原文中引文所在句的其余部分（引文之前到上一个句号/问号/叹号，引文之后到下一个句末，跨过逗号、分号、冒号）不得出现任何否定或限定词（not、only if、but、unless、provided、不、仅在、除非、但、前提…）。不再使用 3 词 / 4 字窗口，多个副词也挤不出否定词；“, but only if …”“; only if …”“；仅在…”都会使引文核对失败（R-QUOTE-UNVERIFIED，非低风险）。
- **预测情态**：推测词类表补 will / shall / won't / going to / is set to / expected to / bound to 与 将会、必将、势必、终将、注定、即将；完整直引里出现也算 R-INFERENCE。
- **仓位事实句与适合句式硬拦**（E-BLOCK-INVEST，宏观稿同时 E-BLOCK-MACRO-OPINION）：“<资产> 是/为/占/构成 … 组合/资产/仓位/持仓 … <比例>”，“组合/仓位 … <比例> … <资产>”，以及“<资产> + 适合/适宜/宜于/适于 + 持有/买/配置”。硬拦是 FAIL，有人工批准记录也不能发布。
- **股市主题**：词表 `stock`（股票、个股、股价、收盘价、涨停、A 股、stock…）命中 → R-STOCK，可公开但永不低风险（含纯事实直引）。
- **front matter 日期例外**：只对词表 `fm_date_keys`（date、publishDate、lastmod、expiryDate、updated、published、created）里的字段生效，且值必须是真实存在的日期/时间（2026-02-30、25:00 都不行）；其他字段即使值像日期，数字照常判 E-REPLAY-001。
- **空 repo**：`repo` 为空串、纯空白或非路径类型 → E-SELFCHECK-REPO（不再退回当前目录）。
- **FRED 存档**（**已被 r13 / 决定 59 修订，现行规则如下**）：必须是合法 JSON（否则 E-REPLAY-READ）。存档里有 `series_id`（或 `seriess[].id`）时，必须唯一且等于 URL 的系列 ID；没有这个字段时，只接受文件名等于该系列 ID、且内容是合法 FRED observations JSON 的存档。其他情况判 E-REPLAY-004。
- **词表每次重读**：每次自检重新读取并校验 `lexicon.json`；缺失、损坏或与已加载版本不同 → E-SELFCHECK-LEXICON。
- **免责声明**：只放行“本文不含投资建议。”这一句精确写法，句末标点也须一致（整体验收 r2，王总定），少一个或多一个标点都不放行。英文版（*.en.md）固定为 “This article does not constitute investment advice.”（协调决定 2026-10-11，经 Grok Bot 转达），同样只放行精确原文（句号不可省）；同一行再加任何内容照常检查。

## 第 9 轮审查补充：结构性收紧（2026-10-11 09:07 决定）

不再逐个补词，改为结构规则：

- **原文直引只移出低风险（R-*，不硬拦）**（以下 low_risk / R-* 规则 t161u 后只作审查参考，路由不读取，不是发布门禁）：直引里只要出现以下任一结构，就不算低风险，走 Codex 审查：
  - R-QUOTE-NUMERIC：任何数字、百分比、分数（X 分之 Y、1/3）、倍数/成数、货币或价格词（元、美元、dollars、price、每股、收于…）、英文数量词（half、third、million…）；
  - R-QUOTE-COMPARATIVE：比较级或评价性比较（-er than、than、more/less、better、superior、outperform、exceed、优于、超过、高于、更、最…）；
  - R-QUOTE-MODAL：情态或预测（will、would、should、can、could、may、must、expect、forecast、将、会、应该、可能、预计、有望…）；
  - R-QUOTE-ENTITY：全大写词或股票代号（NVIDIA、AAPL、$TSLA、600519.SH）、句中大写开头的专有名词、驼峰名（OpenAI）。
- **硬拦（E-BLOCK-INVEST）只保留明确的买卖建议与仓位比例句**，覆盖变体：中文分数（五分之一、三分之二、1/3）、英文仓位（“… are half the portfolio”“… make up 30% of the portfolio”“accounts for a third of holdings”）、英文建议（should buy/sell/hold、allocate X% of your portfolio to …）。
- **宏观预测（历史口径，已被下方“中英口径一致”取代）**：早期按 09:07 决定，“Inflation will rise.” 这类只标 R-MACRO + R-QUOTE-MODAL、不硬拦。**现行规则**：直引以外的宏观预测/判断一律 `E-BLOCK-MACRO-OPINION` 硬拦；只有完整原文直引里的宏观预测才只标 R-MACRO（参考）并交 Codex。
- **分句器**：中文 。！？ 随处断句；英文 . ! ? 只有后接空白或文本结束才算句末，小数点、版本号（2.0、3.5）不再把句子断开。

## 第 10 轮补充：双语规则（t141u，经 Grok Bot 转达）

- 稿件里只要出现以“译文：”（或“译文:”，允许前置 `>`、列表符号、空白）开头的行，即标 `R-TRANSLATION`：不算低风险，须走 Codex；不硬拦。
- 文件名为 `*.en.md` 的稿件同样不算低风险（由路由按路径判定，见 #21 docs/approvals.md）。

## 第 11 轮：日报一律过 Codex（王总 t161u，经 Grok Bot 转达，2026-10-11）

- 王总定：日报一律按新写法写，每天都要过 Codex，**取消低风险自动批准**。selfcheck 输出的 `low_risk` 与 `R-*` 保留，只作参考（审查提示），不再决定任何稿件能否发布（发布门禁见 #21 route）。
- 因此第 10 轮审查提出的、只为判低风险而做的收紧（严格句式白名单、推测词类表补充、拼写数词/罗马数字识别、缩写分句器）不再做；此前提交的 8aa4888 已整体回退，硬拦部分重新实现如下。
- 硬拦（E-BLOCK-*）保留并修正漏拦/误拦：
  - 中英口径一致：直引以外的宏观预测/判断，中文推测词与英文情态（will、may、likely…）同样硬拦；原文直引里的宏观预测中英都只标 R-MACRO（参考），交 Codex。
  - 英文单词写的仓位比例（forty percent of the portfolio、two-thirds、three quarters）硬拦 E-BLOCK-INVEST。
  - 英文资产评价句（“Treasury yields are attractive.”“stocks look cheap”“bonds are overvalued”）硬拦 E-BLOCK-MACRO-OPINION。
  - 单独一个 buy/sell 不再拦（“buy signals”是研究对象），只拦 should buy、time to buy、buy now、buy rating 等建议说法。
- `check_text(internal_terms=...)` 注入的词表为空、含空串/空白或类型不对，直接抛 ValueError。

## 第 12 轮（r12）

- **评价与机会类说法硬拦**（E-BLOCK-MACRO-OPINION）：宏观稿中任何位置（含原文直引）出现 opportunity、excellent、attractive、compelling、bargain、cheap、undervalued、overvalued、upside、worth buying 等，或中文 值得（“值得注意/值得一提”除外）、机会（“机会成本”除外）、吸引力、便宜、低估、高估、划算、性价比、上涨空间、买点、卖点，即硬拦；非宏观稿与明确资产词（stocks、bonds、treasuries、gold、bitcoin… / 股票、债券、黄金…）同行时同样硬拦。固定免责声明不受影响。
- **英文评价句的资产词**改用无歧义集合：去掉单数 stock、yields、markets、shares，避免 “The stock of knowledge is rich.”“Our method yields excellent results.” 误拦；宏观稿内不论资产词一律拦。
- **“占/占比”** 只在紧跟资产词时算仓位句：“黄金占30%”仍拦，“黄金样本占30%”不拦。
- **internal_terms**：`check_text` 只认本机真实内部名单（`internal_terms="load"`），调用方传入任何替代值（含非空、看似合法的词表）一律 ValueError；测试改为替换 `load_internal_terms`。
- **R-TRANSLATION** 识别带列表前缀的译文行：`+ 译文：`、`1. 译文：`、`2) 译文：`、`3、译文：`、`> - 译文:` 等。
- 硬拦变体正反例见 `tests/test_selfcheck.py` 的 `R12HardBlockVariants`；其余 MEDIUM（宏观算式核原始操作数、链接不可达仍 PASS、FRED 嵌套 series_id、来源注释回放）记为 follow-up。

## 发布依据只有 route_pr（r17，王总定）

- **只有 `route_pr`（CLI `scripts/route.py --pr <编号>`）给出的结论才算发布依据。** 它只接受 PR 编号，PR head、稿件字节、sha、更正信息和原稿类别都由它自己从 gh 和 git 取，不接受调用方传进来的任何身份或更正信息。`publishable` 只在 `route_pr` 里设置。
- 直接 import 内部函数（`_route_one`、`_diagnose_from_git`、`_diagnose` 等）得到的结果不带 `publishable`，**不算发布依据**。
- 威胁模型 (c)：门禁只防误操作。有意 import 私有函数、伪造参数这类绕过记为 FOLLOW-UP，归 markjin-data#30（第 2 阶段签名）。

## r6：结论有效期（协调方 Grok Bot 定）

`scripts/route.py --pr` 的输出带 `decided_at`、`valid_until`（decided_at + 60 秒）与 `head_sha`。生产 bot 须在 `valid_until` 前发布，并在发布前用 `gh pr merge --match-head-commit <head_sha>` 再确认 head 与 PR 状态，否则重新路由。decided_at 之后到发布之间的空档记为 FOLLOW-UP（详见 docs/approvals.md“结论有效期与发布前再确认”）。
- **整体验收 r9 修复（王总定）**：front matter 用未规范化的原始行（保留缩进）交给 yaml.safe_load；解析出的类别全部参与类型判定——宏观、宗教类别也置位 macro / religion 标记（与正文词表取并集）。审批类型最终由 route.py 按路径、categories、正文词表三者取并集判定，未知类别照旧须王总批准。

- **整体验收 r10 修复**：(1) front matter 分类键只有一份定义 `scripts/markjin/fmkeys.py:FM_CATEGORY_KEYS`（categories、category、tags、tag、keywords、keyword、type、series、section、sections、topics、topic、kind、subject、subjects，大小写不敏感），selfcheck 与 route 共用，新增分类键只改这里。(2) front matter 解析出的 macro 类别先于整篇宏观判定置位，`is_macro_doc` 因此为真，整篇宏观观点硬拦（`E-BLOCK-MACRO-OPINION`）照常生效。(3) 依赖：`pip install -r requirements.txt`（PyYAML ≥ 6.0）。缺 PyYAML 时 selfcheck 记 `E-DEP-PYYAML` 硬错误（按医疗类处理），route 给结构化 HOLD（`E-DEP-PYYAML`，非零退出），不抛 `ModuleNotFoundError`。

- **整体验收 r11 修复**：(1) 同一句里每一个「算式：」都必须是一个能完整解析的算式起点，并逐个验算、检查后缀；任一处格式不对或结果不符，整句 `E-FORMULA-MISMATCH`。(2) **严格 JSON 入口清单**（重复键一律判失败，`object_pairs_hook`）：`selfcheck.load_lexicon`（词表，→ `E-SELFCHECK-LEXICON`）、`selfcheck` FRED 存档（→ `E-REPLAY-READ`）、`selfcheck` 其他原始 JSON 引文回放（X 等，→ 不可回放、判失败），以上用 `markjin/strictjson.py`；`approvals.parse_record`、`ledger` 台账行、`statechange.loads_strict`、`route` 读取 `gh pr view` 输出（#21/#22 分支，各自的 `object_pairs_hook`，见对应分支）。代码里不再有未带 `object_pairs_hook` 的 `json.load/json.loads`，tests 逐文件断言。

- **整体验收 r11 文档对齐**：宏观预测改为标明“历史口径 / 现行规则”；`route.MAC_STATUS_TTL` 注释改为“心跳过期 → 需审查稿一律 HOLD（`E-ROUTE-MAC-STALE`，可重试，不归档）”，与 `_diagnose` 一致；`route` 读取 `gh` 输出改用 `strictjson`（重复键 → `E-ROUTE-PR-FILES`）。
- **整体验收 r12 修复（数字核对范围）**：`check_pair` 判“来源支持”时只用被引用的那一条——arXiv / X 为 `select_entries` 按条目 id（及版本）选出的正文域；FRED 存档已按 series_id 绑定为单一系列（URL 不带 vintage），范围即该系列文件。同一 raw 里其他条目的数字不再算作支持。
- **整体验收 r13 修复（审查 bot 定）**：FRED 只在被引用的那一期观测里核数字（断言写观测日期则按 date 选；写 vintage 则再按 realtime_start/realtime_end 限定；多条观测且没写日期 → 不算支持；日期与 vintage 本身不当作要核对的数字）；带来源段落、非结构化行核对时带上断言原文（去掉 raw 路径与 URL），断言里有数字却不被引用条目支持 → R-SUPPORT-UNVERIFIED。
- **整体验收 r15 修复（审查 bot 定的技术方案）**：(1) front matter 统一用 yaml.safe_load 解析一次，更正稿元数据（corrects / corrected_at）与日期字段都按解析后的值判断，带引号与不带引号等价；(2) tongyi 长文豁免：front matter `type: tongyi` 且路径为 `tongyi/<name>.md`（站点 `content/posts/tongyi/<name>.md`）的稿件及其更正稿，不报日报专用的 E-INFER-UNCLEAR、E-REPLAY-001；硬拦（买卖建议、仓位、宏观观点、内部词表、X-only 等）照常；type 与路径只有一方是 tongyi → E-TONGYI-MISMATCH（fail-closed，照常跑日报检查）。理由：长文由 Codex 加王总 v2 direct 逐篇把关。`check_text` 新增 `rel` 参数，CLI 按稿件相对 --repo 的路径传入。

## 采集规则（PR #3 审查 REJECTED 修复，2026-10-12）

- 公共层 `markjin/collect.py`，`capture_sources.py` 只经它访问网络。
- **审批门禁**：只采集 `enabled: true` + `approval_status: approved` + 非空 `approval_basis` 的源；其他一律拒绝（`--only` 点名未审批源 → 退出码 1）。`approval_basis` 写法见 `improve/sources.yaml` 文件头。
- **许可**：所有源默认 `url+hash-only`。不再有整源或整域名（含 .gov/.mil）全文许可；整份 RSS/API 响应永不进公开目录。全文只能逐条目公开：须有针对该 URL 的许可证据（`url, license, license_url, evidence_url, attribution, verified_by, verified_at`，许可限 CC-BY-4.0 / CC0-1.0 / US-Gov-PD 且后者须 `third_party_excluded: true`），由 `collect.public_fulltext_ok` 在写公开目录前逐条校验，否则默认私有。
- **原件与只追加**：原字节不解压、不脱敏，按 sha256 独占创建写入私有 `raw/DATE/[round2/]<id>/<sha256>.<ext>`，追加私有 `MANIFEST.sha256`；解压等派生物写 `derived/` 并登记 `DERIVED.sha256` / `DERIVED-FROM.tsv`。公开目录每次运行只独占创建 `<id>/index-<run>.json`、`query-log-<run>.jsonl`、`failures-<run>.json`，追加公开 `MANIFEST.sha256`，任何已存在文件都不改写（字节不同 → `ArchiveError`）。
- **访问礼仪**：UA `markjin-collector/0.1 (+https://markjin-lab.github.io)`（不写死邮箱；SEC 另见下文）``；按站点限速（未公布限速的站点每站每分钟最多 1 次、跨进程共享；另有每主机下限 2 秒，`--interval` 须为有限数且不低于 2，否则退出码 2；robots `Crawl-delay`/`Request-rate` 更严则从严；见下文「封锁规则」规则 4），robots.txt 请求本身也限速；RSS/API 也查 robots；不自动跟随重定向，每一跳重新查拒绝主机（t.co）、源状态、主机停用与本轮停止、URL 冷却、robots 与限速。robots.txt 自身的跳转也逐跳查 scheme、t.co，跨主机跳转按禁止处理；robots.txt 返回 401/403/429、验证页或登录墙 → 与正文相同，该主机本轮停止（见下文「封锁规则」）；HTML 判断不只看 Content-Type，正文以 `<` 开头的标签片段（如 text/plain 下的 `<div>…`）也算；5xx 返回 HTML → 不重试，本轮按禁止；404/410 仍按“没有 robots”处理；robots 的每一跳请求前也过地址策略；不再逐条加厂商特征，rss/api 按采集方式校验内容：looks_html、rss 的 XML 根元素不是 rss/feed/RDF、api 应为 JSON 却解析不了（api 源可声明 `format: xml` + `xml_roots`），任一条都记 `suspected_challenge:<原因>`：算可疑（该主机本轮停止、URL 冷却）、不写成功索引（原字节仍私有存档）；通用验证短语（Check(ing) your browser、verify you are human、enable JavaScript and cookies 等，`collect.CHALLENGE_PHRASES`）在 title 和可见文本（去脚本/样式/标签）的前 2KB 里匹配，不看整页长度；Fetcher 每一跳、robots、fetch_primary、scrapers 共用；text/plain 正文以 HTML 标签开头单独不算可疑；XML 根元素按完整 QName（`{namespace}local`）比对，`xml_roots` 也写完整名字；含 DOCTYPE/ENTITY 的 XML 一律拒收；JSON 顶层必须是对象或数组；每一跳收到的原字节先私有存档（`hop_raws`），再决定丢弃或跳转；每一跳（含 3xx）拿到响应后先做验证页检测，命中即算可疑（该主机本轮停止），不处理 Location、不再抓正文。验证页识别只有 `collect.classify_page` 一份。**地址策略强制生效**：每个 Fetcher 都装有 `AddressPolicy`（不能关闭，外部策略只能叠加），初始 URL、DNS 结果、每一跳都拒绝本机/内网/链路本地/保留地址；出站经透明代理、DNS 返回 RFC 2544 假 IP（198.18.0.0/15 内的某个地址）时，用 `--proxy-fakeip-cidr` 或 `MARKJIN_PROXY_FAKEIP_CIDR` 显式声明该网段，只对主机名解析结果放行，IP 字面量永远拒绝。
- **拒绝与重试**：401/403、429、验证页（厂商组件或只命中短语）、登录墙、rss/api 格式校验不通过 → 算可疑：该主机本轮停止、URL 冷却 24 小时、给源记一次可疑，不重试（详见下文「封锁规则」）；收到任何 HTTP 状态（含 429、5xx）都不重发，只有网络错误有限重试；超过 25 MiB 明确失败，不存半截。
- **路径与日志**：私有根目录必须 `--private-root` 或 `MARKJIN_PRIVATE_DIR` 显式给出，且与公开根目录互不包含；代码中无本机默认路径。公开记录只写 `stored: private|internal`、错误类别和脱敏 URL（默认只写 `scheme://主机/#sha256=<完整 URL 的 sha256>`，路径也不写——路径里也可能有凭证；逐源确认路径不含凭证后在 sources.yaml 声明 `public_path: true` 才写路径；去 userinfo、片段和查询值，只记参数个数 `query_param_count`，不记参数名；某源确需公开的参数值，在 sources.yaml 里按源声明 `public_params`）；重定向 `hops[].from` 从一开始就只存脱敏 URL，私有日志同样不含凭证；需要免费密钥的 API 用 `auth_env`/`auth_param`，密钥只在请求时拼接，不进任何记录。
- **严格 JSON**：`capture_sources.parse_ok`、`collect.SourceHealth`、`collect.load_license_evidence` 用 `markjin/strictjson.py`（重复键 → 无法解析）。
- 测试：`tests/test_collect.py`（审批门禁、路径、URL 脱敏、逐条许可、只追加档案、robots/重定向/t.co、单次可疑即停该主机本轮、URL 冷却与按轮存储、5 轮 3 轮 → pending-disable 下一轮起生效、站点 60 秒跨进程限速、旧停用表迁移（`BlockRule1522`、`LegacyHosts`）、限速、超限、重复键）。`tests/fixtures/px_blocking_template.html` 是 PerimeterX 官方 SDK（perimeterx-python-wsgi）测试用的拦截模板样例，只用于离线识别测试。
## 采集辅助（2026-10-12；PR #6 审查 REJECTED 修复）

- `x_capture.py`：X 计划 / 额度预留 / 入账 / 补全 / 线索导出。**每次实际 X 调用（首页、翻页、`get_posts_by_ids` 补全）前必须 `reserve`**，入账只认已预留且未入账的 call_id；≤400 次 / UTC 日（00:00Z 重置）、≤25 次 / 滚动 60 秒。`plan --date --round` 必填并自动计算窗口（round1 = D−3 21:00Z，round2 = D−1 21:00Z）；查询完整参数写入状态，翻页从状态恢复。页数上限按 x-queries.md：账号批次 4 页、主题 2 页。`reserve` 预留时核对：search 必须是已计划 slug、`--page` 恰为下一页且不超上限；补全必须给 `--batch`（hydrate 批次号）；返回本次必须使用的完整参数并把其摘要 `args_digest`（及补全批次的 id 集合）绑定到 call_id，`ingest-hydrate` 拒绝批次外 id。进度按「日期 + 轮次 + slug」分开存，ids / posts / calls 两轮共用同一状态文件（round2 直接沿用 round1 的状态文件，跨轮按 id 去重，每日 400 次额度共享）。所有子命令都要私有根目录（`--private-root` 或 `$MARKJIN_PRIVATE_DIR`；与 `--out-root` 不重叠，且不能位于任何 git 工作树内，用 `git rev-parse --show-toplevel` 判断），`--state` 和 `--file` 都必须位于其下（如 `$PRIVATE/x/state.json`）；`leads` 先把待导出记录写进状态、再写档案、最后记 `exported_at`，中途失败下次运行自动核对恢复；I/O 错误只输出错误类别，不带私有路径；每条帖子保留首次采集的日期与轮次，再次采到时更新 public_metrics，并记录首次达到门槛的日期 `lead_date`；导出 `lead_date` ≤ 当天且尚未导出的帖子（私有状态记 `exported_at`，重复运行幂等；入账后才进白名单的帖子在导出时补记 `lead_date`），按 id 去重；`get_posts_by_ids` 的 `post.fields` 含 `public_metrics`，回填时同样更新互动数，按文档派生规则过滤（`like_count ≥ 20` 或 `retweet_count ≥ 5` 或作者在 from: 批次白名单），每条固定 `label: 线索`、`source_role: lead` 并写 `lead_reason`；结果写入私有档案 `raw/DATE/x/leads-<run>.json`（独占创建 + MANIFEST 只追加），stdout 只输出相对私有根目录的路径和条数。
  - r9：`--state`、`--file` 和 leads 输出目录（`raw/DATE`、`raw/DATE/x`）先解析符号链接，真实路径须在私有根内，再对真实路径做 git 工作树检查（根内嵌套仓库、经符号链接进入任何仓库都拒绝）。读状态→核额度→写状态整段在 `PRIVATE/state/locks/x-state.lock` 的 fcntl 排他锁内完成。`pending_export` 同时记档案 sha256；恢复时不论导出几条（含 0 条）都先核对档案哈希，再核对或补登 MANIFEST，最后记 `exported_at`；哈希不符、或旧状态没有 sha256，一律不认、照常重导；其中旧状态没有 sha256 但档案已写出的，按档案实际内容算 sha256 补登 MANIFEST（不据此标记已导出）。
- `fetch_primary.py`：按线索 `unwound_url`/`expanded_url` 抓一手 URL，全部经 `markjin/collect.py`（逐跳 robots/源状态/主机停用与本轮停止/URL 冷却/限速、不自动重定向、拒绝 t.co、401/403/429/验证页/登录墙即停该主机本轮、超限明确失败）。**域名不构成许可**：原字节与提取文本默认只进私有档案；仅当 `--license-evidence` 中针对该*完整* URL（含全部查询参数，不按脱敏 URL）且 `sha256` 与本次响应一致的逐条目证据通过 `public_fulltext_ok`（原 URL 与最终 URL 各自要有证据），原字节与带署名头的 `.txt` 才进公开目录，证据（url / evidence_url / license_url 均经 public_url 脱敏）随条目写入公开 index；`stored=private` 的条目在公开 index 里不写 `title` 等正文派生字段。外部传入的 Fetcher 自带地址策略时，与强制策略合取。**公开 `leads-primary` 不含帖文**：只留帖子 id/URL（只有规范正整数帖子 id 才写，`0012` 之类前导零拒绝，输入里的 url 从不复制）、帖文 sha256、一手 URL（默认只写主机 + 完整 URL sha256；逐条许可证据核实后 index 才写路径）与 sha256、`fetch_status`、线索身份字段；完整线索进私有 `primary/leads-<run>.json`；私有 fetch-log 也只写脱敏 URL。**目标地址策略**（`collect.AddressPolicy`）：初始 URL、DNS 解析结果、每一跳都拒绝本机/内网/链路本地/保留/组播地址，被拒时不发任何请求（含 robots.txt）。例外仅一处：出站经透明代理、DNS 返回 RFC 2544 基准网段内的假 IP 时，须用 `--proxy-fakeip-cidr 198.18.0.0/15` 或 `MARKJIN_PROXY_FAKEIP_CIDR` 显式声明；只接受 198.18.0.0/15 内的网段，只对主机名解析结果生效，IP 字面量（含 198.18.x.x）永远拒绝，混有其他非公网地址仍拒绝。残余风险：该模式下真实目标 IP 由代理远端解析，本地无法核对（若公网 DNS 把某主机名指向内网，需由代理侧拦截）；非代理模式下检查与连接之间仍存在 DNS 重绑定窗口。线索保持 `label: 线索`，抓取结果只写 `fetch_status`，`primary_verification` 恒为 `unverified`——HTTP 200 不等于核验。公开输出按运行戳独占创建并登记 MANIFEST；URL 先脱敏。
- `scrapers/`：`method: scraper` 的列表页/官方 sitemap 解析器。网络请求全部由 `capture_sources.run_scraper` 提供的 fetch 完成：每个请求（含子 sitemap）逐个查 robots/源状态/主机停用与本轮停止/URL 冷却/限速，原始响应先按字节私有存档并登记 MANIFEST；条目 JSON 只作派生物（`derived/…items-<run>.json`）。无 JS、无 cookie、遇验证页即停该主机本轮，不绕过。sitemap 返回 200 时根元素必须是 sitemaps.org 命名空间（`http://www.sitemaps.org/schemas/sitemap/0.9`）下的 urlset 或 sitemapindex，含 DOCTYPE/ENTITY 拒收，sitemap index 嵌套超过一层报错（不当成 0 条），否则 ScrapeError；每次响应的原字节（含 robots、重试、跳转与验证页）先私有存档，scraper 无论成功、无条目还是出错，都在私有 fetch-log 里统一写一条带 `hop_raws` 的记录；子 sitemap 只有 robots 不允许或 404/410 才跳过；challenge、401/403/429、源被拦、主机已停、URL 冷却、地址被拒都会向上抛出，本轮记为失败、不写成功索引。
- 严格 JSON 入口（新增）：`fetch_primary` 读取 leads、`x_capture` 读取状态/查询/工具结果，均用 `markjin/strictjson.py`。
- 测试：`tests/test_primary_x.py`（scraper 原件存档与子 sitemap robots、许可分流与逐条证据、重定向后许可、t.co/403 停该主机本轮、⑩ 按被拒那一跳的主机计数、超限、不可改写、线索身份、X 预留/翻页/页数/每分钟与 UTC 日预算、重复键）。

## SEC（*.sec.gov）

- UA 必须从环境变量 `MARKJIN_SEC_USER_AGENT` 读取，且要带联系方式（邮箱或网址）；代码里不写死任何邮箱。
- 未设置（或不含联系方式）时，SEC 的请求一律不发，源记为 `not_configured`（写进 `skipped-<run>.json`），不算失败，也不算可疑。
- SEC 所有主机共用一个全局限速桶：每秒最多 5 次（SEC 公示上限是 10 次/秒，留了余量），同时仍受每主机 2 秒的下限约束。

## 封锁规则与来源健康状态（现行版，取代 r8–r12 的「持久停用主机」和 13:51 初版「单次只让该 URL 失败、连续 3 轮待停用」）

出处：王总 10-18 13:50 决定切回正常模式、恢复 #3/#6（14:15 改为立即生效）；封锁细则由 Grok Bot 定，10-18 13:51 初版，15:22 按审查意见收紧为现行版，底线是王总 10-11 确认的『遇到拦截即停』。

- **可疑响应**：HTTP 401/403、429、验证页（`classify_page` 返回 `vendor` 或 `phrase`）、登录墙（跳到登录页 `is_login_url`，或不跳转、返回 200 等状态的登录页：登录标题加表单与密码框，`login_page`）、rss/api 格式校验不通过。robots.txt、每一跳重定向、正文一视同仁。收到任何 HTTP 状态都不重发（429、5xx 也不重试）；只有没收到响应的网络错误有限重试（`NET_RETRIES`）。
- **规则 1，单次即停该主机**：一次可疑 → 该主机本轮全部停止（私有 `state/source-health.json` 的 `host_stops.<轮次>.<主机>`，跨进程生效），同主机的其他 URL、其他源本轮都不再请求（`host_stopped_this_round`，列入 `skipped-<run>.json`，不另算可疑）。
- **规则 2，URL 冷却 ≥24 小时**：被拒的 URL 记入 `urls.<轮次>`（只存规范化 URL 的 sha256：scheme、主机小写，去默认端口，空路径补 `/`，去 fragment），24 小时内任何轮次都不再请求（`url_cooldown`）。经重定向时，最初请求的 URL 和返回可疑响应的那一跳都记冷却；但本轮停止的只是返回可疑响应那一跳的主机，起点主机不停（r15 ⑤：doi.org 跳到出版商 403，同轮其他 DOI 照常）。记录按轮次分开存，补跑 r1 不会清掉 r2 的记录；只保留最近 10 轮。查记录、发请求、写记录在同一把按 URL 的跨进程文件锁内完成（`state/locks/urls/`），两个进程不会同时请求同一 URL；rss/api 格式校验也在锁内（r15 ④）。站点限速锁里等待结束后、发送之前重跑完整预检（旧表停用、源状态、本轮主机停止、URL 冷却），可疑分类与停止写入也在站点限速锁内完成，「写停止」与同站「发请求」互斥（r15 ①）。超过 25 MiB 的 401/403/429 先按状态码判可疑、停主机，再报 `too_large`（r15 ③）。
- **规则 3，5 轮 3 轮 → pending-disable**：每轮结束，`capture_sources` 只给本轮实际发过请求的源记一轮（轮次 id `YYYY-MM-DD/rN`；同一轮重跑按「任一次可疑即可疑」合并）。最近 5 个记录轮里有 3 轮可疑（不要求连续）→ `pending-disable`，**从下一轮起**生效：触发的那一轮照常跑完，下一轮起该源不再请求（`source_blocked`），每轮报告继续列出。被主机停止、冷却、停用跳过而没发请求的源不记轮。
- **当天汇报显眼可见**：当轮有 pending-disable 的源时写 `source-health-<run>.json`（条目带 `flag: grok-bot-review`）和 `GROK-BOT-REVIEW-<run>.md`（公开源写公开目录、internal_only 源写内部目录；列源 id、是否本轮新转入、最近 5 轮可疑轮数、触发轮、最近原因，不含 URL）；stderr 末尾打一行 `=== 待 Grok Bot 复核（pending-disable）N 个源：… ===`，最后一行 `done: … pending_disable=N`。写当天 `capture-failures.md` 时照抄，报给 Grok Bot，等人工确认。
- **规则 4，限速**：没有公布限速的站点每站（`site_of`，按可注册域名近似）每分钟最多 1 次，跨进程共享（`state/locks/rate-site-<站点>.lock`），robots.txt、每一跳都算。只有 `improve/sources.yaml` 顶层 `site_rate_limits: {站点: {min_interval_s, basis}}` 写明公布限额和依据的站点按其限额（缺 `basis` → 配置错误，退出码 2）。SEC 按其公布的 5 次/秒（0.2 秒）。robots `Crawl-delay`/`Request-rate` 更严则从严。限速锁文件损坏（不是 `{"site": 数, "hosts": {主机: 数}}`）→ 拒绝本次请求并报 `rate_lock_invalid`，不当空桶放行（r15 ⑥）。
- **规则 6，旧停用表**：私有 `state/collector-hosts.json`（旧版按主机持久停用）里还有未迁移条目时，`capture_sources`、`fetch_primary` 和 `source_health.py`（`migrate` 除外）一律拒绝运行（退出码 2，不发请求）。先跑 `scripts/source_health.py migrate`：每个主机导入为「已停用（等人工复核）」（`hosts.<主机>.status = disabled`、`review = pending-manual-review`，原因保留原文），不自动恢复，不计入 5 轮 3 轮计数。按原文归类：验证页 → `bot_check`，401 或登录 → `login`，403 → `http_403`，其他 → `other`；`bot_check`、`login` 额外标 `unrecoverable`。这些主机一律不发请求，包括 robots.txt 和经跳转到达（`host_disabled`）。迁移按旧文件 sha256 幂等；旧文件不改不删；旧文件损坏时拒绝运行。
- **人工操作**：`source_health.py confirm-disable --id <id> --reason "<谁确认、依据>"` → `disabled`；`enable --id <id> --reason …` 或 `enable --host <主机> --reason …` → 恢复为 `ok`；`unrecoverable`（因验证页或登录墙停用）的主机和源永不恢复，没有放行开关，只能改 `sources.yaml` 并重新审批；`report` 查看当前状态（只打到终端，可含人工 `--reason` 与旧表原因原文）。
- **公开输出只写固定代码（r15 ⑦）**：`skipped-<run>.json` 的 `detail`、`source-health-<run>.json`（`reason_code`、各轮 `reasons`）和 `GROK-BOT-REVIEW-<run>.md` 只写固定代码（如 `source disabled:manual-confirm`、`host disabled:legacy-import:bot_check:unrecoverable`、`suspected_challenge:xml_root`）；旧表停用原因、人工 `--reason` 等自由文本只留在私有状态文件。
- **状态文件**：不要手改。读取严格校验：`version` 必须是整数 2，顶层只能是 `version`、`sources`、`urls`、`host_stops`、`hosts`、`legacy_imports`（缺键、多键都算损坏），每条源记录必须带 `sid`。损坏或读不了时拒绝一切请求，也拒绝改写；`report()` 读失败直接报错。
- `fetch_primary.py`（须给 `--round 1|2`；来源健康状态更新失败时退出码 1，让上层停下）：同样遵守上面的规则 1–4、6（单次可疑停该主机本轮、URL 冷却、站点限速、旧表停用主机不请求）。文章按**返回可疑响应的那一跳**的主机归入伪源 `primary:<主机>` 计数（r14 ⑩：经跳转到别的主机被拒，记在被拒的主机上，不记在起点主机上），与 sources.yaml 的源分开计数；但主机停止是按主机的，本轮对所有源都生效。伪源最近 5 轮 3 轮可疑同样转为 `pending-disable`（下一轮起），报告写在公开 `primary/source-health-<run>.json`，当轮另写 `primary/GROK-BOT-REVIEW-<run>.md`，stderr 打出「待 Grok Bot 复核」一行，summary 行带 `pending_disable=N`。scraper 源与 rss/api 源同样按源计数，子 sitemap 被拒算该源可疑，列表页主机已停或列表页冷却时整源本轮跳过。
- 永不绕过付费墙、登录或验证：不重试、不换 UA、不跑 JS、不带 cookie。

## 验证页识别

- 先按状态码：HTTP 403、401、429（robots 与每一跳都一样）直接判可疑，不再看正文。其余按 `classify_page(ctype, body, headers, url)` 分 `vendor`（厂商组件，高置信）和 `phrase`（疑似），robots、正文、每一跳同一套；两者后果相同（该主机本轮停止、URL 冷却），区分只为报告写清原因。响应 URL 传入分类器，`src` 一律 `urljoin` 补全后核对同源（scheme + 主机 + 端口），相对、协议相对 `//a.org/…`、同主机绝对地址都认，其他主机不认。高置信标记：响应头 `cf-mitigated: challenge`；Cloudflare——script src 或 `x.src = '…'` 指向 challenges.cloudflare.com 或本站 `/cdn-cgi/challenge-platform/h/<字母>/orchestrate/`（`/cdn-cgi/challenge-platform/scripts/jsd/` 是注入正常页面的检测脚本，不算）、不在引号里的 `window._cf_chl_opt =`、class `cf-turnstile`；reCAPTCHA/hCaptcha——class `g-recaptcha`、对应 api.js；Incapsula——`<script src>` 指向本站 `/_Incapsula_Resource`，或 `<iframe src>` 指向本站 `/_Incapsula_Resource?…` 且正文含 “Incapsula incident ID”；PerimeterX——script src（含赋值）指向 captcha.px-cdn.net / captcha.px-cloud.net、meta description 为 `px-captcha` 且标题为 “Access to this page has been denied”、`div#px-captcha` 且整页可见文本 ≤1000 字符；`form#challenge-form`。单独的 `window._pxAppId =` 是正常页面的 Sensor，不算（r13）。没闭合的 `<script>` 永不算高置信：内容里混入 HTML 标签（如 `<pre>`）时不判定，纯脚本命中标记只算 `phrase`（r13）。script 内容先去掉字符串字面量和注释。免检只有 `<textarea>`/`<xmp>`/`<plaintext>`/`<title>`、注释和可见文本；`<pre>`/`<code>` 照常检查。`data-class`/`data-src` 不算。
- 泛用短语（`CHALLENGE_PHRASES`）只在 HTML 形态的正文里匹配，且只看 title，或可见文本很短（≤512 字符）且短语占一半以上；只命中短语（包括 text/plain 以标签开头再加短语）→ `suspected_challenge`，算可疑。
- JSON / XML 只做格式校验：格式不对记 `suspected_challenge:<原因>`，算可疑。XML 用 `xml.parsers.expat` 按编码与语法检查（含 UTF-16、DOCTYPE 引号里的 `>`）：`StartDoctypeDeclHandler` 的 has_internal_subset 为真即拒收，`EntityDeclHandler` 见到实体声明即拒收，未声明的实体引用也拒收；外部 DOCTYPE（如 pubmed、RSS 0.91）放行但不加载。
- RSS 兼容边界：允许外部 DOCTYPE，但不联网加载、也不加载其中声明的实体；正文里直接写 `&nbsp;` 这类外部 DTD 实体的文档会被拒收——算可疑（格式错误）。转义写法 `&amp;nbsp;`、CDATA、数字实体 `&#160;` 正常通过。
- robots.txt 返回 HTML 但无厂商标记（401/403/429 以外）：本轮按禁止处理，不算可疑。
- 每收到一次响应（含 robots.txt、429/5xx、3xx）都先交给 `raw_sink` 私有存档，再做判定。
- SEC 站点限速同样走跨进程文件锁（私有目录 `state/locks/rate-site-sec.gov.lock`，fcntl）：同一时间只有一个实例在请求 SEC，间隔按锁文件里的时间戳控制。 SEC 的 UA 或 `lock_dir` 缺一个，`_raw()` 就返回 `not_configured`、不发请求（get、robots、直接调用都一样），不算可疑。锁文件里同时记站点上次请求时间和每台主机上次请求时间，站点间隔（SEC 0.2 秒）与单主机间隔（≥2 秒，含 Crawl-delay）都在锁内执行，跨进程有效。
