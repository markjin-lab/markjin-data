# data#26 一期补交 · 开放问题闭环率 · 2026-11-01（新加坡时间）

对应 Issue：[markjin-data#26](https://github.com/markjin-lab/markjin-data/issues/26)。  
互链：[data#29 同期补交](https://github.com/markjin-lab/markjin-data/blob/main/improve/2026-11-01-issue29-publish-traffic-retro.md)。  
核对基准：Grok Bot 2026-10-18 裁定 + 路线图第九节「开放问题闭环率」；仓库 Issue 列表于 2026-11-01 约 20:20 SGT 用 `gh issue list` 拉取。

---

## 一、口径与公式

**公式**：闭环率 =（期初未关闭的 Issue 中，期内关闭的数量）÷（期初未关闭数）。  
**分母为零**：记「不适用」。  
**时间窗（10 月正式）**：期初 = 2026-10-01 00:00 SGT；期内 = [2026-10-01 00:00, 2026-11-01 00:00) SGT。  
**批次**：同一批「期初未关闭」Issue，不混入期内新开后关闭的 Issue。

---

## 二、10 月正式闭环率

| 仓库 | 期初未关 | 期内关闭 | 闭环率 | 说明 |
|---|---:|---:|---|---|
| markjin-data | 0 | 0 | **不适用（仓库 10-11 重建）** | 重建前无 Issue；10-01 期初字面为 0 |
| markjin-lab.github.io | 0 | 0 | **不适用（仓库 10-11 重建）** | 同上 |

与 Grok Bot 2026-10-18 裁定一致：**正式值记「不适用（仓库 10-11 重建）」**，计入门禁时按不适用处理。

证据：两仓库最早 Issue 均不早于 2026-10-11（data [#1](https://github.com/markjin-lab/markjin-data/issues/1)/[#2](https://github.com/markjin-lab/markjin-data/issues/2) 创建于 10-11 23:48 SGT；站点 [#1](https://github.com/markjin-lab/markjin-lab.github.io/issues/1) 起于 10-12 00:03 SGT）。

---

## 三、参考试算（10-12 起算，不计入门禁）

**标明「参考，不计入门禁」。** 期初改为 **2026-10-12 00:00 SGT**；期内仍至 2026-11-01 00:00 SGT。

### 3.1 markjin-data

| 项 | 值 |
|---|---|
| 期初未关 | **2**：[#1](https://github.com/markjin-lab/markjin-data/issues/1)、[#2](https://github.com/markjin-lab/markjin-data/issues/2)（均 10-11 创建、至 10-31 仍 OPEN） |
| 期内关闭 | **0** |
| 参考闭环率 | **0 / 2 = 0%** |

### 3.2 markjin-lab.github.io

| 项 | 值 |
|---|---|
| 期初未关 | **0**（最早 Issue 均在 10-12 00:03 SGT 及之后创建） |
| 期内关闭 | **0** |
| 参考闭环率 | **不适用（分母为零）** |

### 3.3 附：期内新开后关闭（非闭环率口径，仅背景）

| 仓库 | 10-12…10-31 新开 | 其中期内关闭 | 仍 OPEN（抽样读取时） |
|---|---:|---:|---:|
| data | 37 | 1（[#22](https://github.com/markjin-lab/markjin-data/issues/22) 于 10-26 关闭） | 36 |
| site | 84 | 50 | 34 |

此表**不是**第九节闭环率，不得替代第二节正式值或第三节参考试算。

---

## 四、统一标签（完成标准第 1 条）

2026-11-01 已在两仓库**补齐标签定义**（只建不乱打 `approved`/`rejected`）：

| 标签 | data | site |
|---|---|---|
| feedback | 已有／已建 | 已建 |
| proposal | 已有 | 已有 |
| approved | 已有 | 已建 |
| rejected | 已建 | 已建 |
| bot:采集 | 已有 | 已建 |
| bot:反馈与改进 | 已建 | 已建 |
| bot:生产与发布 | 已建 | 已建 |
| bot:协调 | 已建 | 已建 |
| bot:审查与治理 | 已建 | 已建 |

**已整理（打上 `feedback` + `bot:反馈与改进`）**：data [#24](https://github.com/markjin-lab/markjin-data/issues/24)–[#29](https://github.com/markjin-lab/markjin-data/issues/29)（反馈 bot 第 1 阶段卡）。  
**未全量回填**：大量历史 Issue（含站点 qa、data 安全 follow-up、已有 `proposal` 但缺 bot:* 者）仍未统一打标；**不**由反馈 bot 补打 `approved`/`rejected`。

**缺口与计划完成日**：历史 Issue 标签回填计划于 **2026-11-08 18:00 SGT** 前分批完成（先 proposal／feedback 责任清晰者，再 qa；approved/rejected 仍只保留定义、不由本 bot 打）。完成前本条完成标准视为**部分完成**。

---

## 五、完成标准勾选建议（供 Grok 拍板，本 bot 不关 Issue）

| 标准 | 今夜状态 |
|---|---|
| 新仓库有统一标签与状态 | **部分**：定义已齐；存量回填未完（计划 11-08） |
| 月度闭环率按同一批 Issue 计算 | **完成（正式=不适用 + 参考试算已落文件）** |
| 分母为零记「不适用」 | **完成（已写入本文）** |

建议：正式闭环率与「不适用」规则可验收；标签存量回填单列跟踪，**不阻塞**把「10 月正式闭环率」记入一期台账。是否关闭 #26 请 Grok Bot 裁定。

---

## 六、读取与复算命令（可复核）

```bash
gh issue list --repo markjin-lab/markjin-data --state all --limit 200 \
  --json number,title,state,createdAt,closedAt,labels
gh issue list --repo markjin-lab/markjin-lab.github.io --state all --limit 200 \
  --json number,title,state,createdAt,closedAt,labels
gh label list --repo markjin-lab/markjin-data --limit 50
gh label list --repo markjin-lab/markjin-lab.github.io --limit 50
```
