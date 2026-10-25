# data#29 部分交付 · 2026-10-25（新加坡时间）

对应 Issue：[markjin-data#29](https://github.com/markjin-lab/markjin-data/issues/29)。  
依据：王总经 Grok Bot 裁定——今晚先交部分材料；完整包随 W44／2026-11-01 18:00 补齐。

本文件覆盖：W42 按时发布率（推算）、迟发清单、已有复盘要点。  
**未覆盖**：流量诊断（GoatCounter 待通后再补）；W43 按时发布率正式表；完成标准勾选。

---

## 一、W42 按时发布率（推算）

**周次**：W42 = 2026-10-12 至 2026-10-18（7 天）。

**口径**：原定日期 **07:00 SGT 前**，站点仓库 main 上当日日报文件的**最早提交**（author.date）视为按时；否则记「迟发」。  
`cron-delays.md` 自 2026-10-18 20:26 SGT 起才记录，W42 全部早于该起点，故一律标 **「推算」**（来源：站点 `content/posts/daily/YYYY-MM-DD.md` 最早 commit）。  
分母 = 应出的当日日报天数。本试算**不计入门禁正式值**。

| 日期 | 首次提交 UTC | 首次提交 SGT | 相对 07:00 | 判定 | 证据 |
|---|---|---|---|---|---|
| 10-12 | 2026-10-11T22:07:11Z | 10-12 06:07 | −53 min | 按时（推算） | [`9b6b4b2`](https://github.com/markjin-lab/markjin-lab.github.io/commit/9b6b4b2) daily: 2026-10-12 (zh+en) (#6) |
| 10-13 | 2026-10-12T23:14:10Z | 10-13 07:14 | +14 min | **迟发（推算）** | [`fd98267`](https://github.com/markjin-lab/markjin-lab.github.io/commit/fd98267) daily: 2026-10-13 (zh+en) (#55) |
| 10-14 | 2026-10-13T22:06:11Z | 10-14 06:06 | −54 min | 按时（推算） | [`a81558a`](https://github.com/markjin-lab/markjin-lab.github.io/commit/a81558a) daily 2026-10-14 (ZH+EN) (#57) |
| 10-15 | 2026-10-14T22:07:57Z | 10-15 06:07 | −53 min | 按时（推算） | [`0e1ecd5`](https://github.com/markjin-lab/markjin-lab.github.io/commit/0e1ecd5) daily: 2026-10-15 (#60) |
| 10-16 | 2026-10-15T23:17:39Z | 10-16 07:17 | +17 min | **迟发（推算）** | [`a2bd4cf`](https://github.com/markjin-lab/markjin-lab.github.io/commit/a2bd4cf) daily: 2026-10-16 zh/en (#61) |
| 10-17 | 2026-10-16T22:02:58Z | 10-17 06:02 | −58 min | 按时（推算） | [`1618fe8`](https://github.com/markjin-lab/markjin-lab.github.io/commit/1618fe8) daily: 2026-10-17 zh/en (#62) |
| 10-18 | 2026-10-17T22:15:13Z | 10-18 06:15 | −45 min | 按时（推算） | [`449100a`](https://github.com/markjin-lab/markjin-lab.github.io/commit/449100a) daily: 2026-10-18 zh/en (#65) |

**按时发布率（试算）**：5 / 7 ≈ **71.4%**（推算；非门禁正式值）。

时间戳于 2026-10-25 核对站点 API，与上表一致。

## 二、迟发清单（W42）

1. **2026-10-13**：约晚 14 分钟（推算）。证据：[`fd98267`](https://github.com/markjin-lab/markjin-lab.github.io/commit/fd98267)。
2. **2026-10-16**：约晚 17 分钟（推算）。证据：[`a2bd4cf`](https://github.com/markjin-lab/markjin-lab.github.io/commit/a2bd4cf)。

`cron-delays.md` 至本交付起草时表内仍无数据行（无 >30 分钟延迟记录）；上列两条均未满 30 分钟，故未进 cron-delays 表，但仍按 #29「顺延稿记迟发」口径列入本清单。

## 三、已有复盘要点（W43 · 2026-10-19 至 2026-10-25）

材料：`feedback/` 本周日汇总与 `review/`；公开日报；台账 `ledger/branches.csv`。W43 按当时限制只做常规归纳 + 产业计数，**未**开 proposal Issue。

### 读者与评论入口

- 读者评论连续多日为零；Discussions Comments 仍仅有 [讨论 #31](https://github.com/markjin-lab/markjin-lab.github.io/discussions/31)（0 评）。至 10-25 日汇总为连续 14 天为零。
- 评论入口 [S#81](https://github.com/markjin-lab/markjin-lab.github.io/issues/81) 经 [S#122](https://github.com/markjin-lab/markjin-lab.github.io/pull/122) 于 10-19 上线；观察期至 11-01；计划 11-02 出 14 天观察报告。

### 发布与审查（质感）

- 术语可读性仍是日报驳回主因（如 10-19 多轮、10-23/10-24 r1 因可读性 MEDIUM 被拒后 r2 合）。
- 10-21 起落实 X 官方账号线索筛选；其后各日有 1–3 条官方账号帖。
- 10-25 日报 r2 合并；产业链接首日上线，R-INDUSTRY-STRAINED: 0。

### 产业计数（W43）

- 直接 **1**、间接 **1**、无 **19**；Codex 牵强 **0**；写稿/审查用时无数据。
- [D#113](https://github.com/markjin-lab/markjin-data/pull/113) 于 10-24 约 08:12 SGT squash 合并（`675b0a6`）；10-25 为合并后首日有公开产业链接（条目 2 间接、3 直接）。

### 宏观与运行

- 台账无合格修订证据行；本周无框架修订。
- FRED 未请求；cron-delays 本周无新增行。
- 公开数字：已开放非 BEA（优先美联储理事会）；BEA 仍等书面授权；FRED 仍禁。

### 状态备忘（不催办）

- data [#91](https://github.com/markjin-lab/markjin-data/pull/91) 仍 OPEN，未另令前不催合。
- 完整周提案自 W44／2026-11-01 18:00 起按完整流程开。

## 四、流量诊断

**待通后再补。** GoatCounter（站点 changelog 记为 markjin.goatcounter.com）导出或接口读出方式尚未核实；本交付无浏览量、页面、来源数字。不勾选 #29 流量完成标准。

## 五、缺口与剩余截止

| 项 | 今晚状态 | 剩余计划 |
|---|---|---|
| W42 按时发布率（推算） | **已交**（本文第一节） | 11-01 可复核口径；正式值仍标明推算或不计入门禁 |
| W42 迟发清单 | **已交**（本文第二节） | 同上 |
| 已有复盘要点 | **已交**（本文第三节，W43） | 11-01 可并入正式周日复盘正文 |
| 流量诊断 | **缺口**（待 GoatCounter） | 通后补；目标不晚于 **2026-11-01 18:00 SGT** |
| W43 按时发布率正式表 | **缺口** | 随 W44／**2026-11-01 18:00 SGT** 完整包 |
| #29 完成标准四条勾选 | **今晚均不勾** | 完整包交齐后再判能否关闭 |

**剩余截止（新加坡时间）**：**2026-11-01 18:00** — 随 W44 补齐流量诊断（若已通）+ W43 发布率表 + 正式周日复盘正文；再对完成标准勾选与能否关闭作判。
