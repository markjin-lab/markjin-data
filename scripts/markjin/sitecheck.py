"""站点 PR 的更正规则检查（Grok Bot 2026-10-18；PR #52 r1 审查后改为按 Hugo 实际发布结果判定）。

route_pr 只看数据仓库顶层的 daily/、digest/ 等稿件，站点 PR 直接改 content/posts/（或 content/cards/）页面时，
更正规则（E-ROUTE-CORRECTION-*）没人检查。本模块对站点仓库某个 base..head 范围内改动的页面做同一套检查，
front matter 解析、日期解析、标题行可见文字的判断复用 route.py，不另写一份。

“已发布”按 Hugo 判定：把 merge-base 与 head 两个提交各自导出（git archive，不动工作树），用站点部署所用的同一版本
Hugo 以同一时钟（默认当前时间）构建，`hugo list published` 中 kind=page、且构建输出里确有对应 HTML 的页面才算已发布
（草稿、未来 date/publishDate、过期 expiryDate、build.render: never、cascade 继承的同类设置都不算）。

对 merge-base(base, head)..head 中每个改动的页面 content/posts/<section>/<name>[.en].md、content/cards/<name>[.en].md：
- base 上已发布的页面：
  · 删除、改名，或 head 上不再发布、permalink 改变 → E-SITE-PAGE-DELETED；
  · 有改动但 front matter 没有 corrects 与 corrected_at → E-SITE-CORRECTION-MISSING；
- base 上未发布的页面（含新增、草稿、未来稿）且不带更正字段 → 不查（首次发布前的修改）；
- 带更正字段的页面按 route._correction 的同一组规则：
  · 缺一、为空或不是字符串 → E-ROUTE-CORRECTION-INVALID；
  · corrects 须等于由路径推出的 draft_id（<section>-<name>[-en]，卡片为 cards-<name>[-en]），页面须在 base 上已发布，
    base 版 front matter 须有合法 date → 否则 E-ROUTE-CORRECTION-TARGET；
  · corrected_at 须是 YYYY-MM-DD，不早于页面日期（base 版 date 按 SGT 取日期）、不晚于今天（SGT）、不早于 base 版已有的
    corrected_at；head 版 date 须与 base 版完全相同 → 否则 E-ROUTE-CORRECTION-DATE；
  · 更正区须有与 corrected_at 对应的新格式条目或过渡期旧格式标题（route.correction_heading_ok）→ 否则 E-ROUTE-CORRECTION-NOTE；
    普通改动（无论同日或跨日）还须让写有本次 corrected_at 的更正次数比 base 版多，纯格式迁移例外 → 否则 E-ROUTE-CORRECTION-NOTE。
- 路径推不出合法 draft_id 的已发布页面被改动 → E-ROUTE-CORRECTION-TARGET（不能用怪路径绕开规则）。
- front matter 解析失败 → E-ROUTE-FRONT-MATTER。
- 读不到对象、非 UTF-8 路径或内容、Hugo 缺失或版本与站点部署不符、构建失败 → E-SITE-INPUT（失败关闭）。
列表页（_index.md，kind 不是 page）、模板、配置、静态文件不查。
"""
import csv
import datetime as dt
import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from . import route as R

SITE_PAGE_ROOTS = (R.SITE_CONTENT + "/", R.SITE_CARDS + "/")
DEPLOY_WORKFLOW = ".github/workflows/hugo.yml"
_HEADING_RE = re.compile(r"^[ ]{0,3}#{1,6}[ \t]")


class SiteInputError(RuntimeError):
    pass


def hugo_bin():
    return os.environ.get("MARKJIN_HUGO") or "hugo"


def page_draft_id(path):
    """站点页面路径 → draft_id（route.site_path 的逆映射）；推不出合法 draft_id → None。"""
    p = PurePosixPath(path)
    name = p.name
    if not name.endswith(".md"):
        return None
    en = name.endswith(".en.md")
    stem = name[: -len(".en.md")] if en else name[: -len(".md")]
    if not en and stem.endswith(R.EN_SUFFIX):
        return None                          # a-en.md 与 a.en.md 不得推出同一 draft_id（r1 MEDIUM 6）
    parts = p.parts
    if len(parts) == 4 and "/".join(parts[:2]) == R.SITE_CONTENT:
        sec = parts[2]
        if sec == R.CARD_SECTION:
            return None                      # 卡片只认 content/cards/<name>.md（与 route.site_path 一致）
    elif len(parts) == 3 and "/".join(parts[:2]) == R.SITE_CARDS:
        sec = R.CARD_SECTION
    else:
        return None
    if not R.SECTION_RE.fullmatch(sec) or not R.SEG_RE.fullmatch(stem):
        return None
    did = f"{sec}-{stem}" + (R.EN_SUFFIX if en else "")
    if not R.DRAFT_ID_RE.fullmatch(did) or R.site_path(did, en) != path:
        return None
    return did


def _git_ok(repo, *args, text=True):
    r = R._git(repo, *args, text=text)
    if r.returncode != 0:
        raise SiteInputError(f"E-SITE-INPUT: git {' '.join(str(a) for a in args[:2])} 失败")
    return r.stdout


def _show_required(repo, ref, path):
    r = R._git(repo, "show", f"{ref}:{path}", text=False)
    if r.returncode != 0:
        raise SiteInputError(f"E-SITE-INPUT: 无法读取 {ref}:{path}")
    try:
        return r.stdout.decode("utf-8")
    except UnicodeDecodeError:
        raise SiteInputError(f"E-SITE-INPUT: 非 UTF-8 内容 {path}") from None


def changed_pages(repo, base, head):
    """返回 (merge-base, [(状态, 路径)])；只含 content/posts、content/cards 下的 .md。不跟踪改名（改名 = 删除 + 新增）。
    diff 按字节解析：NUL 字段须成对，路径须是严格 UTF-8，否则 E-SITE-INPUT（r1 MEDIUM 5）。"""
    mb = _git_ok(repo, "merge-base", base, head).strip()
    out = _git_ok(repo, "diff", "--name-status", "--no-renames", "-z", mb, head, "--",
                  R.SITE_CONTENT, R.SITE_CARDS, text=False)
    toks = out.split(b"\0")
    if toks and toks[-1] == b"":
        toks = toks[:-1]
    if len(toks) % 2:
        raise SiteInputError("E-SITE-INPUT: git diff 输出字段不成对")
    pairs = []
    for i in range(0, len(toks), 2):
        try:
            st, path = toks[i].decode("ascii"), toks[i + 1].decode("utf-8")
        except UnicodeDecodeError:
            raise SiteInputError("E-SITE-INPUT: 非 UTF-8 路径") from None
        if st[:1] not in ("A", "M", "D", "T"):
            raise SiteInputError(f"E-SITE-INPUT: 未知 diff 状态 {st}")
        if path.endswith(".md") and path.startswith(SITE_PAGE_ROOTS):
            pairs.append((st[0], path))
    return mb, pairs


def required_hugo_version(repo, ref):
    """站点部署工作流（.github/workflows/hugo.yml）按 YAML 解析出的 jobs.build.env.HUGO_VERSION（没有则取顶层 env.HUGO_VERSION）；
    注释里的同形文字不算。缺失或读不出 → E-SITE-INPUT（PR #52 r2 LOW 6、r7 MEDIUM 4）。"""
    import yaml
    r = R._git(repo, "show", f"{ref}:{DEPLOY_WORKFLOW}")
    version = None
    try:
        wf = yaml.safe_load(r.stdout) if r.returncode == 0 else None
        if isinstance(wf, dict):
            job_env = ((wf.get("jobs") or {}).get("build") or {}).get("env") or {}
            top_env = wf.get("env") or {}
            version = job_env.get("HUGO_VERSION") if isinstance(job_env, dict) and "HUGO_VERSION" in job_env \
                else (top_env.get("HUGO_VERSION") if isinstance(top_env, dict) else None)
    except (yaml.YAMLError, AttributeError, TypeError):
        version = None
    m = re.fullmatch(r"v?(\d+\.\d+\.\d+)", version) if isinstance(version, str) else None
    if not m:
        raise SiteInputError("E-SITE-INPUT: 无法从站点部署工作流确定 Hugo 版本")
    return m.group(1)


def _visible_candidate_indices(lines, indices):
    """indices 里渲染后可见的那些行号（代码块、注释、隐藏元素里的不算；PR #52 r7 MEDIUM 2）。"""
    token = uuid.uuid4().hex
    probe = list(lines)
    for i in indices:
        probe[i] += f"\ue000{token}:{i}\ue001"
    shown = R.visible_text("\n".join(probe), body_only=True, correction_syntax=True)
    return [i for i in indices if f"\ue000{token}:{i}\ue001" in shown]


def check_hugo(want):
    exe = shutil.which(hugo_bin())
    if not exe:
        raise SiteInputError("E-SITE-INPUT: 找不到 hugo")
    v = subprocess.run([exe, "version"], capture_output=True, text=True)
    if v.returncode != 0 or not re.search(r"\bv" + re.escape(want) + r"\b", v.stdout):
        raise SiteInputError(f"E-SITE-INPUT: 本机 hugo 版本与站点部署（{want}）不符")
    return exe


def rendered_pages(repo, ref, clock, exe):
    """{源路径: permalink}：ref 这一版在 clock 时刻会实际生成 HTML 的 kind=page 页面（只含 content/posts、content/cards）。"""
    data = _git_ok(repo, "archive", "--format=tar", ref, text=False)
    with tempfile.TemporaryDirectory(prefix="sitecheck-") as tmp:
        src, pub = Path(tmp) / "src", Path(tmp) / "public"
        src.mkdir()
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            for m in tf.getmembers():
                if m.issym() or m.islnk() or m.name.startswith("/") or ".." in PurePosixPath(m.name).parts:
                    raise SiteInputError("E-SITE-INPUT: 站点归档含链接或越界路径")
            if hasattr(tarfile, "data_filter"):
                tf.extractall(src, filter="data")
            else:
                tf.extractall(src)
        env = {**os.environ, "HUGO_ENVIRONMENT": "production", "HUGO_ENV": "production"}
        ls = subprocess.run([exe, "list", "published", "--clock", clock, "-s", str(src)],
                            capture_output=True, text=True, env=env)
        bd = subprocess.run([exe, "--quiet", "--clock", clock, "-s", str(src), "-d", str(pub)],
                            capture_output=True, text=True, env=env)
        if ls.returncode != 0 or bd.returncode != 0:
            raise SiteInputError(f"E-SITE-INPUT: hugo 构建 {ref} 失败")
        out = {}
        for row in csv.DictReader(io.StringIO(ls.stdout)):
            path = (row.get("path") or "").replace("\\", "/")
            if row.get("kind") != "page" or not path.startswith(SITE_PAGE_ROOTS):
                continue
            permalink = row.get("permalink") or ""
            rel = urlparse(permalink).path.lstrip("/")
            if not rel:
                continue                     # build.render: never 等不生成页面时 permalink 为空，不能落到首页
            html = pub / rel / "index.html" if rel.endswith("/") else pub / rel
            if html.is_file():
                out[path] = permalink        # 存完整 permalink：只改 baseURL 主机名也算 URL 改变（PR #52 r3 MEDIUM 1）
        return out


def _corrections_dated(body, at, en):
    """写有日期 at 的更正次数。新格式页只数更正区里日期为 at 的条目（其他带日期的标题不算，PR #52 r2 MEDIUM 3）；
    旧格式页取 max(带该日期的可见标题数, 该日期的更正说明行数)（10-12 这类首条更正说明没有标题）。
    同日再次更正时，head 的次数必须多于 base（新增一条）；格式迁移本身不改变次数。"""
    heads, entries = R.correction_section(body, en)
    if heads:
        return sum(1 for d, _ in entries if d == at)
    vis = R.visible_text(body, body_only=True, correction_syntax=True).splitlines()
    dated_heads = R.old_correction_heading_dates(body).count(at)   # 只数旧格式更正标题（PR #52 r3 MEDIUM 3）
    notes = sum(1 for ln in vis if (m := _OLD_NOTE_RE[en].match(ln.strip())) and m.group(1) == at)
    return max(dated_heads, notes)


# —— 旧格式 → 新格式的纯格式迁移（Grok Bot 要求的明确例外，Issue #71）
_OLD_NOTE_RE = {False: re.compile(r"^\*更正说明（(\d{4}-\d{2}-\d{2})）：(.*)\*$"),
                True: re.compile(r"^\*Correction note \((\d{4}-\d{2}-\d{2})\): (.*)\*$")}
_OLD_HEAD_RE = {False: re.compile(r"^## 更正 (\d{4}-\d{2}-\d{2})(?:[：:].*)?$"),
                True: re.compile(r"^## Correction (\d{4}-\d{2}-\d{2})(?:: .*)?$")}
_NEW_HEAD = {False: "## 更正", True: "## Corrections"}
_OLD_HEAD_GENERIC = {False: "本次修订的具体内容见下方更正说明。", True: "The note below lists the changes in this revision."}
# 页首一行的白名单：只允许在下列写法之间互换，前面列出的更正日期必须一字不差
_TOP_LINE_RE = {False: re.compile(r"^\*本文于 (.+?) 更正，说明见文末(?:「更正」)?。\*$"),
                True: re.compile(r"^\*This article was corrected on (.+?); see (?:the notes? at the end|Corrections at the end)\.\*$")}


def format_migration_only(old, new, en):
    """只把旧格式更正区改成新格式、不动其他内容 → True（不算新更正）。条件全部满足才成立：
    front matter 原文逐字节相同；旧版更正区（第一条到最后一条旧格式更正说明/更正标题之间，只含这两种行与空行）
    与新版更正区（唯一的「## 更正」/「## Corrections」标题及紧随其后的条目行与空行）以外的正文逐字节相同，
    页首一行只许按 _TOP_LINE_RE 白名单改写；旧版更正说明的（日期, 说明）与新版条目一一对应、文字完全相同；新版条目按日期升序。"""
    mo, mn = R._FM_RE.match(old), R._FM_RE.match(new)
    if not mo or not mn or mo.group(0) != mn.group(0):
        return False
    ol, nl = old[mo.end():].split("\n"), new[mn.end():].split("\n")
    oidx = _visible_candidate_indices(ol, [i for i, ln in enumerate(ol) if _OLD_NOTE_RE[en].match(ln) or _OLD_HEAD_RE[en].match(ln)])
    if not oidx:
        return False
    o0, o1 = oidx[0], oidx[-1]
    keep = set(oidx)
    if any(ln.strip() and i not in keep for i, ln in enumerate(ol[o0:o1 + 1], o0)):
        return False
    raw_notes = sorted((m.group(1), m.group(2)) for m in (_OLD_NOTE_RE[en].match(ln) for ln in ol[o0:o1 + 1]) if m)
    # 某日期有更正说明行时：该日期的旧标题不多于说明行，旧标题若有通用句以外的实质说明，须原样出现在说明里（PR #52 r2 MEDIUM 4）。
    # 某日期只有旧标题、没有说明行时：旧标题的实质说明就是这次更正的说明，迁成同文字的条目；说明为空或只是通用句则不算迁移
    # （PR #52 r6 MEDIUM 2）。
    old_heads = [m for m in (_OLD_HEAD_RE[en].match(ln) for ln in ol[o0:o1 + 1]) if m]
    note_dates = Counter(d for d, _ in raw_notes)
    head_dates = Counter(m.group(1) for m in old_heads)
    if any(note_dates[d] and n > note_dates[d] for d, n in head_dates.items()):
        return False
    notes = list(raw_notes)
    for m in old_heads:
        d = m.group(1)
        expl = m.group(0).split(d, 1)[1].lstrip("：: ").strip()
        substantive = bool(expl) and expl != _OLD_HEAD_GENERIC[en]
        if note_dates[d]:
            if substantive and (d, expl) not in raw_notes:
                return False
        elif not substantive:
            return False
        else:
            notes.append((d, expl))
    notes.sort()
    hidx = _visible_candidate_indices(nl, [i for i, ln in enumerate(nl) if ln == _NEW_HEAD[en]])
    if len(hidx) != 1:
        return False
    n0, eidx, j = hidx[0], [], hidx[0] + 1
    while j < len(nl) and (not nl[j].strip() or R.CORRECTION_ENTRY_RE[en].match(nl[j])):
        if nl[j].strip():
            eidx.append(j)
        j += 1
    if not eidx:
        return False
    entries = [(m.group(1), m.group(2)) for m in (R.CORRECTION_ENTRY_RE[en].match(nl[k]) for k in eidx)]
    if [d for d, _ in entries] != sorted(d for d, _ in entries) or sorted(entries) != notes:
        return False
    # 新旧更正区都须渲染后可见：代码块、注释、隐藏元素里的同形行不能冒充迁移（PR #52 r5 MEDIUM 2）
    old_vis = R.visible_text(old[mo.end():], body_only=True, correction_syntax=True).splitlines()
    visible_notes = Counter((m.group(1), m.group(2)) for ln in old_vis if (m := _OLD_NOTE_RE[en].match(ln.strip())))
    visible_old_heads = Counter(m.group(1) for ln in old_vis if (m := _OLD_HEAD_RE[en].match(ln)))
    visible_heads, visible_entries = R.correction_section(new[mn.end():], en)
    if visible_notes != Counter(raw_notes) or visible_old_heads != head_dates \
            or visible_heads != 1 or visible_entries != entries:
        return False
    pre_o, pre_n, suf_o, suf_n = ol[:o0], nl[:n0], ol[o1 + 1:], nl[eidx[-1] + 1:]
    if suf_o != suf_n or len(pre_o) != len(pre_n):
        return False
    # 页首白名单只适用于第一个标题之前唯一的那一行页首提示（PR #52 r2 MEDIUM 5）
    candidates = [i for i, ln in enumerate(pre_o) if _TOP_LINE_RE[en].match(ln)]
    first_heading = len(pre_o)
    for i, ln in enumerate(pre_o):
        if _HEADING_RE.match(ln):
            first_heading = i
            break
        if i and re.fullmatch(r"[ ]{0,3}(?:=+|-+)[ \t]*", ln) and pre_o[i - 1].strip():
            first_heading = i - 1                     # Setext 标题（PR #52 r3 LOW 5）
            break
    allowed = candidates[0] if len(candidates) == 1 and candidates[0] < first_heading else None
    for i, (a, b) in enumerate(zip(pre_o, pre_n)):
        if a != b:
            ma, mb = _TOP_LINE_RE[en].match(a), _TOP_LINE_RE[en].match(b)
            if i != allowed or not (ma and mb and ma.group(1) == mb.group(1)):
                return False
    return True


# 只改 front matter 顶层 lastmod 的维护改动不算更正（Grok Bot 2026-10-18 定，POLICY「字节改动」选 B）：正文逐字节相同，
# front matter 原文去掉顶层「lastmod:」单行后逐字节相同。其他字段、正文里的 lastmod 字样、带缩进或续行的写法都不豁免。
_LASTMOD_LINE_RE = re.compile(r"^lastmod[ \t]*:[^\n]*(?:\n|$)", re.M)


def lastmod_only(old, new):
    mo, mn = R._FM_RE.match(old), R._FM_RE.match(new)
    if not mo or not mn or old[mo.end():] != new[mn.end():]:
        return False
    return _LASTMOD_LINE_RE.sub("", mo.group(0)) == _LASTMOD_LINE_RE.sub("", mn.group(0))


def check_page(repo, mb, head, path, status, today, base_pages, head_pages):
    """单个页面：返回错误码列表（空 = 通过）。base_pages / head_pages 来自 rendered_pages。"""
    did = page_draft_id(path)
    published = path in base_pages
    old = None if status == "A" else _show_required(repo, mb, path)
    new = None if status == "D" else _show_required(repo, head, path)
    if new is None:
        return ["E-SITE-PAGE-DELETED"] if published else []
    codes = []
    if published and head_pages is not None and head_pages.get(path) != base_pages[path]:
        codes.append("E-SITE-PAGE-DELETED")          # 不再生成或 URL 改变，等于删除原页面（r1 HIGH 2）
    try:
        fm, body = R.front_matter(new)
    except R.FrontMatterError:
        return sorted(set(codes + ["E-ROUTE-FRONT-MATTER"]))
    if published and old is not None and old != new and lastmod_only(old, new):
        return sorted(set(codes))                     # 只改 lastmod：不算更正（只豁免这一项）
    en = path.endswith(".en.md")
    # 纯格式迁移不算新更正（Issue #71 例外）：只豁免“同日须新增一条”，其余字段与新格式更正区校验照常（PR #52 r3 MEDIUM 2）
    migration = published and old is not None and format_migration_only(old, new, en)
    if "corrects" not in fm and "corrected_at" not in fm:
        if published:
            codes.append("E-SITE-CORRECTION-MISSING")
        return sorted(set(codes))                     # 未发布页面：首次发布前的修改，不查（r1 MEDIUM 3）
    if not fm.get("corrects") or not fm.get("corrected_at") \
            or not isinstance(fm["corrects"], str) or not isinstance(fm["corrected_at"], str):
        return sorted(set(codes + ["E-ROUTE-CORRECTION-INVALID"]))
    if did is None or fm["corrects"] != did or not published:
        codes.append("E-ROUTE-CORRECTION-TARGET")
    ofm, old_body = None, ""
    if old is not None:
        try:
            ofm, old_body = R.front_matter(old)
        except R.FrontMatterError:
            codes.append("E-ROUTE-CORRECTION-TARGET")
    od = R._orig_date_sgt(ofm.get("date")) if ofm is not None else None
    if ofm is not None and od is None:
        codes.append("E-ROUTE-CORRECTION-TARGET")
    prev = ofm.get("corrected_at") if ofm is not None else None
    if not R.valid_date(fm["corrected_at"]):
        codes.append("E-ROUTE-CORRECTION-DATE")
    else:
        ca = dt.date.fromisoformat(fm["corrected_at"])
        if ca > today \
                or (od is not None and ca < dt.date.fromisoformat(od)) \
                or (ofm is not None and fm.get("date") != ofm.get("date")) \
                or (isinstance(prev, str) and R.valid_date(prev) and ca < dt.date.fromisoformat(prev)):
            codes.append("E-ROUTE-CORRECTION-DATE")     # date 按完整值比较（r1 MEDIUM 4）
        elif not migration and old != new and \
                _corrections_dated(body, fm["corrected_at"], en) <= _corrections_dated(old_body, fm["corrected_at"], en):
            codes.append("E-ROUTE-CORRECTION-NOTE")     # 无论同日或跨日，本次日期的更正次数须比 base 多（r1 HIGH 1、PR #52 r5 MEDIUM 3）
    if not R.correction_heading_ok(body, fm["corrected_at"], en=en):
        codes.append("E-ROUTE-CORRECTION-NOTE")
    return sorted(set(codes))


_NOTE_GENERIC_HINT = ("更正区写法：正文末尾空一行写「## 更正」（英文稿「## Corrections」），再空一行，每次更正顶格一行"
                     "「**YYYY-MM-DD**：说明」（英文「**YYYY-MM-DD**: …」），按日期升序；corrected_at 须有同日期的条目，"
                     "本次改动须新增一条（纯格式迁移除外）；更正区内不要用 HTML、缩进或 Setext 标题。")


def correction_hints(repo, head, path, status):
    """E-ROUTE-CORRECTION-NOTE 时给作者的改写提示：规范写法的具体问题 + 通用写法说明。"""
    if status == "D":
        return [_NOTE_GENERIC_HINT]
    try:
        _, body = R.front_matter(_show_required(repo, head, path) or "")
    except (R.FrontMatterError, SiteInputError):
        return [_NOTE_GENERIC_HINT]
    return R.correction_format_problems(body) + [_NOTE_GENERIC_HINT]


def now_sgt():
    return R._real_now().astimezone(R.SGT)


def check_range(repo, base, head, today=None, clock=None):
    """检查 base..head（以 merge-base 为基线）改动的站点页面。返回结果 dict；ok=False 表示有页面不合规。
    clock：判定“已发布”用的 Hugo 时钟（ISO 8601，默认当前时间）；today：corrected_at 上限（SGT 日期，默认今天）。"""
    now = now_sgt()
    today = today or now.date()
    clock = clock or now.isoformat(timespec="seconds")
    head_sha = _git_ok(repo, "rev-parse", "--verify", head + "^{commit}").strip()
    base_sha = _git_ok(repo, "rev-parse", "--verify", base + "^{commit}").strip()
    mb, pairs = changed_pages(repo, base_sha, head_sha)
    base_pages = head_pages = {}
    # 任何文件有改动就构建两版并比较全部已发布页面：只改 _index.md 的 cascade、配置或模板也可能让已发布页面消失（PR #52 r2 HIGH 1）
    changed_any = bool(_git_ok(repo, "diff", "--name-only", mb, head_sha, text=False).strip())
    if changed_any:
        want = required_hugo_version(repo, mb)
        if required_hugo_version(repo, head_sha) != want:     # PR 改部署 Hugo 版本：失败关闭，另行验证升级（PR #52 r7 MEDIUM 4）
            raise SiteInputError("E-SITE-INPUT: PR 更改了站点部署的 Hugo 版本，须另行验证两版构建")
        exe = check_hugo(want)                              # 两版都用 base（已部署）那一版的 Hugo 版本构建
        base_pages = rendered_pages(repo, mb, clock, exe)
        # head 上改动页面的 front matter 先解析：有解析失败的，Hugo 也构建不了，直接按 E-ROUTE-FRONT-MATTER 报，
        # 不再构建 head（此时结果必为不通过，其余页面不做“是否仍生成”的比较）。
        broken = False
        for st, path in pairs:
            if st != "D":
                try:
                    R.front_matter(_show_required(repo, head_sha, path))
                except R.FrontMatterError:
                    broken = True
        head_pages = None if broken else rendered_pages(repo, head_sha, clock, exe)
    pages = []
    for st, path in pairs:
        codes = check_page(repo, mb, head_sha, path, st, today, base_pages, head_pages)
        entry = {"path": path, "status": st, "draft_id": page_draft_id(path),
                 "published_at_base": path in base_pages, "codes": codes}
        if "E-ROUTE-CORRECTION-NOTE" in codes:
            entry["hints"] = correction_hints(repo, head_sha, path, st)
        pages.append(entry)
    if head_pages is not None:
        seen = {p["path"] for p in pages}
        for path, url in sorted(base_pages.items()):
            if path not in seen and head_pages.get(path) != url:
                pages.append({"path": path, "status": "indirect", "draft_id": page_draft_id(path),
                              "published_at_base": True, "codes": ["E-SITE-PAGE-DELETED"]})
    return {"base": base_sha, "head": head_sha, "merge_base": mb, "today_sgt": today.isoformat(), "clock": clock,
            "pages": pages, "ok": all(not p["codes"] for p in pages)}


def fetch_pr(repo, number):
    """站点仓库 origin 须是 markjin-lab/markjin-lab.github.io；fetch main 与 PR head（会更新本地 Git 对象和引用）。"""
    u = R._git(repo, "remote", "get-url", "origin")
    if u.returncode != 0 or not R._site_remote_ok(u.stdout):
        raise SiteInputError("E-SITE-INPUT: 站点仓库 origin 不是 " + R.SITE_REMOTE)
    head_ref = f"refs/remotes/origin/pr/{int(number)}"
    _git_ok(repo, "fetch", "-q", "origin", "+refs/heads/main:refs/remotes/origin/main",
            f"+refs/pull/{int(number)}/head:{head_ref}")
    return "refs/remotes/origin/main", head_ref
