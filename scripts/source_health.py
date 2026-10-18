#!/usr/bin/env python3
"""逐源可疑状态的查看与人工操作（2026-10-18 新规则，规则见 scripts/markjin/collect.py 的 SourceHealth）。

Usage:
  source_health.py report          --private-root DIR (或 MARKJIN_PRIVATE_DIR) [--out-root REPO_ROOT]
  source_health.py confirm-disable --id SID --reason TEXT ...   # 人工确认停用（通常针对 pending-disable 的源）
  source_health.py enable          --id SID [--reason TEXT] ...  # 人工恢复：状态改回 ok，连续可疑计数清零
  source_health.py enable          --host HOST --reason TEXT ... # 人工恢复旧表导入的停用主机
  source_health.py import-legacy   ...                           # 显式导入 PRIVATE/state/collector-hosts.json（幂等）

旧 collector-hosts.json 里的主机 / 源一律导入为「已停用、等人工复核」（采集脚本启动时也会自动导入）：不自动恢复，
不参与 3 轮计数。因机器人验证（bot_check）或登录（login）停用的标 unrecoverable：enable 默认拒绝，
只有加 --allow-unrecoverable 并用 --reason 写明谁、依据什么复核过才放行。

只改私有状态文件 PRIVATE/state/source-health.json，不发任何网络请求。report 输出 JSON（源 id、状态、轮次与原因，
以及旧表停用主机；不含 URL 或本机路径），只打到终端，不写进公开目录。
Exit code: 0 = ok, 2 = 参数/配置错误、状态文件损坏，或拒绝恢复 unrecoverable 条目。
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import collect  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("report", "confirm-disable", "enable", "import-legacy"))
    ap.add_argument("--private-root")
    ap.add_argument("--out-root", default=".")
    ap.add_argument("--id")
    ap.add_argument("--host")
    ap.add_argument("--reason", default="")
    ap.add_argument("--allow-unrecoverable", action="store_true",
                    help="允许恢复标 unrecoverable（机器人验证 / 登录）的条目；须同时用 --reason 写明复核依据")
    a = ap.parse_args(argv)
    try:
        root = collect.resolve_private_root(a.private_root, a.out_root)
        h, imported = collect.open_source_health(root)
    except collect.ConfigError as e:
        print(f"config: {e}", file=sys.stderr); return 2
    except (collect.StateError, OSError) as e:
        print(f"source health invalid: {e}", file=sys.stderr); return 2
    if h.error:
        print(f"source health invalid: {h.error}", file=sys.stderr); return 2
    try:
        if a.cmd == "report":
            print(json.dumps({"sources": h.report(), "disabled_hosts": h.host_report()}, ensure_ascii=False, indent=1))
            return 0
        if a.cmd == "import-legacy":
            print(json.dumps(imported or {"hosts": 0, "sources": 0, "skipped": False, "legacy_file": "absent"},
                             ensure_ascii=False))
            return 0
        if a.cmd == "enable" and a.host:
            if a.id:
                print("give --id or --host, not both", file=sys.stderr); return 2
            if not a.reason.strip():
                print("--reason required (who reviewed the host, and why)", file=sys.stderr); return 2
            h.enable_host(a.host, a.reason, allow_unrecoverable=a.allow_unrecoverable)
            print(json.dumps({"host": a.host.lower(), "status": "enabled"}, ensure_ascii=False))
            return 0
        if not a.id:
            print("--id required", file=sys.stderr); return 2
        if a.cmd == "confirm-disable":
            if not a.reason.strip():
                print("--reason required (who confirmed, and why)", file=sys.stderr); return 2
            h.set_status(a.id, "disabled", a.reason)
        else:
            h.set_status(a.id, "ok", a.reason or "manually re-enabled", allow_unrecoverable=a.allow_unrecoverable)
    except (collect.StateError, collect.ConfigError) as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr); return 2
    print(json.dumps(h.report(sids={a.id}), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
