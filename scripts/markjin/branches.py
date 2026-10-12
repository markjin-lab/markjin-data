"""分支台账 ledger/macro-branches.csv 的格式校验（只用标准库）。

字段与规则照站点路线图第六节“分支台账”、第十三节 13.1。
只校验格式与登记规则，不判 HIT/MISS，不读取内核。
"""
import csv, io, re, subprocess
from datetime import date

LEDGER_PATH = "ledger/macro-branches.csv"

HEADER = [
    "draft_id", "slug", "publish_date", "framework_version", "framework_sha256",
    "observed_variable", "unit", "data_source", "data_vintage", "window_start", "window_end",
    "branch_order", "interval_low", "interval_low_closed", "interval_high", "interval_high_closed",
    "trigger_condition", "n_quarters", "lu_basis_date", "registered_by", "registered_at",
    "actual_value", "actual_branch", "check_result", "error_source", "window_quarters",
    "quarter_readings", "l_value", "u_value", "lu_evidence", "checked_by", "checked_at", "evidence",
]
# 事先登记、事后不改的字段（第十三节 13.1 第 1 步，另加 draft_id 等身份字段）
PRE_REGISTERED = [
    "draft_id", "slug", "publish_date", "framework_version", "framework_sha256",
    "observed_variable", "unit", "data_source", "data_vintage", "window_start", "window_end",
    "branch_order", "interval_low", "interval_low_closed", "interval_high", "interval_high_closed",
    "trigger_condition", "n_quarters", "window_quarters", "lu_basis_date", "l_value", "u_value",
    "lu_evidence", "registered_by", "registered_at",
]
INTERVAL = ["interval_low", "interval_low_closed", "interval_high", "interval_high_closed"]
CHECK_RESULTS = {"PENDING", "HIT", "MISS", "NONE_HIT", "MULTI_HIT", "TRIGGER_UNOBSERVABLE", "DATA_UNAVAILABLE"}
WRONG = {"NONE_HIT", "MULTI_HIT", "TRIGGER_UNOBSERVABLE"}
ERROR_SOURCES = {"采集", "解读", "框架"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
VER_RE = re.compile(r"^v\d+\.\d+$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00$")
Q_RE = re.compile(r"^(\d{4})Q([1-4])$")
NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")


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
    """返回该行的错误码列表。"""
    e = []
    for f in ("draft_id", "slug", "framework_version", "framework_sha256", "observed_variable", "unit",
              "data_source", "data_vintage", "trigger_condition", "registered_by", "registered_at"):
        if not row[f].strip():
            e.append(f"E-BR-EMPTY:{f}")
    if row["framework_sha256"] and not SHA_RE.match(row["framework_sha256"]):
        e.append("E-BR-SHA256")
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
    if not re.fullmatch(r"[1-9]\d*", row["branch_order"]):
        e.append("E-BR-ORDER")
    cr = row["check_result"]
    if cr not in CHECK_RESULTS:
        e.append("E-BR-CHECK-RESULT")
    quarterly = bool(row["n_quarters"].strip())
    if quarterly:
        # 按季读数型分支
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
        if not row["lu_evidence"].strip():
            e.append("E-BR-LU-EVIDENCE")
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
        for f in ("lu_basis_date", "l_value", "u_value", "lu_evidence", "window_quarters", "quarter_readings"):
            if row[f]:
                e.append(f"E-BR-QUARTERLY-ONLY:{f}")
    # 到期字段
    if cr == "PENDING":
        if row["actual_branch"] or row["error_source"] or row["checked_at"]:
            e.append("E-BR-PENDING-FILLED")
    elif cr in CHECK_RESULTS:
        if not (row["checked_by"] and TS_RE.match(row["checked_at"])):
            e.append("E-BR-CHECKED")
        if cr != "DATA_UNAVAILABLE" and not row["evidence"].strip() and not row["quarter_readings"].strip():
            e.append("E-BR-EVIDENCE")
    if row["actual_branch"] not in ("", "是", "否"):
        e.append("E-BR-ACTUAL-BRANCH")
    if cr == "HIT" and row["actual_branch"] != "是" or cr in ("MISS", "NONE_HIT") and row["actual_branch"] != "否" \
            or cr in ("TRIGGER_UNOBSERVABLE", "DATA_UNAVAILABLE") and row["actual_branch"]:
        e.append("E-BR-ACTUAL-BRANCH")
    es = row["error_source"]
    if es:
        parts = es.split(";")
        if cr not in WRONG or any(p not in ERROR_SOURCES for p in parts) or len(set(parts)) != len(parts):
            e.append("E-BR-ERROR-SOURCE")
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
    # 同一 draft_id + branch_order 的后续行：事先登记字段必须与第一行一致
    first = {}
    seen = set()
    for i, row in rows:
        key = (row["draft_id"], row["branch_order"])
        if tuple(r for r in row.values()) in seen:
            errs.append((i, "E-BR-DUPLICATE"))
        seen.add(tuple(row.values()))
        if key in first:
            if any(row[f] != first[key][f] for f in PRE_REGISTERED):
                errs.append((i, "E-BR-PREREG-CHANGED"))
        else:
            first[key] = row
    return rows, errs


def append_only(old_text, new_text):
    """新版本必须以旧版本为前缀（只追加行）。"""
    return new_text.startswith(old_text)


def git_show(repo, ref, path=LEDGER_PATH):
    p = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout.decode("utf-8")
