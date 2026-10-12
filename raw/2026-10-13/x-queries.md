# markjin X query set v2（P0 新源接入；生效 2026-10-12 起）

> 2026-10-13 round1 snapshot: start_time = 2026-10-10T21:06:00Z (now − 48h, 05:06 SGT). Pagination: A ≤4 pages, B ≤2 pages. Internal query set: not run (no internal query file present this round).

来源：source-research/report.md 第四节（123 个已核验账号，x_all.tsv active30d=Y 全部覆盖）+ 第五节分主题查询。旧版保存为 x-queries.v1.md。

## 通用参数

- 工具 `x.search_posts_all`；`post.fields=created_at,author_id,public_metrics,entities`，`expansions=author_id,attachments.media_keys`，`user.fields=username`。链接匹配用 `entities.urls[].unwound_url`/`expanded_url`，不用 t.co。
- `max_results=25`；from: 批次按 recency，主题查询按 relevancy。
- **round1（05:00 SGT）**：`start_time = now − 48h`。**round2（06:00 SGT）**：`start_time = 当日 05:00 SGT（前一 UTC 日 21:00Z）`，与 round1 按 id 去重。
- 所有查询都带 `-is:retweet -is:reply`；每条 ≤512 字符（实际最长 375）。
- **`min_faves` 在当前 API 套餐不可用**（2026-10-12 00:1x SGT 实测：`Reference to invalid operator 'min_faves'`），报告中的 min_faves 条件全部去掉，改为在派生过滤阶段按 `public_metrics.like_count ≥ 20 或 retweet_count ≥ 5 或作者在白名单` 过滤（白名单 = 下列 from: 批次的全部账号）。
- 报告中已被 from: 批次完全覆盖的主题查询（如 `from:NickTimiraos` 的 FOMC、`from:BLS_gov/BEA_News`、`from:CERN/Fermilab/PhysRevLett`、`from:SECGov/HKEXGroup`、`from:CopernicusECMWF/hausfath`、`from:planet4589/jeff_foust/SpaceX`）不单独发请求。
- 旧版中不在 123 名单内的账号（如 xai、NatureNews 不存在/异常；OpenAIDevs、JeffDean 等未入核验名单）已移出；如需保留请单独补核验。

## A. from: 账号批次（7 条）

| # | slug | 主题 | 账号数 | query |
|---|---|---|---|---|
| A01 | accounts-01 | AI 前沿 | 18 | `(from:karpathy OR from:ylecun OR from:demishassabis OR from:AndrewYNg OR from:OpenAI OR from:AnthropicAI OR from:GoogleDeepMind OR from:AIatMeta OR from:deepseek_ai OR from:Alibaba_Qwen OR from:huggingface OR from:_akhaliq OR from:jackclarkSF OR from:EpochAIResearch OR from:SemiAnalysis_ OR from:dylan522p OR from:natolambert OR from:simonw) -is:retweet -is:reply` |
| A02 | accounts-02 | AI 前沿 / 宏观投资 | 18 | `(from:fchollet OR from:polynoamial OR from:DrJimFan OR from:emollick OR from:Miles_Brundage OR from:Yoshua_Bengio OR from:sama OR from:federalreserve OR from:NewYorkFed OR from:FedResearch OR from:BLS_gov OR from:BEA_News OR from:ecb OR from:bankofengland OR from:IMFNews OR from:NickTimiraos OR from:elerianm OR from:jasonfurman) -is:retweet -is:reply` |
| A03 | accounts-03 | 宏观投资 / 物理与前沿科学 | 18 | `(from:Brad_Setser OR from:michaelxpettis OR from:adam_tooze OR from:TheStalwart OR from:lisaabramowicz1 OR from:biancoresearch OR from:LizAnnSonders OR from:SoberLook OR from:Lingling_Wei OR from:niubi OR from:ChinaBeigeBook OR from:georgemagnus1 OR from:M_C_Klein OR from:EconBerger OR from:CERN OR from:Fermilab OR from:APSphysics OR from:PhysRevLett) -is:retweet -is:reply` |
| A04 | accounts-04 | 物理与前沿科学 / 公共卫生/医学 / 股市 | 18 | `(from:PhysicsMagazine OR from:QuantaMagazine OR from:Nature OR from:ScienceMagazine OR from:skdh OR from:preskill OR from:stephen_wolfram OR from:ProfBrianCox OR from:arxiv OR from:NASAWebb OR from:NIH OR from:WHO OR from:NatureMedicine OR from:EricTopol OR from:statnews OR from:SECGov OR from:HKEXGroup OR from:WSJmarkets) -is:retweet -is:reply` |
| A05 | accounts-05 | 股市 / 地缘政治与 AI 治理 / 气候与地球系统 | 18 | `(from:charliebilello OR from:MacroCharts OR from:carlquintanilla OR from:caixin OR from:SCMPNews OR from:XHNews OR from:CSIS OR from:CFR_org OR from:CSETGeorgetown OR from:AISecurityInst OR from:ianbremmer OR from:KeithBradsher OR from:metaculus OR from:NOAA OR from:IPCC_CH OR from:CopernicusECMWF OR from:hausfath OR from:KHayhoe) -is:retweet -is:reply` |
| A06 | accounts-06 | 气候与地球系统 / 能源 / 生物技术与长寿 / 半导体与算力 | 18 | `(from:OurWorldInData OR from:IEA OR from:EIAgov OR from:ENERGY OR from:iaeaorg OR from:NRCgov OR from:iterorg OR from:CFS_energy OR from:JesseJenkins OR from:AukeHoekstra OR from:BloombergNEF OR from:broadinstitute OR from:arcinstitute OR from:patrickc OR from:bryan_johnson OR from:nvidia OR from:ASMLcompany OR from:dnystedt) -is:retweet -is:reply` |
| A07 | accounts-07 | 航天 / 量子计算 / 人口 / 脑机接口 | 12 | `(from:NASA OR from:esa OR from:SpaceX OR from:planet4589 OR from:jeff_foust OR from:SpaceflightNow OR from:GoogleQuantumAI OR from:IBMResearch OR from:NIST OR from:lymanstoneky OR from:MaxCRoser OR from:neuralink) -is:retweet -is:reply` |

## B. 主题查询（17 条）

| # | slug | query |
|---|---|---|
| B01 | ai-tech-reports | `("technical report" OR "model card" OR "system card") (from:OpenAI OR from:AnthropicAI OR from:GoogleDeepMind OR from:deepseek_ai OR from:Alibaba_Qwen) -is:retweet -is:reply` |
| B02 | ai-arxiv | `url:arxiv.org (LLM OR reasoning OR RL) lang:en -is:retweet -is:reply` |
| B03 | ai-benchmarks | `(SOTA OR benchmark) (ARC-AGI OR SWE-bench OR FrontierMath) lang:en -is:retweet -is:reply` |
| B04 | ai-compute | `(GPU OR datacenter OR gigawatt) (cluster OR training) lang:en -is:retweet -is:reply` |
| B05 | macro-pboc | `(PBOC OR 人民银行 OR 社融 OR LPR) -is:retweet -is:reply` |
| B06 | macro-liquidity | `(SOFR OR "reverse repo" OR TGA OR "bank reserves") lang:en -is:retweet -is:reply` |
| B07 | physics-arxiv | `url:arxiv.org ("quantum gravity" OR "string theory" OR holography) -is:retweet -is:reply` |
| B08 | stock-chanlun | `(缠论 OR 缠中说禅) -is:retweet -is:reply` |
| B09 | stock-a-share | `(上证 OR 沪深300 OR 创业板) (成交额 OR 北向) lang:zh -is:retweet -is:reply` |
| B10 | geo-export-controls | `("export controls" OR BIS) (chips OR AI) lang:en -is:retweet -is:reply` |
| B11 | ai-governance | `("AI Safety Institute" OR "frontier AI" OR "AI Act") lang:en -is:retweet -is:reply` |
| B12 | energy | `(fusion OR SMR OR "grid interconnection" OR "sodium-ion") lang:en -is:retweet -is:reply` |
| B13 | bio | `(url:biorxiv.org OR CRISPR OR "base editing" OR "prime editing") -is:retweet -is:reply` |
| B14 | semis | `(TSMC OR ASML OR HBM OR CoWoS) -is:retweet -is:reply` |
| B15 | quantum | `("logical qubit" OR "error correction") (quantum OR qubit) lang:en -is:retweet -is:reply` |
| B16 | population | `(fertility OR TFR OR 出生人口) -is:retweet -is:reply` |
| B17 | bci | `(BCI OR "brain-computer interface" OR 脑机接口) -is:retweet -is:reply` |

## 调用预算（每次请求 = 1 次调用，25 条/次）

| 轮次 | A 批次 | B 主题 | 小计（基础） | 上限（含翻页） |
|---|---|---|---|---|
| round1 05:00 | 7（next_token 存在时最多再翻 2 页） | 17（不翻页） | 24 | 38 |
| round2 06:00 | 7（最多再翻 1 页） | 17 | 24 | 31 |
| 账号核验 lookup（每月 1 次，100 个/次） | | | 0 | 2 |
| **公开集合合计/日** | | | **48** | **71** |

另有内部专用查询集（不在公开仓库，见本机内部目录），每日 ≤ 8 次（含翻页上限 ≤ 12）。
全部合计每日基础约 56 次、上限约 83 次，低于约 400 次/日 的目标与 1000 次/日 硬上限；限速 30 次/分，批次之间间隔 ≥ 2.5 秒。
注意：X 每日额度在 00:00Z（08:00 SGT）重置，05:00 与 06:00 两轮落在同一额度日内。

## 有效性实测（2026-10-12 00:1x SGT，各 1 次）

- A01（18 个账号）：有效，返回 8 条（start_time 2026-10-10T16:00Z，max 10）。
- B15 quantum：有效，返回 10 条。
- `(TSMC OR ASML OR HBM OR CoWoS) -is:retweet -is:reply min_faves:100`：**无效**（min_faves 不可用），故 B14 已去掉该条件。

## 翻页（next_token）与链接补全 — 2026-10-12 修订（取代上方“调用预算”中的翻页上限）

实测（2026-10-12 06:2x SGT，`x.search_posts_all`，同一查询连续 2 页）：
- 工具把 `max_results` 限制在 **25/次**。
- 翻页参数名：**`next_token`**，取上一页 `meta.next_token` 原值传入（schema 另列 `pagination_token`，未用；统一用 `next_token`）。
- 第 2 页返回 25 条新 id，与第 1 页 0 重叠，且全部早于第 1 页（recency 排序），翻页有效。
- **`search_posts_all` 不返回 `entities`**（即便 `post.fields` 含 entities）。链接必须用 `get_posts_by_ids`（≤100 id/次，`post.fields=entities,created_at,note_tweet`）补全，取 `entities.urls[].unwound_url`，无则 `expanded_url`。
- t.co 的 robots.txt 对 `*` 全站 Disallow：**不自行解析 t.co**。

每查询页数上限：A 批次（from: 账号）**4 页**；B 主题 **2 页**。到上限、无 `next_token`、本页无新 id、或日预算用尽即停。
预算：**≤400 次/SGT 日，≤25 次/分钟**（工具硬限 30/分、1000/日）。
| 轮次 | A（7×≤4） | B（17×≤2） | 补全 get_posts_by_ids | 上限 |
|---|---|---|---|---|
| round1 | ≤28 | ≤34 | ≤10 | ≤72 |
| round2 | ≤28 | ≤34 | ≤10 | ≤72 |
| 合计/日（含内部集 ≤24） | | | | **≤168** |

辅助脚本 `x_capture.py`（不直接调 X，由 agent 调工具并以 write_to_file 落盘后交给脚本）：
```
x_capture.py plan    --queries q.json [--start-time ISO]          # 首页调用参数
x_capture.py ingest  --state S.json --slug A01 --kind account --page 1 --file RESULT.txt --prev-args ARGS.json
                     # -> {"next": {...args with next_token..., "sleep_s": N}} 或 {"next": null, "reason": ...}
x_capture.py hydrate --state S.json                               # get_posts_by_ids 批次（≤100）
x_capture.py budget  --state S.json                               # 今日已用/剩余、需等待秒数
```
补全后的链接写入 leads.json 的 `expanded_url`/`unwound_url`，再交 `fetch_primary.py` 抓一手来源。
