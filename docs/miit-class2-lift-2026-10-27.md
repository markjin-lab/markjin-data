# 书面 lift：工信部第 2 类停源（Mac 路径）· 2026-10-27

签发：Grok Bot（协调）。依据停源解除门槛：Mac 试通 + robots 复核口径 + 王总确认。

- wang quote_ref：`grokbot-chat:t731s3020`（批准出具本 lift）
- 前置 Mac 路径批准：`grokbot-chat:t723s2964`
- Mac 试通：`/gxsj/` 与运行局信息发布相关页在 Mac Studio 得 HTTP 200、非验证页；箱内仍为 Kong/JSL 拦截 → **箱内继续停源**
- robots：`robots.txt` 为 404、无 Disallow 文本；日采按「无禁止规则文本 + 站内限速 + 遇拦即停」执行，**不**把 404 当成对方书面许可文件

## 允许

- 仅在 **Mac Studio** 对已登记候选 `miit-gxsj`、`miit-yxj-xxfb` 开日采（`enabled: true`，主机限定 Mac）
- 原件默认私存；公开数值 / 公开 raw 须另案

## 不允许

- 箱内对 miit.gov.cn 发 body 或绕过验证
- 扩大未登记栏目
- 无本 lift 时自动启用

## 回滚

403 / 验证页 / 条款疑义 → 立即停用并报协调方；须新的书面 lift 才能再开。
