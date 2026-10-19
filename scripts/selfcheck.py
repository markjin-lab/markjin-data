#!/usr/bin/env python3
"""用法：scripts/selfcheck.py DRAFT.md --repo REPO_ROOT --date YYYY-MM-DD --card-type daily|signal [--json] [--baseline FILE | --baseline-ref REF]
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
g = ap.add_mutually_exclusive_group()
g.add_argument("--baseline", help="已发布旧版稿件文件：E-FRED-CITED 只查相对它新增或改动的行")
g.add_argument("--baseline-ref", help="git 提交（在 --repo 里）：取该提交上同一路径的旧版作基准；该路径不存在时按新稿查全部行")
a = ap.parse_args()
baseline = None
if a.baseline:
    baseline = Path(a.baseline).read_bytes().decode("utf-8")
elif a.baseline_ref:
    import subprocess
    rel = Path(a.draft).resolve().relative_to(Path(a.repo).resolve()).as_posix()
    p = subprocess.run(["git", "-C", a.repo, "show", f"{a.baseline_ref}:{rel}"], capture_output=True)
    if p.returncode == 0:
        baseline = p.stdout.decode("utf-8")
    elif subprocess.run(["git", "-C", a.repo, "rev-parse", "--verify", "--quiet", a.baseline_ref + "^{commit}"],
                        capture_output=True).returncode != 0:
        sys.exit(f"selfcheck: --baseline-ref {a.baseline_ref} 不是可用的提交")
r = check_file(a.draft, a.repo, a.date, a.card_type, link_checker=None if a.no_link_check else http_link_checker,
               baseline=baseline)
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
