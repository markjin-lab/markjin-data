# 错误码表

由 `scripts/markjin/codes.py` 生成（`python3 scripts/gen-error-codes.py`），以代码为准。台账只能引用本表登记的错误码。

| 错误码 | 含义 |
|---|---|
| `E-REPLAY-001` | 断言缺少来源链接或 raw 存档路径 |
| `E-REPLAY-002` | 引用的 raw 存档文件不存在 |
| `E-REPLAY-003` | raw 存档未登记在 MANIFEST.sha256 或哈希不一致 |
| `E-REPLAY-004` | 来源标识（arXiv id / X post id / FRED 序列）在存档中找不到 |
| `E-REPLAY-005` | 来源 URL 类型未知（只接受 arXiv abs / X status / FRED series），直接失败 |
| `E-REPLAY-006` | 来源未与 raw 文件绑定（raw 与 URL 不成对、不在目标日期目录、类型不一致或路径非法） |
| `E-REPLAY-SYMLINK` | raw 路径（含祖先目录）或 MANIFEST 是符号链接，一律拒绝 |
| `E-REPLAY-VERSION-UNCLEAR` | arXiv 链接无版本号，而存档里该 ID 有多个版本：判为不确定（UNCLEAR，不发布） |
| `E-REPLAY-READ` | raw 存档或 MANIFEST 读取/解码失败 |
| `E-MANIFEST-PARSE` | MANIFEST.sha256 格式非法（非法行、重复路径、路径越界或为空） |
| `E-INFER-UNCLEAR` | 无法判别是否含推断（断言无来源结构），按分类不明处理 |
| `E-COUNT-001` | 稿件中手写的计数与脚本生成的计数不一致 |
| `E-COUNT-002` | counts 注释格式非法（多个注释、未知键、重复键、非法值或非整行） |
| `E-BLOCK-INVEST` | 含投资措辞（股票代码、买入/卖出、仓位、目标价等） |
| `E-BLOCK-MACRO-OPINION` | 宏观内容含观点或仓位表述 |
| `E-FORMULA-MISMATCH` | 宏观算式验算失败（表达式非法，计算结果与写出的值按其小数位舍入后不一致，或算式字段在分隔符/来源标记前还有未验算的后缀） |
| `E-X-ONLY` | 日报中的断言（原文直引、结构化断言、带来源的行）只有 X 来源支撑，或虽另列非 X 来源但没有一条经核对实际支撑该断言（#32，迁移自旧库 #51）；X 只作线索，硬拦 |
| `E-SUPPORT-LOCATOR-MISSING` | 日报断言的非 X 来源没有写明原文支持位置（〔原文：…〕），或断言写在无法标注位置的非结构化行里（#32） |
| `E-SUPPORT-LOCATOR-MISMATCH` | 原文支持位置不是所引条目原文的连续子串，或断言中的数字、指标/对象术语未全部出现在该位置（#32）；语义是否支持仍由 Codex 审查 |
| `E-BLOCK-INTERNAL` | 命中仅供内部研究的主题（细节只记本机内部目录） |
| `E-INTERNAL-LIST-MISSING` | 本机内部主题清单缺失、不可读或结构不完整，无法完成内部主题检查 |
| `E-SELFCHECK-INPUT` | 稿件为空 |
| `E-DEP-PYYAML` | 缺少运行依赖 PyYAML（requirements.txt）：无法解析 front matter，结构化判失败 / HOLD，不直接崩溃（整体验收 r10） |
| `E-TONGYI-MISMATCH` | front matter type 为 tongyi 与稿件路径（tongyi/<name>.md 或 content/posts/tongyi/<name>.md）不一致：fail-closed，不给长文豁免（整体验收 r15，审查 bot 定） |
| `E-SELFCHECK-FM-ALIAS` | front matter 含 YAML 锚点（&）、别名（*）或合并键（<<），或无法按 yaml.safe_load 解析为映射：fail-closed 判失败，并按医疗类处理（r8） |
| `E-SELFCHECK-READ` | 稿件无法读取或不是合法 UTF-8 |
| `E-SELFCHECK-CARDTYPE` | card_type 未显式给出或取值非法（只接受 daily / signal） |
| `E-SELFCHECK-DATE` | 目标日期未显式给出或不是真实日历日期 |
| `E-SELFCHECK-LEXICON` | 公开词表 lexicon.json 缺失、不可读或结构非法 |
| `E-SELFCHECK-REPO` | 仓库根目录未显式给出或不存在 |
| `R-INFERENCE` | 含推断、判断、转述或情态措辞（may/could/might/suggest/likely、可能/或将/有望；直引里也算），非低风险 |
| `R-UNSTRUCTURED` | 断言不是结构化复述格式（引用块、表格行等） |
| `R-SUPPORT-UNVERIFIED` | 无法由机器确认来源支持该断言（断言中的数字未全部出现在 raw 存档） |
| `R-LINK-UNCHECKED` | 未检查来源链接能否打开（未提供链接检查器，如离线运行） |
| `R-STRUCTURE` | 正文出现低风险结构白名单（标题 / 原文直引 / 来源链接）以外的块，非低风险，转 Codex 审查 |
| `R-QUOTE-UNVERIFIED` | 原文直引逐字核对不通过（不是该来源条目原文的连续子串、太短，或非日报），非低风险 |
| `R-LINK-UNREACHABLE` | 来源链接打不开 |
| `R-NO-ASSERTION` | 没有任何可回放的结构化断言 |
| `R-SIGNAL-CARD` | 信号卡 |
| `R-MACRO` | 宏观内容（整篇判定） |
| `R-MEDICAL` | 医疗相关内容（含中医、佛学及针灸、中药、经络、方剂等中医疗法词）：可以公开，但不算低风险 |
| `R-TRANSLATION` | 译文内容（含“译文：”行或 *.en.md 稿件）：不算低风险，须 Codex 审查（t141u） |
| `R-RELIGION` | 佛学等宗教内容：可以公开，但不算低风险 |
| `R-STOCK` | 股市主题内容（含纯事实直引，如个股收盘价）：可以公开，但永不低风险 |
| `R-QUOTE-NUMERIC` | 直引含数字、百分比、分数、倍数、货币或价格词：移出低风险（结构性收紧，不硬拦） |
| `R-QUOTE-COMPARATIVE` | 直引含比较级或评价性比较（than、better、superior、outperform、优于、超过、更、最…）：移出低风险 |
| `R-QUOTE-MODAL` | 直引含情态或预测词（will、should、can、may、expect、将、会、应该、可能…）：移出低风险 |
| `R-QUOTE-ENTITY` | 直引含全大写词/股票代号、句中大写开头的专有名词或驼峰名（公司、机构、人名）：移出低风险 |
| `R-X-ONLY` | 只有 X 来源（日报断言另判 E-X-ONLY 硬拦；此标记仍用于纯来源链接行与信号卡） |
| `E-ROUTE-UNCLEAR` | 分类不明，当天不发布 |
| `E-ROUTE-SELFCHECK-FAIL` | 自检失败，当天不发布 |
| `E-ROUTE-NO-CODEX` | 缺少 Codex 审查记录或 VERDICT 不是 APPROVED，王总批准不足以发布 |
| `E-ROUTE-NO-WANG` | 缺少王总批准记录 |
| `E-ROUTE-LINK-UNREACHABLE` | 来源链接打不开（HTTP 错误，或网络问题重试一次后仍不通）；route_pr 判 HOLD，detail 写明 URL 与原因 |
| `E-ROUTE-LINK-UNCHECKED` | 来源链接未检查；route_pr 不允许关闭链接检查，判 HOLD |
| `E-ROUTE-FRONT-MATTER` | 稿件 front matter 不是合法 YAML 映射（r16：用 yaml.safe_load 解析，失败即判失败） |
| `E-ROUTE-CORRECTION-INVALID` | 更正稿 front matter 的 corrects / corrected_at 缺一或为空 |
| `E-ROUTE-CORRECTION-TARGET` | 更正稿的 corrects 与本稿 draft_id 不一致，或站点仓库 origin/main 上查不到原稿（未发布）、原稿 front matter 无日期、内容未变 |
| `E-ROUTE-CORRECTION-DATE` | corrected_at 不是 YYYY-MM-DD，或早于原稿日期、晚于实际发布当天（SGT） |
| `E-ROUTE-CORRECTION-NOTE` | 更正稿的标题行（渲染后可见文字，链接目标、图片、HTML 属性不算）没有注明 corrected_at 更正日期 |
| `E-ROUTE-CORRECTION` | 更正稿被拦住（如 codex_in_production 为真），不归档原稿 |
| `I-CORRECTION` | 更正稿：不受 06:55 / 07:00 与顺延限制，其余检查照常 |
| `E-ROUTE-RECORD-INVALID` | approvals/ 记录文件解析失败或有行不符合严格 schema（整份文件不采信） |
| `E-ROUTE-RECORD-MISMATCH` | 批准记录与稿件不符：draft_id 不一致，或渠道不符合要求（信号卡、tongyi 只接受 direct） |
| `E-ROUTE-RECORD-EXPIRED` | 批准记录过期：王总记录时间非法、晚于当前时间或不是当天（Asia/Singapore 日历日）；Codex 记录早于稿件日期、早于更正时间，或顺延稿的 Codex 记录不是可发布日当天（前一日记录作废，r7） |
| `E-ROUTE-RECORD-V2-REQUIRED` | 需要王总批准的稿件（宏观、医疗、宗教、tongyi、信号卡）只接受带 quote_ref、绑定 draft_id 的 v2 记录；信号卡、tongyi 与真实发信还须 direct |
| `E-ROUTE-APPROVALS-REWRITTEN` | approvals/ 历史被改写（不是只追加），记录不采信 |
| `E-ROUTE-ARCHIVE-REVERTED` | 发布状态历史中已归档条目被修改或删除，拒绝 |
| `E-ROUTE-RECORD-INTERNAL` | 批准记录的自由文本字段命中内部清单，该类记录全部不采信 |
| `E-ROUTE-RECORD-LATE` | 王总批准记录（或 Codex 记录的 reviewed_at）晚于可发布日 06:55（SGT）审查截止（route.CUTOFF），不采信 |
| `E-ROUTE-PR-SCOPE` | 稿件 PR 夹带了稿件与 raw/<日期>/ 数据证据（含 MANIFEST.sha256）以外的改动（规则、代码、路线图、模板、配置、审查与批准记录等）：不可发布，这些改动单独走 PR（B4，r7） |
| `E-ROUTE-PUBLISH-LATE` | 已过可发布日 07:00（SGT，route.PUBLISH_DEADLINE）发布截止：首次逾期一律顺延到次日，顺延稿再逾期则归档 |
| `E-ROUTE-DEFERRED-SAMEDAY` | 顺延稿须在次日（SGT）及以后再路由，同日再跑 HOLD |
| `E-ROUTE-RECORD-ORDER` | 王总批准记录早于 Codex 审查完成时间（recorded_at < reviewed_at），不采信 |
| `E-ROUTE-DEFER-MISMATCH` | 顺延记录的 content_sha256 或原日期与当前稿件不一致：HOLD（顺延不能挪给别的内容或日期） |
| `E-ROUTE-NOT-YET` | 未到可发布日（稿件日期在未来），HOLD，不得提前自动批准 |
| `E-ROUTE-MAC-STALE` | 需审查稿：Mac 心跳超过 30 分钟未更新（状态未知），HOLD，可重试，不归档（不需要王总批准且已有有效 Codex APPROVED 的日报不受心跳影响） |
| `E-ROUTE-PAIR-MISSING` | 只有 <name>.en.md、没有同 PR 的 <name>.md（t145u） |
| `E-ROUTE-DISCLAIMER-MISSING` | 日报缺少固定免责声明（中文「本文不含投资建议。」/ 英文 "This article does not constitute investment advice."），不得发布 |
| `E-ROUTE-RETRY` | 判定可能已失效，整批 HOLD、重跑：开始时与结束时（end，即 decided_at）两遍判定结论（state/codes）不一致（如心跳在路由期间过期），开始到 end 之间跨过 06:55 / 07:00 / SGT 午夜，或记下 decided_at 之后核对发现远端 main 已变化（整体验收 r3–r6，r7） |
| `E-ROUTE-PR-FILES` | PR 稿件组合不合法：只允许单篇 <name>.md，或同 section、同 name 的 <name>.md + <name>.en.md |
| `E-ROUTE-PAIR-MISMATCH` | 中英配对的 Codex 记录 pair_sha256 未互相引用、reviewed_at 不同，或单篇稿使用了配对记录 |
| `E-ROUTE-PAIR-INCOMPLETE` | 中英配对中另一版缺 Codex 记录、未 APPROVED 或本身不可发布：两版都不得发布 |
| `E-ROUTE-DRAFT-PATH` | 稿件路径不符合 <section>/<name>.md 规则（section 只含小写字母与数字，不含 -），无法得出 draft_id |
| `E-STATE-CHANGE-INVALID` | 状态变更格式不合法或违反写回规则（如二次顺延） |
| `E-STATE-CHANGE-STALE` | 心跳 updated_at 早于状态文件中的现有值，拒绝 |
| `E-ROUTE-INPUT` | 路由入口参数缺字段、类型不对或为 None，拒绝 |
| `E-ROUTE-STATE` | main 分支发布状态文件缺失、不可读或不合法，拒绝 |
| `E-ROUTE-ARCHIVED-REUSE` | 已归档稿件被再次提交为可发稿 |
| `E-ROUTE-HARD-REJECT` | internal-only 内容，发布与 newsletter 硬拒绝 |
| `A-MAC-OFFLINE` | 归档：Mac 离线 |
| `A-NOT-APPROVED` | 归档：未获批 |
| `A-NO-REVIEW-PATH` | 归档：无审查路径（Codex 参与生产） |
| `A-OVERDUE-TWICE` | 归档：二次逾期（顺延稿在可发布日 07:00 仍未发布，且已获批） |
| `E-LEDGER-FIELD` | 台账写入含白名单外字段，已拒绝 |
| `E-LEDGER-VALUE` | 台账字段值不合法，已拒绝 |
| `E-LEDGER-DATE` | 台账日期不是真实日历日期，或与文件名日期不一致 |
| `E-LEDGER-DIR` | review/ledger/ 目录缺失 |
| `E-LEDGER-FILE` | review/ledger/ 下出现白名单以外的文件（只允许 .gitkeep 与 YYYY-MM-DD.jsonl） |
| `E-LEDGER-EMPTY` | 台账文件为空 |
| `E-REVIEW-FORMAT` | review/ 日审记录、轮次文件或 Codex 日志格式不合规（大小、控制字符、内部路径、首行/VERDICT 行格式） |
| `E-REVIEW-PATH` | review/ 下出现白名单以外的路径 |
| `E-CHECK-EMPTY` | 给出的 --rev/--range 解析后没有任何提交，拒绝报告通过 |
| `E-LEDGER-CARD` | 台账 card_id 在公开稿件中没有对应锚点 |
| `E-CHECK-GIT` | 守卫无法读取 git 对象（git 调用失败、子模块或对象缺失），按失败处理 |
| `E-CHECK-STDIN` | pre-push stdin 为空或格式异常，或未指定检查目标，拒绝推送 |
| `E-CHECK-DECODE` | 路径、文件内容或提交说明不是合法 UTF-8，或二进制类型文件（.pdf/.jpg/.jpeg/.png/.gif/.webp，不论能否解码）未登记，拒绝（不跳过）；唯一例外：raw/<日期>/ 下已在同一提交树的 raw/<日期>/MANIFEST.sha256 按字节 sha256 登记、扩展名为 pdf/jpg/jpeg/png/gif/webp 的二进制原件 |
| `E-PUBLIC-INTERNAL-PATH` | 内部材料路径被 git 跟踪 |
| `I-AUTO-APPROVED` | 已停用（王总 t161u：日报一律过 Codex，不再有自动批准）；路由不再产生；台账只许记 count=0，非零判 E-LEDGER-VALUE（r11） |
| `I-NEEDS-REVIEW` | 计数：尚未取得有效 Codex APPROVED（及按类型要求的王总批准）的稿件 |
| `I-DEFERRED` | 计数：顺延 1 天的稿件 |
