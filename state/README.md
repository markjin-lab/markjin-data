# state/

`publish-state.json` 由生产 bot 提交（公开）。`scripts/route.py` 只从 main 分支读取，字段与规则见 `scripts/README.md`「route」一节与 `scripts/markjin/approvals.py`。
文件缺失或不合法 → 路由拒绝（`E-ROUTE-STATE`）；Mac 心跳超过 30 分钟未更新 → Mac 状态未知 → HOLD（`E-ROUTE-MAC-STALE`，可重试，不归档；不需要王总批准且已有有效 Codex APPROVED 的日报不受影响）；只有心跳新鲜且 `mac_online=false` 才按离线归档；已归档条目不得修改或删除（归档不可逆）。
