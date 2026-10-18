"""分支台账 ledger/branches.csv 的格式与规则校验（只用标准库）。

字段与规则照站点路线图第六节“分支台账”、第十三节 13.1，以及协调 bot 2026-10-12 的决定（见 ledger/README.md）。
只校验格式与登记、对账规则，不判 HIT/MISS，不读取内核。
"""
import csv, io, re, subprocess
from datetime import date
from decimal import Decimal, InvalidOperation

LEDGER_PATH = "ledger/branches.csv"

HEADER = [
    "row_id", "corrects_row_id", "reason",
    "draft_id", "classification_id", "slug", "publish_date", "domain", "framework_version", "framework_sha256",
    "framework_commit", "observed_variable", "unit", "data_source", "data_vintage", "window_start", "window_end",
    "branch_order", "interval_low", "interval_low_closed", "interval_high", "interval_high_closed",
    "trigger_condition", "n_quarters", "lu_basis_date", "registered_by", "registered_at",
    "actual_value", "actual_branch", "check_result", "error_source", "window_quarters",
    "quarter_readings", "l_value", "u_value", "lu_evidence", "checked_by", "checked_at", "evidence",
]
DOMAINS = {"macro", "ai", "energy", "space", "bio", "other"}
# 不可改字段：事先登记字段 + registered_at。对账行、结论更正行必须与“当前登记”完全一致；
# 只有观测开始前的登记更正行可以改（registered_at 写更正行自己的时间）。
FROZEN = [
    "draft_id", "classification_id", "slug", "publish_date", "domain", "framework_version", "framework_sha256",
    "framework_commit", "observed_variable", "unit", "data_source", "data_vintage", "window_start", "window_end",
    "branch_order", "interval_low", "interval_low_closed", "interval_high", "interval_high_closed",
    "trigger_condition", "n_quarters", "window_quarters", "lu_basis_date", "l_value", "u_value",
    "lu_evidence", "registered_by", "registered_at",
]
PRE_REGISTERED = FROZEN  # 兼容旧名
INTERVAL = ["interval_low", "interval_low_closed", "interval_high", "interval_high_closed"]
QUARTERLY = ["n_quarters", "window_quarters", "lu_basis_date", "l_value", "u_value", "lu_evidence"]
CHECK_RESULTS = {"VOID", "VOID_REVOKED", "PENDING", "HIT", "MISS", "NONE_HIT", "MULTI_HIT", "TRIGGER_UNOBSERVABLE", "DATA_UNAVAILABLE"}
FINAL = {"HIT", "MISS", "NONE_HIT", "MULTI_HIT", "TRIGGER_UNOBSERVABLE"}
WRONG = {"NONE_HIT", "MULTI_HIT", "TRIGGER_UNOBSERVABLE"}
ERROR_SOURCES = {"采集", "解读", "框架"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
VER_RE = re.compile(r"^v\d+\.\d+$")
TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T([01]\d|2[0-3]):[0-5]\d:[0-5]\d\+08:00$")
Q_RE = re.compile(r"^(\d{4})Q([1-4])$")
NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
CID_RE = re.compile(r"^c[1-9]\d{0,2}$")  # classification_id：c1、c2…，同一稿件内每个完成分类的条目一个
# raw 路径：raw/YYYY-MM-DD/<相对路径>，段内只允许常规字符，禁止 . 与 .. 段
RAW_RE = re.compile(r"^raw/(\d{4}-\d{2}-\d{2})/((?:[A-Za-z0-9_\-][A-Za-z0-9._\-]*/)*[A-Za-z0-9_\-][A-Za-z0-9._\-]*)$")
# 读数绑定：季度:读数@vintage#raw 路径:sha256；lu_evidence 另加 |来源链接
READING_RE = re.compile(r"^(\d{4}Q[1-4]):(-?\d+(?:\.\d+)?)@(\d{4}-\d{2}-\d{2})#([^:|;]+):([0-9a-f]{64})$")
LU_RE = re.compile(r"^(\d{4}Q[1-4]):(-?\d+(?:\.\d+)?)@(\d{4}-\d{2}-\d{2})#([^:|;]+):([0-9a-f]{64})\|(https?://[^\s;|]+)$")
# evidence：raw 路径:sha256[,raw 路径:sha256…]|scripts/路径@40 位 commit|取值时间
EVIDENCE_RE = re.compile(r"^([^|]+)\|(scripts/[A-Za-z0-9._/\-]+)@([0-9a-f]{40})\|(\S+)$")


# 自由文本字段：不得出现绝对路径、file: URI、内部目录名。先去掉 http(s) 网址再查。
FREE_TEXT = ["slug", "reason", "observed_variable", "unit", "data_source", "data_vintage", "trigger_condition",
             "registered_by", "checked_by", "actual_value"]
# 网址按明确边界剔除：只吃 URL 合法字符，遇到 | , ; 引号 括号 空白 中文 即止（https://x.org|/opt/x 里的路径仍要检出）
URL_RE = re.compile(r"(?i)https?://[A-Za-z0-9\-._~:/?#@!$&*+=%]+")
# 绝对路径：斜杠后必须跟 ASCII 字母、下划线、点或 ~（/年、bp /月、x /5 不算）；斜杠前不能是字母数字（km/s、SRC:GDP/CPI 不算），
# 冒号后直接跟的绝对路径（a:/opt/x）要算
ABS_RE = re.compile(r"(?:(?<![\w.~%/-])|(?<=:))/[A-Za-z_.~][\w.~-]*")
# 斜杠前是中文（如「见/opt/private/x」）：后面是 ASCII 路径词并且还有下一段，才算路径（「亿元/年」「人/km2」不算）
ROOT_NAMES = "opt|home|workspace|Users|var|etc|tmp|root|private|mnt|srv|usr|Volumes|Library"
# 中文紧贴「/名单里的根目录」，后面是结尾、空白、标点、中文或下一段：算路径（见/opt、见/Users）
CJK_ROOT_RE = re.compile(r"(?<=[\u3000-\u9fff\uff00-\uffef])/(?:" + ROOT_NAMES + r")(?![A-Za-z0-9_.~-])")
CJK_PATH_RE = re.compile(r"(?<=[\u3000-\u9fff\uff00-\uffef])/[A-Za-z_.~][A-Za-z0-9_.~-]*/")
# unit：只要出现「斜杠 + ASCII 词 + 斜杠」就算路径（如 /data/private/report）
UNIT_PATH_RE = re.compile(r"/[A-Za-z_.~][A-Za-z0-9_.~-]*/")
COMMON_RE = re.compile(r"(?i)file:|\\\\|\b[a-z]:[\\/]|markjin-internal|markjin-core|topics-private|(?<![\w])~/")
# unit 放宽：只认已知的本机根目录
ROOTS_RE = re.compile(r"(?:(?<![\w.~%/-])|(?<=:))/(?:" + ROOT_NAMES + r")(?![A-Za-z0-9_.~-])")


def private_text(field, v):
    v = URL_RE.sub(" ", v)
    if COMMON_RE.search(v):
        return True
    if CJK_PATH_RE.search(v) or CJK_ROOT_RE.search(v):
        return True
    if field == "unit":
        return bool(ROOTS_RE.search(v) or UNIT_PATH_RE.search(v))
    return bool(ABS_RE.search(v))


def blank(v):
    return v in ("", "NA")


def expected_row_id(draft_id, classification_id, branch_order, seq):
    """row_id 生成规则：<draft_id>-<classification_id>-b<branch_order>-r<seq>，
    seq 为同一分支（draft_id + classification_id + branch_order）在文件中的第几行（从 1 起）。"""
    return f"{draft_id}-{classification_id}-b{branch_order}-r{seq}"


def branch_key(row):
    return (row["draft_id"], row["classification_id"], row["branch_order"])


def group_key(row):
    """判定分组：同一稿件中同一个完成分类的条目。HIT 与互斥判定在组内进行。"""
    return (row["draft_id"], row["classification_id"])


def _date(s):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _ts(s):
    """完整 SGT 时间戳 → 可比较的字符串（同一时区，按字典序即时间序）；非法返回 None。"""
    m = TS_RE.match(s or "")
    return s if m and _date(m.group(1)) else None


def _quarters(s):
    out = []
    for part in (s or "").split(";"):
        m = Q_RE.match(part)
        if not m:
            return None
        out.append((int(m.group(1)), int(m.group(2))))
    return out


def _q_end(y, q):
    return date(y, q * 3, {3: 31, 6: 30, 9: 30, 12: 31}[q * 3])


def _consecutive(qs):
    return all((b[0] * 4 + b[1]) - (a[0] * 4 + a[1]) == 1 for a, b in zip(qs, qs[1:]))


def _raw_ok(path, sha, manifest):
    m = RAW_RE.match(path)
    if not m or _date(m.group(1)) is None:
        return "FORMAT"
    if manifest is not None and manifest(path) != sha:
        return "MANIFEST"
    return None


def fmt_bound(v):
    return v if NUM_RE.match(v) else None


def canonical_trigger(row):
    """区间型分支 trigger_condition 的机器写法：L <(=) x <(=) U / x <(=) U / L <(=) x。至少一端有限。"""
    lo, hi = row["interval_low"], row["interval_high"]
    parts = []
    if lo:
        parts.append(f"{lo} {'<=' if row['interval_low_closed'] == 'true' else '<'} ")
    parts.append("x")
    if hi:
        parts.append(f" {'<=' if row['interval_high_closed'] == 'true' else '<'} {hi}")
    return "".join(parts) if (lo or hi) else None


def D(v):
    """数值一律用 Decimal 比较，避免浮点舍入。"""
    try:
        return Decimal(v)
    except (InvalidOperation, TypeError):
        return None


def in_interval(row, v):
    v = D(v) if not isinstance(v, Decimal) else v
    lo, hi = row["interval_low"], row["interval_high"]
    if lo and (v < D(lo) or (v == D(lo) and row["interval_low_closed"] != "true")):
        return False
    if hi and (v > D(hi) or (v == D(hi) and row["interval_high_closed"] != "true")):
        return False
    return True


def is_quarterly(row):
    return not blank(row["n_quarters"])


def is_interval(row):
    return not is_quarterly(row) and not all(row[f] == "NA" for f in INTERVAL)


def check_row(row, manifest=None):
    """单行规则（不看其他行）。manifest(path)->sha256 或 None，用于核对 raw 绑定；None 表示不核对 MANIFEST。"""
    e = []
    # 所有行都要过的检查（按季行、作废行也不例外）
    for f in FREE_TEXT:
        if private_text(f, row[f]):
            e.append(f"E-BR-PRIVATE-TEXT:{f}")
    if bool(row["corrects_row_id"]) != bool(row["reason"].strip()):
        e.append("E-BR-CORRECTION-REASON")
    if row["check_result"] in ("VOID", "VOID_REVOKED"):
        # 作废行 / 撤销作废行：只追加，reason 必填，不填任何对账字段
        if not row["corrects_row_id"] and "E-BR-CORRECTION-REASON" not in e:
            e.append("E-BR-CORRECTION-REASON")
        if any(not blank(row[f]) for f in ("actual_value", "actual_branch", "error_source", "evidence", "quarter_readings",
                                           "checked_by", "checked_at")):
            e.append("E-BR-VOID-FILLED")
        return e
    for f in ("draft_id", "classification_id", "slug", "domain", "framework_version", "framework_sha256", "framework_commit",
              "observed_variable", "unit", "data_source", "data_vintage", "trigger_condition",
              "registered_by", "registered_at"):
        if not row[f].strip():
            e.append(f"E-BR-EMPTY:{f}")
    if row["draft_id"] and not ID_RE.match(row["draft_id"]):
        e.append("E-BR-DRAFT-ID")
    if row["classification_id"] and not CID_RE.match(row["classification_id"]):
        e.append("E-BR-CLASSIFICATION-ID")
    if row["domain"] and row["domain"] not in DOMAINS:
        e.append("E-BR-DOMAIN")
    if row["framework_sha256"] and not SHA_RE.match(row["framework_sha256"]):
        e.append("E-BR-SHA256")
    if row["framework_commit"] and not COMMIT_RE.match(row["framework_commit"]):
        e.append("E-BR-COMMIT")
    if row["framework_version"] and not VER_RE.match(row["framework_version"]):
        e.append("E-BR-VERSION")
    for f in ("publish_date", "window_start", "window_end"):
        if _date(row[f]) is None:
            e.append(f"E-BR-DATE:{f}")
    pd, ws, we = _date(row["publish_date"]), _date(row["window_start"]), _date(row["window_end"])
    if ws and we and ws > we:
        e.append("E-BR-WINDOW")
    # 观测开始 = window_start 当日 00:00（SGT）；规定 window_start 至少是发布次日
    if pd and ws and ws <= pd:
        e.append("E-BR-WINDOW-START")
    reg = _ts(row["registered_at"])
    if row["registered_at"] and not reg:
        e.append("E-BR-TS:registered_at")
    elif reg and ws and date.fromisoformat(reg[:10]) >= ws:
        e.append("E-BR-REGISTERED-AFTER-START")
    if not re.fullmatch(r"[1-9]\d*", row["branch_order"]):
        e.append("E-BR-ORDER")
    cr = row["check_result"]
    if cr not in CHECK_RESULTS:
        e.append("E-BR-CHECK-RESULT")
    chk = _ts(row["checked_at"]) if row["checked_at"] else None
    if row["checked_at"] and not chk:
        e.append("E-BR-TS:checked_at")
    if is_quarterly(row):
        if not re.fullmatch(r"[1-9]\d*", row["n_quarters"]):
            e.append("E-BR-N")  # N ≥ 1
        if any(row[f] != "NA" for f in INTERVAL):
            e.append("E-BR-INTERVAL-NA")
        lb = _date(row["lu_basis_date"])
        if lb is None:
            e.append("E-BR-DATE:lu_basis_date")
        elif reg and lb > date.fromisoformat(reg[:10]):
            e.append("E-BR-LU-BASIS-FUTURE")
        lv, uv = row["l_value"], row["u_value"]
        if not (NUM_RE.match(lv) and NUM_RE.match(uv)):
            e.append("E-BR-LU")
        elif D(lv) > D(uv):
            e.append("E-BR-L-GT-U")  # L ≤ U
        if blank(row["lu_evidence"].strip()):
            e.append("E-BR-LU-EVIDENCE")
        else:
            for x in row["lu_evidence"].split(";"):
                m = LU_RE.match(x)
                if not m or _date(m.group(3)) is None:
                    e.append("E-BR-LU-EVIDENCE-FORMAT"); break
                if reg and date.fromisoformat(m.group(3)) > date.fromisoformat(reg[:10]):
                    e.append("E-BR-LU-VINTAGE-FUTURE"); break
                bad = _raw_ok(m.group(4), m.group(5), manifest)
                if bad:
                    e.append(f"E-BR-LU-RAW-{bad}"); break
        qs = _quarters(row["window_quarters"])
        if qs is None:
            e.append("E-BR-WQ")
        else:
            if re.fullmatch(r"[1-9]\d*", row["n_quarters"]) and len(qs) != int(row["n_quarters"]):
                e.append("E-BR-WQ-COUNT")
            if not _consecutive(qs):
                e.append("E-BR-WQ-GAP")
            if we and (qs[-1][0], qs[-1][1]) > (we.year, (we.month - 1) // 3 + 1):
                e.append("E-BR-WQ-AFTER-END")
        if not blank(row["quarter_readings"]):
            items = row["quarter_readings"].split(";")
            for x in items:
                m = READING_RE.match(x)
                if not m or _date(m.group(3)) is None:
                    e.append("E-BR-READINGS-FORMAT"); break
                y, q = int(m.group(1)[:4]), int(m.group(1)[5])
                v = date.fromisoformat(m.group(3))
                if v <= _q_end(y, q):
                    e.append("E-BR-READING-VINTAGE-EARLY"); break  # vintage 不早于该季度结束（须在季末之后发布）
                if not chk or v > date.fromisoformat(chk[:10]):
                    e.append("E-BR-READING-VINTAGE-LATE"); break   # 不晚于本行写入时间（checked_at）
                bad = _raw_ok(m.group(4), m.group(5), manifest)
                if bad:
                    e.append(f"E-BR-READING-RAW-{bad}"); break
            else:
                if qs:
                    wq = [f"{y}Q{q}" for y, q in qs]
                    got = [x.split(":")[0] for x in items]
                    if got != wq[:len(got)]:
                        e.append("E-BR-READINGS-QUARTERS")  # 必须从第一个季度起按顺序
        # 王总确认判定规则前：只允许 PENDING（路线图第六节“按季读数判定的分支”）
        if cr != "PENDING":
            e.append("E-BR-QUARTERLY-RESULT")
        if row["error_source"]:
            e.append("E-BR-QUARTERLY-ERROR-SOURCE")
        for f in ("actual_value", "actual_branch", "evidence"):
            if not blank(row[f]):
                e.append("E-BR-PENDING-FILLED")
        if not blank(row["quarter_readings"]) and not (row["checked_by"] and chk):
            e.append("E-BR-CHECKED")  # 读数行须记写入人和写入时间
        if blank(row["quarter_readings"]) and (row["checked_by"] or row["checked_at"]):
            e.append("E-BR-PENDING-FILLED")
        return e
    # —— 非按季分支 ——
    for f in QUARTERLY[1:] + ["quarter_readings"]:
        if not blank(row[f]):
            e.append(f"E-BR-QUARTERLY-ONLY:{f}")
    if is_interval(row):
        for f in ("interval_low", "interval_high"):
            if row[f] and not NUM_RE.match(row[f]):
                e.append(f"E-BR-INTERVAL:{f}")
        for f in ("interval_low_closed", "interval_high_closed"):
            if row[f] not in ("true", "false"):
                e.append(f"E-BR-INTERVAL:{f}")
        if NUM_RE.match(row["interval_low"]) and NUM_RE.match(row["interval_high"]) \
                and D(row["interval_low"]) > D(row["interval_high"]):
            e.append("E-BR-INTERVAL-ORDER")
        if not any(c.startswith("E-BR-INTERVAL") for c in e):
            canon = canonical_trigger(row)
            if canon is None or " ".join(row["trigger_condition"].split()) != canon:
                e.append("E-BR-TRIGGER-MISMATCH")
    if cr == "PENDING":
        if any(not blank(row[f]) for f in ("actual_value", "actual_branch", "error_source", "checked_by",
                                            "checked_at", "evidence")):
            e.append("E-BR-PENDING-FILLED")
    elif cr in CHECK_RESULTS:
        if not (row["checked_by"] and chk):
            e.append("E-BR-CHECKED")
        elif we and date.fromisoformat(chk[:10]) <= we:
            e.append("E-BR-CHECKED-BEFORE-END")  # checked_at 必须晚于 window_end
        if cr in ("HIT", "MISS", "NONE_HIT", "MULTI_HIT"):
            if is_interval(row) and not NUM_RE.match(row["actual_value"]):
                e.append("E-BR-ACTUAL-VALUE")
            elif is_interval(row) and not any(c.startswith("E-BR-INTERVAL") for c in e):
                inside = in_interval(row, D(row["actual_value"]))
                if inside != (cr in ("HIT", "MULTI_HIT")) or inside != (row["actual_branch"] == "是"):
                    e.append("E-BR-ACTUAL-MISMATCH")  # 按开闭端点算出的归属与 check_result / actual_branch 不符
            elif not row["actual_value"].strip():
                e.append("E-BR-ACTUAL-VALUE")
        if cr != "DATA_UNAVAILABLE" or not blank(row["evidence"]):
            m = EVIDENCE_RE.match(row["evidence"])
            if not m or not _ts(m.group(4)):
                e.append("E-BR-EVIDENCE")
            else:
                for pair in m.group(1).split(","):
                    p, _, sha = pair.rpartition(":")
                    bad = "FORMAT" if not SHA_RE.match(sha) else _raw_ok(p, sha, manifest)
                    if bad:
                        e.append(f"E-BR-EVIDENCE-RAW-{bad}"); break
    if row["actual_branch"] not in ("", "是", "否"):
        e.append("E-BR-ACTUAL-BRANCH")
    if cr == "HIT" and row["actual_branch"] != "是" or cr in ("MISS", "NONE_HIT") and row["actual_branch"] != "否" \
            or cr in ("TRIGGER_UNOBSERVABLE", "DATA_UNAVAILABLE") and row["actual_branch"]:
        e.append("E-BR-ACTUAL-BRANCH")
    if cr == "TRIGGER_UNOBSERVABLE" and not blank(row["actual_value"]):
        e.append("E-BR-TU-VALUE")  # 触发条件观测不到，就不得有读数；有读数就按读数判定
    es = row["error_source"]
    if es:
        parts = es.split(";")
        if cr not in WRONG or any(p not in ERROR_SOURCES for p in parts) or len(set(parts)) != len(parts):
            e.append("E-BR-ERROR-SOURCE")
    return e


def _readings(row):
    return [] if blank(row["quarter_readings"]) else row["quarter_readings"].split(";")


def parse(text, manifest=None):
    """返回 (rows, errors)。errors 为 (行号, 错误码)，表头为第 1 行。"""
    if text.startswith("\ufeff"):
        return [], [(1, "E-BR-BOM")]
    if text and not text.endswith("\n"):
        return [], [(0, "E-BR-NO-FINAL-NEWLINE")]
    rd = list(csv.reader(io.StringIO(text)))
    if not rd or rd[0] != HEADER:
        return [], [(1, "E-BR-HEADER")]
    rows, errs = [], []
    for i, r in enumerate(rd[1:], start=2):
        if len(r) != len(HEADER):
            errs.append((i, "E-BR-COLUMNS"))
            continue
        row = dict(zip(HEADER, r))
        rows.append((i, row))
        errs += [(i, c) for c in check_row(row, manifest)]
    # 行间规则
    seq, ids, reg, final, last_readings, seen = {}, {}, {}, {}, {}, set()
    first_id, voided, void_groups = {}, set(), set()
    # 被 VOID_REVOKED 撤销的作废行不再生效
    revoked = {r["corrects_row_id"] for _, r in rows if r["check_result"] == "VOID_REVOKED"}
    revoked_seen = set()
    group_closed, prev_group = set(), None
    for i, row in rows:
        key = branch_key(row)
        seq[key] = seq.get(key, 0) + 1
        g = group_key(row)
        if seq[key] == 1:
            # 组的分支集合在登记时固定：同组登记行必须连续出现，组内一旦出现别的行或别的组的行，就不能再加新分支
            if g in group_closed:
                errs.append((i, "E-BR-GROUP-LATE"))
        else:
            group_closed.add(g)
        if prev_group is not None and prev_group != g:
            group_closed.add(prev_group)
        prev_group = g
        if row["row_id"] != expected_row_id(row["draft_id"], row["classification_id"], row["branch_order"], seq[key]):
            errs.append((i, "E-BR-ROW-ID"))
        if row["row_id"] in ids:
            errs.append((i, "E-BR-ROW-ID-DUP"))
        body = tuple(row[f] for f in HEADER[3:])
        if body in seen and not row["corrects_row_id"]:
            errs.append((i, "E-BR-DUPLICATE"))
        seen.add(body)
        if seq[key] == 1:
            # 第一行是登记行：PENDING、无更正、无读数；registered_at 的日期等于 publish_date
            if row["corrects_row_id"] or row["check_result"] != "PENDING" or _readings(row):
                errs.append((i, "E-BR-FIRST-ROW"))
            if row["registered_at"][:10] != row["publish_date"]:
                errs.append((i, "E-BR-REGISTERED-DATE"))
            reg[key], final[key], last_readings[key] = row, None, []
            first_id[key] = row["row_id"]
            ids[row["row_id"]] = row
            continue
        cur = reg[key]
        changed = [f for f in FROZEN if row[f] != cur[f]]
        if row["check_result"] == "VOID_REVOKED":
            # 撤销作废：指向本分支一条作废行，每条作废行只能撤销一次
            t = ids.get(row["corrects_row_id"])
            if t is None or t["check_result"] != "VOID" or branch_key(t) != key or row["corrects_row_id"] in revoked_seen:
                errs.append((i, "E-BR-CORRECTS-TARGET"))
            revoked_seen.add(row["corrects_row_id"])
            if changed:
                errs.append((i, "E-BR-PREREG-CHANGED"))
            ids[row["row_id"]] = row
            continue
        if key in voided or (g in void_groups and row["check_result"] != "VOID"):
            errs.append((i, "E-BR-AFTER-VOID"))
        if row["check_result"] == "VOID":
            # 作废行只留痕：指向该分支第一行，事先登记字段照抄当前登记；排除与否由可信合并时间决定
            if row["corrects_row_id"] != first_id[key]:
                errs.append((i, "E-BR-CORRECTS-TARGET"))
            if changed:
                errs.append((i, "E-BR-PREREG-CHANGED"))
            if row["row_id"] not in revoked:
                void_groups.add(g); voided.add(key)
            ids[row["row_id"]] = row
            continue
        if row["corrects_row_id"]:
            target = row["corrects_row_id"]
            if row["check_result"] == "PENDING":
                # 登记更正：只能在观测开始前，指向当前登记行，registered_at 写更正行自己的时间（晚于原登记）
                if target != cur["row_id"]:
                    errs.append((i, "E-BR-CORRECTS-TARGET"))
                if not (row["registered_at"] > cur["registered_at"]):
                    errs.append((i, "E-BR-CORRECTION-TIME"))
                if any(row[f] != cur[f] for f in ("draft_id", "classification_id", "branch_order", "publish_date")):
                    errs.append((i, "E-BR-CORRECTS-KEY"))
                if final[key] is not None or last_readings[key] or _readings(row) \
                        or row["registered_at"][:10] >= cur["window_start"]:
                    errs.append((i, "E-BR-CORRECTION-AFTER-START"))
                reg[key] = row
            else:
                # 结论更正：只改对账字段，必须指向当前最终结论
                if changed:
                    errs.append((i, "E-BR-PREREG-CHANGED"))
                if final[key] is None or target != final[key]["row_id"]:
                    errs.append((i, "E-BR-CORRECTS-TARGET"))
                if row["check_result"] not in FINAL:
                    errs.append((i, "E-BR-CORRECTION-RESULT"))
                final[key] = row
        else:
            if changed:
                errs.append((i, "E-BR-PREREG-CHANGED"))
            if row["check_result"] in FINAL:
                if final[key] is not None:
                    errs.append((i, "E-BR-SECOND-FINAL"))
                else:
                    final[key] = row
            # 按季读数：只能在前一行基础上往后追加，已有条目不改不删
            cur_r = _readings(row)
            if cur_r[:len(last_readings[key])] != last_readings[key] or len(cur_r) < len(last_readings[key]):
                errs.append((i, "E-BR-READINGS-REWRITE"))
            elif is_quarterly(row) and len(cur_r) <= len(last_readings[key]):
                errs.append((i, "E-BR-READINGS-NOT-LONGER"))  # 不带更正的读数行须至少多一个季度
            if cur_r:
                last_readings[key] = cur_r
        ids[row["row_id"]] = row
    errs += _group_errors(rows, final)
    errs += _group_shape_errors(rows, reg)
    # 作废按整组：组内每一支都要有作废行，且全组作废行连续出现（同一个提交由逐提交检查核对）
    for g in void_groups:
        ks = {branch_key(r) for _, r in rows if group_key(r) == g}
        vl = [i for i, r in rows if group_key(r) == g and r["check_result"] == "VOID" and r["row_id"] not in revoked]
        if not ks <= voided or vl != list(range(vl[0], vl[0] + len(vl))):
            errs.append((vl[0], "E-BR-VOID-PARTIAL"))
    return rows, errs


GROUP_SAME = ["publish_date", "window_start", "window_end", "observed_variable", "unit", "data_source", "data_vintage"]


def _group_shape_errors(rows, reg):
    """每组至少 2 支；同组分支（按当前登记）的观测口径完全相同。"""
    errs, members, line = [], {}, {}
    for i, row in rows:
        members.setdefault(group_key(row), []).append(branch_key(row))
        line.setdefault(group_key(row), i)
    for g, keys in members.items():
        ks = list(dict.fromkeys(keys))
        if len(ks) < 2:
            errs.append((line[g], "E-BR-GROUP-SIZE"))
        regs = [reg[k] for k in ks if k in reg]
        if any(tuple(x[f] for f in GROUP_SAME) + (x["registered_at"][:10],) !=
               tuple(regs[0][f] for f in GROUP_SAME) + (regs[0]["registered_at"][:10],) for x in regs):
            errs.append((line[g], "E-BR-GROUP-MISMATCH"))
    return errs


def _partition_error(regs):
    """只作提示：同组区间型分支是否两两互斥、是否覆盖全部实数（按端点开闭）。返回 W-BR-GROUP-GAP / W-BR-GROUP-OVERLAP 或 None。
    不拦登记：NONE_HIT（漏分类）和 MULTI_HIT（条件失效）必须能出现。"""
    INF = Decimal("Infinity")
    try:
        iv = sorted(((D(x["interval_low"]) if x["interval_low"] else -INF, x["interval_low_closed"] == "true",
                      D(x["interval_high"]) if x["interval_high"] else INF, x["interval_high_closed"] == "true")
                     for x in regs), key=lambda t: (t[0], not t[1]))
    except (ValueError, TypeError):
        return None
    if iv[0][0] != -INF or iv[-1][2] != INF:
        return "W-BR-GROUP-GAP"
    for (l1, lc1, h1, hc1), (l2, lc2, h2, hc2) in zip(iv, iv[1:]):
        if h1 > l2 or (h1 == l2 and hc1 and lc2):
            return "W-BR-GROUP-OVERLAP"
        if h1 < l2 or (h1 == l2 and not hc1 and not lc2):
            return "W-BR-GROUP-GAP"
    return None


def _group_errors(rows, final):
    """组内互斥判定（按 (draft_id, classification_id) 分组，只看各分支当前最终结论）：
    恰一支 HIT 其余 MISS；全部 NONE_HIT；≥2 支 MULTI_HIT 其余 MISS；全部 TRIGGER_UNOBSERVABLE。
    组内未全部出结论时只查不矛盾；全部出结论后查完整；error_source 组内一致。"""
    errs, members, line = [], {}, {}
    for i, row in rows:
        members.setdefault(group_key(row), set()).add(branch_key(row))
        if final.get(branch_key(row)) is row:
            line[branch_key(row)] = i
    for g, keys in members.items():
        fs = {k: final[k] for k in keys if final.get(k) is not None}
        if not fs:
            continue
        # 同组对账必须基于同一次观测：同一个 actual_value、同一份 evidence
        if len({r["actual_value"] for r in fs.values()}) > 1 or len({r["evidence"] for r in fs.values()}) > 1:
            errs.append((max(line[k] for k in fs), "E-BR-GROUP-OBSERVATION"))
            continue
        # 全是区间型分支：先用共同取值统一算出每一支是否命中，再与各行结论核对
        v = D(next(iter(fs.values()))["actual_value"])
        reg_rows = {k: _reg_of(rows, k) for k in keys}
        if v is not None and all(is_interval(x) for x in reg_rows.values()):
            hits = {k for k, x in reg_rows.items() if in_interval(x, v)}
            for k, r in fs.items():
                if k in hits:
                    exp = "HIT" if len(hits) == 1 else "MULTI_HIT"
                else:
                    exp = "NONE_HIT" if not hits else "MISS"
                if r["check_result"] != exp:
                    errs.append((line[k], "E-BR-GROUP-RESULT")); break
        res = [r["check_result"] for r in fs.values()]
        n_hit, n_multi = res.count("HIT"), res.count("MULTI_HIT")
        kinds = set(res) - {"MISS"}
        bad = (n_hit > 1 or (n_hit and n_multi) or len(kinds) > 1
               or ("NONE_HIT" in kinds and "MISS" in res) or ("TRIGGER_UNOBSERVABLE" in kinds and "MISS" in res))
        if not bad and len(fs) == len(keys):
            bad = (kinds == set() or (n_multi == 1 and len(keys) > 1))
        if not bad and len({r["error_source"] for r in fs.values()}) > 1:
            bad = True
        if bad:
            errs.append((max(line[k] for k in fs), "E-BR-GROUP-RESULT"))
    return errs


def _reg_of(rows, key):
    """该分支当前登记（第一行或最后一条登记更正行）。"""
    cur = None
    for _, r in rows:
        if branch_key(r) == key and (cur is None or (r["corrects_row_id"] and r["check_result"] == "PENDING")):
            cur = r
    return cur


def active_voids(rows):
    """未被撤销的作废行。"""
    revoked = {r["corrects_row_id"] for _, r in rows if r["check_result"] == "VOID_REVOKED"}
    return [(i, r) for i, r in rows if r["check_result"] == "VOID" and r["row_id"] not in revoked]


def complete_void_groups(rows):
    """作废完整的组：组内每一支都有未撤销的作废行，且这些行连续。"""
    av = active_voids(rows)
    out = set()
    for g in {group_key(r) for _, r in av}:
        ks = {branch_key(r) for _, r in rows if group_key(r) == g}
        vl = [i for i, r in av if group_key(r) == g]
        if {branch_key(r) for _, r in av if group_key(r) == g} == ks and vl == list(range(vl[0], vl[0] + len(vl))):
            out.add(g)
    return out


def partition_warnings(rows):
    """同组区间型分支的覆盖与互斥提示（不是错误）。"""
    out, members = {}, {}
    for _, r in rows:
        members.setdefault(group_key(r), []).append(branch_key(r))
    for g, ks in members.items():
        regs = [_reg_of(rows, k) for k in dict.fromkeys(ks)]
        if len(regs) >= 2 and all(is_interval(x) for x in regs):
            w = _partition_error(regs)
            if w:
                out["-".join(g)] = w
    return out


def first_rows(rows):
    first = {}
    for _, row in rows:
        first.setdefault(branch_key(row), row)
    return first


def conclusion_changes(rows):
    """每个分支“结论改过”的次数 = 该分支结论更正行的条数（可由台账推导，不另设字段）。"""
    out = {}
    for _, row in rows:
        if row["corrects_row_id"] and row["check_result"] in FINAL:
            k = branch_key(row); out[k] = out.get(k, 0) + 1
    return out


def hit_stats(rows, excluded=frozenset()):
    """命中率口径：分支身份与分母取每个分支的第一行（按组计）；事先条件取观测开始前的最后一次登记更正（没有则第一行）；
    结果取当前有效最终结论（结论更正后的最新一条）。另列做过登记更正的分支数和结论更正次数。"""
    final, reg_corr, members = {}, set(), {}
    for _, row in rows:
        k = branch_key(row)
        members.setdefault(group_key(row), set()).add(k)
        if row["corrects_row_id"] and row["check_result"] == "PENDING":
            reg_corr.add(k)
        elif row["check_result"] in FINAL:
            final[k] = row
    judged = correct = 0
    for g, ks in members.items():
        if g in excluded:
            continue
        fs = [final[k] for k in ks if k in final]
        if len(fs) != len(ks):
            continue
        judged += 1
        res = [x["check_result"] for x in fs]
        correct += int(res.count("HIT") == 1 and res.count("MISS") == len(res) - 1)
    return {"groups": len(members), "groups_judged": judged, "groups_correct": correct,
            "branches": sum(len(v) for v in members.values()), "registration_corrected_branches": len(reg_corr),
            "conclusion_corrections": sum(conclusion_changes(rows).values()),
            "excluded_late_groups": len(excluded), "partition_warnings": partition_warnings(rows)}


def gate_count(rows, cutoff="2026-12-31", domain=None, excluded=frozenset()):
    """门禁计数：每个分支（draft_id + classification_id + branch_order）只按第一行算：
    第一行 window_end 不晚于 cutoff 且 check_result 为 PENDING 的计 1。"""
    return sum(1 for k, r in first_rows(rows).items()
               if group_key(r) not in excluded and r["check_result"] == "PENDING" and r["window_end"] <= cutoff and (domain is None or r["domain"] == domain))


def append_only(old_text, new_text):
    """新版本必须以旧版本为前缀（只追加行）。"""
    return new_text.startswith(old_text)


class GitError(Exception):
    pass


def commit_exists(repo, ref):
    p = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{ref}^{{commit}}"], capture_output=True)
    return p.returncode == 0


def git_show(repo, ref, path=LEDGER_PATH):
    """读 ref:path。提交不存在 → GitError；提交存在但没有该文件 → None。"""
    if not commit_exists(repo, ref):
        raise GitError(ref)
    p = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True)
    if p.returncode != 0:
        t = subprocess.run(["git", "-C", str(repo), "ls-tree", "--name-only", ref, path], capture_output=True)
        if t.returncode != 0:
            raise GitError(ref)
        if t.stdout.strip():
            raise GitError(ref)  # 文件存在却读不出
        return None
    return p.stdout.decode("utf-8")


def manifest_from_git(repo, ref):
    """返回 manifest(path)->sha256：从 ref 树中 raw/<日期>/MANIFEST.sha256 查该文件的登记哈希。"""
    cache = {}

    def look(path):
        m = RAW_RE.match(path)
        if not m:
            return None
        day = m.group(1)
        if day not in cache:
            p = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:raw/{day}/MANIFEST.sha256"], capture_output=True)
            d = {}
            if p.returncode == 0:
                for ln in p.stdout.decode("utf-8", "replace").splitlines():
                    sha, _, rel = ln.partition("  ")
                    d[rel[2:] if rel.startswith("./") else rel] = sha
            cache[day] = d
        return cache[day].get(m.group(2))
    return look
