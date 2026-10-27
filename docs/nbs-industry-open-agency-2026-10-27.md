# 统计局：公开 industry-data 机构白名单 · 2026-10-27

经 Grok Bot 转达。前置：#132 公开三项范围已批（`grokbot-chat:t733s3040` / wang `37724fc2…`）；试摘录包与 raw 已入库；本 vintage（发布日约 2026-10-19）相对采集日 2026-10-27 已超 industry-data 48h 窗，**本 vintage 仍不写公开数值**。

## 王总拍板（quote_ref `grokbot-chat:t742s3077`）

批准现在开 data PR，把下列两项加入公开 industry-data 机构白名单（`INDUSTRY_OPEN_AGENCY_DOMAINS` / 已开放机构名）：

1. 域名：`stats.gov.cn`（含子域名，如 `www.stats.gov.cn`、`data.stats.gov.cn`）
2. 机构名：「国家统计局」

## 生效后规则

- 同块命中上述域名或机构名时，可按既有 industry-data 四条件写公开数值（含已批三项：工增同比·环比、能源四项同比、固投设备工器具同比；占比仍不写）。
- **本 vintage 仍不写**（超 48h）。以后同指标若落在 48h 窗内，可写。
- BEA / FRED / Census / EIA 等既有闸门不变。

## 实现范围（本 PR）

- `scripts/markjin/selfcheck.py`：开放域与开放机构名
- 相关单测与 `review/error-codes.md` 口径
- 本说明 + wang 批准登记
- **不**写入任何公开日报 industry-data 数值正文
