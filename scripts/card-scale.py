#!/usr/bin/env python3
"""用法：scripts/card-scale.py DRAFT.md --repo REPO_ROOT --date YYYY-MM-DD --card-type daily|signal [--json]
         [--no-link-check] [--frame-list PATH]

卡片审查量表自动评分（路线图第九节；data#22）。五项否决项，全部达标才 overall_pass。
量表只统计，不改变发布/拒发；本脚本不调用 route。

第(5)项默认只读本机内部目录下的 frame-conjecture.md（$MARKJIN_INTERNAL_DIR 或 <repo>/../markjin-internal）；
--frame-list 仅供本机测试注入临时 fixture，不得把真实私有清单提交进公开仓。
公开 JSON 只含错误码、计数、比率、日期与各项 status，不含命中原文或清单路径。
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin.card_scale import score_file  # noqa: E402
from markjin.selfcheck import http_link_checker  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("draft")
ap.add_argument("--repo", required=True)
ap.add_argument("--date", required=True)
ap.add_argument("--card-type", required=True, choices=["daily", "signal"])
ap.add_argument("--json", action="store_true")
ap.add_argument("--no-link-check", action="store_true", help="不检查链接（与 selfcheck 一致）")
ap.add_argument("--frame-list", help="测试用临时清单路径（生产勿用真实清单路径写入公开输出）")
a = ap.parse_args()
r = score_file(
    a.draft, a.repo, a.date, a.card_type,
    link_checker=None if a.no_link_check else http_link_checker,
    frame_list_path_override=a.frame_list,
)
if a.json:
    print(json.dumps(r, ensure_ascii=False, indent=2))
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
