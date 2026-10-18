#!/usr/bin/env python3
"""来源健康状态的查看与人工操作（封锁规则见 scripts/markjin/collect.py「封锁规则与来源健康状态」）。

Usage:
  source_health.py report          --private-root DIR (或 MARKJIN_PRIVATE_DIR) [--out-root REPO_ROOT]
  source_health.py migrate         ...                           # 迁移 PRIVATE/state/collector-hosts.json（幂等）
  source_health.py confirm-disable --id SID --reason TEXT ...   # 人工确认停用（通常针对 pending-disable 的源，立即生效）
  source_health.py enable          --id SID [--reason TEXT] ...  # 人工恢复：状态改回 ok，可疑轮次清空
  source_health.py enable          --host HOST --reason TEXT --approved-by grok-bot|review-bot (--quote-ref REF | --review-commit SHA) ...
                                                                 # 人工恢复旧表迁移来的停用主机（须书面批准，引用只能用一次）
  source_health.py approve-retest  --source KEY --approved-by grok-bot|review-bot (--quote-ref REF | --review-commit SHA) ...
                                                                 # 批准一次重测（冷却到期、标为待批准重测的来源；只放行一次请求）

旧 collector-hosts.json 存在且未迁移时，采集脚本和本工具的其他命令都拒绝运行（退出码 2）。migrate 把其中每个主机 / 源
迁移为「已停用（等人工复核）」：不请求、不自动恢复、不参与可疑计数。因机器人验证（bot_check）或登录（login）停用的标
unrecoverable：永不恢复（enable 一律拒绝，没有放行开关），只能改 sources.yaml 并重新审批。原因写法含糊或未知的同样不可恢复。

人工批准门禁（Grok Bot 2026-10-18 20:51 SGT）：URL / 来源冷却到期后，采集脚本不自动再请求，只把来源标成「待批准重测」
（report 的 retest 一节，status=pending-approval）。enable --host 与 approve-retest 都必须带 Grok Bot 或审查 bot 的书面批准：
--approved-by 写批准方，--quote-ref（批准消息的引用，格式同 docs/approvals.md 的 quote_ref）或 --review-commit（审查记录的
提交号）至少一个。每个引用只能用一次；批准的重测只放行一次正文请求（robots.txt 按规则先取、不占这一次），之后本轮该来源不再请求；
收到不可疑的响应 → 下一轮起照常，可疑 → 重新冷却 24 小时，没收到响应 → 重新待批准。

只改私有状态文件 PRIVATE/state/source-health.json，不发任何网络请求。report 输出 JSON（源 id、状态、轮次与原因，
以及旧表停用主机；不含 URL 或本机路径），只打到终端，不写进公开目录：其中 status_reason_private 与旧表 reason 是自由文本
（人工 --reason、旧表原因原文），只留在私有状态与终端。采集脚本写进公开目录的报告只含固定代码（r15 ⑦）。
Exit code: 0 = ok, 2 = 参数/配置错误、状态文件损坏、旧表未迁移，或拒绝恢复 unrecoverable 条目（永不恢复）。
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import collect  # noqa: E402


def _approval(a):
    """命令行参数里的书面批准；缺批准方或引用 → ConfigError（退出码 2）。"""
    if not a.approved_by:
        raise collect.ConfigError("--approved-by grok-bot|review-bot required (written approval)")
    return collect.make_approval(a.approved_by, a.quote_ref, a.review_commit)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("report", "migrate", "confirm-disable", "enable", "approve-retest"))
    ap.add_argument("--private-root")
    ap.add_argument("--out-root", default=".")
    ap.add_argument("--id")
    ap.add_argument("--host")
    ap.add_argument("--reason", default="")
    ap.add_argument("--source", help="approve-retest: 来源键（见 report 的 retest 一节）")
    ap.add_argument("--approved-by", help="grok-bot 或 review-bot（书面批准方）")
    ap.add_argument("--quote-ref")
    ap.add_argument("--review-commit")
    a = ap.parse_args(argv)
    try:
        root = collect.resolve_private_root(a.private_root, a.out_root)
    except collect.ConfigError as e:
        print(f"config: {e}", file=sys.stderr); return 2
    try:
        if a.cmd == "migrate":
            h = collect.SourceHealth(root / "state" / "source-health.json")
            if h.error:
                print(f"source health invalid: {h.error}", file=sys.stderr); return 2
            legacy = root / "state" / collect.LEGACY_HOSTS_FILE
            res = h.migrate_legacy(legacy) if legacy.exists() else {"hosts": 0, "sources": 0, "skipped": False,
                                                                    "legacy_file": "absent"}
            print(json.dumps(res, ensure_ascii=False))
            return 0
        h = collect.open_source_health(root)
        if a.cmd == "report":
            print(json.dumps({"sources": h.report(include_text=True), "disabled_hosts": h.host_report(),
                              "retest": h.retest_report()}, ensure_ascii=False,
                             indent=1))   # 只打到终端（私有）：可含 status_reason 原文
            return 0
        if a.cmd == "approve-retest":
            if not (a.source or "").strip():
                print("--source required", file=sys.stderr); return 2
            h.approve_retest(a.source.strip(), _approval(a))
            print(json.dumps({"source": a.source.strip(), "retest": "approved"}, ensure_ascii=False))
            return 0
        if a.cmd == "enable" and a.host:
            if a.id:
                print("give --id or --host, not both", file=sys.stderr); return 2
            if not a.reason.strip():
                print("--reason required (who reviewed the host, and why)", file=sys.stderr); return 2
            h.enable_host(a.host, a.reason, _approval(a))
            print(json.dumps({"host": a.host.lower(), "status": "enabled"}, ensure_ascii=False))
            return 0
        if not a.id:
            print("--id required", file=sys.stderr); return 2
        if a.cmd == "confirm-disable":
            if not a.reason.strip():
                print("--reason required (who confirmed, and why)", file=sys.stderr); return 2
            h.set_status(a.id, "disabled", a.reason)
        else:
            h.set_status(a.id, "ok", a.reason or "manually re-enabled")
        print(json.dumps(h.report(sids={a.id}), ensure_ascii=False))
    except (collect.StateError, collect.ConfigError, OSError) as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
