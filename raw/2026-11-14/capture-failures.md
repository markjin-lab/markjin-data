# capture-failures｜2026-11-14一次人工补采v1

- actual_source_requests_sgt: 2026-11-14T09:13:39.335695+08:00 .. 2026-11-14T09:14:09.442870+08:00
- arXiv: 5/5 HTTP200、Atom非错误feed，各50条；准入API元数据/摘要，不代表全文核验。
- X: A01既有查询一次无凭据可达性请求，HTTP401 Unauthorized，0条准入；无可用认证连接器且本任务禁止凭据访问，A02–A07/B01–B17不再请求。未改用网页、手机、Grok或其他源重试。
- sources.yaml: 当前data main完整树未见该文件；按既有5分类baseline及站点collection-plan§2映射，不扩源。
- 本批为09时后人工补采，不是自动采集恢复，也不证明Grok R1/R2曾运行。
- FRED永久停用：零请求。其余来源不在本次范围，不取私人材料、不调用M5。
- 当期24h/48h论文日期统计及旧论文标记见candidates.json；没有新提交不等于无可用当期发现。旧论文不冒称当日首发。
