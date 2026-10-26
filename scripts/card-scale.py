#!/usr/bin/env python3
"""用法：scripts/card-scale.py DRAFT.md --repo REPO_ROOT --date YYYY-MM-DD --card-type daily|signal [--json]
         [--no-link-check]

卡片审查量表自动评分（路线图第九节；data#22）。五项否决项，全部达标才 overall_pass。
量表只统计，不改变发布/拒发；本脚本不调用 route。

第(5)项只读本机内部目录下的 frame-conjecture.md（$MARKJIN_INTERNAL_DIR 或 <repo>/../markjin-internal）；
双侧去标签后仅子串匹配（无同义/改写启发式）；无生产路径清单覆盖参数；测试请 mock internal_dir()。
--json 输出公开白名单字段（白名单错误码/计数/比率/日期）；人读模式可显示本机审查侧明细。
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin.card_scale import public_score, score_file  # noqa: E402
from markjin.selfcheck import http_link_checker  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("draft")
ap.add_argument("--repo", required=True)
ap.add_argument("--date", required=True)
ap.add_argument("--card-type", required=True, choices=["daily", "signal"])
ap.add_argument("--json", action="store_true", help="公开白名单 JSON（错误码/计数/比率/日期）")
ap.add_argument("--no-link-check", action="store_true", help="不检查链接（与 selfcheck 一致）")
a = ap.parse_args()
r = score_file(
    a.draft, a.repo, a.date, a.card_type,
    link_checker=None if a.no_link_check else http_link_checker,
)
if a.json:
    print(json.dumps(public_score(r), ensure_ascii=False, indent=2))
else:
    s = r["summary"]
    print(f"card-scale: overall_pass={r['overall_pass']}  "
          f"pass={s['pass_count']}/{s['item_count']}  "
          f"fail={s['fail_count']}  pending_human={s['pending_human_count']}  "
          f"pass_ratio={s['pass_ratio']}  date={s['date']}")
    for k, it in r["items"].items():
        codes = ",".join(it.get("codes") or []) or "-"
        extra = ""
        if k == "no_frame_conjecture":
            extra = f"  list_available={it.get('list_available')}  hit_count={it.get('hit_count')}"
        print(f"  {k}: {it['status']}  codes={codes}{extra}")
sys.exit(0 if r["overall_pass"] else 1)
