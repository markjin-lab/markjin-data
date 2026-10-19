#!/usr/bin/env python3
"""用法：scripts/selfcheck.py DRAFT.md --repo REPO_ROOT --date YYYY-MM-DD --card-type daily|signal [--json] [--baseline-ref REF]
三个参数都必须显式给出（不退回当前目录，不默认 daily）。默认检查来源链接能否打开（--no-link-check 关闭）。
退出码：0=PASS，1=FAIL（当天不发布），2=UNCLEAR（分类不明，当天不发布），3=输入错误（E-SELFCHECK-INPUT）。
王总 t161u（原话“1、行；2、按新写法，每天过codex”）：日报一律过 Codex，不再有自动批准；
PASS 与 low_risk、R-* 只作审查参考，任何稿件都须取得有效 Codex APPROVED 才能发布。"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin.selfcheck import check_file, http_link_checker  # noqa: E402
from markjin.codes import ERROR_CODES  # noqa: E402

ap = argparse.ArgumentParser(allow_abbrev=False)   # 不接受缩写：--baseline 不能被当成 --baseline-ref
ap.add_argument("draft")
ap.add_argument("--repo", required=True)
ap.add_argument("--date", required=True)
ap.add_argument("--card-type", required=True, choices=["daily", "signal"])
ap.add_argument("--json", action="store_true")
ap.add_argument("--no-link-check", action="store_true", help="不检查链接（结果带 R-LINK-UNCHECKED，非低风险）")
ap.add_argument("--baseline-ref", help="已发布旧版所在的 git 提交（在 --repo 里，须是 origin/main 的祖先）：E-FRED-CITED 只查相对"
                "该提交上同一路径旧版新增或改动的行；该路径在提交里不存在时按新稿查全部行")
a = ap.parse_args()


def input_error(msg):
    """输入错误：明确报告并以 3 退出；--json 时输出结构化结果。"""
    if a.json:
        print(json.dumps({"status": "INPUT-ERROR", "errors": [{"code": "E-SELFCHECK-INPUT", "line": 0, "detail": msg}]},
                         ensure_ascii=False, indent=2))
    else:
        print(f"selfcheck: INPUT-ERROR  E-SELFCHECK-INPUT  {msg}", file=sys.stderr)
    sys.exit(3)


baseline = None
if a.baseline_ref:
    import subprocess
    git = ["git", "-C", a.repo]
    if subprocess.run(git + ["rev-parse", "--verify", "--quiet", a.baseline_ref + "^{commit}"], capture_output=True).returncode != 0:
        input_error(f"--baseline-ref {a.baseline_ref} 不是可用的提交")
    if subprocess.run(git + ["merge-base", "--is-ancestor", a.baseline_ref, "origin/main"], capture_output=True).returncode != 0:
        input_error(f"--baseline-ref {a.baseline_ref} 不是 origin/main 的祖先提交（基准只能取已发布的版本）")
    try:
        rel = Path(a.draft).resolve().relative_to(Path(a.repo).resolve()).as_posix()
    except ValueError:
        input_error("稿件不在 --repo 内，无法在基准提交里定位同一路径")
    p = subprocess.run(git + ["show", f"{a.baseline_ref}:{rel}"], capture_output=True)
    if p.returncode == 0:
        try:
            baseline = p.stdout.decode("utf-8")
        except UnicodeDecodeError:
            input_error("基准提交里的旧版不是 UTF-8")
try:
    r = check_file(a.draft, a.repo, a.date, a.card_type, link_checker=None if a.no_link_check else http_link_checker,
                   baseline=baseline)
except ValueError as ex:
    input_error(str(ex))
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
