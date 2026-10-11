#!/usr/bin/env python3
"""本机推送前的内部主题检查（由 scripts/hooks/pre-push 调用；CI 不运行）。

用法：
  scripts/check-internal.py --pre-push        从 stdin 读取 pre-push 行，检查每个 local_sha 对应的 git 对象
  scripts/check-internal.py --rev REV ...      检查 REV 可达的全部提交
  scripts/check-internal.py --range A..B ...   检查区间内的每个提交
  三者都不给 → 拒绝（E-CHECK-STDIN）。不检查工作树。

pre-push 时另查推送的引用名（分支/标签）与附注标签说明。
逐个提交检查：完整树中的每个路径名、每个文件内容（逐行，并在整份文件拼接层面查跨行写法）、提交说明。
词表 = 本机 $MARKJIN_INTERNAL_DIR/topics-private.md 三列全部单元格（严格解析）。fail-closed：
  清单缺失/不可读/结构不完整（E-INTERNAL-LIST-MISSING）、stdin 为空或格式异常（E-CHECK-STDIN）、
  git 调用失败（E-CHECK-GIT）、解码失败（E-CHECK-DECODE）→ 退出码 1，推送被拒。
报错已脱敏：只输出 提交短 SHA、文件序号、行号，不输出文件名、命中词或行内容。"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin.internal import load_internal_terms  # noqa: E402
from markjin.textnorm import compact  # noqa: E402
from markjin import gitscan  # noqa: E402


def hits_in(text, terms):
    """返回命中行号列表（0 = 仅跨行拼接后命中）。"""
    out = []
    for i, line in enumerate(text.splitlines() or [text], 1):
        c = compact(line)
        if any(t in c for t in terms):
            out.append(i)
    if not out and any(t in compact(text) for t in terms):
        out.append(0)
    return out


def main(argv=None, stdin=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pre-push", action="store_true")
    ap.add_argument("--rev", action="append", default=[])
    ap.add_argument("--range", action="append", default=[])
    ap.add_argument("--remote", default=None)       # pre-push 的 $1（远端名）
    ap.add_argument("--remote-url", default=None)   # pre-push 的 $2（本次实际推送的 URL）；缺省 → 全量扫描
    a = ap.parse_args(argv)
    raw_terms = load_internal_terms()
    if not raw_terms:
        print("FAIL E-INTERNAL-LIST-MISSING 本机内部主题清单缺失、不可读或结构不完整，拒绝推送（fail-closed）")
        return 1
    terms = [compact(t) for t in raw_terms if compact(t)]
    try:
        meta = []
        if a.pre_push:
            updates = gitscan.parse_push_stdin((stdin or sys.stdin).read())
            commits, tips = gitscan.commits_for_push(updates, remote=a.remote, remote_url=a.remote_url)
            meta = gitscan.push_meta(updates)            # 分支名 / 标签名 / 附注标签说明也会公开
        elif a.rev or a.range:
            commits, tips = gitscan.commits_for_revs(a.rev, a.range)
        else:
            raise gitscan.GitScanError("E-CHECK-STDIN")
        fail, cache = 0, {}
        for kind, idx, text in meta:
            if text is None:
                print(f"FAIL E-CHECK-DECODE 无法解码: {gitscan.loc('', kind, idx, 0)}"); fail = 1
                continue
            for ln in hits_in(text, terms):
                print(f"FAIL E-BLOCK-INTERNAL 命中内部主题: {gitscan.loc('', kind, idx, ln)}"); fail = 1
        for c in commits:
            for kind, idx, _path, text in gitscan.iter_commit(c, blob_cache=cache):
                if text is None:
                    print(f"FAIL E-CHECK-DECODE 无法解码: {gitscan.loc(c, kind, idx, 0)}"); fail = 1
                    continue
                for ln in hits_in(text, terms):
                    print(f"FAIL E-BLOCK-INTERNAL 命中内部主题: {gitscan.loc(c, kind, idx, ln)}"); fail = 1
    except gitscan.GitScanError as e:
        print(f"FAIL {e.code} 无法完成检查，拒绝推送（fail-closed）")
        return 1
    print("check-internal: " + ("失败" if fail else f"通过（{len(commits)} 个提交，未命中）"))
    return fail


if __name__ == "__main__":
    sys.exit(main())
