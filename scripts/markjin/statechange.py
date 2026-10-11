"""发布状态写回接口（协调决定 2026-10-10）。

门禁（route）本身不写任何文件，只在输出里给出状态变更（state_change）；由生产 bot 用本模块 / scripts/state-change.py
把变更应用到 state/publish-state.json 并提交。Mac 心跳也走同一接口。格式见 docs/approvals.md「状态写回接口」。

变更对象（恰好这些键）：
  draft     {"schema": "markjin.state-change/v1", "kind": "draft", "draft_id", "date", "content_sha256",
             "status": "archived"|"deferred", "reason", "at"}
  heartbeat {"schema": "markjin.state-change/v1", "kind": "heartbeat", "mac_online": bool, "updated_at"}
应用规则：
  - draft：只改 drafts[draft_id]（写入 status/reason/at/date/content_sha256 五个键）；已归档的条目不可再改（归档不可逆）；
    deferred 只能写一次（只顺延一次）；archived 的 reason 必须是 A-*，deferred 的 reason 必须是 I-DEFERRED。
  - heartbeat：只改 updated_at 与 mac_online 两个字段；updated_at 不得早于文件中现有值。
  - 其余字段（version、wang_present、codex_in_production、其他 drafts）一律不动。
"""
import copy
import datetime as dt
import json
import re

SCHEMA = "markjin.state-change/v1"
DRAFT_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ARCHIVE_CODES = {"A-MAC-OFFLINE", "A-NOT-APPROVED", "A-NO-REVIEW-PATH", "A-OVERDUE-TWICE"}
DRAFT_KEYS = {"schema", "kind", "draft_id", "date", "content_sha256", "status", "reason", "at"}
HB_KEYS = {"schema", "kind", "mac_online", "updated_at"}


class StateChangeError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _ts(s):
    if not isinstance(s, str):
        return None
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo else None


def _date(s):
    if not isinstance(s, str) or not DATE_RE.match(s):
        return False
    try:
        dt.date.fromisoformat(s)
    except ValueError:
        return False
    return True


def draft_change(draft, status, reason, now):
    return {"schema": SCHEMA, "kind": "draft", "draft_id": draft["draft_id"], "date": draft["date"],
            "content_sha256": draft["content_sha256"], "status": status, "reason": reason, "at": now.isoformat()}


def heartbeat(mac_online, now):
    return {"schema": SCHEMA, "kind": "heartbeat", "mac_online": mac_online, "updated_at": now.isoformat()}


def validate_change(c):
    if not isinstance(c, dict) or c.get("schema") != SCHEMA:
        raise StateChangeError("E-STATE-CHANGE-INVALID")
    if c.get("kind") == "heartbeat":
        if set(c) != HB_KEYS or type(c["mac_online"]) is not bool or _ts(c["updated_at"]) is None:
            raise StateChangeError("E-STATE-CHANGE-INVALID")
    elif c.get("kind") == "draft":
        ok = (set(c) == DRAFT_KEYS and isinstance(c["draft_id"], str) and DRAFT_ID_RE.match(c["draft_id"])
              and _date(c["date"]) and isinstance(c["content_sha256"], str) and SHA256_RE.match(c["content_sha256"])
              and _ts(c["at"]) is not None
              and ((c["status"] == "archived" and c["reason"] in ARCHIVE_CODES)
                   or (c["status"] == "deferred" and c["reason"] == "I-DEFERRED")))
        if not ok:
            raise StateChangeError("E-STATE-CHANGE-INVALID")
    else:
        raise StateChangeError("E-STATE-CHANGE-INVALID")
    return c


def apply_change(state, change):
    """返回新的状态对象（不修改入参）。违反规则 → StateChangeError。"""
    validate_change(change)
    if not isinstance(state, dict) or not isinstance(state.get("drafts"), dict):
        raise StateChangeError("E-ROUTE-STATE")
    from .route import validate_state
    if validate_state(state, dt.datetime.max.replace(tzinfo=dt.timezone.utc)) is None:
        raise StateChangeError("E-ROUTE-STATE")          # 旧状态不合规：不得借写回接口悄悄修复
    new = copy.deepcopy(state)
    if change["kind"] == "heartbeat":
        old = _ts(state.get("updated_at"))
        if old is not None and _ts(change["updated_at"]) < old:
            raise StateChangeError("E-STATE-CHANGE-STALE")
        new["updated_at"] = change["updated_at"]
        new["mac_online"] = change["mac_online"]
        return new
    cur = state["drafts"].get(change["draft_id"])
    if cur and cur.get("status") == "archived":
        raise StateChangeError("E-ROUTE-ARCHIVED-REUSE")
    if cur and change["status"] == "deferred":
        raise StateChangeError("E-STATE-CHANGE-INVALID")   # 只顺延一次
    new["drafts"][change["draft_id"]] = {"status": change["status"], "reason": change["reason"],
                                         "at": change["at"], "date": change["date"],
                                         "content_sha256": change["content_sha256"]}
    return new


def dumps(state):
    return json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def loads_strict(text):
    """整体验收 r9 MEDIUM：状态文件与变更 JSON 严格解析——重复键 → StateChangeError("E-STATE-CHANGE-INVALID")，
    不让后一个值静默覆盖前一个（与 approvals.loads_strict 同口径）。"""
    import json as _json

    def hook(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise StateChangeError("E-STATE-CHANGE-INVALID")
            d[k] = v
        return d
    return _json.loads(text, object_pairs_hook=hook)
