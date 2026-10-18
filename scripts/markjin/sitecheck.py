"""站点 PR 的更正规则检查（Grok Bot 2026-10-18）。

route_pr 只看数据仓库顶层的 daily/、digest/ 等稿件，站点 PR 直接改 content/posts/（或 content/cards/）页面时，
更正规则（E-ROUTE-CORRECTION-*）没人检查。本模块对站点仓库某个 base..head 范围内改动的页面做同一套检查，
判断逻辑尽量复用 route.py（front matter 解析、日期解析、标题行可见文字），不另写一份。

对 merge-base(base, head)..head 中每个改动的页面 content/posts/<section>/<name>[.en].md、content/cards/<name>[.en].md：
- 新增页面（base 上没有）且不带更正字段 → 不查（新稿由日报流程审查）。
- 删除或改名 base 上已有的页面 → E-SITE-PAGE-DELETED。
- 改动 base 上已有的页面：front matter 须有 corrects 与 corrected_at，否则 E-SITE-CORRECTION-MISSING；
  有更正字段时（含新增页面带了更正字段）按 route._correction 的同一组规则：
  · 缺一、为空或不是字符串 → E-ROUTE-CORRECTION-INVALID；
  · corrects 须等于由页面路径推出的 draft_id（<section>-<name>[-en]，卡片为 cards-<name>[-en]），
    且页面须在 base 上已存在（已发布），base 版 front matter 须有合法 date → 否则 E-ROUTE-CORRECTION-TARGET；
  · corrected_at 须是 YYYY-MM-DD，不早于页面日期（base 版 date 按 SGT 取日期），不晚于今天（SGT），
    不早于 base 版已有的 corrected_at；head 版 date 须与 base 版相同 → 否则 E-ROUTE-CORRECTION-DATE；
  · corrected_at 须出现在某个标题行渲染后可见的文字里（route.correction_heading_ok）→ 否则 E-ROUTE-CORRECTION-NOTE。
- front matter 解析失败 → E-ROUTE-FRONT-MATTER。
其他文件（列表页 _index.md、模板、配置、静态文件等）不查。只读：不写文件、不改仓库（--pr 时只 fetch PR 引用）。
"""
import datetime as dt
from pathlib import PurePosixPath

from . import route as R

SITE_PAGE_ROOTS = (R.SITE_CONTENT + "/", R.SITE_CARDS + "/")


class SiteInputError(RuntimeError):
    pass


def page_draft_id(path):
    """站点页面路径 → draft_id（route.site_path 的逆映射）；不是可检查的页面 → None。"""
    p = PurePosixPath(path)
    name = p.name
    if not name.endswith(".md"):
        return None
    en = name.endswith(".en.md")
    stem = name[: -len(".en.md")] if en else name[: -len(".md")]
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
        return None                          # _index.md 等列表页不查
    did = f"{sec}-{stem}" + (R.EN_SUFFIX if en else "")
    if R.site_path(did, en) != path:
        return None
    return did


def _git_ok(repo, *args):
    r = R._git(repo, *args)
    if r.returncode != 0:
        raise SiteInputError(f"E-SITE-INPUT: git {' '.join(args[:2])} 失败")
    return r.stdout


def _show(repo, ref, path):
    r = R._git(repo, "show", f"{ref}:{path}", text=False)
    if r.returncode != 0:
        return None
    try:
        return r.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return ""                            # 非 UTF-8：当作内容存在但无法解析


def changed_pages(repo, base, head):
    """返回 (merge-base, [(状态, 路径)])；只含 content/posts、content/cards 下的 .md。不跟踪改名（改名 = 删除 + 新增）。"""
    mb = _git_ok(repo, "merge-base", base, head).strip()
    out = _git_ok(repo, "diff", "--name-status", "--no-renames", "-z", mb, head, "--", R.SITE_CONTENT, R.SITE_CARDS)
    toks = [t for t in out.split("\0") if t]
    pairs = []
    for i in range(0, len(toks) - 1, 2):
        st, path = toks[i], toks[i + 1]
        if path.endswith(".md") and path.startswith(SITE_PAGE_ROOTS):
            pairs.append((st[0], path))
    return mb, pairs


def check_page(repo, mb, head, path, today):
    """单个页面：返回错误码列表（空 = 通过）。"""
    did = page_draft_id(path)
    old = _show(repo, mb, path)
    new = _show(repo, head, path)
    if new is None:
        return ["E-SITE-PAGE-DELETED"] if old is not None and did else []
    if did is None:
        return []
    try:
        fm, body = R.front_matter(new)
    except R.FrontMatterError:
        return ["E-ROUTE-FRONT-MATTER"]
    has = "corrects" in fm or "corrected_at" in fm
    if not has:
        return ["E-SITE-CORRECTION-MISSING"] if old is not None else []
    if not fm.get("corrects") or not fm.get("corrected_at") \
            or not isinstance(fm["corrects"], str) or not isinstance(fm["corrected_at"], str):
        return ["E-ROUTE-CORRECTION-INVALID"]
    codes = []
    if fm["corrects"] != did or old is None:
        codes.append("E-ROUTE-CORRECTION-TARGET")
    ofm = None
    if old is not None:
        try:
            ofm, _ = R.front_matter(old)
        except R.FrontMatterError:
            codes.append("E-ROUTE-CORRECTION-TARGET")
    od = R._orig_date_sgt(ofm.get("date")) if ofm is not None else None
    if ofm is not None and od is None:
        codes.append("E-ROUTE-CORRECTION-TARGET")
    if not R.valid_date(fm["corrected_at"]):
        codes.append("E-ROUTE-CORRECTION-DATE")
    else:
        ca = dt.date.fromisoformat(fm["corrected_at"])
        prev = ofm.get("corrected_at") if ofm is not None else None
        if ca > today \
                or (od is not None and ca < dt.date.fromisoformat(od)) \
                or (od is not None and R._orig_date_sgt(fm.get("date")) != od) \
                or (isinstance(prev, str) and R.valid_date(prev) and ca < dt.date.fromisoformat(prev)):
            codes.append("E-ROUTE-CORRECTION-DATE")
    if not R.correction_heading_ok(body, fm["corrected_at"]):
        codes.append("E-ROUTE-CORRECTION-NOTE")
    return sorted(set(codes))


def today_sgt():
    return R._real_now().astimezone(R.SGT).date()


def check_range(repo, base, head, today=None):
    """检查 base..head（以 merge-base 为基线）改动的站点页面。返回结果 dict；ok=False 表示有页面不合规。"""
    today = today or today_sgt()
    head_sha = _git_ok(repo, "rev-parse", "--verify", head + "^{commit}").strip()
    base_sha = _git_ok(repo, "rev-parse", "--verify", base + "^{commit}").strip()
    mb, pairs = changed_pages(repo, base_sha, head_sha)
    pages = []
    for st, path in pairs:
        codes = check_page(repo, mb, head_sha, path, today)
        pages.append({"path": path, "status": st, "draft_id": page_draft_id(path), "codes": codes})
    return {"base": base_sha, "head": head_sha, "merge_base": mb, "today_sgt": today.isoformat(),
            "pages": pages, "ok": all(not p["codes"] for p in pages)}


def fetch_pr(repo, number):
    """站点仓库 origin 须是 markjin-lab/markjin-lab.github.io；fetch main 与 PR head。返回 (base_ref, head_ref)。"""
    u = R._git(repo, "remote", "get-url", "origin")
    if u.returncode != 0 or not R._site_remote_ok(u.stdout):
        raise SiteInputError("E-SITE-INPUT: 站点仓库 origin 不是 " + R.SITE_REMOTE)
    head_ref = f"refs/remotes/origin/pr/{int(number)}"
    _git_ok(repo, "fetch", "-q", "origin", "+refs/heads/main:refs/remotes/origin/main",
            f"+refs/pull/{int(number)}/head:{head_ref}")
    return "refs/remotes/origin/main", head_ref
