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
- 可信合并时间（--main-ref + --push-runs）：每条登记行和登记更正行 = head_sha 恰为其首次进入 main 的提交的最早 push 运行的
  created_at，必须早于 window_start。查不到判“时间未知”，不顺延。时间相关问题只输出 warn，不改退出码；
  晚合并组自动排除，时间未知或缺 --main-ref / 运行记录时 gate_count / stats 输出 INVALID。计数只是预估，以人工核对为准。
输出只含行号、提交短 SHA、错误码与计数。退出码 0=通过，1=不通过。
"""
import argparse, json, re, subprocess, sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import branches  # noqa: E402

MAX_SKEW = timedelta(hours=6)
VOID_CODES = {"E-BR-VOID-PARTIAL", "E-BR-VOID-FILLED", "E-BR-AFTER-VOID", "E-BR-VOID-SPLIT", "E-BR-VOID-UNVERIFIED"}


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


RUN_RE = re.compile(r"(?<![\w:])run:(\d+)(?!\d)")


def run_ids(reason):
    """从 reason 里解析出完整的 run:<id>，精确比较用（run:9010 不等于 run:901）。"""
    return set(RUN_RE.findall(reason))


def first_on_main(repo, main_ref):
    """{row_id: 首次出现该行的 main（first-parent）提交}。"""
    log = _git(repo, "log", "--first-parent", "--reverse", "--format=%H", main_ref, "--", branches.LEDGER_PATH)
    present = {}
    for c in log.stdout.split():
        for _, x in _rows(branches.git_show(repo, c) or ""):
            present.setdefault(x["row_id"], c)
    return present


def row_time(c, runs):
    """可信时间 = head_sha 恰为 c 的最早一次 push 运行的 created_at。查不到就是“时间未知”，
    不拿后来的运行顺延（一次 push 多个提交、运行记录过期或超出 1000 条上限时都会落到这里）。"""
    hits = [(t, rid_) for rid_, head, t in (runs or []) if head == c]
    return (min(hits)[1], min(hits)[0]) if hits else (None, None)


def trust_check(repo, rows, main_ref, runs):
    """全量复核每一条已进 main 的登记行和登记更正行：其可信时间必须早于 window_start。
    返回 (errors, warnings, late_groups, counts_valid)。时间相关的问题只给警告，不让 main 一直红；
    但只要有时间未知，门禁与命中率就输出 INVALID。"""
    errs, warns, late, late_run, valid = [], [], set(), {}, True
    present = first_on_main(repo, main_ref)
    # 登记行（每支第一行）和登记更正行，各用自己首次进入 main 的时间核对
    regs = [(ln, r) for ln, r in rows if r["check_result"] == "PENDING" and r["row_id"] in present
            and (r["corrects_row_id"] or r["row_id"].endswith("-r1"))]
    if regs and runs is None:
        warns.append((0, "W-BR-PUSH-TIME-UNAVAILABLE")); valid = False
    unknown = set()
    for ln, r in regs:
        g = branches.group_key(r)
        rid_, t = row_time(present[r["row_id"]], runs)
        if rid_ is None:
            unknown.add(g)
            if runs is not None:
                warns.append((ln, "W-BR-PUSH-TIME-UNKNOWN")); valid = False
        elif t >= _dt(r["window_start"] + "T00:00:00+08:00"):
            late.add(g); late_run.setdefault(g, rid_)
    complete = branches.complete_void_groups(rows)
    first = {}
    for ln, r in rows:
        first.setdefault(branches.group_key(r), ln)
    for g in late:
        if g not in complete:
            warns.append((first[g], "W-BR-LATE-UNHANDLED"))
    for ln, r in branches.active_voids(rows):
        g = branches.group_key(r)
        if g in unknown or (regs and runs is None):
            warns.append((ln, "W-BR-VOID-UNVERIFIABLE")); valid = False
        elif g not in late or run_ids(r["reason"]) != {late_run[g]}:
            warns.append((ln, "E-BR-VOID-UNVERIFIED")); valid = False
    return errs, warns, late, valid


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
    warns, late, valid = [], set(), True
    if a.main_ref:
        if not branches.commit_exists(a.repo, a.main_ref):
            print(f"E-BR-MAIN-REF {a.main_ref} 不是可读的提交"); return 1
        t_errs, warns, late, valid = trust_check(a.repo, rows, a.main_ref, load_runs(a.push_runs))
        out += [f"line {ln}: {code}" for ln, code in t_errs]
    else:
        valid = False   # 没有 main 引用就无法核对可信时间，计数不作数
    if a.base:
        try:
            branches.git_show(a.repo, a.base)
            out += [f"commit {c} line {ln}: {code}" for c, ln, code in history_errors(a.repo, a.base, a.ref, a.now)]
        except branches.GitError:
            print(f"E-BR-BASE-UNREADABLE 基线 {a.base} 不存在或无法读取（fail-closed）")
            return 1
    # 自动排除与 VOID 相关的问题一律只警告（main 和 PR 都一样），不改退出码，但计数输出 INVALID
    void_lines = {str(ln) for ln, r in rows if r["check_result"] in ("VOID", "VOID_REVOKED")}
    keep = []
    for x in out:
        code = x.rsplit(": ", 1)[-1]
        ln = x.split("line ", 1)[-1].split(":", 1)[0]
        if code in VOID_CODES or ln in void_lines:
            warns.append((ln, code)); valid = False
        else:
            keep.append(x)
    out = keep
    for x in out:
        print(x)
    for ln, code in warns:   # 时间相关问题只作警告输出，不改变退出码
        print(f"warn line {ln}: {code}")
    # 检查失败、缺 main 引用或运行记录、时间未知时，不输出看起来有效的计数；有效时也只是预估，以人工核对为准
    ok = not out and valid
    if a.count_gate:
        n = branches.gate_count(rows, a.cutoff, a.domain, late) if ok else "INVALID"
        print(f"gate_count {n} (cutoff {a.cutoff}, domain {a.domain or 'all'}; 预估，以人工核对为准)")
    if a.stats:
        print("stats " + (json.dumps(branches.hit_stats(rows, late), ensure_ascii=False, sort_keys=True) if ok else "INVALID"))
    print("PASS" if not out else f"FAIL ({len(out)})")
    return 0 if not out else 1


if __name__ == "__main__":
    sys.exit(main())
