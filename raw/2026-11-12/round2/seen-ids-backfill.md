# seen-ids r2-precheck 2026-11-12

- tool: `seen_ids.py r2-precheck --date 2026-11-12 --round1-raw-dir raw/2026-11-12`
- updated: 2026-11-12（当天，正常）
- 补前缺口: arxiv=20 / x=57 / fred=0
- 补后缺口: arxiv=0 / x=0 / fred=0
- pending merge: ok; cleared=[]; retained=[]; added arxiv=0 x=0 fred=0（开跑时 pending 已空）
- backfill: ok; attempt=1; bak-20261112r2pre; upgrade_notes=[]
- bak-20261112r2precheck sha256=5fc5005631198892db3cfc443a939d55643d04fc951774f0cfb58b277c3f212e
- counts after precheck: arxiv=3611 / x=22904 / fred=32816（与 R1 merge after 一致；缺口 20+57 已从已核验 R1 编号补登，added 计入 backfill 而非此次 pending merge）
- fallback_sets: null
- 结论: 补后无缺口，可继续采集；去重基线 = seen-ids ∪ R1 文件 ∪ 前几天 raw
