"""#10 全站唯一审查路由（路线图 v0.9 第三节），第 2 轮。

输出状态：
  AUTO_APPROVED  已取消（王总 t161u：日报每天都要过 Codex，取消低风险自动批准）；不再产生
  NEEDS_REVIEW   需 Codex 审查（宏观/tongyi/卡片/中医佛学稿另需王总批准），尚未获批（当天截止 06:55 前）
  APPROVED       origin/main 的 approvals/ 中有逐项校验通过的 Codex 审查记录（及按类型要求的王总批准记录）
  HOLD           当天不发布（自检失败 / 分类不明 / 入口或状态不合法），记错误码
  DEFERRED       07:00 未获批，或需王总批准的稿件王总缺席，顺延 1 天（只顺延一次）
  ARCHIVED       最终状态，不可逆，带原因代码（A-MAC-OFFLINE / A-NOT-APPROVED / A-NO-REVIEW-PATH / A-OVERDUE-TWICE）
  REJECTED       internal-only，硬拒绝

批准不再来自 CLI 自报（已删除 --approver / --codex-reviewed），也不读本机内部目录。唯一来源是 markjin-data
main 分支（git 对象，不是工作树）上的公开文件，见 markjin/approvals.py：
  approvals/codex/<sha256>.json  Codex 审查记录（审查与治理 bot 写）：content_sha256、codex_session（UUID）、verdict、log_path
  approvals/wang/<sha256>.json   王总批准记录（协调 bot 写）：content_sha256、recorded_at、channel、quote
  state/publish-state.json       发布状态（生产 bot 提交）：Mac 在线、王总在岗、Codex 是否参与生产、归档/顺延
记录用稿件内容 sha256 绑定（文件名即 sha256）；schema 见 docs/approvals.md。只有王总本人的原话、由协调 bot 回传的批准记录才有效。
本模块不读取公开台账（review/ledger/）：台账里的 I-AUTO-APPROVED 只是统计数字，不是批准凭证。
"""
import datetime as dt
import hashlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Optional

from .approvals import is_v2, load_from_ref, parse_ts, valid_codex, valid_wang
from .selfcheck import CARD_TYPES, COUNT_KEYS, FLAG_KEYS, valid_date
from .deps import require_yaml
from . import strictjson
from .fmkeys import FM_CATEGORY_KEYS
import re

SGT = dt.timezone(dt.timedelta(hours=8))
# 日报时间表（王总 2026-10-11 08:37 定，quote_ref grok-bot:t130u）：07:00 发布。时间点只在这里定义（SGT），
# 代码其他地方只引用这两个常量，不另写死。成稿截止（06:30）只在站点侧定义，本门禁不使用。
CUTOFF = dt.time(6, 55)            # 审查/批准上限：Codex reviewed_at 与王总 recorded_at 不得晚于此时
PUBLISH_DEADLINE = dt.time(7, 0)   # 发布截止：赶不上即首次顺延到次日；顺延稿再逾期归档
MAC_STATUS_TTL = dt.timedelta(minutes=30)  # Mac 状态超过此时长未更新 → 未知 → 需审查稿一律 HOLD（E-ROUTE-MAC-STALE，可重试，不按离线归档）
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DRAFT_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
ARCHIVE_CODES = {"A-MAC-OFFLINE", "A-NOT-APPROVED", "A-NO-REVIEW-PATH", "A-OVERDUE-TWICE"}
STATE_KEYS = {"version", "updated_at", "mac_online", "wang_present", "codex_in_production", "drafts"}
DRAFT_STATE_KEYS = {"status", "reason", "at", "date", "content_sha256"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
TONGYI_SECTION = "tongyi"   # 协调决定 10-11：tongyi 系列 tongyi/<name>.md → tongyi-<name>，永不低风险，须 Codex + 王总 v2 direct 逐篇批准
EN_SUFFIX = "-en"   # t141u：<section>/<name>.en.md → <section>-<name>-en
CARD_SECTION = "cards"   # 协调决定：卡片稿件位于 cards/<name>.md，draft_id = cards-<name>（与站点仓库实际路径一致）


@dataclass
class Decision:
    state: str
    codes: list = field(default_factory=list)
    publishable: bool = False
    state_change: Optional[dict] = None   # 需要写回 state/publish-state.json 的变更（由生产 bot 写入）
    detail: Optional[str] = None          # HOLD 的原因说明（如链接检查失败的 URL 与原因）


def _hold(*codes):
    return Decision("HOLD", list(codes))


# —— 入口 schema
def validate_selfcheck(sc) -> bool:
    try:
        if not isinstance(sc, dict) or sc.get("status") not in ("PASS", "FAIL", "UNCLEAR"):
            return False
        if not isinstance(sc.get("error_codes"), list) or not all(isinstance(c, str) for c in sc["error_codes"]):
            return False
        f, c = sc.get("flags"), sc.get("counts")
        if not isinstance(f, dict) or set(f) != set(FLAG_KEYS) or not all(type(v) is bool for v in f.values()):
            return False
        if not isinstance(c, dict) or set(c) != set(COUNT_KEYS) | {"errors"}:
            return False
        if not all(type(v) is int and v >= 0 for v in c.values()):
            return False
        if sc.get("card_type") not in CARD_TYPES or not valid_date(sc.get("date")):
            return False
        return type(sc.get("low_risk")) is bool and isinstance(sc.get("errors"), list)
    except (TypeError, AttributeError):
        return False


def validate_draft(d) -> bool:
    return (isinstance(d, dict) and set(d) == {"draft_id", "date", "content_sha256"}
            and isinstance(d["draft_id"], str) and bool(DRAFT_ID_RE.match(d["draft_id"]))
            and valid_date(d["date"]) and isinstance(d["content_sha256"], str)
            and bool(SHA256_RE.match(d["content_sha256"])))


def validate_state(st, now):
    """返回规范化的状态或 None（缺失、类型不对、None 值、时间非法一律 None）。"""
    if not isinstance(st, dict) or set(st) != STATE_KEYS or type(st["version"]) is not int or st["version"] != 1:
        return None
    for k in ("mac_online", "wang_present", "codex_in_production"):
        if type(st[k]) is not bool:
            return None
    upd = parse_ts(st["updated_at"])
    if upd is None or upd > now or not isinstance(st["drafts"], dict):
        return None
    for did, ds in st["drafts"].items():
        if not (isinstance(did, str) and DRAFT_ID_RE.match(did) and isinstance(ds, dict)
                and set(ds) == DRAFT_STATE_KEYS and ds["status"] in ("archived", "deferred")
                and parse_ts(ds["at"]) is not None and valid_date(ds["date"])
                and isinstance(ds["content_sha256"], str) and SHA_RE.match(ds["content_sha256"])):
            return None
        if ds["status"] == "archived" and ds["reason"] not in ARCHIVE_CODES:
            return None
        if ds["status"] == "deferred" and ds["reason"] != "I-DEFERRED":
            return None
    out = dict(st)
    out["heartbeat_fresh"] = (now - upd) <= MAC_STATUS_TTL   # 心跳超过 30 分钟 → Mac 状态未知
    return out


def _strict_v2(draft, card_type):
    return card_type == "signal" or draft["draft_id"].startswith(TONGYI_SECTION + "-")


MACRO_SECTION = "macro"   # 宏观稿件 macro/<name>.md → macro-<name>，须王总批准


MEDICAL_CATEGORIES = ("medical", "religion", "macro")   # Codex 记录 category 字段的取值：任一 → 需王总批准


def medical_section(did):
    """稿件路径在医疗栏目（lexicon medical_sections：medical/、health/、tcm/、zhongyi/…）下 → 按医疗类处理。"""
    from .selfcheck import load_lexicon
    try:
        secs = load_lexicon().get("medical_sections") or []
    except Exception:
        return True                                   # 词表读不到 → 从严
    return any(did.startswith(x + "-") for x in secs)


def codex_category(records, sha):
    """兼容旧接口：返回该内容 Codex 判定类别中的一个（从严时请用 codex_categories）。"""
    cats = codex_categories(records, sha)
    return sorted(cats)[0] if cats else None


def codex_categories(records, sha):
    """整体验收 r13 BLOCKER（审查 bot 定）：审批类型取该内容全部 Codex 记录类别的并集——首日 <sha>.json、
    批准校验选中的当日 <sha>.<D>.json 都在其中（另含其他日期文件，只会更严）。不再取“最后一条”，避免当日判出的
    医疗/宗教/宏观类别被首日记录盖掉。"""
    out = set()
    for r in (records or {}).get("codex") or []:
        if r.get("content_sha256") == sha and isinstance(r.get("category"), str):
            out.add(r["category"])
    return out


def needs_wang(draft, card_type, flags=None, records=None):
    """需要王总批准（因而在岗检查适用）的稿件：宏观稿、tongyi 稿、信号卡（cards-*），以及标为中医/佛学（医疗/宗教）
    或宏观内容的稿件（严格路径）。其余日报（含中英配对）只需 Codex APPROVED，不看王总在岗（用户决定：日报只需 Codex）。"""
    did = draft["draft_id"]
    if card_type == "signal" or did.startswith((CARD_SECTION + "-", TONGYI_SECTION + "-", MACRO_SECTION + "-")):
        return True
    if medical_section(did):
        return True                                   # r7 BLOCKER 2：医疗栏目路径兜底
    if codex_categories(records, draft["content_sha256"]) & set(MEDICAL_CATEGORIES):
        return True                                   # 脚本只拦已知词和标记；Codex 判为医疗/宗教/宏观类 → 需王总批准
    f = flags or {}
    return bool(f.get("macro") or f.get("medical") or f.get("religion"))


def check_approval(records, draft, card_type, now, target=None, pair=None, wang_required=True, no_cutoff=False, min_review=None,
                   deferred=False):
    """返回 None（已批准）或错误码。records = {"codex": [...], "wang": [...], "error": code|None}。
    target：本次可发布的 SGT 日期（普通稿 = 稿件日期；顺延稿 = 顺延日次日）。
    deferred=True（顺延稿）：Codex reviewed_at 必须落在可发布日（SGT）当天——顺延到第二天后，前一天的 Codex 记录作废
    （路线图第 89 行“顺延稿重新走当日审批路径”，r7 HIGH）；王总记录本来就要求当天。"""
    target = target or now.astimezone(SGT).date()
    cutoff = dt.datetime.combine(target, CUTOFF, SGT)
    if deferred:
        min_review = max(min_review or target, target)   # r7 HIGH：顺延稿的前一日 Codex 记录作废，须按可发布日重新审查
    if records.get("error"):
        return records["error"]
    sha = draft["content_sha256"]
    did = draft["draft_id"]
    # 稿件身份绑定：记录的 content_sha256 与 draft_id 都必须等于当前稿件（同一内容换路径不能复用批准）
    # 整体验收 r12 HIGH（王总定）：首日发布只认 <sha>.json；顺延到 D 日只认 <sha>.<D>.json（reviewed_at 须在 D 日，读取时已核）
    want_day = target.isoformat() if deferred else None
    cx = [r for r in records.get("codex") or [] if r["content_sha256"] == sha and r.get("_for_date") == want_day]
    if cx and cx[-1]["draft_id"] != did:
        return "E-ROUTE-RECORD-MISMATCH"
    if not cx or cx[-1]["verdict"] != "APPROVED":
        return "E-ROUTE-NO-CODEX"
    # 中英配对（t145u）：pair = 配对另一版的 content_sha256（单篇为 None）。记录的 pair_sha256 必须与之互相引用，
    # 对方记录必须同样 APPROVED、reviewed_at 完全相同；单篇稿不得使用带 pair_sha256 的记录。
    if cx[-1].get("pair_sha256") != pair:
        return "E-ROUTE-PAIR-MISMATCH"
    if pair is not None:
        ox = [r for r in records.get("codex") or [] if r["content_sha256"] == pair and r.get("_for_date") == want_day]   # 两版同一个 D
        if not ox or ox[-1]["verdict"] != "APPROVED":
            return "E-ROUTE-PAIR-INCOMPLETE"
        if ox[-1].get("pair_sha256") != sha or ox[-1]["reviewed_at"] != cx[-1]["reviewed_at"]:
            return "E-ROUTE-PAIR-MISMATCH"
    ct = parse_ts(cx[-1]["reviewed_at"])
    # Codex 完成时间：不晚于当前时间，不早于稿件日期（SGT），且不晚于可发布日 06:55（SGT）
    if ct is None or ct > now or ct.astimezone(SGT).date() < dt.date.fromisoformat(draft["date"]):
        return "E-ROUTE-RECORD-EXPIRED"
    if ct > cutoff and not no_cutoff:
        return "E-ROUTE-RECORD-LATE"
    if deferred and ct.astimezone(SGT).date() != target:
        return "E-ROUTE-RECORD-EXPIRED"         # 顺延稿：reviewed_at 必须是 D 日
    if min_review is not None and ct.astimezone(SGT).date() < min_review:
        return "E-ROUTE-RECORD-EXPIRED"         # 更正稿：Codex 审查不得早于 corrected_at
    if not wang_required:
        return None                             # 日报（非严格路径）：只需 Codex APPROVED
    # 整体验收 r13 HIGH（审查 bot 定，与 Codex 对称）：首日只认 approvals/wang/<sha>.json，顺延到 D 日只认 <sha>.<D>.json
    wg = [r for r in records.get("wang") or [] if r["content_sha256"] == sha and r.get("_for_date") == want_day]
    if not wg:
        return "E-ROUTE-NO-WANG"
    w = wg[-1]
    if is_v2(w) and w["draft_id"] != did:
        return "E-ROUTE-RECORD-MISMATCH"
    t = parse_ts(w["recorded_at"])
    # 当天有效：recorded_at 与当前时间按 Asia/Singapore 日历日相同，且不晚于当前时间
    if t is None or t > now or t.astimezone(SGT).date() != now.astimezone(SGT).date() \
            or t.astimezone(SGT).date() != target:
        return "E-ROUTE-RECORD-EXPIRED"
    if t > cutoff and not no_cutoff:
        return "E-ROUTE-RECORD-LATE"            # 王总批准须在当天 06:55（SGT）前（更正稿不受此限）
    if t < ct:
        return "E-ROUTE-RECORD-ORDER"           # 王总批准不得早于 Codex 审查完成（recorded_at >= reviewed_at）
    if not is_v2(w):
        return "E-ROUTE-RECORD-V2-REQUIRED"     # r12：需要王总批准的稿件（宏观、医疗、宗教、tongyi、信号卡）只接受绑定 draft_id 的 v2 记录
    if _strict_v2(draft, card_type) and not is_v2(w):
        return "E-ROUTE-RECORD-V2-REQUIRED"     # 信号卡与 tongyi 稿必须使用带 quote_ref、绑定 draft_id 的 v2 记录（逐篇）
    if _strict_v2(draft, card_type) and w["channel"] != "direct":
        return "E-ROUTE-RECORD-MISMATCH"
    return None


def _diagnose_from_git(sc, draft, repo, now, pair=None, correction=None, force_wang=False):
    """r17（王总定）：诊断 + 状态变更，不设 publishable。批准记录与状态只在这里用
    git show APPROVALS_REF:approvals/... 与 state/publish-state.json 从 repo 读取。
    发布结论只有 route_pr 给出：它在自己从 gh/git 取得 PR head、稿件字节、sha、更正信息与原稿类别之后，
    才把诊断为 APPROVED 的结果标为 publishable。直接 import 本函数得到的结果不算发布依据（威胁模型 (c)：
    有意绕过记 FOLLOW-UP，归 #30）。"""
    from .statechange import draft_change
    state, records = load_from_ref(repo, APPROVALS_REF)
    d = _diagnose(sc, draft, state, records, now, pair, correction, force_wang)
    # r8 BLOCKER 2：报告本稿按类型是否需要王总批准，供 route_pr 对中英配对取并集
    try:
        wr = bool(force_wang or (correction or {}).get("wang")
                  or needs_wang(draft, sc["card_type"], sc["flags"], records if isinstance(records, dict) else None))
    except (KeyError, TypeError, AttributeError):
        wr = True                                    # 判不出 → 从严
    setattr(d, "wang_required", wr)
    if d.state in ("ARCHIVED", "DEFERRED") and "E-ROUTE-ARCHIVED-REUSE" not in d.codes:
        if d.state == "DEFERRED":
            d.state_change = draft_change(draft, "deferred", "I-DEFERRED", now)
        else:
            reason = next(c for c in d.codes if c.startswith("A-"))
            d.state_change = draft_change(draft, "archived", reason, now)
    return d


def _diagnose(sc, draft, state, records, now, pair=None, correction=None, force_wang=False):
    """纯函数，只给诊断（不带 publishable）。records = {"codex": [...], "wang": [...], "error": code|None}（来自 approvals.load_from_ref）。"""
    if not (isinstance(now, dt.datetime) and now.tzinfo is not None):
        return _hold("E-ROUTE-INPUT")
    if not validate_selfcheck(sc) or not validate_draft(draft) or sc["date"] != draft["date"]:
        return _hold("E-ROUTE-INPUT")
    if sc.get("content_sha256") != draft["content_sha256"]:
        return _hold("E-ROUTE-INPUT")              # r12：自检结果必须是这篇稿件的（content_sha256 一致）
    st = validate_state(state, now)
    if st is None:
        return _hold("E-ROUTE-STATE")
    if not isinstance(records, dict) or not isinstance(records.get("codex"), list) or not isinstance(records.get("wang"), list):
        return _hold("E-ROUTE-STATE")
    if not all(valid_codex(r) for r in records["codex"]) or not all(valid_wang(r) for r in records["wang"]):
        return _hold("E-ROUTE-RECORD-INVALID")      # r13：记录字段缺一个（或类型不符）即失败，不靠 check_approval 部分字段放行
    ds = st["drafts"].get(draft["draft_id"])
    if ds and ds["status"] == "archived":              # 最终状态，永不复活
        return Decision("ARCHIVED", ["E-ROUTE-ARCHIVED-REUSE", ds["reason"]])
    same = [x for k, x in st["drafts"].items() if x["status"] == "archived" and x["content_sha256"] == draft["content_sha256"]]
    if same:                                           # 已归档稿改名（换 draft_id）后同样不能复活
        return Decision("ARCHIVED", ["E-ROUTE-ARCHIVED-REUSE", same[0]["reason"]])
    is_deferred = bool(ds and ds["status"] == "deferred")
    # r15 HIGH（协调方批准）：更正稿的判定在顺延核对之前——原稿曾顺延、后在站点 main 发布（_route_one 已核验），
    # 其顺延条目（绑定旧稿 sha）不能拦住更正稿；自检、内部词、记录错误等前置检查照常先于更正判定。
    if correction is not None:
        if sc["flags"]["internal"]:
            return Decision("REJECTED", ["E-ROUTE-HARD-REJECT"])
        if sc["status"] == "FAIL":
            return _hold("E-ROUTE-SELFCHECK-FAIL", *sc["error_codes"])
        if records.get("error"):
            return _hold(records["error"])
        return _decide_correction(sc, draft, st, ds, records, now, pair, correction, force_wang)
    if is_deferred and (ds["content_sha256"] != draft["content_sha256"] or ds["date"] != draft["date"]):
        return _hold("E-ROUTE-DEFER-MISMATCH")      # 顺延记录必须绑定同一稿件内容与原日期
    if is_deferred and now.astimezone(SGT).date() <= dt.date.fromisoformat(ds["date"]):
        return _hold("E-ROUTE-DEFERRED-SAMEDAY")    # 顺延稿只能在次日（SGT）及以后再路由

    if sc["flags"]["internal"]:
        return Decision("REJECTED", ["E-ROUTE-HARD-REJECT"])
    if sc["status"] == "FAIL":
        return _hold("E-ROUTE-SELFCHECK-FAIL", *sc["error_codes"])
    if records.get("error"):
        return _hold(records["error"])            # approvals 读取/校验失败：先 HOLD，任何可发布出口之前
    # 可发布日：普通稿 = 稿件日期；顺延稿 = 顺延日（ds.date）的次日。截止时间都按可发布日计算。
    target = dt.date.fromisoformat(ds["date"]) + dt.timedelta(days=1) if is_deferred else dt.date.fromisoformat(draft["date"])
    now_sgt = now.astimezone(SGT)
    if now_sgt.date() < target:
        return _hold("E-ROUTE-NOT-YET")           # 未到可发布日（未来日期稿）：不得提前自动批准
    # 王总 t161u（经 Grok Bot 转达，2026-10-11）：日报每天都要过 Codex，取消低风险自动批准。
    # AUTO_APPROVED 路径永久关闭：任何稿件没有有效的 Codex APPROVED（+ 王总批准）记录就不得发布。
    # selfcheck 的 low_risk / R-* 只作审查参考，这里不再读取。
    low = False
    wreq = needs_wang(draft, sc["card_type"], sc["flags"], records) or force_wang
    if (not wreq and sc["status"] == "PASS" and now_sgt < dt.datetime.combine(target, PUBLISH_DEADLINE, SGT)
            and check_approval(records, draft, sc["card_type"], now, target, pair, False, deferred=is_deferred) is None):
        if st["codex_in_production"]:
            return Decision("ARCHIVED", ["A-NO-REVIEW-PATH"])   # r12：快通道排在 codex_in_production 检查之后
        # 用户决定（2026-10-11，经 Grok Bot 转达）：不需要王总批准的稿件（日报，含中英配对）一旦已有有效 Codex APPROVED
        # （06:55 前完成、绑定内容与配对），就不再因 Mac 离线、心跳过期或王总不在场而 HOLD/归档；07:00 截止照旧。
        return Decision("APPROVED", [])
    if not low and st["heartbeat_fresh"] and not st["mac_online"]:
        # 协调决定（10-11）：需审查稿在心跳新鲜且 mac_online=false 时当天归档，优先于 07:00 顺延
        return Decision("ARCHIVED", (["E-ROUTE-UNCLEAR"] if sc["status"] == "UNCLEAR" else []) + ["A-MAC-OFFLINE"])
    if now_sgt >= dt.datetime.combine(target, PUBLISH_DEADLINE, SGT):
        # 协调决定：07:00 首次逾期一律顺延到次日（低风险稿也一样）；顺延稿再次逾期 → 归档
        if is_deferred:
            # 顺延稿再次逾期：需审查且仍缺有效批准 → A-NOT-APPROVED；低风险稿或已获批稿 → A-OVERDUE-TWICE（二次逾期）
            e2 = None if low else check_approval(records, draft, sc["card_type"], now, target, pair, wreq, deferred=is_deferred)
            return Decision("ARCHIVED", ["E-ROUTE-PUBLISH-LATE"] + ([e2, "A-NOT-APPROVED"] if e2 else ["A-OVERDUE-TWICE"]))
        return Decision("DEFERRED", ["E-ROUTE-PUBLISH-LATE", "I-DEFERRED"])

    # 以下均为需要 Codex 审查的稿件：心跳只对它们生效（协调决定：低风险稿不看心跳，也不按离线归档）。
    if not st["heartbeat_fresh"]:
        return _hold("E-ROUTE-MAC-STALE")         # 心跳过期：Mac 状态未知，一律 HOLD，可重试；不归档

    if sc["status"] == "UNCLEAR":
        if not st["mac_online"]:
            return Decision("ARCHIVED", ["E-ROUTE-UNCLEAR", "A-MAC-OFFLINE"])
        return _hold("E-ROUTE-UNCLEAR", *sc["error_codes"])
    if st["codex_in_production"]:
        return Decision("ARCHIVED", ["A-NO-REVIEW-PATH"])
    if not st["mac_online"]:
        return Decision("ARCHIVED", ["A-MAC-OFFLINE"])

    e = check_approval(records, draft, sc["card_type"], now, target, pair, wreq, deferred=is_deferred)
    codes = [e] if e else []
    if e is None:
        return Decision("APPROVED", [])   # 07:00 截止已在上面统一处理

    end_of_day = now_sgt >= dt.datetime.combine(target, CUTOFF, SGT)
    # 王总在场（wang_present）只对需要王总批准的稿件生效；日报不依赖在岗状态
    if not end_of_day and (st["wang_present"] or not wreq):
        return Decision("NEEDS_REVIEW", codes + ["I-NEEDS-REVIEW"])
    if is_deferred:
        return Decision("ARCHIVED", codes + ["A-NOT-APPROVED"])
    return Decision("DEFERRED", codes + ["I-DEFERRED"])


def _decide_correction(sc, draft, st, ds, records, now, pair, corr, force_wang=False):
    """更正稿（Grok Bot 定，2026-10-11）：只要 Codex 批准（原稿类别须王总批准的仍须王总批准）即可发布，
    不受 06:55 / 07:00 与顺延限制；自检、配对、codex_in_production 照常。corr 由 _route_one 校验后给出。"""
    if ds is not None and ds["status"] != "deferred":
        return _hold("E-ROUTE-CORRECTION-TARGET")     # 非顺延的状态条目（归档已在前面拦下）→ fail-closed
    # r15 HIGH：顺延条目只说明原稿曾顺延；是否已发布以 _route_one 核验的站点 main 原稿为准
    if st["codex_in_production"]:
        return _hold("E-ROUTE-CORRECTION", "A-NO-REVIEW-PATH")   # 不归档已发布稿，只拦住
    if sc["status"] != "PASS":
        return _hold("E-ROUTE-UNCLEAR", *sc["error_codes"])
    wreq = needs_wang(draft, sc["card_type"], sc["flags"], records) or corr["wang"] or force_wang
    today = now.astimezone(SGT).date()
    e = check_approval(records, draft, sc["card_type"], now, today, pair, wreq, no_cutoff=True,
                       min_review=corr["corrected_at"])
    if e is None:
        return Decision("APPROVED", ["I-CORRECTION"])
    return Decision("NEEDS_REVIEW", [e, "I-CORRECTION", "I-NEEDS-REVIEW"])


_FM_RE = re.compile(r"\A---[ \t]*\n(.*?)\n?---[ \t]*(?:\n|\Z)", re.S)


class FrontMatterError(ValueError):
    pass


def _fm_scalar(v):
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    return v


def _yaml_loader():
    yaml = require_yaml()   # r10：缺 PyYAML → DependencyError（E-DEP-PYYAML），CLI 结构化 HOLD

    class _NoDupLoader(yaml.SafeLoader):
        pass

    def _map(loader, node, deep=False):
        keys = set()
        for k, _ in node.value:
            kv = loader.construct_object(k, deep=deep)
            if not isinstance(kv, str):
                raise FrontMatterError("non-string key %r" % (kv,))   # 整体验收 r2：键不是字符串 → 结构化 HOLD，不崩溃
            if kv in keys:
                raise FrontMatterError("duplicate key %r" % (kv,))
            keys.add(kv)
        return yaml.SafeLoader.construct_mapping(loader, node, deep)
    _NoDupLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _map)
    return _NoDupLoader


def front_matter(text):
    """r16（王总定）：用 yaml.safe_load 解析文首 --- … ---。返回 (字段 dict, 正文)；没有 front matter → ({}, text)。
    YAML 解析失败或顶层不是映射 → FrontMatterError（调用方判失败）。日期值转成 ISO 字符串。"""
    yaml = require_yaml()   # r10：缺 PyYAML → DependencyError（E-DEP-PYYAML），CLI 结构化 HOLD
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.load(m.group(1), Loader=_yaml_loader())   # SafeLoader + 重复键判失败（r17）
    except FrontMatterError:
        raise
    except (yaml.YAMLError, TypeError, ValueError) as e:
        raise FrontMatterError(str(e)) from None
    if fm is None:
        fm = {}
    if not isinstance(fm, dict) or not all(isinstance(k, str) for k in fm):
        raise FrontMatterError("front matter is not a mapping")
    return {k: _fm_scalar(v) for k, v in fm.items()}, text[m.end():]


def _labels(v):
    """categories / tags 等：支持标量、行内列表 [a, b] 与多行列表；其他结构（映射、嵌套）→ None（识别不出）。"""
    if isinstance(v, (str, int, float)) and not isinstance(v, bool):
        return [str(v).strip()]
    if isinstance(v, list) and all(isinstance(x, (str, int, float)) and not isinstance(x, bool) for x in v):
        return [str(x).strip() for x in v]
    return None


_ORIG_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?)?")


def _orig_date_sgt(v):
    """整体验收 r5 MEDIUM：原稿 date 整体解析（不再只截前 10 个字符）。纯日期直接用；带时间的按 SGT 换算后取日期
    （不带时区的按 SGT 理解）。任何非法后缀或非法日期 → None（调用方判 E-ROUTE-CORRECTION-TARGET）。返回 ISO 日期字符串。"""
    if not isinstance(v, str) or not _ORIG_DATE_RE.fullmatch(v):
        return None
    try:
        if len(v) == 10:
            return dt.date.fromisoformat(v).isoformat()
        t = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=SGT)
    return t.astimezone(SGT).date().isoformat()


SITE_REF = "origin/main"            # r15（王总定）：“已发布”以站点仓库 origin/main 上确实有这篇为准
SITE_CONTENT = "content/posts"
SITE_CARDS = "content/cards"
SITE_REMOTE = "markjin-lab/markjin-lab.github.io"   # r16（王总定）：站点仓库只接受这个 remote
_SITE_REMOTE_RE = re.compile(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
                             r"markjin-lab/markjin-lab\.github\.io(?:\.git)?/?")
WANG_SECTIONS = (MACRO_SECTION, TONGYI_SECTION, CARD_SECTION)
_WANG_FM_RE = re.compile(r"宏观|医疗|中医|佛学|佛教|宗教|tongyi|统一系统观|信号卡|卡片|\bmacro\b|\bmedical\b|\breligio|\bcards?\b|\bsignal", re.I)
# r16（王总定）：类别识别不出来就按最严一类（须王总批准）。只有以下标签可识别为“日报类、不需王总批准”。
DAILY_LABELS = {"daily", "digest", "日报", "每日信号", "摘要", "daily signals"}
CAT_KEYS = FM_CATEGORY_KEYS   # 整体验收 r10 BLOCKER：与 selfcheck 共用 fmkeys 的同一份定义（含 keywords）


def _site_remote_ok(url):
    return bool(_SITE_REMOTE_RE.fullmatch(url.strip()))


def _site_main(site_repo):
    """r16：站点仓库 origin 必须是 SITE_REMOTE；先 fetch origin main，再要求本地 origin/main 等于远端 main。失败 → None。"""
    u = _git(site_repo, "remote", "get-url", "origin")
    if u.returncode != 0 or not _site_remote_ok(u.stdout):
        return None
    if _git(site_repo, "fetch", "-q", "origin", "+refs/heads/main:refs/remotes/origin/main").returncode != 0:
        return None
    rem = _git(site_repo, "ls-remote", "origin", "refs/heads/main")
    loc = _git(site_repo, "rev-parse", "origin/main")
    rs = rem.stdout.split()[0] if rem.returncode == 0 and rem.stdout.split() else None
    if rs is None or loc.returncode != 0 or loc.stdout.strip() != rs:
        return None
    return rs


def _orig_needs_wang(sec, ofm):
    """原稿类别：section 属于宏观/tongyi/信号卡，或标签命中宏观、医疗、宗教等 → 须王总；
    非 daily/digest 栏目，或任何标签不在 DAILY_LABELS 里（识别不出）→ 按最严，须王总。"""
    if sec in WANG_SECTIONS or sec not in ("daily", "digest"):
        return True
    return labels_need_wang(ofm)


def labels_need_wang(fm):
    """整体验收 r9 BLOCKER（王总定）：front matter 用 YAML 解析后的类别全部参与审批类型判定（本稿与更正原稿共用）。
    分类键（fmkeys.FM_CATEGORY_KEYS：categories / tags / keywords / type / series 等，与 selfcheck 共用）里出现 macro、religion、medical、tongyi、card 等需王总批准的类别 → 须王总；
    未知类别（不在 DAILY_LABELS）、null、空列表、空串或无法解释 → 照旧须王总。与路径、正文词表取并集（见 _route_one）。"""
    for k, v in fm.items():
        if str(k).lower() not in CAT_KEYS:
            continue
        ls = _labels(v)
        if not ls or any(not x for x in ls):
            return True                               # r17：字段存在但为 null、空列表、空串或无法解释 → 须王总
        for x in ls:
            if _WANG_FM_RE.search(x) or x.lower() not in DAILY_LABELS:
                return True
    return False


def site_path(did, en):
    """section / name → 站点 content/posts/<section>/<name>[.en].md。"""
    if en:
        did = did[: -len(EN_SUFFIX)]
    sec, name = did.split("-", 1)
    base = f"{SITE_CARDS}/{name}" if sec == CARD_SECTION else f"{SITE_CONTENT}/{sec}/{name}"   # 信号卡站点路径为 content/cards/<name>.md
    return base + (".en.md" if en else ".md")


_NONRENDER_TAGS = {"template", "script", "style", "noscript", "head", "title", "textarea", "iframe", "object"}
# 整体验收 r6 HIGH：带 hidden、aria-hidden="true"、style（可能 display:none / visibility:hidden）或 class（外部 CSS 无法判断）
# 的元素一律当作不可见，连同其内容一起去掉
_HIDE_ATTR_RE = re.compile(r"""(?:^|\s)(?:hidden(?:\s|=|$)|aria-hidden\s*=\s*["']?\s*true|style\s*=|class\s*=)""", re.I)
_START_TAG_RE = re.compile(r"<([A-Za-z][A-Za-z0-9-]*)\b([^>]*)>")


def _drop_hidden_html(t):
    """去掉不可见的内联 HTML 元素及其内容（同名标签按嵌套深度配对；找不到结束标签 → 去到行尾）。"""
    pos = 0
    while True:
        m = _START_TAG_RE.search(t, pos)
        if not m:
            return t
        tag, attrs = m.group(1).lower(), m.group(2)
        if tag not in _NONRENDER_TAGS and not _HIDE_ATTR_RE.search(attrs):
            pos = m.end(); continue
        if attrs.rstrip().endswith("/"):
            t = t[:m.start()] + t[m.end():]; pos = m.start(); continue
        depth, j = 1, m.end()
        tok = re.compile(r"<(/?)" + re.escape(m.group(1)) + r"\b[^>]*>", re.I)
        end = len(t)
        for k in tok.finditer(t, m.end()):
            depth += -1 if k.group(1) else 1
            if depth == 0:
                end = k.end(); break
        t = t[:m.start()] + t[end:]
        pos = m.start()


def _heading_shown(ln):
    """整体验收 r3 MEDIUM：标题行渲染后可见的文字——去掉图片、链接目标、HTML 标签与属性、自动链接，只留显示文本。
    整体验收 r6 HIGH：HTML 注释、不渲染的元素（template/script/style/noscript…），以及带 hidden、aria-hidden="true"、
    style、class 属性的元素，其中的文字（含更正日期）一律不算可见。"""
    t = re.sub(r"<!--.*?(?:-->|$)", "", ln)                     # 注释（含未闭合）里的不算
    t = _drop_hidden_html(t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)                 # 图片整体不显示文字（alt 不算）
    t = re.sub(r"!\[[^\]]*\]\[[^\]]*\]", "", t)                 # 引用式图片（整体验收 r4）
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)              # [文字](目标) → 文字
    t = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", t)            # 引用式链接
    t = re.sub(r"<[^>]*>", "", t)                                 # 其余 HTML 标签（含属性）与 <自动链接>
    return t


def _correction(rel, text, did, date, now, site_repo):
    """None = 不是更正稿；str = 错误码；dict = 校验通过的更正信息。
    r15：原稿是否已发布、原稿日期与类别，只看站点仓库 SITE_REF 上那一版的路径与 front matter；不用发布状态，不重跑自检。"""
    try:
        fm, body = front_matter(text)
    except FrontMatterError:
        return "E-ROUTE-CORRECTION-INVALID" if re.search(r"(?m)^(corrects|corrected_at)\s*:", text) else None
    if "corrects" not in fm and "corrected_at" not in fm:
        return None
    if not fm.get("corrects") or not fm.get("corrected_at"):
        return "E-ROUTE-CORRECTION-INVALID"
    if not isinstance(fm["corrects"], str) or not isinstance(fm["corrected_at"], str):
        return "E-ROUTE-CORRECTION-INVALID"
    if fm["corrects"] != did:
        return "E-ROUTE-CORRECTION-TARGET"           # 更正稿与原稿 section、name 必须一致（同一 draft_id）
    if not valid_date(fm["corrected_at"]):
        return "E-ROUTE-CORRECTION-DATE"
    if not site_repo:
        return "E-ROUTE-CORRECTION-TARGET"           # 没有站点仓库就无法证明已发布 → 失败
    if SITE_REF == "origin/main" and _site_main(site_repo) is None:
        return "E-ROUTE-CORRECTION-TARGET"           # r16：只认 remote 为 SITE_REMOTE 的仓库，先 fetch，origin/main 须等于远端 main
    sp = site_path(did, did.endswith(EN_SUFFIX))
    r = _git(site_repo, "show", SITE_REF + ":" + sp, text=False)
    if r.returncode != 0:
        return "E-ROUTE-CORRECTION-TARGET"           # 站点 main 上查不到原稿 → 未发布，失败
    try:
        orig = r.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return "E-ROUTE-CORRECTION-TARGET"
    try:
        ofm, _ = front_matter(orig)
    except FrontMatterError:
        return "E-ROUTE-CORRECTION-TARGET"           # r16：原稿 front matter 解析失败 → 失败
    od = _orig_date_sgt(ofm.get("date"))
    if od is None:
        return "E-ROUTE-CORRECTION-TARGET"           # 原稿 front matter 无合法日期 → 失败
    if od != date:
        return "E-ROUTE-CORRECTION-DATE"             # 更正稿沿用原稿日期（站点 main 那一版的 front matter）
    ca = dt.date.fromisoformat(fm["corrected_at"])
    if ca < dt.date.fromisoformat(od) or ca > now.astimezone(SGT).date():
        return "E-ROUTE-CORRECTION-DATE"             # 不早于原稿日期，不晚于实际发布当天（SGT）
    if orig == text:
        return "E-ROUTE-CORRECTION-TARGET"
    if not any(re.match(r"^[ ]{0,3}#{1,6}[ \t]", ln) and fm["corrected_at"] in _heading_shown(ln)
               for ln in visible_text(body).splitlines()):
        return "E-ROUTE-CORRECTION-NOTE"             # 整体验收 r2（王总定）：更正日期须出现在标题行（# … 行）里
    sec = did.split("-", 1)[0]
    return {"corrected_at": ca, "wang": _orig_needs_wang(sec, ofm)}


# —— 稿件路径 → draft_id（协调决定：<section>-<文件名>，如 daily/2026-10-11.md → daily-2026-10-11）
SEG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SECTION_RE = re.compile(r"^[a-z0-9]+$")   # r11：section 不得含 '-'，避免 a-b/c.md 与 a/b-c.md 推出同一 draft_id


def draft_id_for(repo, draft_path):
    """稿件必须位于仓库内 <section>/<name>.md（恰好两级），section 与 name 只含小写字母、数字、连字符；
    draft_id = f"{section}-{name}"，不超过 64 个字符。否则返回 None。"""
    try:
        rel = Path(draft_path).resolve().relative_to(Path(repo).resolve())
    except (ValueError, OSError, TypeError):
        return None
    parts = PurePosixPath(rel.as_posix()).parts
    if len(parts) != 2 or not parts[1].endswith(".md"):
        return None
    section, name, en = parts[0], parts[1][:-3], False
    if name.endswith(".en"):
        name, en = name[:-3], True                     # t141u：<name>.en.md → <section>-<name>-en
    elif name.endswith(EN_SUFFIX):
        return None                                    # <name>-en.md 会与 <name>.en.md 撞 draft_id，拒绝
    if not (SECTION_RE.match(section) and SEG_RE.match(name)):
        return None
    did = f"{section}-{name}" + (EN_SUFFIX if en else "")
    return did if DRAFT_ID_RE.match(did) else None


# —— 从 main 分支读取
RESERVED_DIRS = {"docs", "review", "raw", "approvals", "state", "scripts", "tests", "feedback", "proposals", ".github",
                 "content", "layouts", "static", "i18n", "assets"}


APPROVALS_REF = "origin/main"   # r13：Codex 与王总记录只从 origin/main 的 approvals/ 读取（调用方不能指定）


KNOWN_SECTIONS = ("daily", "digest", MACRO_SECTION, TONGYI_SECTION, CARD_SECTION)   # r15：只允许已知栏目


def _route_one(rel, data, tree, date, card_type, now, link_checker=None, pair=None, records_repo=None, site_repo=None,
               force_wang=False):
    """单篇路由（私有）。只由 route_pr 调用：稿件路径 rel 与字节 data 来自 PR head 的 git 对象；
    tree 是 PR head 提交检出的只读目录（raw/ 与 MANIFEST 也从这里读）；记录从 records_repo 的 APPROVALS_REF 读。"""
    from .selfcheck import check_text
    did = draft_id_for(tree, Path(tree) / rel)
    if did is None or (card_type == "signal") != did.startswith(CARD_SECTION + "-"):
        return None, _hold("E-ROUTE-DRAFT-PATH")       # 卡片必须在 cards/，cards/ 下只能是卡片
    if did.split("-", 1)[0] not in KNOWN_SECTIONS:
        return None, _hold("E-ROUTE-DRAFT-PATH")       # r15：未知栏目一律失败（不按日报放行）
    try:
        text = data.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        return None, _hold("E-SELFCHECK-READ")
    try:
        fm_parsed = front_matter(text)[0]
    except FrontMatterError:
        return None, _hold("E-ROUTE-FRONT-MATTER")       # r16（王总定）：front matter 用 YAML 解析，失败即判失败
    # 整体验收 r9 BLOCKER：解析出的类别全部参与审批类型判定；与路径（needs_wang 的栏目判定）、正文词表（selfcheck flags）取并集
    force_wang = force_wang or labels_need_wang(fm_parsed)
    sha = hashlib.sha256(data).hexdigest()
    sc = check_text(text, tree, date, card_type, link_checker=link_checker, rel=rel)   # r15：tongyi 长文豁免需 type 与路径一致
    sc["content_sha256"] = sha                           # r12：自检结果绑定稿件内容，_decide() 核对
    draft = {"draft_id": did, "date": date, "content_sha256": sha}
    nm = PurePosixPath(rel).stem.split(".", 1)[0]
    if did.split("-", 1)[0] in DAILY_SECTIONS and re.match(r"\d{4}-\d{2}-\d{2}", nm) and nm[:10] != date:
        return None, _hold("E-ROUTE-INPUT")              # r14（r13 H-4）：日期命名的日报类稿件，路径日期必须等于 --date
    corr = _correction(rel, text, did, date, now, site_repo)
    if isinstance(corr, str):
        return sc, _hold(corr)
    daily_like = did.split("-", 1)[0] in DAILY_SECTIONS
    if disclaimer_required(did, date, corr) and not has_disclaimer(text, did.endswith(EN_SUFFIX)):
        return sc, _hold("E-ROUTE-DISCLAIMER-MISSING")   # r12/r13：日报类稿件须有可见的固定免责声明；2026-10-13 起只用站点页脚（见 disclaimer_required）
    d = _diagnose_from_git(sc, draft, records_repo or tree, now, pair, correction=corr, force_wang=force_wang)
    if did.endswith(EN_SUFFIX) and "R-TRANSLATION" not in sc["error_codes"]:
        d.codes.append("R-TRANSLATION")
    return sc, d


DAILY_SECTIONS = ("daily", "digest")       # r13：日报类稿件放在 daily/ 或 digest/ 都查免责声明
DISCLAIMER_FROM = "2026-10-12"              # r13：从 2026-10-12 的稿件起执行，历史稿不追溯
FOOTER_ONLY_FROM = "2026-10-13"             # 2026-10-16 王总／Grok Bot：此日起日报只用站点页脚免责声明（smoke 查 footer_disclaimer），正文不加、不查
_COMMENT_RE = re.compile(r"<!--.*?(?:-->|\Z)", re.S)
_FENCE_RE = re.compile(r"^[ ]{0,3}((`|~)\2{2,}).*?(?:^[ ]{0,3}\1\2*[ \t]*$|\Z)", re.S | re.M)   # r8：闭围栏同字符、长度 ≥ 开围栏（与台账一致）


def footer_only(date):
    """2026-10-13 起的日报类稿件（含其更正稿，按稿件日期）只用站点页脚免责声明，正文不查。"""
    return isinstance(date, str) and date >= FOOTER_ONLY_FROM


def needs_disclaimer(did, date):
    return (did.split("-", 1)[0] in DAILY_SECTIONS and isinstance(date, str) and date >= DISCLAIMER_FROM
            and not footer_only(date))


def disclaimer_required(did, date, corr=None):
    """正文固定免责声明是否必需：2026-10-12 的日报类稿件必需；更早日期的日报类更正稿仍必需（r13）；
    2026-10-13 起一律不查正文（只用站点页脚）。"""
    if did.split("-", 1)[0] not in DAILY_SECTIONS or footer_only(date):
        return False
    return needs_disclaimer(did, date) or bool(corr)


def visible_text(text):
    """r13：去掉 HTML 注释（含未闭合注释到文末）与围栏代码块；r12（整体验收）：再用 HTML 解析器去掉整篇范围内的隐藏元素子树。免责声明、更正标题只在可见文本里认。"""
    try:
        body = front_matter(text)[1]                  # r14：front matter 是元数据，不算页面可见文字
    except FrontMatterError:
        m = _FM_RE.match(text); body = text[m.end():]  # 解析失败的稿件在 _route_one 已判失败；这里只为诊断
    return _hide_html(_FENCE_RE.sub("", _COMMENT_RE.sub("", body)))


_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def _hide_html(text):
    """整体验收 r12 BLOCKER（王总定）：用 HTML 解析器按整篇正文追踪隐藏范围（与站点 smoke 同一思路），不再逐行处理。
    hidden、aria-hidden="true"、style（可能 display:none / visibility:hidden）、class（外部 CSS 无法判断）属性的元素，
    以及 template/script/style/noscript 等不渲染元素，其整个子树（可跨任意多行）都不算可见；未闭合的隐藏元素一直隐藏到文末
    （fail-closed）。注释与围栏代码块在调用前已去掉。返回保留换行的可见文字（标签本身去掉）。"""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack = []          # [(tag, hidden)]
            self.out = []

        def _hidden(self):
            return any(h for _, h in self.stack)

        def handle_starttag(self, tag, attrs):
            if tag in _VOID_TAGS:
                return
            a = " " + " ".join(k + ("=" + (v or "") if v is not None else "") for k, v in attrs)
            hid = tag in _NONRENDER_TAGS or bool(_HIDE_ATTR_RE.search(a)) or any(
                k == "aria-hidden" and (v or "").strip().lower() == "true" for k, v in attrs)
            self.stack.append((tag, hid))

        def handle_startendtag(self, tag, attrs):
            pass                     # 自闭合：没有内容

        def handle_endtag(self, tag):
            for k in range(len(self.stack) - 1, -1, -1):
                if self.stack[k][0] == tag:
                    del self.stack[k:]
                    return           # 找不到同名开标签的结束标签忽略

        def handle_data(self, d):
            if self._hidden():
                self.out.append("\n" * d.count("\n"))   # 隐藏内容不输出，只保留换行，行结构不变
            else:
                self.out.append(d)

        def handle_comment(self, d):
            self.out.append("\n" * d.count("\n"))

    p = P()
    p.feed(text)
    p.close()
    return "".join(p.out)


def has_disclaimer(text, en):
    from .selfcheck import DISCLAIMER, DISCLAIMER_EN
    want = (DISCLAIMER_EN,) if en else (DISCLAIMER,)   # 整体验收 r2（王总定）：逐字匹配，句末标点也须一致
    return any(ln.strip() in want for ln in visible_text(text).splitlines())


def _git(repo, *args, text=True):
    import subprocess
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=text)


def _gh_pr(repo, number):
    """r13：PR 元数据只从 gh 取（baseRefOid、headRefOid、state、文件列表）。测试可替换本函数。
    部分 gh 版本的 `gh pr view --json` 没有 baseRefOid 字段，所以 SHA 与状态用 gh api 的 pulls/<N>（base.sha、head.sha、state），文件列表用 gh pr view --json files。"""
    import json, subprocess
    def run(args):
        r = subprocess.run(["gh"] + args, cwd=str(repo), capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("E-ROUTE-PR-FILES: gh failed: " + " ".join(args[:3]))
        try:
            return strictjson.loads(r.stdout)   # r11：gh 输出含重复键同样判失败
        except ValueError:
            raise RuntimeError("E-ROUTE-PR-FILES: gh output not JSON (or duplicate keys)")
    pr = run(["api", "repos/{owner}/{repo}/pulls/%d" % int(number)])
    files = run(["pr", "view", str(int(number)), "--json", "files"])
    try:
        return {"baseRefOid": pr["base"]["sha"], "headRefOid": pr["head"]["sha"],
                "state": "OPEN" if pr["state"] == "open" else str(pr["state"]).upper(),
                "files": files["files"]}
    except (KeyError, TypeError):
        raise RuntimeError("E-ROUTE-PR-FILES: gh output missing fields")


def pr_draft_files(repo, base, head):
    """PR 的变更清单由 git diff --name-status base...head 得到。任何删除、改名、复制或类型变更 → ValueError（一律判失败）。
    返回稿件 [rel_path]（<section>/<name>.md，排除保留目录）与全部变更路径。"""
    r = _git(repo, "diff", "--name-status", "--no-renames", "-z", f"{base}...{head}", text=False)
    if r.returncode != 0:
        raise RuntimeError("E-ROUTE-PR-FILES: git diff failed")
    parts = [x for x in r.stdout.decode("utf-8", "surrogateescape").split("\0")]
    drafts, allp = [], []
    i = 0
    while i + 1 < len(parts):
        st, p = parts[i], parts[i + 1]; i += 2
        if not st:
            break
        if st not in ("A", "M"):
            raise ValueError("E-ROUTE-PR-FILES: deleted/renamed/type-changed file in PR")
        allp.append(p)
        pp = PurePosixPath(p)
        if len(pp.parts) == 2 and pp.suffix == ".md" and pp.parts[0] not in RESERVED_DIRS:
            drafts.append(p)
    return sorted(drafts), sorted(allp)


PR_DATA_RE = re.compile(r"raw/\d{4}-\d{2}-\d{2}/[^\0]+")   # 白名单：同日/往日 raw 数据、证据与其 MANIFEST.sha256


def pr_scope_violations(drafts, allp):
    """稿件 PR 的准入（B4，r7）：变更只允许 ① 稿件本身（<section>/<name>.md）② raw/<日期>/ 下的数据与证据文件
    （含 MANIFEST.sha256）。其余任何路径（scripts/、docs/（含路线图）、review/、approvals/、state/、.github/、
    lexicon、模板 layouts/、配置、tests/、根目录文件…）都返回在列表里，路由给 E-ROUTE-PR-SCOPE；这些改动单独走 PR。"""
    ds = set(drafts)
    return sorted(p for p in allp if p not in ds and not PR_DATA_RE.fullmatch(p))


def _blob(repo, head, rel):
    r = _git(repo, "show", f"{head}:{rel}", text=False)
    return r.stdout if r.returncode == 0 else None


def _checkout_tree(repo, head):
    """把 head 提交的完整树导出到临时目录（raw/ 与 MANIFEST 从这里读，不读工作树）。"""
    import subprocess, tempfile, io, tarfile
    d = tempfile.mkdtemp(prefix="route-head-")
    r = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", head], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("E-ROUTE-PR-FILES: git archive failed")
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as t:
        try:
            t.extractall(d, filter="data")
        except TypeError:                     # 旧版 Python 无 filter 参数
            t.extractall(d)
    return d


def pair_of(paths):
    """一个 PR 的稿件文件清单 → [(path, pair_path|None)] 或错误码。只允许：单个 <name>.md；
    或同一 section、同一 name 的 <name>.md + <name>.en.md 两个文件（t145u）。其余组合一律报错。"""
    ps = [PurePosixPath(str(p)) for p in paths]
    if len(ps) == 1:
        return "E-ROUTE-PAIR-MISSING" if ps[0].name.endswith(".en.md") else [(paths[0], None)]
    if len(ps) != 2:
        return "E-ROUTE-PR-FILES"
    zh = [i for i, p in enumerate(ps) if not p.name.endswith(".en.md")]
    en = [i for i, p in enumerate(ps) if p.name.endswith(".en.md")]
    if len(zh) != 1 or len(en) != 1:
        return "E-ROUTE-PR-FILES"
    z, e = ps[zh[0]], ps[en[0]]
    if z.parent != e.parent or e.name[:-len(".en.md")] + ".md" != z.name:
        return "E-ROUTE-PR-FILES"                      # section 或 name 不同
    return [(paths[zh[0]], paths[en[0]]), (paths[en[0]], paths[zh[0]])]


VALIDITY = dt.timedelta(seconds=60)   # r6（协调方 Grok Bot 定）：可发布结论的有效期；生产 bot 须在 valid_until 前发布


def still_valid(decision, now=None):
    """生产 bot 发布前调用：结论 publishable 且当前真实时间早于 valid_until 才返回 True；否则须重新路由。
    还须另用 `gh pr merge --match-head-commit <head_sha>`（或等价的 head 比对）确认 PR head 与状态未变。"""
    if not getattr(decision, "publishable", False):
        return False
    vu = getattr(decision, "valid_until", None)
    try:
        vu = dt.datetime.fromisoformat(vu)
    except (TypeError, ValueError):
        return False
    now = _real_now() if now is None else now
    return now < vu


def _crosses_boundary(start, end):
    """start < 边界 <= end 时为 True。边界：每个 SGT 日的 06:55、07:00 与午夜。end 早于 start（时钟回拨）也算跨越。"""
    if end < start:
        return True
    a, b = start.astimezone(SGT), end.astimezone(SGT)
    day = a.date()
    while day <= b.date():
        for hh, mm in ((0, 0), (6, 55), (7, 0)):
            t = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=SGT)
            if a < t <= b:
                return True
        day += dt.timedelta(days=1)
    return False


def _real_now():
    return dt.datetime.now(dt.timezone.utc)


def _http_probe(url, timeout=10):
    """(ok, reason)。reason：None / "http <状态码>" / "network: <异常类型>"。HEAD 不行再 GET。"""
    import urllib.request, urllib.error
    last = "network: unknown"
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": "markjin-route/1"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status < 400:
                    return True, None
                last = f"http {r.status}"
        except urllib.error.HTTPError as e:
            last = f"http {e.code}"
        except Exception as e:   # noqa: BLE001 —— URLError、超时、DNS 等都算网络问题
            last = f"network: {type(e).__name__}"
    return False, last


class _LinkProbe:
    """整体验收 r1 HIGH 2（王总定，做法一）：route_pr 一律检查链接，不能关闭。
    网络问题（异常、超时、DNS）重试一次，仍不通记下原因；HTTP 错误码不重试。"""
    RETRY_SLEEP = 2.0

    def __init__(self, cache=None):
        self.failures = {}
        self.cache = {} if cache is None else cache       # 同一次 route_pr 内复用：第二遍按结束时间重算时不再联网

    def _once(self, url):
        try:
            return _http_probe(url)
        except Exception as e:   # noqa: BLE001
            return False, f"network: {type(e).__name__}"

    def __call__(self, url):
        import time
        if url in self.cache:
            ok, why = self.cache[url]
            if not ok:
                self.failures[url] = why
            return ok
        ok, why = self._once(url)
        if not ok and why and why.startswith("network"):
            time.sleep(self.RETRY_SLEEP)
            ok, why2 = self._once(url)
            why = None if ok else f"{why2}（已重试一次）"
        self.cache[url] = (ok, why)
        if not ok:
            self.failures[url] = why
        return ok


def route_pr(repo, pr_number, date, card_type, *, site_repo=None):
    """唯一发布入口。整体验收 r2（王总定）：公开签名不收 now 与 link_checker——时间只用真实时钟，链接只用内置检查。"""
    require_yaml()   # r10：缺 PyYAML 时在任何 git/gh 操作之前给出 E-DEP-PYYAML（RuntimeError 子类）
    return _route_pr(repo, pr_number, date, card_type, _real_now(), site_repo=site_repo, publish=True)


def dry_run(repo, pr_number, date, card_type, now, site_repo=None):
    """CLI --dry-run 用：可指定时间做演练，结果永远 publishable=False。"""
    require_yaml()
    return _route_pr(repo, pr_number, date, card_type, now, site_repo=site_repo, publish=False)


def _route_pr(repo, pr_number, date, card_type, now, site_repo=None, publish=False):
    """按 PR 路由（唯一发布入口，r13）。只接受 PR 编号：base/head/文件列表由 gh pr view 取得，
    head 必须是 PR 当前 head 且本地已有该提交；gh 文件列表须与 git diff base...head 完全一致；
    删除、改名一律失败；稿件、raw/、MANIFEST 都从 head 提交读取；批准记录只从 origin/main 读取。
    返回 {path: (selfcheck, Decision)}；失败抛 ValueError/RuntimeError（CLI 输出 HOLD）。"""
    import shutil
    if not (isinstance(now, dt.datetime) and now.tzinfo is not None):
        raise ValueError("E-ROUTE-INPUT: now must be timezone-aware")
    if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number <= 0:
        raise ValueError("E-ROUTE-PR-FILES: PR number required")
    meta = _gh_pr(repo, pr_number)
    base, head = meta.get("baseRefOid"), meta.get("headRefOid")
    if meta.get("state") != "OPEN" or not (isinstance(base, str) and re.fullmatch(r"[0-9a-f]{40}", base)
                                             and isinstance(head, str) and re.fullmatch(r"[0-9a-f]{40}", head)):
        raise ValueError("E-ROUTE-PR-FILES: PR not open or bad base/head")
    if _git(repo, "cat-file", "-e", head + "^{commit}").returncode != 0 or \
            _git(repo, "cat-file", "-e", base + "^{commit}").returncode != 0:
        raise RuntimeError("E-ROUTE-PR-FILES: PR base/head commit not available locally (fetch first)")
    if APPROVALS_REF == "origin/main":                   # r14（r13 H-3）：本地 origin/main 必须等于远端当前 main
        rem = _git(repo, "ls-remote", "origin", "refs/heads/main")
        loc = _git(repo, "rev-parse", "origin/main")
        rs = rem.stdout.split()[0] if rem.returncode == 0 and rem.stdout.split() else None
        if rs is None or loc.returncode != 0 or loc.stdout.strip() != rs:
            raise RuntimeError("E-ROUTE-STATE: local origin/main differs from remote main (git fetch first)")
    paths, allp = pr_draft_files(repo, base, head)
    gh_files = sorted(f.get("path") for f in meta.get("files") or [] if isinstance(f, dict))
    if gh_files != allp:
        raise ValueError("E-ROUTE-PR-FILES: gh file list differs from git diff base...head")
    if not paths:
        raise ValueError("E-ROUTE-PR-FILES: no draft files in PR")
    extra = pr_scope_violations(paths, allp)
    if extra:
        # r7 BLOCKER 1（B4）：稿件 PR 只能改稿件本身与白名单数据/证据文件；碰到规则、代码、路线图、模板、配置 → 不可发布
        return {p: (None, _hold("E-ROUTE-PR-SCOPE")) for p in paths}
    plan = pair_of(paths)
    if isinstance(plan, str):
        return {p: (None, _hold(plan)) for p in paths}
    cache = {}

    def _pass(at):
        tree = _checkout_tree(repo, head)
        try:
            blobs = {p: _blob(repo, head, p) for p in paths}

            def _run(force):
                res = {}
                for p, q in plan:
                    if blobs[p] is None or (q is not None and blobs[q] is None):
                        res[p] = (None, _hold("E-SELFCHECK-READ")); continue
                    pair = hashlib.sha256(blobs[q]).hexdigest() if q is not None else None
                    probe = _LinkProbe(cache)        # 不能关闭，也不能注入：只用内置 HTTP 检查（测试里 monkeypatch _http_probe）
                    sc, d = _route_one(p, blobs[p], tree, date, card_type, at, link_checker=probe, pair=pair,
                                       records_repo=repo, site_repo=site_repo, force_wang=force)
                    if sc is not None and d.state not in ("REJECTED", "ARCHIVED") and \
                            (sc["flags"].get("link_unreachable") or sc["flags"].get("link_unchecked")):
                        code = "E-ROUTE-LINK-UNREACHABLE" if sc["flags"].get("link_unreachable") else "E-ROUTE-LINK-UNCHECKED"
                        why = "; ".join(f"{u} → {r}" for u, r in probe.failures.items()) or "来源链接未检查"
                        d = Decision("HOLD", [code], detail=why)
                    res[p] = (sc, d)
                return res

            res = _run(False)
            # 整体验收 r8 BLOCKER 2（王总定，从严）：中英配对稿取两版审批类型的并集——只要有一版需要王总批准，
            # 两版都按需王总批准重判，各自都必须有绑定自身 content_sha256 的王总记录（不接受一条记录覆盖两版）。
            if any(q is not None for _, q in plan) and any(getattr(d, "wang_required", False) for _, d in res.values()):
                res = _run(True)
            return res
        finally:
            shutil.rmtree(tree, ignore_errors=True)

    def _same_pr(tag):
        m = _gh_pr(repo, pr_number)                       # r14（r13 H-2）：PR head/base 必须未变，且仍是 OPEN
        if m.get("headRefOid") != head or m.get("baseRefOid") != base:
            raise RuntimeError(f"E-ROUTE-PR-FILES: PR head changed during routing ({tag})")
        if m.get("state") != "OPEN":
            raise RuntimeError(f"E-ROUTE-PR-FILES: PR no longer open ({tag})")

    def _verdicts(o):
        return {k: (v[1].state, list(v[1].codes)) for k, v in o.items()}

    out = _pass(now)
    _same_pr("after first pass")
    decided_at = now
    if publish:
        # 整体验收 r4–r6 + r7 协调方决定：
        # 1) 第二遍：用结束时的真实时间 end 重算全部判定（链接复用第一遍结果，不再联网）；两遍结论（state、codes）不同、
        #    或开始到 end 之间跨过 06:55 / 07:00 / SGT 午夜 → 整批 E-ROUTE-RETRY（06:55 前开始的路由按原规则处理）。
        # 2) decided_at = end：判定时间就是第二遍所用的时间点，先记下；
        # 3) 之后才做外部核对：PR（OPEN、base/head 未变）与远端 main；有任何变化 → 整批 HOLD（E-ROUTE-PR-FILES / E-ROUTE-RETRY）。
        #    因此所有外部核对都在 decided_at 之后，核对之后到实际发布的空档全部落在 68A（FOLLOW-UP）范围内。
        # 4) 结论只在 VALIDITY（60 秒）内有效；生产 bot 须在 valid_until 前发布，发布前用 --match-head-commit 再确认。
        #    不再做“end + 120 秒”的第三遍（r7 协调方定：有效期与发布前确认已覆盖该风险）。
        end = _real_now()
        later = _pass(end)
        decided_at = end
        if _verdicts(out) != _verdicts(later):
            raise RuntimeError("E-ROUTE-RETRY: decision changed between start and end of routing; rerun")
        if _crosses_boundary(now, end):
            raise RuntimeError("E-ROUTE-RETRY: routing crossed a time boundary (06:55 / 07:00 / SGT midnight); rerun")
        _same_pr("after decided_at")
        if APPROVALS_REF == "origin/main":
            rem2 = _git(repo, "ls-remote", "origin", "refs/heads/main")
            if not (rem2.returncode == 0 and rem2.stdout.split() and rem2.stdout.split()[0] == rs):
                raise RuntimeError("E-ROUTE-RETRY: remote main changed during routing; fetch and rerun")
        out = later                                        # 状态变更按第二遍（end）生成
    else:
        for _, (sc, d) in out.items():
            d.state_change = None                          # 整体验收 r4：演练（Python 与 CLI 一致）不输出可写回的状态变更
    for p, (sc, d) in out.items():
        d.codes = list(d.codes)
        setattr(d, "head_sha", head)
        setattr(d, "decided_at", decided_at.astimezone(SGT).isoformat())        # r6：判定时间
        setattr(d, "valid_until", (decided_at + VALIDITY).astimezone(SGT).isoformat())
        # r17（王总定）：发布入口只有 route_pr。publishable 只在这里设置，且只针对本函数自己从 gh/git 取得的稿件。
        d.publishable = publish and d.state == "APPROVED"   # dry-run 永远不判 publishable
    if len(out) == 2 and not all(d.publishable for _, d in out.values()):
        for p, (sc, d) in out.items():
            if d.publishable:
                h = _hold("E-ROUTE-PAIR-INCOMPLETE")
                for k in ("head_sha", "decided_at", "valid_until"):   # r6 FOLLOW-UP：保留诊断元数据
                    setattr(h, k, getattr(d, k, None))
                out[p] = (sc, h)
    return out
