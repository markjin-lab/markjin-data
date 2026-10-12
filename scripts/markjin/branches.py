"""分支台账 ledger/branches.csv 的格式校验（只用标准库）。

字段与规则照站点路线图第六节“分支台账”、第十三节 13.1。
只校验格式与登记规则，不判 HIT/MISS，不读取内核。
"""
import csv, io, re, subprocess
from datetime import date

LEDGER_PATH = "ledger/branches.csv"

HEADER = [
    "row_id", "corrects_row_id", "reason",
    "draft_id", "slug", "publish_date", "domain", "framework_version", "framework_sha256", "framework_commit",
    "observed_variable", "unit", "data_source", "data_vintage", "window_start", "window_end",
    "branch_order", "interval_low", "interval_low_closed", "interval_high", "interval_high_closed",
    "trigger_condition", "n_quarters", "lu_basis_date", "registered_by", "registered_at",
    "actual_value", "actual_branch", "check_result", "error_source", "window_quarters",
    "quarter_readings", "l_value", "u_value", "lu_evidence", "checked_by", "checked_at", "evidence",
]
DOMAINS = {"macro", "ai", "energy", "space", "bio", "other"}
# 事先登记、事后不改的字段（更正行除外：更正行可写更正后的值）
PRE_REGISTERED = [
    "draft_id", "slug", "publish_date", "domain", "framework_version", "framework_sha256", "framework_commit",
    "observed_variable", "unit", "data_source", "data_vintage", "window_start", "window_end",
    "branch_order", "interval_low", "interval_low_closed", "interval_high", "interval_high_closed",
    "trigger_condition", "n_quarters", "window_quarters", "lu_basis_date", "l_value", "u_value",
    "lu_evidence", "registered_by",
]
CHECK_FIELDS = ["actual_value", "actual_branch", "error_source", "quarter_readings", "checked_by", "checked_at", "evidence"]
INTERVAL = ["interval_low", "interval_low_closed", "interval_high", "interval_high_closed"]
QUARTERLY = ["n_quarters", "window_quarters", "lu_basis_date", "l_value", "u_value", "lu_evidence"]
CHECK_RESULTS = {"PENDING", "HIT", "MISS", "NONE_HIT", "MULTI_HIT", "TRIGGER_UNOBSERVABLE", "DATA_UNAVAILABLE"}
WRONG = {"NONE_HIT", "MULTI_HIT", "TRIGGER_UNOBSERVABLE"}
ERROR_SOURCES = {"采集", "解读", "框架"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
VER_RE = re.compile(r"^v\d+\.\d+$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00$")
Q_RE = re.compile(r"^(\d{4})Q([1-4])$")
NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")
FINAL = {"HIT", "MISS", "NONE_HIT", "MULTI_HIT", "TRIGGER_UNOBSERVABLE"}
# 按季读数型分支：王总确认判定规则前只允许这三种结论
QUARTERLY_ALLOWED = {"PENDING", "TRIGGER_UNOBSERVABLE", "DATA_UNAVAILABLE"}
# 读数绑定格式：季度:读数@vintage(YYYY-MM-DD)#raw 路径:sha256；lu_evidence 另加 |来源链接
READING_RE = re.compile(r"^(\d{4}Q[1-4]):(-?\d+(?:\.\d+)?)@(\d{4}-\d{2}-\d{2})#(raw/[A-Za-z0-9._/\-]+):([0-9a-f]{64})$")
LU_RE = re.compile(r"^(\d{4}Q[1-4]):(-?\d+(?:\.\d+)?)@(\d{4}-\d{2}-\d{2})#(raw/[A-Za-z0-9._/\-]+):([0-9a-f]{64})\|(https?://[^\s;|]+)$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


def blank(v):
    return v in ("", "NA")


def expected_row_id(draft_id, branch_order, seq):
    """row_id 生成规则：<draft_id>-b<branch_order>-r<seq>，seq 为同一分支在文件中的第几行（从 1 起）。"""
    return f"{draft_id}-b{branch_order}-r{seq}"


def _date(s):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _quarters(s):
    out = []
    for part in s.split(";"):
        m = Q_RE.match(part)
        if not m:
            return None
        out.append((int(m.group(1)), int(m.group(2))))
    return out


def _consecutive(qs):
    return all((b[0] * 4 + b[1]) - (a[0] * 4 + a[1]) == 1 for a, b in zip(qs, qs[1:]))


def check_row(row):
    """返回该行的错误码列表（单行规则，不看其他行）。"""
    e = []
    for f in ("draft_id", "slug", "domain", "framework_version", "framework_sha256", "framework_commit",
              "observed_variable", "unit", "data_source", "data_vintage", "trigger_condition",
              "registered_by", "registered_at"):
        if not row[f].strip():
            e.append(f"E-BR-EMPTY:{f}")
    if row["draft_id"] and not ID_RE.match(row["draft_id"]):
        e.append("E-BR-DRAFT-ID")
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
    ws, we = _date(row["window_start"]), _date(row["window_end"])
    if ws and we and ws > we:
        e.append("E-BR-WINDOW")
    if row["registered_at"] and not TS_RE.match(row["registered_at"]):
        e.append("E-BR-TS:registered_at")
    elif we and _date(row["registered_at"][:10]) and date.fromisoformat(row["registered_at"][:10]) > we:
        e.append("E-BR-REGISTERED-AFTER-END")  # registered_at 须早于 window_end 当日结束
    if not re.fullmatch(r"[1-9]\d*", row["branch_order"]):
        e.append("E-BR-ORDER")
    cr = row["check_result"]
    if cr not in CHECK_RESULTS:
        e.append("E-BR-CHECK-RESULT")
    quarterly = not blank(row["n_quarters"])
    if quarterly:
        # 按季读数型分支（多见于宏观）
        if not re.fullmatch(r"[1-9]\d*", row["n_quarters"]):
            e.append("E-BR-N")  # N ≥ 1
        if any(row[f] != "NA" for f in INTERVAL):
            e.append("E-BR-INTERVAL-NA")
        if _date(row["lu_basis_date"]) is None:
            e.append("E-BR-DATE:lu_basis_date")
        lv, uv = row["l_value"], row["u_value"]
        if not (NUM_RE.match(lv) and NUM_RE.match(uv)):
            e.append("E-BR-LU")
        elif float(lv) > float(uv):
            e.append("E-BR-L-GT-U")  # L ≤ U
        if blank(row["lu_evidence"].strip()):
            e.append("E-BR-LU-EVIDENCE")
        elif not all(LU_RE.match(x) and _date(LU_RE.match(x).group(3)) for x in row["lu_evidence"].split(";")):
            e.append("E-BR-LU-EVIDENCE-FORMAT")
        if not blank(row["quarter_readings"]):
            items = row["quarter_readings"].split(";")
            ms = [READING_RE.match(x) for x in items]
            if not all(m and _date(m.group(3)) for m in ms):
                e.append("E-BR-READINGS-FORMAT")
            elif qs := _quarters(row["window_quarters"]):
                wq = [f"{y}Q{q}" for y, q in qs]
                got = [m.group(1) for m in ms]
                if any(g not in wq for g in got) or got != sorted(got, key=wq.index) or len(set(got)) != len(got):
                    e.append("E-BR-READINGS-QUARTERS")
        if cr not in QUARTERLY_ALLOWED:
            e.append("E-BR-QUARTERLY-RESULT")
        if row["error_source"]:
            e.append("E-BR-QUARTERLY-ERROR-SOURCE")
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
    else:
        # 非按季分支：按季字段与 quarter_readings 只能留空或 NA
        for f in QUARTERLY[1:] + ["quarter_readings"]:
            if not blank(row[f]):
                e.append(f"E-BR-QUARTERLY-ONLY:{f}")
        if all(row[f] == "NA" for f in INTERVAL):
            pass  # 无数值区间（定性条件），判定以 trigger_condition 为准
        else:
            # 区间型分支：端点空=无穷；closed 取 true/false
            for f in ("interval_low", "interval_high"):
                if row[f] and not NUM_RE.match(row[f]):
                    e.append(f"E-BR-INTERVAL:{f}")
            for f in ("interval_low_closed", "interval_high_closed"):
                if row[f] not in ("true", "false"):
                    e.append(f"E-BR-INTERVAL:{f}")
            if NUM_RE.match(row["interval_low"]) and NUM_RE.match(row["interval_high"]) \
                    and float(row["interval_low"]) > float(row["interval_high"]):
                e.append("E-BR-INTERVAL-ORDER")
    # 到期字段
    if cr == "PENDING":
        if any(not blank(row[f]) for f in ("actual_value", "actual_branch", "error_source", "checked_by", "checked_at", "evidence")):
            e.append("E-BR-PENDING-FILLED")
    elif cr in CHECK_RESULTS:
        if not (row["checked_by"] and TS_RE.match(row["checked_at"])):
            e.append("E-BR-CHECKED")
        elif we and date.fromisoformat(row["checked_at"][:10]) <= we:
            e.append("E-BR-CHECKED-BEFORE-END")  # checked_at 必须晚于 window_end（SGT 日期）
        if cr != "DATA_UNAVAILABLE" and blank(row["evidence"].strip()) and blank(row["quarter_readings"].strip()):
            e.append("E-BR-EVIDENCE")
    if row["actual_branch"] not in ("", "是", "否"):
        e.append("E-BR-ACTUAL-BRANCH")
    if cr == "HIT" and row["actual_branch"] != "是" or cr in ("MISS", "NONE_HIT") and row["actual_branch"] != "否" \
            or cr in ("TRIGGER_UNOBSERVABLE", "DATA_UNAVAILABLE") and row["actual_branch"]:
        e.append("E-BR-ACTUAL-BRANCH")
    es = row["error_source"]
    if es and not quarterly:
        parts = es.split(";")
        if cr not in WRONG or any(p not in ERROR_SOURCES for p in parts) or len(set(parts)) != len(parts):
            e.append("E-BR-ERROR-SOURCE")
    # 更正字段：两者同空或同填
    if bool(row["corrects_row_id"]) != bool(row["reason"].strip()):
        e.append("E-BR-CORRECTION-REASON")
    if row["corrects_row_id"] and cr != "PENDING":
        e.append("E-BR-CORRECTION-PENDING")
    return e


def parse(text):
    """返回 (rows, errors)。errors 为 (行号, 错误码)。行号含表头，表头为第 1 行。"""
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
        errs += [(i, c) for c in check_row(row)]
    # 行间规则：row_id、更正行指向、事先登记字段不变
    seq, ids, current, seen, final = {}, {}, {}, set(), {}
    for i, row in rows:
        key = (row["draft_id"], row["branch_order"])
        seq[key] = seq.get(key, 0) + 1
        if row["row_id"] != expected_row_id(row["draft_id"], row["branch_order"], seq[key]):
            errs.append((i, "E-BR-ROW-ID"))
        if row["row_id"] in ids:
            errs.append((i, "E-BR-ROW-ID-DUP"))
        if tuple(row[f] for f in HEADER[3:]) in seen and not row["corrects_row_id"]:
            errs.append((i, "E-BR-DUPLICATE"))
        seen.add(tuple(row[f] for f in HEADER[3:]))
        if seq[key] == 1:
            if row["corrects_row_id"] or row["check_result"] != "PENDING":
                errs.append((i, "E-BR-FIRST-ROW"))
            current[key] = row
            final[key] = False
        elif row["corrects_row_id"]:
            target = ids.get(row["corrects_row_id"])
            if target is None or (target["draft_id"], target["branch_order"]) != key:
                errs.append((i, "E-BR-CORRECTS-UNKNOWN"))
            current[key] = row  # 更正行成为该分支此后对账行的登记依据，最终结论另算
            final[key] = False
        elif any(row[f] != current[key][f] for f in PRE_REGISTERED):
            errs.append((i, "E-BR-PREREG-CHANGED"))
        if seq[key] > 1 and not row["corrects_row_id"] and row["check_result"] in FINAL:
            if final.get(key):
                errs.append((i, "E-BR-SECOND-FINAL"))
            final[key] = True
        ids[row["row_id"]] = row
    return rows, errs


def gate_count(rows, cutoff="2026-12-31", domain=None):
    """门禁计数：每个分支（draft_id + branch_order）只算第一行；
    第一行 window_end 不晚于 cutoff 且 check_result 为 PENDING 的计 1。"""
    first = {}
    for _, row in rows:
        first.setdefault((row["draft_id"], row["branch_order"]), row)
    return sum(1 for r in first.values()
               if r["check_result"] == "PENDING" and r["window_end"] <= cutoff and (domain is None or r["domain"] == domain))


def append_only(old_text, new_text):
    """新版本必须以旧版本为前缀（只追加行）。"""
    return new_text.startswith(old_text)


def git_show(repo, ref, path=LEDGER_PATH):
    p = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout.decode("utf-8")
