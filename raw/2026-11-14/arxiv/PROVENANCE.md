# arXiv 原始响应 provenance｜人工补采v1

- 真实请求起止SGT：2026-11-14T09:13:39.335695+08:00 至 2026-11-14T09:14:09.442870+08:00。
- 基线data main：685ff6a7f55f18bcdcd89b9f2f251e6b1d95d372；不修改Grok采集任务。
- arxiv/*.xml 为HTTP响应body直接落盘的copied-file，未重编码、未解析重写、未复制旧raw。
- 每类50条，包含跨分类重复；作者摘要不是经本站独立验证的研究结果。
- 请求URL、时刻、HTTP状态、响应Date/Content-Type、body bytes与SHA见requests及query-log。
- 仅按既有准入公开归档API元数据/摘要；各篇全文许可未核，不下载PDF/HTML全文、不推定统一CC许可。API若给license则原样列于candidates.json。
- X返回401，0条准入；错误body只作失败证据，不作事实新闻。
- 07:00不是本批首次取得时刻。原始published/updated与本次received_at分开记录。
