#!/usr/bin/env python3
"""从 scripts/markjin/codes.py 重新生成 review/error-codes.md。
--check：只比对，不写文件；不一致时退出码 1（CI 与测试用，整体验收 r1 MEDIUM 2）。"""
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "scripts"))
from markjin.codes import ERROR_CODES  # noqa: E402


def render():
    rows = "\n".join(f"| `{k}` | {v} |" for k, v in ERROR_CODES.items())
    return ("# 错误码表\n\n由 `scripts/markjin/codes.py` 生成（`python3 scripts/gen-error-codes.py`），以代码为准。"
            "台账只能引用本表登记的错误码。\n\n| 错误码 | 含义 |\n|---|---|\n" + rows + "\n")


out = root / "review/error-codes.md"
if "--check" in sys.argv[1:]:
    ok = out.exists() and out.read_text(encoding="utf-8") == render()
    print("error-codes: 一致" if ok else "error-codes: 与 codes.py 不一致，请运行 python3 scripts/gen-error-codes.py")
    sys.exit(0 if ok else 1)
out.write_text(render(), encoding="utf-8")
