#!/usr/bin/env python3
"""校验 raw/ 存档（全部从 git 对象读取，不看工作树）。

用法：scripts/verify-raw.sh [BASE] [--target REV]
  BASE 优先级：参数 > 环境变量 VERIFY_RAW_BASE > git merge-base origin/main target（有 origin/main 时）> target^（根提交则只做快照校验）。
  可信基线：日常检查只从 PR 基线 / 推送前远端 sha 往后查；d6f88b5 及更早是规则生效前的历史违规，不回溯（见 raw/README.md）。
  target 缺省 HEAD。BASE 必须是 target 的祖先（非快进 → 失败）。
对 base..target 中每个提交：
  快照：每个 raw/<日期>/ 目录必须有 MANIFEST.sha256；登记行与 blob sha256 一致（RETRACTIONS.md 登记的撤回行仅当文件已不存在时跳过，
        RETRACTIONS.md 只校验最后一条登记）；目录内每个文件都须登记。
  历史（对比第一父提交）：已提交 raw 文件不得修改；删除仅当日 RETRACTIONS.md 登记且 sha256 匹配；
        MANIFEST.sha256 与 RETRACTIONS.md 均按字节前缀只追加，二者都不得删除（只认精确路径 raw/<日期>/，嵌套同名文件按普通 raw 文件）；
        新增撤回登记须对应本提交删除的文件，sha256 与父提交中的 blob 一致。
任何 git 命令失败 → 失败（fail-closed）。
"""
import argparse, hashlib, os, re, subprocess, sys
from collections import Counter

ZERO = "0" * 40
fail = 0


class GitError(Exception):
    pass


def git(*args, ok_fail=False):
    r = subprocess.run(["git", *args], capture_output=True)
    if r.returncode != 0:
        if ok_fail:
            return None
        raise GitError(f"git {' '.join(args)}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def rev(x):
    out = git("rev-parse", "-q", "--verify", f"{x}^{{commit}}", ok_fail=True)
    return out.decode().strip() if out else None


def bad(msg):
    global fail
    print(f"FAIL {msg}"); fail = 1


def blob(commit, path):
    return git("cat-file", "blob", f"{commit}:{path}")


def tree(commit):
    out = git("ls-tree", "-r", "-z", "--full-tree", commit, "--", "raw")
    res = {}
    for ent in out.split(b"\0"):
        if not ent:
            continue
        meta, path = ent.split(b"\t", 1)
        mode, typ, oid = meta.decode().split()
        res[path.decode("utf-8", "surrogateescape")] = (mode, typ, oid)
    return res


def is_day_file(path, name):
    """只认精确路径 raw/<day>/<name>；嵌套子目录中的同名文件按普通 raw 文件处理。"""
    parts = path.split("/")
    return len(parts) == 3 and parts[0] == "raw" and parts[2] == name


def retraction_rows(commit, day, files):
    """按文件顺序返回全部登记行 [(sha 或 None, path)]，保留重复；sha 格式错误的行记为 None。"""
    r = f"raw/{day}/RETRACTIONS.md"
    if r not in files:
        return []
    out = []
    for line in blob(commit, r).decode("utf-8", "replace").splitlines():
        cols = line.split("|")
        if len(cols) > 4 and cols[1].strip().startswith("raw/"):
            p, h = cols[1].replace(" ", ""), cols[3].replace(" ", "")
            out.append((h if re.fullmatch(r"[0-9a-f]{64}", h) else None, p))
    return out


def retracted(commit, day, files):
    return {x for x in retraction_rows(commit, day, files) if x[0]}


def snapshot(commit):
    files = tree(commit)
    days = {}
    for p in files:
        parts = p.split("/")
        if len(parts) >= 3:
            days.setdefault(parts[1], []).append(p)
    for day in sorted(days):
        d, m = f"raw/{day}", f"raw/{day}/MANIFEST.sha256"
        if m not in files:
            bad(f"缺少 MANIFEST.sha256: {d}/ @ {commit[:7]}"); continue
        ret = retracted(commit, day, files)
        listed, okm, lastr = set(), True, None
        for line in blob(commit, m).decode("utf-8", "surrogateescape").splitlines():
            if not line.strip():
                continue
            h, p = line[:64], line[66:]
            p = p[2:] if p.startswith("./") else p
            listed.add(p)
            if p == "RETRACTIONS.md":
                lastr = (h, p); continue
            full = f"{d}/{p}"
            if (h, full) in ret and full not in files:
                continue                # 仅当文件在本提交中确已不存在时才免校验；仍存在的文件照常比对 sha256
            if full not in files or files[full][1] != "blob" or hashlib.sha256(blob(commit, full)).hexdigest() != h:
                print(f"{full}: FAILED"); okm = False
        if lastr:
            full = f"{d}/RETRACTIONS.md"
            if full not in files or hashlib.sha256(blob(commit, full)).hexdigest() != lastr[0]:
                print(f"{full}: FAILED"); okm = False
        print(f"OK   {m}") if okm else bad(m)
        for p in sorted(days[day]):
            rel = p[len(d) + 1:]
            if rel != "MANIFEST.sha256" and rel not in listed:   # 只豁免顶层 MANIFEST 本身
                bad(f"未登记: {p} @ {commit[:7]}")


def raw_tree(commit):
    out = git("ls-tree", "-d", "--full-tree", commit, "--", "raw")
    return out.split()[2] if out.strip() else None


def is_prefix(parent, commit, path):
    old, new = blob(parent, path), blob(commit, path)
    return new[:len(old)] == old


def history(parent, commit, others=()):
    """对比一个父提交。删除须由本提交（相对该父提交）新追加的撤回登记逐条对应；
    合并提交里，另一父提交中已不存在的文件视为该父提交历史中已校验过的删除（继承），其登记行同样视为继承。"""
    out = git("diff", "--name-status", "--no-renames", "-z", parent, commit, "--", "raw", ":(exclude)raw/README.md")
    toks = [t.decode("utf-8", "surrogateescape") for t in out.split(b"\0") if t]
    added, deleted = [], []
    for st, path in zip(toks[0::2], toks[1::2]):
        if st == "A":
            added.append(path)
        elif st == "M":
            if is_day_file(path, "RETRACTIONS.md"):
                if not is_prefix(parent, commit, path):
                    bad(f"RETRACTIONS.md 非追加式修改: {path} @ {commit[:7]}")
            elif is_day_file(path, "MANIFEST.sha256"):
                if not is_prefix(parent, commit, path):
                    bad(f"MANIFEST 删改了旧行（非字节前缀追加）: {path} @ {commit[:7]}")
            else:
                bad(f"已提交 raw 文件被修改: {path} @ {commit[:7]}")
        elif st == "D":
            if is_day_file(path, "RETRACTIONS.md"):
                bad(f"RETRACTIONS.md 被删除: {path} @ {commit[:7]}")
            elif is_day_file(path, "MANIFEST.sha256"):
                bad(f"MANIFEST 被删除（基线行必须保留）: {path} @ {commit[:7]}")
            else:
                deleted.append(path)
        else:
            bad(f"已提交 raw 文件被删除/改名({st}): {path} @ {commit[:7]}")
    days = {p.split("/")[1] for p in added + deleted if len(p.split("/")) >= 3}
    days |= {p.split("/")[1] for p in toks[1::2] if is_day_file(p, "RETRACTIONS.md")}
    if not days:
        return
    cfiles, pfiles = tree(commit), tree(parent)
    ofiles = {q: tree(q) for q in others}
    for day in sorted(days):
        crows, prows = retraction_rows(commit, day, cfiles), retraction_rows(parent, day, pfiles)
        new = crows[len(prows):] if crows[:len(prows)] == prows else crows   # 只校验新追加的一段（保留顺序与重复）
        inherit = Counter()
        for q in others:
            qc = Counter(retraction_rows(q, day, ofiles[q])) - Counter(prows)
            inherit |= qc
        pending = []
        for row in new:
            if inherit[row] > 0:
                inherit[row] -= 1; continue
            if row[0] is None:
                bad(f"RETRACTIONS.md 登记行 sha256 格式错误: {row[1]} @ {commit[:7]}"); continue
            pending.append(row)
        retracted_paths = {p for _, p in crows}
        for path in added:
            if path.split("/")[1] == day and path in retracted_paths:
                bad(f"新增文件的路径已在 RETRACTIONS.md 中登记撤回（不得重新加回）: {path} @ {commit[:7]}")
        for path in deleted:
            if path.split("/")[1] != day:
                continue
            if any(path not in ofiles[q] for q in others):
                print(f"RETRACTED {path}（继承自另一父提交）"); continue
            h = hashlib.sha256(blob(parent, path)).hexdigest()
            if (h, path) in pending:
                pending.remove((h, path)); print(f"RETRACTED {path}（见 RETRACTIONS.md）")
            elif any(p == path for _, p in pending):
                bad(f"撤回登记 sha256 与父提交中被删除文件不符: {path} @ {commit[:7]}")
                pending = [x for x in pending if x[1] != path]
            else:
                bad(f"已提交 raw 文件被删除，且本提交没有新追加对应的撤回登记: {path} @ {commit[:7]}")
        for h, p in pending:
            if p not in pfiles or pfiles[p][1] != "blob":
                bad(f"撤回登记的文件在父提交中不存在: {p} @ {commit[:7]}")
            elif p in cfiles:
                bad(f"撤回登记的文件在本提交中仍存在: {p} @ {commit[:7]}")
            else:
                bad(f"撤回登记没有对应本提交的删除: {p} @ {commit[:7]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?")
    ap.add_argument("--target", default="HEAD")
    a = ap.parse_args()
    os.chdir(git("rev-parse", "--show-toplevel").decode().strip())
    target = rev(a.target)
    if not target:
        bad(f"目标提交不可用: {a.target}"); return
    base = a.base or os.environ.get("VERIFY_RAW_BASE") or ""
    if base == ZERO:
        base = ""
    if base:
        b = rev(base)
        if not b:
            bad(f"基线提交不可用: {base}"); return
        base = b
    else:
        # 无显式基线：origin/main 存在 → git merge-base origin/main target；不存在 → target^（根提交则只做快照）
        om = git("for-each-ref", "--format=%(objectname)", "refs/remotes/origin/main").decode().strip()
        if om:
            r = subprocess.run(["git", "merge-base", om, target], capture_output=True)
            if r.returncode == 1:
                bad(f"目标 {target[:7]} 与 origin/main 无共同祖先"); return
            if r.returncode != 0:
                raise GitError(f"git merge-base: {r.stderr.decode(errors='replace').strip()}")
            base = r.stdout.decode().strip()
        else:
            base = rev(f"{target}^") or ""
    if base:
        r = subprocess.run(["git", "merge-base", "--is-ancestor", base, target], capture_output=True)
        if r.returncode == 1:
            bad(f"基线 {base[:7]} 不是目标 {target[:7]} 的祖先（非快进，存档历史不可改写）"); return
        if r.returncode != 0:
            raise GitError(f"git merge-base --is-ancestor: {r.stderr.decode(errors='replace').strip()}")
    commits = git("rev-list", "--reverse", "--topo-order", f"{base}..{target}" if base else target).decode().split()
    if not commits:
        commits = [target]          # base == target：仍检查目标提交本身（快照 + 对父提交）
    for c in commits:
        parents = git("rev-list", "--parents", "-n", "1", c).decode().split()[1:]
        # 快照：目标提交总是检查；中间提交仅当 raw/ 树相对第一父提交有变化时检查
        # （raw/ 未变的提交快照与父提交相同：父提交在区间内已查过，或是可信基线）。
        if c == target or not parents or raw_tree(c) != raw_tree(parents[0]):
            snapshot(c)
        for p in parents:           # 合并提交：对每个父提交都检查
            history(p, c, [q for q in parents if q != p])
    print(f"verify-raw: 全部通过（基线 {base[:7] or '无'}，{len(commits)} 个提交）" if not fail else "verify-raw: 失败")


if __name__ == "__main__":
    try:
        main()
    except GitError as e:
        bad(f"git 命令失败: {e}"); print("verify-raw: 失败")
    sys.exit(1 if fail else 0)
