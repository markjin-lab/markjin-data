#!/usr/bin/env python3
"""用法：scripts/selfcheck.py DRAFT.md --repo REPO_ROOT --date YYYY-MM-DD --card-type daily|signal [--json]
三个参数都必须显式给出（不退回当前目录，不默认 daily）。默认检查来源链接能否打开（--no-link-check 关闭）。
退出码：0=PASS，1=FAIL（当天不发布），2=UNCLEAR（分类不明，当天不发布）。
王总 t161u（原话“1、行；2、按新写法，每天过codex”）：日报一律过 Codex，不再有自动批准；
PASS 与 low_risk、R-* 只作审查参考，任何稿件都须取得有效 Codex APPROVED 才能发布。"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin.selfcheck import check_file, http_link_checker  # noqa: E402
from markjin.codes import ERROR_CODES  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("draft")
ap.add_argument("--repo", required=True)
ap.add_argument("--date", required=True)
ap.add_argument("--card-type", required=True, choices=["daily", "signal"])
ap.add_argument("--json", action="store_true")
ap.add_argument("--no-link-check", action="store_true", help="不检查链接（结果带 R-LINK-UNCHECKED，非低风险）")
a = ap.parse_args()
r = check_file(a.draft, a.repo, a.date, a.card_type, link_checker=None if a.no_link_check else http_link_checker)
if a.json:
    print(json.dumps(r, ensure_ascii=False, indent=2))
else:
    print(f"selfcheck: {r['status']}  low_risk={r['low_risk']}  counts={r['counts']}")
    for e in r["errors"]:
        print(f"  L{e['line']:<4} {e['code']}  {ERROR_CODES[e['code']]}")
    for c in r["error_codes"]:
        if c.startswith("R-"):
            print(f"  审查原因 {c}  {ERROR_CODES[c]}")
sys.exit({"PASS": 0, "FAIL": 1, "UNCLEAR": 2}[r["status"]])
