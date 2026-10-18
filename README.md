# markjin-data
markjin 工作流的数据仓库。站点：https://markjin-lab.github.io

本仓库于 2026-10-11 重建，记录从重建之日起。

| 目录 | 用途 |
|---|---|
| raw/ | 原始来源逐字节存档（YYYY-MM-DD/），永不修改 |
| review/ | 每日 11:00 SGT 交叉审核记录 |
| improve/ | 改进提案与决议（Issues 标签 `proposal`/`approved`/`rejected`） |

信源标签：`source-arxiv`、`source-x`。

FRED 已于 2026-10-18 停用，改从原始机构取数；FRED 原始文件及两份含 FRED 数值的年度对账表已由 data PR #87 撤回；登记见 raw/2026-10-10/ 至 raw/2026-10-18/ 各日期的 RETRACTIONS.md。raw/ 中未撤回的历史说明与日志按只追加规则保留原样。

本机内部主题检查（pre-push `check-internal`）默认读取仓库根目录同级的 `../markjin-internal`；克隆不在同级位置（另一父目录、别处的 git worktree 等）时，须设置环境变量 `MARKJIN_INTERNAL_DIR` 指向内部目录，否则推送被拒（fail-closed）。详见 scripts/README.md「内部主题检查」。
