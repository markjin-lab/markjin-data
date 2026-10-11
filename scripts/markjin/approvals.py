"""公开批准记录与发布状态（协调决定 2026-10-10，第 2 轮）。全部从 markjin-data 的 main 分支 git 对象读取，不读工作树。

approvals/codex/<稿件sha256>.json   Codex 审查记录（审查与治理 bot 写；首日发布只认这一份）
approvals/codex/<稿件sha256>.<YYYY-MM-DD>.json   顺延稿在可发布日 D（SGT）的重审记录（整体验收 r12，王总定），reviewed_at 须在 D 日
approvals/wang/<稿件sha256>.json    王总批准记录（协调 bot 写，转达王总本人原话；首日只认这一份）
approvals/wang/<稿件sha256>.<YYYY-MM-DD>.json   顺延稿在可发布日 D 的王总重新批准记录，recorded_at 须在 D 日（整体验收 r13，审查 bot 定的技术方案）
state/publish-state.json            发布状态（生产 bot 提交）
完整 schema 见 docs/approvals.md。

- 一个稿件 sha256 每类最多一个无日期文件；Codex 与王总记录另可各有每个可发布日一份带日期文件；文件名的 sha 必须等于记录里的 content_sha256。
- 两个目录只允许追加：已有文件不得修改、删除或改名。route 读取时与 scripts/audit-approvals.py 都用 git log 检查；
  违反 → E-ROUTE-APPROVALS-REWRITTEN，全部记录不采信。
- 严格 schema：未知键、缺键、None、类型不对、非法 JSON、文件名不符 → 该类记录全部不采信（E-ROUTE-RECORD-INVALID）。
- 所有 bot 共用一个 GitHub 账号，无法按账号区分写入方；写入方约束靠流程，脚本只保证“只追加、可审计、内容绑定”。
  防伪造（共用账号、同一 OS 用户、记录来源无法证明）是 follow-up：markjin-data#30（第 2 阶段用王总 Mac 上的密钥签名）。
- 王总批准记录 v2（多 schema_version=2、quote_ref 与 draft_id）：信号卡与真实发信必须使用 v2；v1 只对日报类审查稿有效。
- 稿件身份绑定（r4）：Codex 记录与王总 v2 记录都带 draft_id，路由要求与当前稿件的 draft_id 一致，防止同一内容换路径重放。
- 内部材料（r4）：记录中的自由文本字段（quote、quote_ref、log_path、draft_id）用本机内部清单扫描，命中 → 该类记录全部不采信
  （E-ROUTE-RECORD-INTERNAL）；内部清单读不到 → 不采信任何记录（E-INTERNAL-LIST-MISSING）。
"""
from .internal import load_internal_terms
import datetime as dt
import json
import re
import subprocess

CODEX_DIR = "approvals/codex"
WANG_DIR = "approvals/wang"
STATE_FILE = "state/publish-state.json"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LOG_PATH_RE = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9._/-]{1,200}$")
CHANNELS = {"direct", "via-grok-bot"}
DRAFT_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
CODEX_CATEGORIES = ("medical", "religion", "macro")
CODEX_KEYS = {"content_sha256", "draft_id", "codex_session", "verdict", "log_path", "reviewed_at"}
WANG_KEYS = {"content_sha256", "recorded_at", "channel", "quote"}
WANG_V2_KEYS = WANG_KEYS | {"schema_version", "quote_ref", "draft_id"}   # v2：信号卡与真实发信必须使用
QUOTE_REF_RE = re.compile(r"^[A-Za-z0-9._:/#@-]{1,200}$")


class ApprovalsError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


ALLOWED_REFS = ("main", "origin/main")   # 协调决定：批准与状态只从 markjin-data main 读取


def _no_dup(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key")
    return dict(pairs)


def loads_strict(text):
    """JSON 解析，重复键 → ValueError（防止前一个值被隐藏）。"""
    return json.loads(text, object_pairs_hook=_no_dup)


def parse_ts(s):
    if not isinstance(s, str):
        return None
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def valid_codex(r):
    if isinstance(r, dict) and "_for_date" in r:      # r12：读取时附加的内存字段（文件名日期），不属于 schema
        r = {k: v for k, v in r.items() if k != "_for_date"}
    # 中英配对（t145u）：可选 pair_sha256 = 配对另一版的 content_sha256（64 位小写十六进制，且不等于自身）
    if isinstance(r, dict) and "pair_sha256" in r:
        if not (isinstance(r["pair_sha256"], str) and SHA256_RE.fullmatch(r["pair_sha256"])
                and r["pair_sha256"] != r.get("content_sha256")):
            return False
        r = {k: v for k, v in r.items() if k != "pair_sha256"}
    # r7 BLOCKER 2：可选 category = Codex 判定的类别（medical / religion / macro）；任一 → 路由要求王总批准
    if isinstance(r, dict) and "category" in r:
        if r["category"] not in CODEX_CATEGORIES:
            return False
        r = {k: v for k, v in r.items() if k != "category"}
    return (isinstance(r, dict) and set(r) == CODEX_KEYS
            and isinstance(r["content_sha256"], str) and bool(SHA256_RE.fullmatch(r["content_sha256"]))
            and isinstance(r["codex_session"], str) and bool(UUID_RE.fullmatch(r["codex_session"]))
            and isinstance(r["draft_id"], str) and bool(DRAFT_ID_RE.fullmatch(r["draft_id"]))
            and isinstance(r["verdict"], str) and r["verdict"] in ("APPROVED", "REJECTED")
            and isinstance(r["reviewed_at"], str) and parse_ts(r["reviewed_at"]) is not None   # Codex 审查完成时间
            and isinstance(r["log_path"], str) and bool(LOG_PATH_RE.fullmatch(r["log_path"])))


def _strip(r):
    if isinstance(r, dict) and "_for_date" in r:      # 读取时附加的内存字段（文件名日期），不属于 schema
        return {k: v for k, v in r.items() if k != "_for_date"}
    return r


def is_v2(r):
    r = _strip(r)
    return isinstance(r, dict) and set(r) == WANG_V2_KEYS and type(r.get("schema_version")) is int and r["schema_version"] == 2


def valid_wang(r):
    r = _strip(r)
    if is_v2(r):
        if not (isinstance(r["quote_ref"], str) and QUOTE_REF_RE.fullmatch(r["quote_ref"])
                and isinstance(r["draft_id"], str) and DRAFT_ID_RE.fullmatch(r["draft_id"])):
            return False
    elif not (isinstance(r, dict) and set(r) == WANG_KEYS):
        return False
    return ( isinstance(r["content_sha256"], str) and bool(SHA256_RE.fullmatch(r["content_sha256"]))
            and parse_ts(r["recorded_at"]) is not None and isinstance(r["channel"], str) and r["channel"] in CHANNELS
            and isinstance(r["quote"], str) and bool(r["quote"].strip()))


SGT = dt.timezone(dt.timedelta(hours=8))


def parse_record(name, text, validator, dated_ok=False):
    """严格解析一个记录文件；任何不合规 → ApprovalsError("E-ROUTE-RECORD-INVALID")。
    整体验收 r12 HIGH（王总定）：Codex 目录另允许顺延稿重审记录 <sha>.<YYYY-MM-DD>.json（日期 = 可发布日，SGT）；
    文件名日期须是真实日期，且等于 reviewed_at 的 SGT 日期，否则判失败。返回的记录带 "_for_date"（无日期文件为 None），
    只在内存中使用、不属于 schema。"""
    m = re.fullmatch(r"([0-9a-f]{64})(?:\.(\d{4}-\d{2}-\d{2}))?\.json", name)   # 整体验收 r4：文件名末尾换行也不放行
    try:
        r = loads_strict(text)
    except ValueError:
        raise ApprovalsError("E-ROUTE-RECORD-INVALID")
    if not m or not validator(r) or r["content_sha256"] != m.group(1):
        raise ApprovalsError("E-ROUTE-RECORD-INVALID")
    fd = m.group(2)
    if fd is not None:
        if not dated_ok:
            raise ApprovalsError("E-ROUTE-RECORD-INVALID")
        try:
            day = dt.date.fromisoformat(fd)
        except ValueError:
            raise ApprovalsError("E-ROUTE-RECORD-INVALID")
        ts = parse_ts(r["reviewed_at"] if "reviewed_at" in r else r["recorded_at"])   # Codex：审查日；王总：批准日
        if ts is None or ts.astimezone(SGT).date() != day:
            raise ApprovalsError("E-ROUTE-RECORD-INVALID")          # 文件名日期与 reviewed_at 日期不一致 → 判失败
    r = dict(r); r["_for_date"] = fd                 # 整体验收 r13：Codex 与王总记录都附加（对称）
    return r


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True)


def show(repo, ref, path):
    """返回 ref:path 的 UTF-8 文本；不存在 → None；git 失败或解码失败 → ApprovalsError。"""
    if _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
        raise ApprovalsError("E-ROUTE-STATE")
    ls = _git(repo, "ls-tree", "-z", ref, "--", path)      # 区分“不存在”（空输出）与 git 失败（非零）
    if ls.returncode != 0:
        raise ApprovalsError("E-ROUTE-STATE")
    if not ls.stdout.strip(b"\0"):
        return None
    r = _git(repo, "cat-file", "blob", f"{ref}:{path}")
    if r.returncode != 0:
        raise ApprovalsError("E-ROUTE-STATE")
    try:
        return r.stdout.decode("utf-8")
    except UnicodeDecodeError:
        raise ApprovalsError("E-ROUTE-RECORD-INVALID")


def check_history(repo, ref):
    """用 git log 沿 ref 全部历史检查：approvals/ 下已有文件从未被修改、删除或改名；state 中已归档条目从未被改动。"""
    r = _git(repo, "log", "--format=%H", "--no-renames", "--diff-filter=MDT", ref, "--", CODEX_DIR, WANG_DIR)
    if r.returncode != 0:
        raise ApprovalsError("E-ROUTE-STATE")
    if r.stdout.strip():
        raise ApprovalsError("E-ROUTE-APPROVALS-REWRITTEN")
    r = _git(repo, "rev-list", "--reverse", ref, "--", STATE_FILE)
    if r.returncode != 0:
        raise ApprovalsError("E-ROUTE-STATE")
    for c in r.stdout.decode().split():
        pr = _git(repo, "rev-list", "--parents", "-n", "1", c)
        if pr.returncode != 0 or not pr.stdout.strip():
            raise ApprovalsError("E-ROUTE-STATE")         # git 失败不得跳过归档不可逆比较
        parents = pr.stdout.decode().split()[1:]
        for p in parents:
            old, new = show(repo, p, STATE_FILE), show(repo, c, STATE_FILE)
            if old:
                try:
                    od = loads_strict(old).get("drafts", {}); nd = loads_strict(new or "{}").get("drafts", {})
                except (ValueError, AttributeError):
                    raise ApprovalsError("E-ROUTE-STATE")
                for did, ds in od.items():
                    if isinstance(ds, dict) and ds.get("status") == "archived" and nd.get(did) != ds:
                        raise ApprovalsError("E-ROUTE-ARCHIVE-REVERTED")


def load_dir(repo, ref, d, validator):
    r = _git(repo, "ls-tree", "-z", "--name-only", f"{ref}:{d}")
    if r.returncode != 0:
        # 只有“ref 可读且该路径确实不存在”才算没有记录；其他读取失败一律 E-ROUTE-STATE（→ HOLD），不返回空
        t = _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{tree}}")
        p = _git(repo, "ls-tree", "--name-only", ref, "--", d) if t.returncode == 0 else None
        if p is not None and p.returncode == 0 and not p.stdout.strip():
            return []
        raise ApprovalsError("E-ROUTE-STATE")
    out = []
    for raw in r.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            name = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ApprovalsError("E-ROUTE-RECORD-INVALID")
        if name == ".gitkeep":
            continue
        out.append(parse_record(name, show(repo, ref, f"{d}/{name}") or "", validator, dated_ok=True))
    check_unique(out)
    return out


def check_unique(records):
    """同一 sha 同一可发布日（或同一 sha 的无日期文件）只能有一份；出现重复 → 判失败（整体验收 r12）。"""
    seen = set()
    for r in records:
        k = (r["content_sha256"], r.get("_for_date"))
        if k in seen:
            raise ApprovalsError("E-ROUTE-RECORD-INVALID")
        seen.add(k)


TEXT_FIELDS = ("quote", "quote_ref", "log_path", "draft_id")


def scan_internal(records, terms):
    """记录自由文本字段命中内部清单 → ApprovalsError。terms 为 None/空 → fail-closed。"""
    from .textnorm import compact
    if not terms:
        raise ApprovalsError("E-INTERNAL-LIST-MISSING")
    ct = [compact(t) for t in terms if compact(t)]
    for r in records:
        for k in TEXT_FIELDS:
            v = r.get(k)
            if isinstance(v, str) and any(t in compact(v) for t in ct):
                raise ApprovalsError("E-ROUTE-RECORD-INTERNAL")


def load_from_ref(repo, ref="origin/main"):
    """读取 ref 上的状态与两类记录。返回 (state 或 None, records)。records["error"] 为错误码或 None。
    r12：内部清单只认本机真实名单（不接受调用方替代值）。"""
    rec = {"codex": [], "wang": [], "error": None}
    internal_terms = load_internal_terms()
    if ref not in ALLOWED_REFS:
        return None, rec                # 其他分支/ref 一律不采信 → HOLD（E-ROUTE-STATE）
    try:
        st_text = show(repo, ref, STATE_FILE)
    except ApprovalsError:
        return None, rec
    try:
        state = loads_strict(st_text) if st_text is not None else None
    except ValueError:
        state = None
    try:
        check_history(repo, ref)
        rec["codex"] = load_dir(repo, ref, CODEX_DIR, valid_codex)
        rec["wang"] = load_dir(repo, ref, WANG_DIR, valid_wang)
        scan_internal(rec["codex"] + rec["wang"], internal_terms)
    except ApprovalsError as e:
        if e.code in ("E-ROUTE-STATE", "E-ROUTE-ARCHIVE-REVERTED"):
            return None, rec
        rec = {"codex": [], "wang": [], "error": e.code}
    return state, rec
