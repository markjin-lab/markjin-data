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
- 可信合并时间（--main-ref + --push-runs）：每组 = 这组行第一次进入 main 的那次 push 运行的 created_at。每次全量复核：
  不早于 window_start（或取不到）的组自动排除出门禁和命中率，并持续报 E-BR-LATE-UNHANDLED，直到追加整组 VOID 留痕
  （reason 写 run:<运行 ID>）。无效 VOID 可用 VOID_REVOKED 撤销。检查失败时 gate_count / stats 输出 INVALID。
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


def _git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)


def _no_dup(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError(f"duplicate key {k}")
        d[k] = v
    return d


def load_runs(path):
    """可信 push 时间：CI 先用 gh api 只读取出 main 上 push 事件的运行，写成 JSON 列表
    [{"id": 运行 ID, "head_sha": ..., "created_at": ISO 时间}]。读不出 → None（从严）。"""
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_no_dup)
        return [(str(x["id"]), x["head_sha"], _dt(x["created_at"].replace("Z", "+00:00"))) for x in data]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def trusted_times(repo, rows, main_ref, runs):
    """每组的可信合并时间 = 这组行第一次进入 main 的那次 push 运行的 created_at。
    先沿 main 的 first-parent 历史找到这组第一支登记行首次出现的提交 c，再取 head_sha 为 c（或以 c 为祖先）的最早一次 push 运行。
    返回 {组: (run_id 或 None, 时间 或 None)}；不在 main 上的组不出现。"""
    out = {}
    if not main_ref or not rows:
        return out
    log = _git(repo, "log", "--first-parent", "--reverse", "--format=%H", main_ref, "--", branches.LEDGER_PATH)
    commits = log.stdout.split()
    present = {}
    for c in commits:
        for _, x in _rows(branches.git_show(repo, c) or ""):
            present.setdefault(x["row_id"], c)
    for _, r in rows:
        g = branches.group_key(r)
        if g in out or r["row_id"] not in present:
            continue
        c = present[r["row_id"]]
        best = None
        for rid_, head, t in (runs or []):
            if head == c or _git(repo, "merge-base", "--is-ancestor", c, head).returncode == 0:
                if best is None or t < best[1]:
                    best = (rid_, t)
        out[g] = best or (None, None)
    return out


def trust_errors(repo, rows, main_ref, runs):
    """全量复核：返回 (错误, 晚合并的组)。晚合并（可信时间不早于 window_start，或取不到时间）的组自动排除；
    未用完整作废行留痕的晚合并组持续报 E-BR-LATE-UNHANDLED；作废行只在组确属晚合并、reason 写明 run:<运行 ID> 时有效。"""
    errs, late = [], set()
    times = trusted_times(repo, rows, main_ref, runs)
    if times and runs is None:
        errs.append(("-", 0, "E-BR-PUSH-TIME-UNAVAILABLE"))
    first = {}
    for ln, r in rows:
        first.setdefault(branches.group_key(r), (ln, r))
    complete = branches.complete_void_groups(rows)
    for g, (run_id, t) in times.items():
        ln, r = first[g]
        start = _dt(r["window_start"] + "T00:00:00+08:00")
        if run_id is None:
            late.add(g)
            if runs is not None:
                errs.append(("-", ln, "E-BR-PUSH-TIME-MISSING"))
        elif t >= start:
            late.add(g)
        if g in late and g not in complete:
            errs.append(("-", ln, "E-BR-LATE-UNHANDLED"))
    for ln, r in branches.active_voids(rows):
        g = branches.group_key(r)
        run_id = times.get(g, (None, None))[0]
        if g not in late or run_id is None or f"run:{run_id}" not in r["reason"]:
            errs.append(("-", ln, "E-BR-VOID-UNVERIFIED"))
    return errs, late


def history_errors(repo, base, ref, now=None):
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
        # 全组作废必须在同一个提交里完成
        added = new_rows[len(old_rows):]
        for g in {branches.group_key(r) for _, r in added if r["check_result"] == "VOID"}:
            ks = {branches.branch_key(r) for _, r in new_rows if branches.group_key(r) == g}
            vk = {branches.branch_key(r) for _, r in added if branches.group_key(r) == g and r["check_result"] == "VOID"}
            if vk != ks:
                errs.append((c[:12], 0, "E-BR-VOID-SPLIT"))
        old_branches = {branches.branch_key(r) for _, r in old_rows}
        for i, r in new_rows[len(old_rows):]:
            if branches.branch_key(r) not in old_branches and branches.group_key(r) in old_groups:
                errs.append((c[:12], i, "E-BR-GROUP-LATE"))
            if r["check_result"] in ("VOID", "VOID_REVOKED"):
                continue
            is_reg = branches.branch_key(r) not in old_branches or (r["corrects_row_id"] and r["check_result"] == "PENDING")
            if is_reg and branches._ts(r["registered_at"]) and branches._date(r["window_start"]):
                start = _dt(r["window_start"] + "T00:00:00+08:00")
                if now:   # PR：只管本次新登记的行：推送时间与 registered_at 相差 ≤ 6 小时，且早于观测开始
                    n = _dt(now)
                    if abs(n - _dt(r["registered_at"])) > MAX_SKEW:
                        errs.append((c[:12], i, "E-BR-PUSH-SKEW"))
                    if n >= start:
                        errs.append((c[:12], i, "E-BR-PUSH-AFTER-START"))
            if branches.branch_key(r) not in old_branches:
                old_branches.add(branches.branch_key(r))
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--base")
    ap.add_argument("--now", help="PR 用：推送/运行时间，YYYY-MM-DDTHH:MM:SS+08:00（6 小时与观测开始核对）")
    ap.add_argument("--main-ref", help="main 提交（PR 取 base，main push 取 HEAD）：据此找每组首次进入 main 的提交")
    ap.add_argument("--push-runs", help="main 上 push 事件运行的 JSON（CI 用 gh api 只读取得）；读不出时从严")
    ap.add_argument("--count-gate", action="store_true", help="输出门禁计数（每个分支只算第一行）")
    ap.add_argument("--cutoff", default="2026-12-31")
    ap.add_argument("--domain")
    ap.add_argument("--stats", action="store_true", help="输出命中率与更正计数")
    a = ap.parse_args(argv)
    for v in (a.now,):
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
    t_errs, late = trust_errors(a.repo, rows, a.main_ref, load_runs(a.push_runs))
    out += [f"line {ln}: {code}" for _, ln, code in t_errs]
    if a.base:
        try:
            branches.git_show(a.repo, a.base)
            out += [f"commit {c} line {ln}: {code}" for c, ln, code in history_errors(a.repo, a.base, a.ref, a.now)]
        except branches.GitError:
            print(f"E-BR-BASE-UNREADABLE 基线 {a.base} 不存在或无法读取（fail-closed）")
            return 1
    for x in out:
        print(x)
    # 检查失败时不输出看起来有效的计数
    if a.count_gate:
        n = branches.gate_count(rows, a.cutoff, a.domain, late) if not out else "INVALID"
        print(f"gate_count {n} (cutoff {a.cutoff}, domain {a.domain or 'all'})")
    if a.stats:
        print("stats " + (json.dumps(branches.hit_stats(rows, late), ensure_ascii=False, sort_keys=True) if not out else "INVALID"))
    print("PASS" if not out else f"FAIL ({len(out)})")
    return 0 if not out else 1


if __name__ == "__main__":
    sys.exit(main())
