#!/usr/bin/env python3
"""审计 approvals/ 只追加（协调决定 2026-10-10）。用法：scripts/audit-approvals.py [--repo .] [--ref origin/main]

用 git log 沿 REF 的全部历史检查：
  1) approvals/codex/、approvals/wang/ 下已有文件从未被修改、删除、改名或改类型（git log --diff-filter=MDT --no-renames）；
  2) 每个记录文件符合 docs/approvals.md 的严格 schema，文件名等于 content_sha256；
  3) state/publish-state.json 中已归档条目从未被修改或删除。
所有 bot 共用一个 GitHub 账号，本脚本不按提交者判断写入方；只报告提交短 SHA 与错误码。退出码非 0 表示失败。"""
import argparse, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import approvals as A  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=None); ap.add_argument("--ref", default="origin/main")
a = ap.parse_args()
repo = a.repo or subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
if not repo:
    print("FAIL E-ROUTE-STATE 找不到仓库"); sys.exit(1)
fail = 0
r = subprocess.run(["git", "-C", repo, "log", "--format=%h", "--no-renames", "--diff-filter=MDT", a.ref, "--",
                    A.CODEX_DIR, A.WANG_DIR], capture_output=True, text=True)
if r.returncode != 0:
    print(f"FAIL E-ROUTE-STATE 无法读取 {a.ref} 的历史"); sys.exit(1)
for h in r.stdout.split():
    print(f"FAIL E-ROUTE-APPROVALS-REWRITTEN 提交 {h} 修改/删除了已有批准记录"); fail = 1
try:
    A.check_history(repo, a.ref)
except A.ApprovalsError as e:
    if e.code != "E-ROUTE-APPROVALS-REWRITTEN":
        print(f"FAIL {e.code}"); fail = 1
for d, v in ((A.CODEX_DIR, A.valid_codex), (A.WANG_DIR, A.valid_wang)):
    try:
        n = len(A.load_dir(repo, a.ref, d, v))
    except A.ApprovalsError as e:
        print(f"FAIL {e.code} {d}/ 有不合 schema 的记录"); fail = 1
    else:
        print(f"{d}/: {n} 条记录合规")
print("audit-approvals: " + ("失败" if fail else "通过"))
sys.exit(fail)
