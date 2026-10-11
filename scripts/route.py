#!/usr/bin/env python3
"""用法：scripts/route.py --pr N --repo REPO --date YYYY-MM-DD --card-type daily|signal
       [--site-repo DIR] [--dry-run [--now ISO8601+时区]]
（整体验收 r2：时间只用真实时钟；--now 只在 --dry-run 下可用，演练结果永远 publishable=false。）
（整体验收 r1 HIGH 2：不能关闭链接检查；--no-link-check 已取消，传入即 HOLD E-ROUTE-INPUT。）
（先 git fetch，使 PR 的 base/head 提交在本地可用。）
r13：只接受 PR 编号（--pr N）：base/head/文件列表由 gh pr view 取得，须与 git diff base...head 一致，删除/改名一律失败；稿件、raw/、MANIFEST 从 head 提交读取，批准记录只读 origin/main；只允许单篇 .md，或同 section 同 name 的 .md + .en.md。
draft_id 由稿件路径推出：REPO/<section>/<name>.md → <section>-<name>（如 daily/2026-10-11.md → daily-2026-10-11）。
门禁不写任何文件：需要写回状态时，输出中的 state_change 交给生产 bot 用 scripts/state-change.py apply 写入。
打印路由决定（JSON）。批准与状态只从 REPO 的 origin/main git 对象读取（不可指定）：
approvals/codex/<sha256>.json、approvals/wang/<sha256>.json、state/publish-state.json（schema 见 docs/approvals.md）。
CLI 不接受任何自报的批准或状态参数；状态文件读不到 → HOLD（E-ROUTE-STATE）。"""
import argparse, datetime as dt, json, sys
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin.route import route_pr, dry_run, draft_id_for  # noqa: E402
from markjin.approvals import parse_ts  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--pr", type=int, required=True, help="PR 编号；base/head/文件列表由 gh pr view 取得")
ap.add_argument("--repo", required=True); ap.add_argument("--date", required=True)
ap.add_argument("--card-type", required=True, choices=["daily", "signal"])
ap.add_argument("--dry-run", action="store_true", help="演练：可配合 --now 指定时间，结果永远 publishable=false")
ap.add_argument("--now", help="只在 --dry-run 下可用")
ap.add_argument("--site-repo", help="站点仓库本地克隆（更正稿用 origin/main 查原稿是否已发布）")
ap.add_argument("--no-link-check", action="store_true", help=argparse.SUPPRESS)
a = ap.parse_args()
if a.no_link_check:
    print(json.dumps({"state": "HOLD", "codes": ["E-ROUTE-INPUT"], "publishable": False,
                      "detail": "route_pr 不允许关闭链接检查（--no-link-check 已取消）"}, ensure_ascii=False)); sys.exit(1)
if a.now and not a.dry_run:
    print(json.dumps({"state": "HOLD", "codes": ["E-ROUTE-INPUT"], "publishable": False,
                      "detail": "--now 已取消；只在显式 --dry-run 下可用（整体验收 r2，王总定）"}, ensure_ascii=False)); sys.exit(1)
now = None
if a.dry_run:
    now = parse_ts(a.now) if a.now else dt.datetime.now(dt.timezone.utc).astimezone()
    if now is None:
        print(json.dumps({"state": "HOLD", "codes": ["E-ROUTE-INPUT"], "publishable": False})); sys.exit(1)
try:
    if a.dry_run:
        out = dry_run(a.repo, a.pr, a.date, a.card_type, now, site_repo=a.site_repo)   # 永远 publishable=false
    else:
        out = route_pr(a.repo, a.pr, a.date, a.card_type, site_repo=a.site_repo)       # 真实时钟 + 内置链接检查
except (ValueError, RuntimeError) as e:          # 清单为空或 git 失败：明确 HOLD，不发布
    print(json.dumps({"state": "HOLD", "codes": [str(e).split(":")[0]], "publishable": False, "detail": str(e)},
                     ensure_ascii=False)); sys.exit(1)
res = [{"path": p, "draft_id": draft_id_for(a.repo, Path(a.repo) / p), "selfcheck": sc and sc["status"],
        "low_risk": bool(sc and sc["low_risk"]), **asdict(d), "head_sha": getattr(d, "head_sha", None),
        "decided_at": getattr(d, "decided_at", None), "valid_until": getattr(d, "valid_until", None)} for p, (sc, d) in out.items()]
if a.dry_run:
    for r in res:
        r["dry_run"] = True; r["state_change"] = None   # 整体验收 r3：演练不输出可写回的状态变更
print(json.dumps(res[0] if len(res) == 1 else res, ensure_ascii=False))
sys.exit(0 if res and all(r["publishable"] for r in res) else 1)
