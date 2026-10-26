"""卡片审查量表与自动评分（路线图第九节；data#22）。

五项均为否决项，全部 status=pass 才 overall_pass。量表只用于质量统计，
不得改变发布或拒发；本模块不得被 route 导入或调用。

(1)(3)(4) 映射复用 selfcheck 结果中的错误码 / 审查原因码。
(2) 机器能判的用直引/回放；判不了的标 pending_human，不硬编。
(5) 只读本机内部目录下的 frame-conjecture.md（路径解析对齐 internal.py）；
    清单缺失 fail-closed；公开输出只含 E-FRAME-CONJECTURE、计数、比率、日期，
    不得含命中原文或清单路径。
"""
from __future__ import annotations

import re
from pathlib import Path

from . import internal
from .selfcheck import check_file, check_text, valid_date, CARD_TYPES
from .textnorm import compact, norm

FRAME_LIST_NAME = "frame-conjecture.md"
ITEM_KEYS = (
    "evidence_replayable",      # (1) 证据可回放
    "faithful_to_source",       # (2) 忠实原文
    "inferences_annotated",     # (3) 推断已标注
    "no_investment_language",   # (4) 不含投资措辞
    "no_frame_conjecture",      # (5) 不含框架猜想/待王总定
)
STATUSES = ("pass", "fail", "pending_human")

# 匹配时只剥标签式写法（括号/引号/「标为」），不剥嵌入专名中的「假说」等字
_TAG_RE = re.compile(
    r"标为\s*[「『]?(?:猜想|待王总定|假说)[」』]?"
    r"|[（(]\s*(?:猜想|待王总定|假说)\s*[)）]"
    r"|[「『](?:猜想|待王总定|假说)[」』]"
)

_SEP = re.compile(r"^:?-{3,}:?$")
_HEADERS = ("id", "phrase", "kind", "source_note")


def frame_list_path() -> Path:
    """对照清单路径：<internal_dir>/frame-conjecture.md（不把绝对路径写入公开输出）。"""
    return internal.internal_dir() / FRAME_LIST_NAME


def _cells(line: str):
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")) or len(s) < 2:
        return None
    return [norm(c) for c in s[1:-1].split("|")]


def parse_frame_list(text: str):
    """解析 frame-conjecture.md。返回 [{"id","phrase","kind"}, ...]；不合规返回 None。

    表头必须恰好为 id | phrase | kind | source_note；允许表外说明文字（与 topics-private 不同：
    本清单可有 NOTES 式旁注，但评分只读第一张合规表）。公开输出不得带回 phrase。
    """
    if not isinstance(text, str) or not text.strip():
        return None
    lines = text.splitlines()
    blocks, cur = [], []
    for ln in lines:
        if ln.strip().startswith("|"):
            cur.append(ln)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    if not blocks:
        return None
    # 取第一张恰好 4 列、表头匹配的表
    for block in blocks:
        if len(block) < 3:
            continue
        rows = [_cells(ln) for ln in block]
        if any(r is None or len(r) != 4 for r in rows):
            continue
        head, sep, data = rows[0], rows[1], rows[2:]
        head_l = [h.lower() for h in head]
        if head_l != list(_HEADERS):
            continue
        if not all(_SEP.match(c.replace(" ", "")) for c in sep):
            continue
        out, seen = [], set()
        ok = True
        for r in data:
            if any(not c or _SEP.match(c.replace(" ", "")) for c in r):
                ok = False
                break
            pid, phrase, kind, _note = r
            key = compact(pid)
            if not key or key in seen or not compact(phrase):
                ok = False
                break
            seen.add(key)
            out.append({"id": pid, "phrase": phrase, "kind": kind})
        if ok and out:
            return out
    return None


def load_frame_list(path: Path | None = None):
    """读取本机清单。缺失/不可读/不合规 → None（调用方 fail-closed）。

    path 仅供测试注入临时 fixture；生产调用不传，用 frame_list_path()。
    """
    p = Path(path) if path is not None else frame_list_path()
    try:
        text = p.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError, TypeError, ValueError):
        return None
    return parse_frame_list(text)


def strip_frame_tags(text: str) -> str:
    """去掉「猜想」「待王总定」等标签后再匹配（去标签仍算命中）。"""
    return _TAG_RE.sub("", text)


def frame_hit_count(text: str, entries) -> int:
    """返回命中条目数。不回显命中原文。entries 为 parse_frame_list 的结果。

    对原文与去标签文本都做 compact 子串匹配（去标签/改写空白后仍算命中）。
    """
    if not entries:
        return 0
    probes = [compact(text), compact(strip_frame_tags(text))]
    n = 0
    for ph in (e["phrase"] for e in entries):
        cp = compact(ph)
        if cp and any(cp in c for c in probes):
            n += 1
    return n


def _codes_of(sc) -> list:
    codes = sc.get("error_codes") or []
    return [c for c in codes if isinstance(c, str)]


def _item(status: str, codes=None, **extra) -> dict:
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status}")
    d = {"status": status, "codes": list(codes or [])}
    d.update(extra)
    return d


def score_item_evidence(sc) -> dict:
    """(1) 证据可回放：有任一 E-REPLAY-* → fail，否则 pass。"""
    hits = [c for c in _codes_of(sc) if c.startswith("E-REPLAY-")]
    return _item("fail" if hits else "pass", hits)


def score_item_faithful(sc) -> dict:
    """(2) 忠实原文：直引核对失败或数字未在存档出现 → fail；
    自由转述/非结构化复述机器无法确认是否夹带原文之外内容 → pending_human；
    仅直引/结构化且机检通过 → pass。不把 structure_other 当作待人工（结构化断言也会置该标记）。"""
    codes = _codes_of(sc)
    flags = sc.get("flags") or {}
    hard = []
    if "R-QUOTE-UNVERIFIED" in codes or flags.get("quote_unverified"):
        hard.append("R-QUOTE-UNVERIFIED")
    if "R-SUPPORT-UNVERIFIED" in codes or flags.get("unsupported"):
        hard.append("R-SUPPORT-UNVERIFIED")
    seen, uniq = set(), []
    for c in hard:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    if uniq:
        return _item("fail", uniq)
    if flags.get("free_text") or flags.get("unstructured"):
        return _item("pending_human", [])
    return _item("pass", [])


def score_item_inference(sc) -> dict:
    """(3) 推断已标注：E-INFER-UNCLEAR → fail；有 R-INFERENCE 时机器无法确认标注质量 → pending_human；否则 pass。"""
    codes = _codes_of(sc)
    flags = sc.get("flags") or {}
    if "E-INFER-UNCLEAR" in codes or flags.get("inference_unclear"):
        return _item("fail", ["E-INFER-UNCLEAR"])
    if "R-INFERENCE" in codes or flags.get("has_inference"):
        return _item("pending_human", ["R-INFERENCE"])
    return _item("pass", [])


def score_item_investment(sc) -> dict:
    """(4) 不含投资措辞：E-BLOCK-INVEST → fail，否则 pass。"""
    codes = _codes_of(sc)
    hits = [c for c in codes if c == "E-BLOCK-INVEST"]
    return _item("fail" if hits else "pass", hits)


def score_item_frame(text: str, entries) -> dict:
    """(5) 不含框架猜想/待王总定。entries is None → fail-closed（清单缺失）。
    公开侧只返回错误码与 hit_count，不回显命中原文。"""
    if entries is None:
        return _item("fail", [], list_available=False, hit_count=0)
    n = frame_hit_count(text, entries)
    if n > 0:
        return _item("fail", ["E-FRAME-CONJECTURE"], list_available=True, hit_count=n)
    return _item("pass", [], list_available=True, hit_count=0)


def score_card(text: str, selfcheck_result: dict, *, frame_entries=None, frame_list_path_override=None) -> dict:
    """对一篇卡片做五项评分。

    selfcheck_result：已有的 selfcheck.check_text / check_file 结果（须含 error_codes/flags/counts/date/card_type）。
    frame_entries：测试可直接注入解析后的清单；默认从本机清单加载。
    frame_list_path_override：测试用临时清单路径。
    返回公开白名单字段：五项 status、codes、计数/比率/日期；不含命中原文与清单绝对路径。
    """
    if frame_entries is None:
        frame_entries = load_frame_list(frame_list_path_override)

    items = {
        "evidence_replayable": score_item_evidence(selfcheck_result),
        "faithful_to_source": score_item_faithful(selfcheck_result),
        "inferences_annotated": score_item_inference(selfcheck_result),
        "no_investment_language": score_item_investment(selfcheck_result),
        "no_frame_conjecture": score_item_frame(text if isinstance(text, str) else "", frame_entries),
    }
    statuses = [items[k]["status"] for k in ITEM_KEYS]
    pass_n = sum(1 for s in statuses if s == "pass")
    fail_n = sum(1 for s in statuses if s == "fail")
    pending_n = sum(1 for s in statuses if s == "pending_human")
    date = selfcheck_result.get("date")
    card_type = selfcheck_result.get("card_type")
    overall = all(s == "pass" for s in statuses)
    # 公开摘要：只含计数、比率、日期与错误码聚合
    public_codes = []
    for k in ITEM_KEYS:
        for c in items[k].get("codes") or []:
            if c not in public_codes:
                public_codes.append(c)
    return {
        "date": date if valid_date(date) else None,
        "card_type": card_type if card_type in CARD_TYPES else None,
        "items": items,
        "overall_pass": overall,
        "summary": {
            "pass_count": pass_n,
            "fail_count": fail_n,
            "pending_human_count": pending_n,
            "item_count": len(ITEM_KEYS),
            "pass_ratio": round(pass_n / len(ITEM_KEYS), 4),
            "date": date if valid_date(date) else None,
            "codes": public_codes,
        },
    }


def score_file(path, repo, date, card_type, *, link_checker=None, frame_list_path_override=None, **kw) -> dict:
    """读稿件 → selfcheck → 量表评分。不调用 route，也不被 route 调用。"""
    try:
        text = Path(path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError, TypeError, ValueError):
        text = ""
    sc = check_file(path, repo, date, card_type, link_checker=link_checker, **kw)
    return score_card(text, sc, frame_list_path_override=frame_list_path_override)


def score_text(text, repo, date, card_type, *, link_checker=None, frame_list_path_override=None, **kw) -> dict:
    sc = check_text(text, repo, date, card_type, link_checker=link_checker, **kw)
    return score_card(text, sc, frame_list_path_override=frame_list_path_override)
