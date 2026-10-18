#!/usr/bin/env python3
"""逐源可疑状态的查看与人工操作（2026-10-18 新规则，规则见 scripts/markjin/collect.py 的 SourceHealth）。

Usage:
  source_health.py report          --private-root DIR (或 MARKJIN_PRIVATE_DIR) [--out-root REPO_ROOT]
  source_health.py confirm-disable --id SID --reason TEXT ...   # 人工确认停用（通常针对 pending-disable 的源）
  source_health.py enable          --id SID [--reason TEXT] ...  # 人工恢复：状态改回 ok，连续可疑计数清零

只改私有状态文件 PRIVATE/state/source-health.json，不发任何网络请求。report 输出 JSON（只含源 id、状态、轮次与原因，
不含 URL 或本机路径）。Exit code: 0 = ok, 2 = 参数/配置错误或状态文件损坏。
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import collect  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("report", "confirm-disable", "enable"))
    ap.add_argument("--private-root")
    ap.add_argument("--out-root", default=".")
    ap.add_argument("--id")
    ap.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    try:
        root = collect.resolve_private_root(a.private_root, a.out_root)
    except collect.ConfigError as e:
        print(f"config: {e}", file=sys.stderr); return 2
    h = collect.SourceHealth(root / "state" / "source-health.json")
    if h.error:
        print(f"source health invalid: {h.error}", file=sys.stderr); return 2
    try:
        if a.cmd == "report":
            print(json.dumps(h.report(), ensure_ascii=False, indent=1))
            return 0
        if not a.id:
            print("--id required", file=sys.stderr); return 2
        if a.cmd == "confirm-disable":
            if not a.reason.strip():
                print("--reason required (who confirmed, and why)", file=sys.stderr); return 2
            h.set_status(a.id, "disabled", a.reason)
        else:
            h.set_status(a.id, "ok", a.reason or "manually re-enabled")
    except (collect.StateError, collect.ConfigError) as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr); return 2
    print(json.dumps(h.report(sids={a.id}), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
