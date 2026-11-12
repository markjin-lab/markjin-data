# seen-ids r2-precheck 2026-11-13

- tool: `seen_ids.py r2-precheck --date 2026-11-13 --round1-raw-dir raw/2026-11-13`
- updated: 2026-11-13（当天，正常；非当天只告警不报错）
- 补前缺口: arxiv=14 / x=33 / fred=0
- 补后缺口: arxiv=0 / x=0 / fred=0
- pending merge: ok; cleared=[]; retained=[]; added arxiv=0 x=0 fred=0（开跑时 pending 已空）
- backfill: ok; attempt=1; bak-20261113r2pre; upgrade_notes=["upgrade arxiv '2611.12167' -> '2611.12167v1'"]
- bak-20261113r2precheck sha256=cd3f0558287b546a8b79e2dedeca53082fc06b3591727a2acfc822c81dbd4b26
- counts after precheck/backfill: arxiv=3644 / x=23759 / fred=32816（R1 merge after 为 arxiv=3631 / x=23726；缺口 14+33 由已核验 R1 编号补登，其中 1 条 arXiv 为版本升级故新增 13+33）
- fallback_sets: null
- 结论: 补后无缺口，可继续采集；去重基线 = seen-ids ∪ R1 文件 ∪ 前几天 raw
