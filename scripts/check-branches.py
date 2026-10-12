#!/usr/bin/env python3
"""分支台账校验（CI 与本机均可运行）。

用法：
  scripts/check-branches.py [--repo .] [--ref HEAD] [--base REF]
- 检查 REF 中的 ledger/macro-branches.csv：表头、逐行登记规则（N≥1、L≤U、window_quarters 等）、
  同一 draft_id+branch_order 的事先登记字段不变。
- 给出 --base 且 base 中已有该文件时，另查只追加：新文件必须以旧文件为前缀。
输出只含行号与错误码。退出码 0=通过，1=不通过。
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import branches  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--base")
    a = ap.parse_args(argv)
    new = branches.git_show(a.repo, a.ref)
    if new is None:
        print(f"E-BR-MISSING {branches.LEDGER_PATH} 不在 {a.ref}")
        return 1
    _, errs = branches.parse(new)
    if a.base:
        old = branches.git_show(a.repo, a.base)
        if old is not None and not branches.append_only(old, new):
            errs.append((0, "E-BR-NOT-APPEND-ONLY"))
    for line, code in errs:
        print(f"line {line}: {code}")
    print("PASS" if not errs else f"FAIL ({len(errs)})")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
