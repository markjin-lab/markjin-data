# arXiv 原始响应 provenance｜2026-11-23 日采

- 真实请求起止SGT：2026-11-23T02:01:15.223+08:00 至 2026-11-23T02:02:45.103+08:00；run_id 2026-11-23T020114+0800。
- 基线data main：1c708de6fdeba699903fa230884514a1282263ef。
- arxiv/*.xml 为HTTP响应body直接落盘的 copied-file，未重编码/改写。
- 每类50条，含跨分类重复；作者摘要非独立验证结果。
- 请求间隔：前一响应结束→下一请求开始，下限16秒；实测间隔(秒)：[16.0, 16.01, 16.009, 16.002, 16.0]。
- arxiv/robots-export-arxiv-org.txt 为每次运行留存的 robots 快照（证据，非许可依据）。
- 不下载全文；各篇许可未核。API若给license则原样列于candidates.json。
- X见 capture-failures.md。
