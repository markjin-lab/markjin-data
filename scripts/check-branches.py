#!/usr/bin/env python3
"""分支台账校验（CI 与本机均可运行）。

用法：
  scripts/check-branches.py [--repo .] [--ref HEAD] [--base REF] [--count-gate [--cutoff YYYY-MM-DD] [--domain D]]
- 检查 REF 中的 ledger/branches.csv：表头、逐行登记规则（N≥1、L≤U、window_quarters 等）、
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
    ap.add_argument("--count-gate", action="store_true", help="输出门禁计数（每个分支只算第一行）")
    ap.add_argument("--cutoff", default="2026-12-31")
    ap.add_argument("--domain")
    a = ap.parse_args(argv)
    new = branches.git_show(a.repo, a.ref)
    if new is None:
        print(f"E-BR-MISSING {branches.LEDGER_PATH} 不在 {a.ref}")
        return 1
    rows, errs = branches.parse(new)
    if a.base:
        old = branches.git_show(a.repo, a.base)
        if old is not None and not branches.append_only(old, new):
            errs.append((0, "E-BR-NOT-APPEND-ONLY"))
    for line, code in errs:
        print(f"line {line}: {code}")
    if a.count_gate:
        print(f"gate_count {branches.gate_count(rows, a.cutoff, a.domain)} (cutoff {a.cutoff}, domain {a.domain or 'all'})")
    print("PASS" if not errs else f"FAIL ({len(errs)})")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
