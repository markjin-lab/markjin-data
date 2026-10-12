#!/usr/bin/env python3
"""公开仓库守卫（CI 与本机均可运行，不依赖本机内部清单）。检查 git 对象，不检查工作树。

用法：
  scripts/check-public.py --pre-push          从 stdin 读取 pre-push 行，检查每个 local_sha 对应的提交
  scripts/check-public.py                      只检查 HEAD 这一个提交对象（不扫祖先，供 CI 使用）
  scripts/check-public.py --rev REV...         检查 REV 可达的全部提交（全史审计用）
  scripts/check-public.py --range A..B         检查区间内的每个提交

逐个提交检查完整树与提交说明：
（原第 1 项“两个硬规则禁词”已于 2026-10-11 解禁撤除，见 docs/approvals.md「解禁记录」。）
1) 解码失败拒绝；
2) 不跟踪内部材料路径（topics-private*、markjin-internal/）；
3) 每个推送目标提交的树中必须有 review/ledger/；每个被扫描提交中，review/ledger/ 下只允许 .gitkeep 与 YYYY-MM-DD.jsonl，
   台账非空、无重复键，每行通过字段白名单、真实日历日期、与文件名日期一致、card_id 有对应公开稿件锚点的校验。
解码失败（E-CHECK-DECODE）、stdin 为空或格式异常（E-CHECK-STDIN）、git 失败（E-CHECK-GIT）一律拒绝。
4) 新增 raw/ 文件不得含 /workspace/、/home/ 本机绝对路径或指向它们的 file: URI（先网址解码；只豁免 http(s)://主机 开头的网址；JSON 先解码）（E-PUBLIC-LOCAL-PATH；本规则引入前已提交的文件豁免）。
内部主题词检查不在这里（见 check-internal.py，仅本机 pre-push）。输出已脱敏：只给提交短 SHA、文件序号、行号。"""
import argparse, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin.ledger import (verify_text, LEDGER_DIR, unique_anchors, is_public_draft, review_path_ok,  # noqa: E402
                            review_record_errors)
from markjin import gitscan  # noqa: E402

def internal_path(p):
    parts = p.split("/")
    return any(x.startswith("topics-private") for x in parts) or "markjin-internal" in parts


# 2026-10-12 合规撤回：新增 raw/ 文件不得含本机绝对路径（'/workspace/'）。
# 豁免：本规则引入前已提交的文件（基线 main@224fd88 树中已有的 raw 路径），以及该提交父提交中已存在的同一路径。
# 按 URI 判断（r3）：
#  - file: URI 指向 /workspace 或 /home 时命中（file:/、file://localhost/、file:///、大小写不敏感）；file:///etc/hosts 等不算；
#  - 裸 /workspace、/home 路径命中，除非它所在的词以 http:// 或 https:// 加主机开头（路径段、?p=/workspace 查询、#/… 片段都属于该网址）；
#  - 先解码：每个候选串再做一次网址解码（%2Fworkspace 等）；整份或逐行 JSON 解析后检查每个字符串（键与值），另把 JSON 转义 \/ 还原为 / 再检查原文。
FILE_URI_RE = re.compile(r"(?i)(?<![A-Za-z0-9+.\-])file:(?://[^/\s\"'<>]*)?/+(?:workspace|home)(?![A-Za-z0-9_.\-])")
BARE_LOCAL_RE = re.compile(r"(?<![A-Za-z0-9._~%\\\-])/(?:workspace|home)(?![A-Za-z0-9_.\-])")
HTTP_URL_RE = re.compile(r"(?i)https?://[A-Za-z0-9\[]")
TOKEN_DELIM = set(" \t\r\n\"'<>()[]{},`|")


def _all_pairs(pairs):
    """重复键也全部保留（键和值都要检查），对象解码为扁平列表。"""
    return [x for kv in pairs for x in kv]


def _json_strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for k, x in v.items():
            yield k
            yield from _json_strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from _json_strings(x)


def _candidates(text):
    import json
    yield text
    yield text.replace("\\/", "/")
    try:
        yield from _json_strings(json.loads(text, object_pairs_hook=_all_pairs)); return
    except (ValueError, RecursionError):
        pass
    for line in text.splitlines():
        line = line.strip()
        if line[:1] in "[{\"":
            try:
                yield from _json_strings(json.loads(line, object_pairs_hook=_all_pairs))
            except (ValueError, RecursionError):
                pass


def _hits(s):
    if FILE_URI_RE.search(s):
        return True
    for m in BARE_LOCAL_RE.finditer(s):
        i = m.start()
        while i > 0 and s[i - 1] not in TOKEN_DELIM:
            i -= 1
        if not HTTP_URL_RE.match(s, i):
            return True
    return False


def has_local_path(text):
    from urllib.parse import unquote
    return any(_hits(c) or _hits(unquote(c)) for c in _candidates(text))


LOCAL_PATH_BASELINE = "224fd88fd0321652a184679664fb5bb5e6a1c730"


def _tree_paths(rev):
    import subprocess
    r = subprocess.run(["git", "ls-tree", "-r", "-z", "--name-only", "--full-tree", rev, "--", "raw"],
                       capture_output=True)
    if r.returncode != 0:
        return set()                     # 基线/父提交不存在（如测试仓库、根提交）→ 无豁免
    return {x.decode("utf-8", "surrogateescape") for x in r.stdout.split(b"\0") if x}


def local_path_exempt_paths(commit):
    import subprocess
    paths = set(_tree_paths(LOCAL_PATH_BASELINE + "^{commit}"))
    r = subprocess.run(["git", "rev-list", "--parents", "-n", "1", commit], capture_output=True, text=True)
    for parent in (r.stdout.split()[1:] if r.returncode == 0 else []):
        paths |= _tree_paths(parent)
    return paths


def main(argv=None, stdin=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pre-push", action="store_true")
    ap.add_argument("--rev", action="append", default=[])
    ap.add_argument("--range", action="append", default=[])
    ap.add_argument("--remote", default=None)       # pre-push 的 $1（远端名）
    ap.add_argument("--remote-url", default=None)   # pre-push 的 $2（本次实际推送的 URL）；缺省 → 全量扫描
    a = ap.parse_args(argv)
    fail = 0
    try:
        if a.pre_push:
            commits, tips = gitscan.commits_for_push(gitscan.parse_push_stdin((stdin or sys.stdin).read()),
                                                   remote=a.remote, remote_url=a.remote_url)
        else:
            if not a.rev and not a.range:
                commits, tips = gitscan.head_only()      # r12：不带参数只查 HEAD 提交对象（不扫祖先），与用法说明一致
            else:
                commits, tips = gitscan.commits_for_revs(a.rev, a.range)
        cache = {}
        for c in commits:
            has_ledger_dir = False
            items = list(gitscan.iter_commit(c, blob_cache=cache))
            anchors = unique_anchors([text for kind, idx, path, text in items
                                      if kind == "blob" and path and text is not None and is_public_draft(path)])
            exempt = None
            for kind, idx, path, text in items:
                if (kind == "blob" and path and path.startswith("raw/") and text is not None
                        and has_local_path(text)):
                    if exempt is None:
                        exempt = local_path_exempt_paths(c)
                    if path not in exempt:
                        print(f"FAIL E-PUBLIC-LOCAL-PATH 新增 raw 文件含本机绝对路径: {gitscan.loc(c, kind, idx, 0)}"); fail = 1
                where = lambda ln: gitscan.loc(c, kind, idx, ln)  # noqa: E731
                if text is None:
                    print(f"FAIL E-CHECK-DECODE 无法解码: {where(0)}"); fail = 1
                    continue
                if kind == "path":
                    if internal_path(text):
                        print(f"FAIL E-PUBLIC-INTERNAL-PATH 内部材料路径被跟踪: {where(0)}"); fail = 1
                    if text.startswith(LEDGER_DIR + "/"):
                        has_ledger_dir = True
                    if text.startswith("review/") and not review_path_ok(text):
                        print(f"FAIL E-REVIEW-PATH review/ 下出现白名单以外的路径: {where(0)}"); fail = 1
                if kind == "blob" and path and path.startswith("review/") and not path.startswith(LEDGER_DIR + "/"):
                    for code in review_record_errors(path, text):
                        print(f"FAIL {code} review/ 记录格式不合规: {where(0)}"); fail = 1
                if kind == "blob" and path and path.startswith(LEDGER_DIR + "/"):
                    rest = path[len(LEDGER_DIR) + 1:]
                    found = [(0, "E-LEDGER-FILE")] if "/" in rest else verify_text(rest, text, anchors)
                    for ln, code in found:
                        print(f"FAIL 台账 {code}: {where(ln)}"); fail = 1
            if c in tips and not has_ledger_dir:
                print(f"FAIL E-LEDGER-DIR 提交树缺少 {LEDGER_DIR}/: {c[:12]}"); fail = 1
    except gitscan.GitScanError as e:
        print(f"FAIL {e.code} 无法完成检查（fail-closed）")
        return 1
    print("check-public: " + ("失败" if fail else f"通过（{len(commits)} 个提交）"))
    return fail


if __name__ == "__main__":
    sys.exit(main())
