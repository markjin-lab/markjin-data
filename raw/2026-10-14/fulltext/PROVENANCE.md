# fulltext 2026-10-14

全文入库规则（王总确认，quote_ref grok-bot:t163s794）：只有许可允许转载的全文才放入公开仓库；其余只记录 URL 和 sha256。

抓取时间：2026-10-14 05:47 SGT（UTC+8），curl，公开页面，未登录。`ORIGINALS.sha256` 列出 2 个抓取原件的 sha256；原件不在本仓库，保留在本机（90 天）。

| 文件 | 来源 URL | 许可 | 是否入库 |
|---|---|---|---|
| anthropic-distillation-defenses.html | https://www.anthropic.com/research/distillation-defenses | 版权页面 | 否，只记 sha256 |
| anthropic-self-replicating-ai.html | https://www.anthropic.com/research/self-replicating-ai | 版权页面 | 否，只记 sha256 |

## 日报引用的页面内容（已在原件中核对）
- distillation-defenses：页面标题 “Strengthening our defenses against distillation attacks”，页面日期 “Oct 12, 2026”（datePublished 2026-10-12T09:30:00.000Z）；正文 “Early evidence suggests that these methods have reduced the amount of data harvested by distillers by around 90 to 99%.”
- self-replicating-ai：页面标题 “AI models may be capable of self-replicating without access to a datacenter”，页面日期 “Oct 12, 2026”（datePublished 2026-10-12T19:30:00.000Z）；正文 “In our simplified evaluations, GLM-5.2 and stronger models are capable of end to end replication.”；页面描述提到 “self-replicate across cheap IoT devices like Android TV boxes”。

未入库的文件不在公开仓库中转载，按上述 URL 重新下载后用 `ORIGINALS.sha256` 核对；若来源页面已改动，哈希不再一致。
