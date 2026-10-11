"""按 git 对象（而不是工作树）逐个提交扫描：路径、文件内容、提交说明。

- 目标来自 pre-push 的 stdin（每行 4 个字段：local_ref local_sha remote_ref remote_sha）或显式 --rev/--range。
- stdin 为空、行格式不对、SHA 不是 40 位十六进制 → GitScanError("E-CHECK-STDIN")，调用方必须拒绝推送。
- r6/r7（协调方 Grok Bot 定、王总定）：新分支（remote_sha 全 0）或 remote_sha 本地不存在时，先核验可信上游 main——
  本次推送的目标 URL（pre-push $2）与 origin 的 URL 都必须是 markjin-lab/markjin-data，且目标 URL 上的远端 main
  （ls-remote）等于本地 refs/remotes/origin/main；推往其他远端、或调用方没给目标 URL → 全量扫描；
  核验通过 → 只扫新引入的提交（`rev-list <local_sha> --not <上游 main>`），已在上游 main 历史里的祖先提交不再扫描
  （#34 的 b5cfa0a、c289cb3 不会再拦住推送）；核验失败（URL 不符、联网失败、本地 origin/main 过期或缺失）→ 照旧扫描 local_sha
  可达的全部提交（fail-closed）。不用 --not --remotes（其他远端引用可能过期或被伪造）。新分支与上游 main 相同、或标签指向旧提交（零新增提交）
  → 至少扫描它指向的那个提交（r6 HIGH）。
- 已有分支：同样先核验目标（r8，王总定）；目标可信才扫描 remote_sha..local_sha 的每个提交（区间为空 → E-CHECK-EMPTY，
  拒绝推送），目标不可信（推往其他远端、未给 URL、远端 main ≠ 基线）→ 从 local_sha 全量扫描。
- 附注标签说明逐层扫描，嵌套不设深度上限。
- 每个被扫描提交的完整树都检查（路径 + 内容），并检查其提交说明。
- 路径、内容、提交说明必须是合法 UTF-8；解码失败 → 命中 E-CHECK-DECODE（拒绝），不跳过。
- 子模块（gitlink）或无法读取的对象 → GitScanError("E-CHECK-GIT")。
- 报告只给提交短 SHA、文件序号（该提交树中按路径排序的 1 起序号）与行号，不输出文件名或命中内容。
"""
import hashlib
from pathlib import PurePosixPath
import re
import subprocess

ZERO = "0" * 40
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class GitScanError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _git(args, cwd=None, inp=None):
    r = subprocess.run(["git", *args], cwd=cwd, input=inp, capture_output=True)
    if r.returncode != 0:
        raise GitScanError("E-CHECK-GIT")
    return r.stdout


def parse_push_stdin(text):
    lines = [ln for ln in (text or "").splitlines()]
    if not lines or all(not ln.strip() for ln in lines):
        raise GitScanError("E-CHECK-STDIN")
    out = []
    for ln in lines:
        parts = ln.split(" ")
        if len(parts) != 4 or not SHA_RE.match(parts[1]) or not SHA_RE.match(parts[3]) or not parts[0] or not parts[2]:
            raise GitScanError("E-CHECK-STDIN")
        out.append(tuple(parts))
    return out


TRUSTED_UPSTREAM_RE = re.compile(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)markjin-lab/markjin-data(?:\.git)?/?")


def trusted_upstream_main(cwd=None, remote=None, remote_url=None):
    """可信上游 main 的提交 SHA；核验不通过返回 None（调用方回退到全量扫描）。只读，不 fetch。
    整体验收 r7 BLOCKER 3：必须同时满足——
      ① 本次推送的目标 URL（pre-push $2）就是 markjin-lab/markjin-data；目标远端名（$1）若给出，也必须是 origin；
      ② origin 的 URL（含 pushurl，如有）也是 markjin-lab/markjin-data；
      ③ 目标 URL 上的远端 main（ls-remote）等于本地基线 refs/remotes/origin/main。
    没有给出目标 URL（直接调用、手工运行）→ None → 全量扫描。"""
    def out(args):
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    if not remote_url or not TRUSTED_UPSTREAM_RE.fullmatch(remote_url):
        return None
    if remote not in (None, "", "origin", remote_url):
        return None
    url = out(["config", "--get", "remote.origin.url"])
    if not url or not TRUSTED_UPSTREAM_RE.fullmatch(url):
        return None
    for pu in (out(["config", "--get-all", "remote.origin.pushurl"]) or "").splitlines():
        if not TRUSTED_UPSTREAM_RE.fullmatch(pu.strip()):
            return None
    rem = out(["ls-remote", remote_url, "refs/heads/main"])
    loc = out(["rev-parse", "--verify", "-q", "refs/remotes/origin/main^{commit}"])
    rs = rem.split()[0] if rem and rem.split() else None
    if not rs or not SHA_RE.match(rs) or rs != loc:
        return None
    return loc


def commits_for_push(updates, cwd=None, remote=None, remote_url=None):
    """返回 (待扫描提交, 推送目标提交)。删除远端分支（local_sha 全 0）无内容可查。"""
    seen, order, tips = set(), [], []
    # 整体验收 r8 BLOCKER 3（王总定）：只有一种情况只扫增量——本次推送目标是 markjin-lab/markjin-data，且远端 main
    # 等于本地基线（trusted_upstream_main 核验通过）。新分支与已有分支都一样；其他情况一律从 local_sha 全量扫描。
    base = trusted_upstream_main(cwd, remote, remote_url) if any(u[1] != ZERO for u in updates) else None
    for _lref, lsha, _rref, rsha in updates:
        if lsha == ZERO:
            continue
        exists = rsha != ZERO and subprocess.run(
            ["git", "cat-file", "-e", rsha + "^{commit}"], cwd=cwd, capture_output=True).returncode == 0
        tips.append(_git(["rev-parse", "--verify", lsha + "^{commit}"], cwd).decode().strip())   # 附注标签解析到所指提交
        if exists and not _git(["rev-list", f"{rsha}..{lsha}"], cwd).decode().split():
            # 已有远端分支被强推倒退（或推送不含新提交）：不论目标是否可信，都不当作“检查通过”
            raise GitScanError("E-CHECK-EMPTY")
        if base is None:
            spec = [lsha]                                   # 目标不可信 → 全量
        elif exists:
            spec = [f"{rsha}..{lsha}"]
        else:
            spec = [lsha, "--not", base]
        got = _git(["rev-list", *spec], cwd).decode().split()
        if base is not None and not exists and not got:
            # 整体验收 r6 HIGH：没有新增提交的 ref 更新（如新标签指向上游 main 上的旧提交）→ 至少扫它指向的那个提交
            got = [tips[-1]]
        if base is not None and exists and not got:
            # 已有远端分支被强推倒退（或推送不含新提交）：零个待扫描提交不能当作“检查通过”
            raise GitScanError("E-CHECK-EMPTY")
        for c in got:
            if c not in seen:
                seen.add(c); order.append(c)
    return order, tips


def head_only(cwd=None):
    """整体验收 r12 MEDIUM：不带 --rev/--range 时只查 HEAD 这一个提交对象（与 check-public 用法说明一致），不扫祖先。"""
    h = _git(["rev-parse", "--verify", "HEAD^{commit}"], cwd).decode().strip()
    if not h:
        raise GitScanError("E-CHECK-EMPTY")
    return [h], [h]


def commits_for_revs(revs, ranges, cwd=None):
    seen, order = set(), []
    for spec in [[r] for r in revs] + [[r] for r in ranges]:
        got = _git(["rev-list", *spec], cwd).decode().split()
        if not got:
            raise GitScanError("E-CHECK-EMPTY")  # 任何一个显式 --rev / --range 为空都报错（不能被另一个有效目标掩盖）
        for c in got:
            if c not in seen:
                seen.add(c); order.append(c)
    tips = [_git(["rev-parse", "--verify", r.split("..")[-1] + "^{commit}"], cwd).decode().strip()
            for r in revs + ranges]
    if (revs or ranges) and not order:
        raise GitScanError("E-CHECK-EMPTY")     # 显式给出的 rev/range 解析后没有任何提交：不能报“通过”

    return order, tips


def push_meta(updates, cwd=None):
    """推送里除提交以外、同样会公开的文字：本地/远端引用名，以及附注标签对象的说明（含嵌套标签）。
    返回 [(kind, index, text)]，kind ∈ {"ref", "tag"}；text 为 None 表示解码失败。"""
    out = []
    for n, (lref, lsha, rref, _rsha) in enumerate(updates, 1):
        out.append(("ref", n, _decode(lref.encode("utf-8", "surrogateescape"))))
        out.append(("ref", n, _decode(rref.encode("utf-8", "surrogateescape"))))
        sha, seen = lsha, set()
        while sha != ZERO:                       # 附注标签嵌套不设深度上限，逐层扫到非标签对象为止
            if sha in seen:
                raise GitScanError("E-CHECK-GIT")     # 环（理论上不可能）→ 拒绝
            seen.add(sha)
            typ = _git(["cat-file", "-t", sha], cwd).decode().strip()
            if typ != "tag":
                break
            raw = _git(["cat-file", "tag", sha], cwd)
            head, _, msg = raw.partition(b"\n\n")
            # 标签头（tag 名、tagger 名称/邮箱等）与说明全部扫描；object/type 行只是 SHA 与类型
            hdr = b"\n".join(l for l in head.split(b"\n") if not l.startswith((b"object ", b"type ")))
            out.append(("tag", n, _decode(hdr + b"\n" + msg)))
            sha = next((l[7:].decode() for l in head.split(b"\n") if l.startswith(b"object ")), ZERO)
    return out



class _Binary:
    __slots__ = ("sha256",)

    def __init__(self, h):
        self.sha256 = h


BINARY_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp")
_DAY_MANIFEST_RE = re.compile(r"raw/\d{4}-\d{2}-\d{2}/MANIFEST\.sha256")
_RAW_BIN_RE = re.compile(r"(raw/\d{4}-\d{2}-\d{2})/(.+)")


_MANIFEST_LINE = re.compile(r"^([0-9a-f]{64})  (?:\./)?([^\s].*)$")   # 与 selfcheck.MANIFEST_LINE 相同


def _manifest_lines(text):
    """整体验收 r6 MEDIUM：与 selfcheck._Ctx.manifest() 同一口径严格解析。任一非空行格式不对、路径为绝对路径或含 ..、
    路径首尾有空白、同一路径重复，或没有任何条目 → 整份 MANIFEST 无效，返回空集合（其中的二进制一律不算登记）。"""
    out, names = set(), set()
    for ln in text.splitlines():
        if not ln.strip():
            continue
        m = _MANIFEST_LINE.match(ln)
        if not m:
            return set()
        name = m.group(2)
        pp = PurePosixPath(name)
        if pp.is_absolute() or ".." in pp.parts or name != name.strip() or name in names:
            return set()
        names.add(name); out.add((m.group(1), name))
    return out


def registered_binary(path, sha256, manifests):
    """二进制原件放行条件（整体验收 r1 HIGH 1）：路径为 raw/<日期>/<相对路径>，扩展名在 BINARY_EXT，
    且同一提交树中 raw/<日期>/MANIFEST.sha256 有 "<sha256>  ./<相对路径>" 一行与字节一致。"""
    if not path or not path.lower().endswith(BINARY_EXT):
        return False
    m = _RAW_BIN_RE.fullmatch(path)
    if not m:
        return False
    return (sha256, m.group(2)) in manifests.get(m.group(1), set())


def _decode(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return None


def iter_commit(commit, cwd=None, blob_cache=None):
    """生成 (kind, file_index, path, text) ：kind ∈ {"msg", "path", "blob"}；text 为 None 表示解码失败。"""
    blob_cache = {} if blob_cache is None else blob_cache
    blob_sha = blob_cache.setdefault(" sha256", {})        # 可解码对象的字节 sha256（键带空格，不会与 git 对象 ID 冲突）
    raw = _git(["cat-file", "commit", commit], cwd)
    head, _, msg = raw.partition(b"\n\n")
    # 提交头（author / committer 名称与邮箱、encoding 等）与说明一起扫描；tree/parent 行只是 SHA
    hdr = b"\n".join(l for l in head.split(b"\n") if not l.startswith((b"tree ", b"parent ")))
    yield "msg", 0, None, _decode(hdr + b"\n" + msg)
    listing = _git(["ls-tree", "-r", "-z", "--full-tree", commit], cwd)
    entries = []
    for rec in listing.split(b"\0"):
        if not rec:
            continue
        meta, _, path = rec.partition(b"\t")
        mode, typ, sha = meta.split(b" ")
        if typ != b"blob":
            raise GitScanError("E-CHECK-GIT")
        entries.append((path, sha.decode()))
    entries.sort()
    need = [s for _, s in entries if s not in blob_cache]
    if need:
        out = _git(["cat-file", "--batch"], cwd, inp=("\n".join(dict.fromkeys(need)) + "\n").encode())
        pos = 0
        while pos < len(out):
            nl = out.index(b"\n", pos)
            hdr = out[pos:nl].split(b" ")
            if len(hdr) != 3 or hdr[1] != b"blob":
                raise GitScanError("E-CHECK-GIT")
            size = int(hdr[2]); start = nl + 1
            data = out[start:start + size]
            txt = _decode(data)
            # r-final：无法解码的对象记下字节的 sha256，供登记过的二进制原件放行判断；内容本身不当文本扫描
            blob_cache[hdr[0].decode()] = txt if txt is not None else _Binary(hashlib.sha256(data).hexdigest())
            if txt is not None:
                blob_sha[hdr[0].decode()] = hashlib.sha256(data).hexdigest()
            pos = start + size + 1
    manifests = {}
    for path, sha in entries:
        p = _decode(path)
        if p and _DAY_MANIFEST_RE.fullmatch(p) and isinstance(blob_cache.get(sha), str):
            manifests[p.rsplit("/", 1)[0]] = _manifest_lines(blob_cache[sha])
    for idx, (path, sha) in enumerate(entries, 1):
        p = _decode(path)
        yield "path", idx, p, p
        v = blob_cache[sha]
        if p and p.lower().endswith(BINARY_EXT) and not isinstance(v, _Binary):
            # 整体验收 r4 HIGH：二进制类型（按扩展名）一律先做登记校验，不以 UTF-8 能否解码为启动条件
            yield "blob", idx, p, ("" if registered_binary(p, blob_sha.get(sha), manifests) else None)
            continue
        if isinstance(v, _Binary):
            # 只放行：raw/<日期>/ 下、扩展名在白名单里、且同一提交树的 raw/<日期>/MANIFEST.sha256
            # 以 "<sha256>  ./<相对路径>" 登记了这份字节的二进制原件。其他无法解码的对象仍判 E-CHECK-DECODE。
            yield "blob", idx, p, ("" if registered_binary(p, v.sha256, manifests) else None)
        else:
            yield "blob", idx, p, v


def loc(commit, kind, idx, line):
    if kind in ("ref", "tag"):
        return f"push:#{idx}:{kind}:L{line}"
    if kind == "msg":
        return f"{commit[:12]}:msg:L{line}"
    if kind == "path":
        return f"{commit[:12]}:#{idx}:path"
    return f"{commit[:12]}:#{idx}:L{line}"
