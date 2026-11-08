# data#29 / 站点#165 流量补交 · 2026-11-08（新加坡时间）

对应 Issue：[markjin-data#29](https://github.com/markjin-lab/markjin-data/issues/29)（仍 OPEN）、[站点#165](https://github.com/markjin-lab/markjin-lab.github.io/issues/165)。  
前件：[improve/2026-11-01-issue29-publish-traffic-retro.md](https://github.com/markjin-lab/markjin-data/blob/main/improve/2026-11-01-issue29-publish-traffic-retro.md) 第六节（当时计划本日补交浏览量／页面／来源；不通则只记阻塞）；[improve/2026-10-25-issue29-partial.md](https://github.com/markjin-lab/markjin-data/blob/main/improve/2026-10-25-issue29-partial.md)。  
互链：[improve/2026-11-08-issue26-label-backfill.md](https://github.com/markjin-lab/markjin-data/blob/main/improve/2026-11-08-issue26-label-backfill.md)。

**结论：GoatCounter 仍不可读；没有浏览量、页面、来源数字。不编造。不另开「只跟流量」新 Issue。**

---

## 一、先读既有评论（生产是否已补导出）

2026-11-08 约 18:10 SGT 用 `gh` 阅读以下评论，**未见**生产 bot 补交导出或取数：

- [data#29](https://github.com/markjin-lab/markjin-data/issues/29)：11-01 一期补交仍记流量缺口；总负责验收评论维持 Issue OPEN，并写明与 S#165 一并跟进、不再单开只跟流量的新 Issue。其后无新的取数／导出评论。
- [站点#165](https://github.com/markjin-lab/markjin-lab.github.io/issues/165)：11-02 周审「修改后通过」；随后「观察备忘补齐」写明本轮不取 GoatCounter，跟踪时点为 **2026-11-08 18:00 SGT**。无数字。
- [站点#81](https://github.com/markjin-lab/markjin-lab.github.io/issues/81) 11-02 观察报告第四节：日报页访问量（GoatCounter）记为**无数据**。

---

## 二、主机名核对

站点仓库 `layouts/_default/baseof.html`（`gh api` 读取，未 clone 站点仓库）含：

```html
<script data-goatcounter="https://markjin.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
```

线上页面同样嵌入该脚本（见第四节）。主机名与 11-01 材料一致：`markjin.goatcounter.com`。

---

## 三、可读性试探（2026-11-08 18:11:41 SGT）

工具：`curl -sS -L`（首页另做一次不跟随重定向）。**没有**使用、寻找或猜测 API key／登录态。无授权即记为不可读。

| URL | HTTP | 响应摘要 |
|---|---|---|
| `https://markjin.goatcounter.com`（不跟随） | **303** | `Location: /user/new` |
| 跟随后的 `/user/new` | **200** | 注册／登录页，不是公开统计仪表盘 |
| `https://markjin.goatcounter.com/api/v0/stats/total` | **401** | 正文 `error 401: no Authorization header`；响应头 `WWW-Authenticate: Basic realm=GoatCounter` |
| 同上，带 `start=2026-10-19&end=2026-11-01` | **401** | 同上 |
| `https://markjin.goatcounter.com/api/v0/stats/hits` | **401** | 同上（需授权） |
| `https://markjin.goatcounter.com/api/v0/me` | **401** | 同上（需授权） |
| `https://markjin.goatcounter.com/counter/TOTAL.json` | **403** | 正文 `error 403: Need to enable the ‘allow using the visitor counter’ setting` |
| `https://markjin.goatcounter.com/counter/.json` | **403** | 与上同类错误页 |
| `https://markjin.goatcounter.com/counter/%2F.json` | **403** | 与上同类错误页 |

相对 11-01：当时记公开 URL／`/api/v0/stats/total` 为 **405**。本次对同一路径的 GET 得到 **401**（无 Authorization）。以本次实测为准，不沿用 405 作为当前状态。两种结果都表明匿名读不到统计数字。

---

## 四、站点页面有没有可见计数

对下列已发布页做 GET（均为 HTTP 200），在 HTML 中检索 `data-goatcounter`、`gc.zgo.at`、`goatcounter-count`：

- https://markjin-lab.github.io/
- https://markjin-lab.github.io/posts/daily/2026-10-19/

两页都嵌了 `data-goatcounter=https://markjin.goatcounter.com/count` 与 `//gc.zgo.at/count.js`（采集脚本）。**没有** `goatcounter-count` 可见计数器，页面上也读不到浏览量数字。

---

## 五、缺口与下一步

仍缺 #29 完成标准要求的三段真实数字：**浏览量、页面、来源**。反馈 bot 没有 GoatCounter 只读授权；公开仪表盘未开放；访客计数 JSON 未开启；站点页无可见计数。

**下一步计划日（新加坡时间）：2026-11-15 18:00**（下周日周复盘）。届时若生产已协助导出或开通只读，再补三段数字并写来源链接；若仍不可读，继续只记阻塞，仍不编造、不另开新 Issue。继续跟 [data#29](https://github.com/markjin-lab/markjin-data/issues/29) 与 [S#165](https://github.com/markjin-lab/markjin-lab.github.io/issues/165)。

本条仍**不勾选** #29「流量只用浏览量、页面、来源」完成标准。不关闭 #29，不改 #165 的 `approved`／`rejected`（这两类标签本轮也未触碰）。
