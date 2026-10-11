"""#11 公开台账 review/ledger/YYYY-MM-DD.jsonl。

字段白名单：date（日期）、error_code（错误码）、count（计数）、ratio（比率）、
card_id（可省略；公开稿件里的锚点，只允许小写字母、数字、连字符，形如 2026-10-10-c03）。
白名单外字段、未登记错误码、非法取值一律拒绝写入（抛 LedgerError，错误码 E-LEDGER-*）。
date 必须是真实日历日期，且与文件名中的日期一致（E-LEDGER-DATE）。review/ledger/ 目录缺失 → E-LEDGER-DIR。
review/ledger/ 下只允许 .gitkeep 与 YYYY-MM-DD.jsonl（其他文件名 → E-LEDGER-FILE）；台账文件不得为空（E-LEDGER-EMPTY）；
JSON 行出现重复键 → E-LEDGER-VALUE。
card_id 必须是卡片稿件里确实存在、且唯一的锚点（E-LEDGER-CARD）：只认 cards/<name>.md（与站点 content/cards/<name>.md
对应），在去掉代码块与 HTML 注释后含 `{#<card_id>}` 或 `id="<card_id>"`；同一锚点出现多次 → 不认。

review/ 整体白名单（REVIEW_ALLOWED）：README.md、error-codes.md、ledger/.gitkeep、ledger/YYYY-MM-DD.jsonl、
YYYY-MM-DD.md、YYYY-MM-DD-rN/{digest.md,post.md,review-prompt.md,result-rN[a-z]?.txt}、codex/<名>.log；其他路径 → E-REVIEW-PATH。

注意：台账只是统计，计数**不是批准凭证**（I-AUTO-APPROVED 计数已随 t161u 停用，不再产生）；路由（route.py）不读取台账来判断是否已批准。
"""
import datetime as _dt
import json
import re
from pathlib import Path

from .codes import ERROR_CODES

LEDGER_DIR = "review/ledger"
WHITELIST = ("date", "error_code", "count", "ratio", "card_id")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl$")
CARD_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
ALLOWED_PLAIN = {".gitkeep"}


def _no_dup(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key")
    return dict(pairs)


def loads_strict(line):
    return json.loads(line, object_pairs_hook=_no_dup)


# 整体验收 r6 MEDIUM：按 CommonMark 围栏规则——开围栏为 ≥3 个 ` 或 ~（行首最多 3 个空格），闭围栏用同一字符、
# 长度不少于开围栏、其后只能有空白；找不到闭围栏 → 延续到文件末尾
_FENCE = re.compile(r"^ {0,3}((`|~)\2{2,})[^\n]*\n(?:.*?^ {0,3}\1\2*[ \t]*$|.*\Z)", re.S | re.M)   # r7：闭围栏同字符、长度 ≥ 开围栏即可
_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.S)   # 整体验收 r5：未闭合的 HTML 注释视为延续到文件末尾
CARD_PATH_RE = re.compile(r"^cards/[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
REVIEW_ALLOWED = [re.compile(p) for p in (
    r"^review/README\.md$", r"^review/error-codes\.md$", r"^review/ledger/\.gitkeep$",
    r"^review/ledger/\d{4}-\d{2}-\d{2}\.jsonl$", r"^review/\d{4}-\d{2}-\d{2}\.md$",
    r"^review/\d{4}-\d{2}-\d{2}-r\d{1,2}/(?:digest\.md|post\.md|review-prompt\.md|result-r\d{1,2}[a-z]?\.txt)$",
    r"^review/codex/[A-Za-z0-9._-]{1,120}\.log$")]


def review_path_ok(path):
    return any(rx.fullmatch(path) for rx in REVIEW_ALLOWED)


_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_VERDICT_LINE = re.compile(r"^VERDICT: (APPROVED|APPROVED_WITH_FOLLOWUPS|REJECTED)$")   # 审查记录（规划文件可用第三种结论）；稿件批准记录仍只认 APPROVED（approvals.py）


def review_record_errors(path, text):
    """review/ 下非台账记录（日审 md、轮次目录、Codex 日志）的格式校验。返回错误码列表（空 = 通过）。
    这些文件无法做字段白名单，因此：格式校验在此（公开守卫，CI 可跑）；内部清单扫描由 check-internal 对全部 blob 执行。"""
    errs = []
    m_day = re.fullmatch(r"^review/(\d{4}-\d{2}-\d{2})\.md$", path)
    m_round = re.fullmatch(r"^review/(\d{4}-\d{2}-\d{2})-r\d{1,2}/(.+)$", path)
    is_log = path.startswith("review/codex/")
    if not (m_day or m_round or is_log):
        return errs
    limit = 4 * 1024 * 1024 if is_log else 512 * 1024
    if len(text.encode("utf-8")) > limit or not text.strip():
        errs.append("E-REVIEW-FORMAT")
    if _CTRL.search(text):
        errs.append("E-REVIEW-FORMAT")
    if "markjin-internal" in text or "topics-private" in text:
        errs.append("E-REVIEW-FORMAT")                 # 不得引用内部材料路径
    lines = [l for l in text.splitlines() if l.strip()]
    first = lines[0] if lines else ""
    if m_day:
        if not real_date(m_day.group(1)) or not (first.startswith("# ") and m_day.group(1) in first):
            errs.append("E-REVIEW-FORMAT")
    elif m_round:
        name = m_round.group(2)
        if not real_date(m_round.group(1)):
            errs.append("E-REVIEW-FORMAT")
        if name.endswith(".md") and not first.startswith("# "):
            errs.append("E-REVIEW-FORMAT")
        if name.endswith(".txt") and not (lines and _VERDICT_LINE.match(lines[-1].strip())):
            errs.append("E-REVIEW-FORMAT")             # 审查结果最后一行必须是纯文本 VERDICT 行
    elif is_log and not first.startswith("OpenAI Codex v"):
        errs.append("E-REVIEW-FORMAT")
    return sorted(set(errs))


_START_TAG = re.compile(r"<[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")
_INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1", re.S)


def anchors_list(text):
    """卡片稿件中的锚点（列表，含重复）：去掉代码块与 HTML 注释后的 {#id} 或 id="id"。"""
    t = _COMMENT.sub("", _FENCE.sub("", text))
    t = re.sub(r"(?m)^(?: {4}|\t).*$", "", t)        # 缩进代码块（4 空格 / Tab 开头的行）里的不算锚点
    t = _INLINE_CODE.sub("", t)                      # 行内代码（`…`、``…``）里的不算锚点
    return (re.findall(r"(?<!\\)\{#([a-z0-9-]+)\}", t)          # 转义文本 \{#id} 不算
            + [a for tag in _START_TAG.findall(t)               # r9 MEDIUM：只认 HTML 起始标签里的 id 属性，纯文本 id="c1" 不算
               for a in re.findall(r'(?<![\w-])id="([a-z0-9-]+)"', tag)])   # data-id="…" 等带前缀的属性不算


def anchors_in(text):
    return set(anchors_list(text))


def unique_anchors(texts):
    """多篇稿件的锚点，只保留全局唯一的。"""
    from collections import Counter
    c = Counter(a for t in texts for a in anchors_list(t))
    return {a for a, n in c.items() if n == 1}


def is_public_draft(path):
    return bool(CARD_PATH_RE.fullmatch(path))


def repo_anchors(repo):
    texts = []
    d = Path(repo) / "cards"
    for p in sorted(d.glob("*.md")) if d.is_dir() else []:
        if not is_public_draft(p.relative_to(repo).as_posix()):
            continue
        try:
            texts.append(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            # 任一候选卡片读不出：唯一性无法确认 → 拒绝（不跳过，避免重复 ID 看似唯一）
            raise LedgerError("E-LEDGER-CARD", "card unreadable")
    return unique_anchors(texts)


class LedgerError(ValueError):
    def __init__(self, code, msg):
        super().__init__(f"{code}: {msg}")
        self.code = code


def real_date(s) -> bool:
    if not isinstance(s, str) or not DATE_RE.fullmatch(s):
        return False
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        return False
    return True


def validate(rec: dict, file_date=None, anchors=None) -> dict:
    """anchors：公开稿件锚点集合；给出时 card_id 必须在其中。append/verify 总会给出。"""
    if not isinstance(rec, dict):
        raise LedgerError("E-LEDGER-VALUE", "记录必须是对象")
    extra = set(rec) - set(WHITELIST)
    if extra:
        raise LedgerError("E-LEDGER-FIELD", f"白名单外字段 {len(extra)} 个")
    for k in ("date", "error_code", "count"):
        if k not in rec:
            raise LedgerError("E-LEDGER-VALUE", f"缺少字段 {k}")
    if not real_date(rec["date"]):
        raise LedgerError("E-LEDGER-DATE", "date 须为真实日历日期 YYYY-MM-DD")
    if file_date is not None and rec["date"] != file_date:
        raise LedgerError("E-LEDGER-DATE", "date 与文件名日期不一致")
    if not isinstance(rec["error_code"], str) or rec["error_code"] not in ERROR_CODES:
        raise LedgerError("E-LEDGER-VALUE", "error_code 未在错误码表登记")
    c = rec["count"]
    if not isinstance(c, int) or isinstance(c, bool) or c < 0:
        raise LedgerError("E-LEDGER-VALUE", "count 须为非负整数")
    if rec["error_code"] in RETIRED_ZERO_ONLY and c != 0:
        raise LedgerError("E-LEDGER-VALUE", f"{rec['error_code']} 已停用（t161u），只许记为 0")   # 整体验收 r11 MEDIUM
    if "ratio" in rec:
        r = rec["ratio"]
        if isinstance(r, bool) or not isinstance(r, (int, float)) or not 0 <= r <= 1:
            raise LedgerError("E-LEDGER-VALUE", "ratio 须为 0–1 的数或省略")
    if "card_id" in rec:
        cid = rec["card_id"]
        if not isinstance(cid, str) or not CARD_ID_RE.fullmatch(cid):
            raise LedgerError("E-LEDGER-VALUE", "card_id 须为公开稿件锚点（小写字母/数字/连字符）")
        if anchors is None or cid not in anchors:
            raise LedgerError("E-LEDGER-CARD", "card_id 在公开稿件中没有对应锚点")
    return {k: rec[k] for k in WHITELIST if k in rec}


# 已停用的错误码：保留在 ERROR_CODES 里供旧记录解释，新记录只许 count=0（整体验收 r11 MEDIUM）
RETIRED_ZERO_ONLY = frozenset({"I-AUTO-APPROVED"})


def ledger_path(repo, date):
    return Path(repo) / LEDGER_DIR / f"{date}.jsonl"


def append(repo, rec: dict) -> Path:
    d = Path(repo) / LEDGER_DIR
    if not d.is_dir():
        raise LedgerError("E-LEDGER-DIR", "review/ledger/ 目录缺失")
    clean = validate(rec, anchors=repo_anchors(repo))
    p = ledger_path(repo, clean["date"])
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(clean, ensure_ascii=False, sort_keys=True) + "\n")
    return p


def record_selfcheck(repo, date, result):
    """把自检结果按错误码写台账（只写错误码与计数；统计用途，不是批准凭证）。"""
    agg = {}
    for e in result["errors"]:
        agg[e["code"]] = agg.get(e["code"], 0) + 1
    return [append(repo, {"date": date, "error_code": c, "count": n}) for c, n in sorted(agg.items())]


def verify_text(filename, text, anchors=frozenset()):
    """校验 review/ledger/ 下一个文件；返回 [(行号, 错误码)]。
    文件名只允许 .gitkeep（内容须为空）与真实日期 YYYY-MM-DD.jsonl；台账不得为空。"""
    if filename in ALLOWED_PLAIN:
        return [] if not text.strip() else [(0, "E-LEDGER-FILE")]
    m = FILE_RE.fullmatch(filename)
    if not m:
        return [(0, "E-LEDGER-FILE")]
    if not real_date(m.group(1)):
        return [(0, "E-LEDGER-DATE")]
    if not text.strip():
        return [(0, "E-LEDGER-EMPTY")]
    bad = []
    for i, line in enumerate(text.splitlines(), 1):
        try:
            validate(loads_strict(line), file_date=m.group(1), anchors=anchors)
        except LedgerError as ex:
            bad.append((i, ex.code))
        except ValueError:
            bad.append((i, "E-LEDGER-VALUE"))
    return bad


def verify_all(repo):
    """校验工作树 review/ledger/（供本地开发使用；守卫以 git 对象为准）。返回 [(文件序号, 行号, 错误码)]。"""
    d = Path(repo) / LEDGER_DIR
    if not d.is_dir():
        return [(0, 0, "E-LEDGER-DIR")]
    bad, anchors = [], repo_anchors(repo)
    for n, p in enumerate(sorted(d.iterdir()), 1):
        if p.is_dir():
            bad.append((n, 0, "E-LEDGER-FILE")); continue
        try:
            text = p.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            bad.append((n, 0, "E-CHECK-DECODE")); continue
        bad += [(n, ln, c) for ln, c in verify_text(p.name, text, anchors)]
    return bad
