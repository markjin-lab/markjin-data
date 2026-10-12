#!/usr/bin/env python3
"""分支台账校验（CI 与本机均可运行）。

用法：
  scripts/check-branches.py [--repo .] [--ref HEAD] [--base REF] [--now TS] [--count-gate [--cutoff D] [--domain D]] [--stats]
- 检查 REF 中的 ledger/branches.csv：表头、逐行规则、行间规则（更正、分组、读数追加）。
- raw 绑定（lu_evidence、quarter_readings、evidence）按 REF 树中 raw/<日期>/MANIFEST.sha256 核对。
- 给出 --base 时逐个提交检查 base..REF：每个提交的台账必须以其父提交的台账为前缀（只追加）；
  已有组在后续提交里不得新增分支（E-BR-GROUP-LATE），同组分支须在同一个提交里登记。
  base 提交不存在或读不出 → 失败；base 中确实没有该文件 → 视为空。
- base 必须是 REF 的祖先（否则 E-BR-NOT-FAST-FORWARD），并直接比较 base 与 REF 的台账（只追加）。
- PR 用 --now（+08:00 完整时间戳，CI 运行时间）：对本次新登记的行和登记更正行核对
  |now − registered_at| ≤ 6 小时，且 now 早于 window_start（当日 00:00 SGT）。
- main 用 --merge-time（合并提交时间）：只核对合并时间早于 window_start。失败的行已落地时，用作废行（VOID）标记。
输出只含行号、提交短 SHA、错误码与计数。退出码 0=通过，1=不通过。
"""
import argparse, json, subprocess, sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import branches  # noqa: E402

MAX_SKEW = timedelta(hours=6)


def _dt(ts):
    return datetime.fromisoformat(ts)


def _rows(text):
    return branches.parse(text)[0] if text else []


def _has_rows(t):
    return len((t or "").splitlines()) > 1


def history_errors(repo, base, ref, now=None, merge_time=None):
    errs = []
    # base 必须是 ref 的祖先（非快进的 push 一律拒绝），并直接比较 base 与 ref 两个版本：只追加
    anc = subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", base, ref], capture_output=True)
    if anc.returncode != 0:
        return [(base[:12], 0, "E-BR-NOT-FAST-FORWARD")]
    b_t, r_t = branches.git_show(repo, base), branches.git_show(repo, ref)
    if b_t is not None and _has_rows(b_t) and (r_t is None or not branches.append_only(b_t, r_t)):
        errs.append((base[:12], 0, "E-BR-NOT-APPEND-ONLY"))
    p = subprocess.run(["git", "-C", repo, "rev-list", "--reverse", "--topo-order", f"{base}..{ref}"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise branches.GitError(base)
    for c in p.stdout.split():
        parents = subprocess.run(["git", "-C", repo, "rev-parse", f"{c}^@"], capture_output=True, text=True).stdout.split()
        old = branches.git_show(repo, parents[0]) if parents else None
        new = branches.git_show(repo, c)
        old_t, new_t = old or "", new or ""
        if new is None and old is not None:
            errs.append((c[:12], 0, "E-BR-LEDGER-REMOVED")); continue
        if new is None:
            continue
        # 只有表头、没有数据行时允许改表头（台账启用前的字段调整）；一旦有数据行，必须严格只追加
        old_has_rows = _has_rows(old_t)
        if old is not None and old_has_rows and not branches.append_only(old_t, new_t):
            errs.append((c[:12], 0, "E-BR-NOT-APPEND-ONLY")); continue
        old_rows, new_rows = _rows(old_t), _rows(new_t)
        old_groups = {branches.group_key(r) for _, r in old_rows}
        old_branches = {branches.branch_key(r) for _, r in old_rows}
        for i, r in new_rows[len(old_rows):]:
            if branches.branch_key(r) not in old_branches and branches.group_key(r) in old_groups:
                errs.append((c[:12], i, "E-BR-GROUP-LATE"))
            is_reg = branches.branch_key(r) not in old_branches or (r["corrects_row_id"] and r["check_result"] == "PENDING")
            if is_reg and branches._ts(r["registered_at"]) and branches._date(r["window_start"]):
                start = _dt(r["window_start"] + "T00:00:00+08:00")
                if now:   # PR：只管本次新登记的行：推送时间与 registered_at 相差 ≤ 6 小时，且早于观测开始
                    n = _dt(now)
                    if abs(n - _dt(r["registered_at"])) > MAX_SKEW:
                        errs.append((c[:12], i, "E-BR-PUSH-SKEW"))
                    if n >= start:
                        errs.append((c[:12], i, "E-BR-PUSH-AFTER-START"))
                if merge_time and _dt(merge_time) >= start:   # main：合并时间早于观测开始
                    errs.append((c[:12], i, "E-BR-MERGE-AFTER-START"))
            if branches.branch_key(r) not in old_branches:
                old_branches.add(branches.branch_key(r))
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--base")
    ap.add_argument("--now", help="PR 用：推送/运行时间，YYYY-MM-DDTHH:MM:SS+08:00（6 小时与观测开始核对）")
    ap.add_argument("--merge-time", help="main 用：合并时间（只核对早于观测开始）")
    ap.add_argument("--count-gate", action="store_true", help="输出门禁计数（每个分支只算第一行）")
    ap.add_argument("--cutoff", default="2026-12-31")
    ap.add_argument("--domain")
    ap.add_argument("--stats", action="store_true", help="输出命中率与更正计数")
    a = ap.parse_args(argv)
    for v in (a.now, a.merge_time):
        if v and not branches._ts(v):
            print("E-BR-NOW 时间格式不对"); return 1
    try:
        new = branches.git_show(a.repo, a.ref)
    except branches.GitError:
        print(f"E-BR-GIT 无法读取 {a.ref}（fail-closed）")
        return 1
    if new is None:
        print(f"E-BR-MISSING {branches.LEDGER_PATH} 不在 {a.ref}")
        return 1
    rows, errs = branches.parse(new, branches.manifest_from_git(a.repo, a.ref))
    out = [f"line {ln}: {code}" for ln, code in errs]
    if a.base:
        try:
            branches.git_show(a.repo, a.base)
            out += [f"commit {c} line {ln}: {code}" for c, ln, code in history_errors(a.repo, a.base, a.ref, a.now, a.merge_time)]
        except branches.GitError:
            print(f"E-BR-BASE-UNREADABLE 基线 {a.base} 不存在或无法读取（fail-closed）")
            return 1
    for x in out:
        print(x)
    if a.count_gate:
        print(f"gate_count {branches.gate_count(rows, a.cutoff, a.domain)} (cutoff {a.cutoff}, domain {a.domain or 'all'})")
    if a.stats:
        print("stats " + json.dumps(branches.hit_stats(rows), ensure_ascii=False, sort_keys=True))
    print("PASS" if not out else f"FAIL ({len(out)})")
    return 0 if not out else 1


if __name__ == "__main__":
    sys.exit(main())
