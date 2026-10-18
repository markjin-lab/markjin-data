#!/usr/bin/env python3
"""用法：scripts/record-industry-strained.py RESULT.txt --repo REPO_ROOT --date YYYY-MM-DD
日报 Codex 审查结束后运行：从 Codex 结果（result.txt）读出唯一一行 “R-INDUSTRY-STRAINED: <计数>”，
写入公开台账 review/ledger/<date>.jsonl（只写 date、error_code、count；路线图 v1.12 15.5）。
退出码：0=已写入；1=读不出唯一计数（不写，交人工核对）；2=参数或台账写入错误。"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin.industry import record_strained  # noqa: E402
from markjin.ledger import LedgerError  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("result")
ap.add_argument("--repo", required=True)
ap.add_argument("--date", required=True)
a = ap.parse_args()
try:
    text = Path(a.result).read_bytes().decode("utf-8")
except (OSError, UnicodeDecodeError):
    print("record-industry-strained: 结果文件读不出", file=sys.stderr)
    sys.exit(2)
try:
    p = record_strained(a.repo, a.date, text)
except LedgerError as e:
    print(f"record-industry-strained: 台账拒绝写入 {e.args[0]}", file=sys.stderr)
    sys.exit(2)
if p is None:
    print("record-industry-strained: 结果里没有唯一的 R-INDUSTRY-STRAINED 计数行，未写入")
    sys.exit(1)
print(f"record-industry-strained: 已写入 review/ledger/{a.date}.jsonl")
