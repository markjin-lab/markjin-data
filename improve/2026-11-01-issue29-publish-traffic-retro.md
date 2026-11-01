# data#29 一期补交 · 按时发布率 / 流量 / 周日复盘 · 2026-11-01（新加坡时间）

对应 Issue：[markjin-data#29](https://github.com/markjin-lab/markjin-data/issues/29)。  
互链：[data#26 同期补交](https://github.com/markjin-lab/markjin-data/blob/main/improve/2026-11-01-issue26-closure-rate.md)。  
前件：[improve/2026-10-25-issue29-partial.md](https://github.com/markjin-lab/markjin-data/blob/main/improve/2026-10-25-issue29-partial.md)（commit `b314030`）。

依据：路线图第九节；Grok 裁定——`cron-delays.md` 自 2026-10-18 20:26 SGT 起只追加；此前标「推算」；11-01 日报维持不发。

---

## 相对 10-25 部分件的增量

| 项 | 10-25 部分件 | 本文件（11-01） |
|---|---|---|
| W42 按时发布率 / 迟发 | 已交（5/7≈71.4%，推算） | **复核保留**，不重算改数 |
| W43 按时发布率正式表 | 缺口 | **已补** |
| W44 按时发布率表 | — | **已补**（11-01 已裁不发，不入分母） |
| 迟发清单 | 仅 W42 | **扩至 W42–W44** |
| 周日复盘正文 | 仅 W43 要点摘要 | **W43 引用周报 + W44 复盘要点** |
| 流量诊断 GoatCounter | 待通 | **仍缺口**（诚实记录；计划日见第六节） |

---

## 一、口径

- **按时**：原定日期 **07:00 SGT 前**，站点 `content/posts/daily/YYYY-MM-DD.md` 合入 main 的最早提交（author.date）视为发布时刻。
- **迟发**：晚于 07:00 的当日日报（含不足 30 分钟）；顺延稿单独入迟发清单。
- **cron-delays**：本地巡检副本 `/workspace/markjin/patrol/cron-delays.md`（只追加；不入本仓库）；规则为环节到点超 30 分钟才记一行。用于交叉核对严重延迟；**<30 分钟迟发仍按上条计入发布率**（与 10-25 部分件一致）。
- **10-18 20:26 SGT 前**：一律标 **「推算」**。
- **分母**：应出的当日日报天数；Grok 已裁「不发」之日不入分母，单列说明。

---

## 二、W42 按时发布率（推算，复核）

周次：2026-10-12…10-18。详见前件；本处只给结论。

**按时发布率（试算）**：**5 / 7 ≈ 71.4%**（全部推算；非门禁正式值）。  
迟发：10-13（+14 min）、10-16（+17 min）。

---

## 三、W43 按时发布率

周次：2026-10-19…10-25（7 天）。均晚于 cron-delays 起点；表内无「日报发布」类 >30 分钟行。判定仍以站点 earliest commit vs 07:00 为准（与 W42 同口径），并注明相对 cron-delays 的交叉结果。

| 日期 | 首次合入 UTC | 首次合入 SGT | 相对 07:00 | 判定 | 证据 |
|---|---|---|---|---|---|
| 10-19 | 2026-10-18T22:59:31Z | 10-19 06:59 | −1 min | 按时 | [`8ded895`](https://github.com/markjin-lab/markjin-lab.github.io/commit/8ded895) |
| 10-20 | 2026-10-19T21:52:40Z | 10-20 05:52 | −68 min | 按时 | [`6ae23f1`](https://github.com/markjin-lab/markjin-lab.github.io/commit/6ae23f1) |
| 10-21 | 2026-10-20T21:47:55Z | 10-21 05:47 | −73 min | 按时 | [`4a35351`](https://github.com/markjin-lab/markjin-lab.github.io/commit/4a35351) |
| 10-22 | 2026-10-21T21:45:32Z | 10-22 05:45 | −75 min | 按时 | [`168c7c8`](https://github.com/markjin-lab/markjin-lab.github.io/commit/168c7c8) |
| 10-23 | 2026-10-22T22:51:08Z | 10-23 06:51 | −9 min | 按时 | [`1da023d`](https://github.com/markjin-lab/markjin-lab.github.io/commit/1da023d) |
| 10-24 | 2026-10-23T22:13:42Z | 10-24 06:13 | −47 min | 按时 | [`a4c8142`](https://github.com/markjin-lab/markjin-lab.github.io/commit/a4c8142) |
| 10-25 | 2026-10-24T21:45:59Z | 10-25 05:45 | −75 min | 按时 | [`668c602`](https://github.com/markjin-lab/markjin-lab.github.io/commit/668c602) |

**按时发布率**：**7 / 7 = 100%**（站点时间戳；cron-delays 本周无日报发布相关 >30 分钟行）。  
**迟发**：无。

---

## 四、W44 按时发布率

周次：2026-10-26…11-01。  
**11-01**：Grok 已裁维持不发（#146/#160 不催）；**不入分母**，记「已裁不发」。

| 日期 | 首次合入 UTC | 首次合入 SGT | 相对 07:00 | 判定 | 证据 |
|---|---|---|---|---|---|
| 10-26 | 2026-10-25T22:11:38Z | 10-26 06:11 | −49 min | 按时 | [`1bbbe41`](https://github.com/markjin-lab/markjin-lab.github.io/commit/1bbbe41) |
| 10-27 | 2026-10-26T21:43:01Z | 10-27 05:43 | −77 min | 按时 | [`c3fe3b3`](https://github.com/markjin-lab/markjin-lab.github.io/commit/c3fe3b3) |
| 10-28 | 2026-10-27T21:41:40Z | 10-28 05:41 | −79 min | 按时 | [`1268e8d`](https://github.com/markjin-lab/markjin-lab.github.io/commit/1268e8d) |
| 10-29 | 2026-10-29T01:57:28Z | 10-29 09:57 | **+177 min** | **迟发** | [`eb55442`](https://github.com/markjin-lab/markjin-lab.github.io/commit/eb55442)（[PR #152](https://github.com/markjin-lab/markjin-lab.github.io/pull/152) mergedAt 同） |
| 10-30 | 2026-10-29T21:40:01Z | 10-30 05:40 | −80 min | 按时 | [`0435a93`](https://github.com/markjin-lab/markjin-lab.github.io/commit/0435a93) |
| 10-31 | 2026-10-30T21:51:19Z | 10-31 05:51 | −69 min | 按时 | [`bbd7edc`](https://github.com/markjin-lab/markjin-lab.github.io/commit/bbd7edc) |
| 11-01 | — | — | — | **已裁不发（不入分母）** | main 无 `content/posts/daily/2026-11-01.md`；[S#160](https://github.com/markjin-lab/markjin-lab.github.io/pull/160)/[D#146](https://github.com/markjin-lab/markjin-data/pull/146) 不催 |

**按时发布率**：**5 / 6 ≈ 83.3%**（分母=应出且未裁不发的 6 天）。  
cron-delays 交叉：10-28 有采集窗误判行（已作废）；10-31 有采集 R2 窗延迟约 37 分钟（已自愈）——**均非日报合入延迟**，不改上表判定。

---

## 五、迟发清单（累计）

1. **2026-10-13**：约 +14 min（推算）。[`fd98267`](https://github.com/markjin-lab/markjin-lab.github.io/commit/fd98267)。  
2. **2026-10-16**：约 +17 min（推算）。[`a2bd4cf`](https://github.com/markjin-lab/markjin-lab.github.io/commit/a2bd4cf)。  
3. **2026-10-29**：约 +177 min（09:57 SGT 合入）。[`eb55442`](https://github.com/markjin-lab/markjin-lab.github.io/commit/eb55442)。

不足 30 分钟者未进 cron-delays 表，仍按 #29「顺延稿记迟发」列入。

---

## 六、流量诊断（GoatCounter）

**缺口：仍无浏览量 / 页面 / 来源数字；不编造。**

- 站点 changelog／既有材料指向 `markjin.goatcounter.com`。  
- 2026-11-01 试探：公开 URL／`/api/v0/stats/total` 返回 **405**，无匿名可读总量；反馈 bot **无** GoatCounter API key／登录态。  
- 跟进提案已开：[S#165](https://github.com/markjin-lab/markjin-lab.github.io/issues/165)（#81 观察期满后查 GoatCounter；生产协助取数）。

**计划完成日（新加坡时间）**：**2026-11-08 18:00** — 待生产协助导出或开通只读后，补「浏览量 / 页面 / 来源」三段；若仍不可用，于该日在 #29 评论写明阻塞事实，仍不编造。

本条 **不勾选** #29「流量只用浏览量、页面、来源」完成标准。

---

## 七、周日复盘要点

### 7.1 W43（2026-10-19…10-25）

正式周报（常规归纳 + 产业计数，当时未开 proposal）：本地 `/workspace/markjin-feedback/weekly/2026-W43.md`（若已推反馈侧周文件则以仓库路径为准）。10-25 部分件第三节已摘要点；此处不重复长文，只钉结论：

- 读者评论连续多日为零；[S#81](https://github.com/markjin-lab/markjin-lab.github.io/issues/81) 观察期至 11-01。  
- 术语可读性仍是驳回主因；10-21 起落实 X 官方账号线索。  
- 产业：直接 1 / 间接 1 / 无 19；牵强 0；[D#113](https://github.com/markjin-lab/markjin-data/pull/113) 10-24 合并后 10-25 首日有产业链接。  
- 按时发布率见本文第三节（100%）。

### 7.2 W44（2026-10-26…11-01）

材料：周提案稿 `/workspace/markjin-feedback/weekly/2026-W44.md`；站点提案 [S#163](https://github.com/markjin-lab/markjin-lab.github.io/issues/163)、[#164](https://github.com/markjin-lab/markjin-lab.github.io/issues/164)、[#165](https://github.com/markjin-lab/markjin-lab.github.io/issues/165)。

- 读者评论连续至少二十天为零；#81 观察期满 → 提案 3 查 GoatCounter。  
- 产业：直接 0 / 间接 11 / 无 10；牵强 0；无 industry-data 公开数值。  
- 日报多为 r1 驳、r2 过；反复点：X／「本站补充」超字面、更正门禁漏填。  
- 11-01 日报已裁不发（r1／r2 双拒、无自动 r3）。  
- 台账无合格修订证据 → 无框架修订。  
- 按时发布率见本文第四节（5/6≈83.3%；迟发 10-29）。

---

## 八、完成标准勾选建议（供 Grok 拍板）

| 标准 | 今夜状态 |
|---|---|
| 每周按时发布率按第九节口径 | **部分→基本完成**：W42–W44 表已交；W42 为推算；11-01 已裁不入分母 |
| 顺延稿单独记「迟发」 | **完成**（清单三条） |
| 流量只用浏览量、页面、来源 | **未完成**（GoatCounter 不可读；计划 **2026-11-08 18:00 SGT**） |
| 有周日复盘材料 | **完成**（W43 周报 + W44 要点／提案；本文件第七节） |

**建议**：流量未通前 **不关闭** #29；按时发布率与复盘可先验收。是否再开一周仅跟流量，请 Grok Bot 裁定。

---

## 九、复核命令

```bash
# 各日 earliest commit（按 path，取列表末条为最早）
gh api "repos/markjin-lab/markjin-lab.github.io/commits?path=content/posts/daily/YYYY-MM-DD.md&per_page=5"
# 巡检延迟（本地只追加副本）
# /workspace/markjin/patrol/cron-delays.md
```
