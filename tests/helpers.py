import atexit, hashlib, os, sys, tempfile
from pathlib import Path

# 测试临时目录：整个测试进程共用一个 TemporaryDirectory（本机放在 /workspace 下，可用 MARKJIN_TEST_TMP 覆盖；
# 其他环境如 CI 用系统默认临时目录），所有 mkdtemp / 子进程 TMPDIR 都落在它里面，进程退出时整体清理。
_root = os.environ.get("MARKJIN_TEST_TMP") or ("/workspace" if os.path.isdir("/workspace") and os.access("/workspace", os.W_OK) else None)
_TMP = tempfile.TemporaryDirectory(prefix="markjin-tests-", dir=_root)
tempfile.tempdir = _TMP.name
os.environ["TMPDIR"] = _TMP.name
atexit.register(_TMP.cleanup)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

DATE = "2026-01-05"
ARXIV_ID = "2610.00001"
XPOST_ID = "1234567890123"
DUMMY_INTERNAL = ["样例内部词甲", "样例内部词乙"]  # 测试用占位词，不是真实内部主题
FILES = {
    "arxiv/cs.AI.xml": f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id>"
                       "<summary>The model reaches 90% accuracy on MMLU. The method handles long documents well.</summary></entry></feed>",
    "x/01.json": f'{{"id": "{XPOST_ID}", "text": "release 2.0"}}',
    "fred/UNRATE.json": '{"series_id": "UNRATE", "realtime_start": "2026-01-02", "value": "4.2"}',
    # #32 r3：FRED 序列单位存档（series 接口元数据的最小形式），支持位置核对用它比对单位
    "fred/UNRATE.series.json": '{"id": "UNRATE", "units": "Percent", "units_short": "%"}',
}


def write_manifest(day, files):
    lines = [f"{hashlib.sha256(b.encode()).hexdigest()}  ./{r}" for r, b in files.items()]
    (day / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_repo(files=None):
    files = dict(FILES if files is None else files)
    d = Path(tempfile.mkdtemp())
    (d / ".git").mkdir()
    day = d / "raw" / DATE
    for rel, body in files.items():
        p = day / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    write_manifest(day, files)
    return d


ARXIV_LOC = "The model reaches 90% accuracy on MMLU."
FRED_LOC = '"series_id": "UNRATE", "realtime_start": "2026-01-02", "value": "4.2"'


def loc(text):
    """#32：原文支持位置标注。传 None 表示不写位置。"""
    return "" if text is None else f" 〔原文：{text}〕"


def arxiv_line(text="模型在 MMLU 上达到 90% 准确率。", locator=ARXIV_LOC):
    return f"- {text} — `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1{loc(locator)}"


def fred_line(text="UNRATE 为 4.2%。", locator=FRED_LOC):
    return f"- {text} — `raw/{DATE}/fred/UNRATE.json` · https://fred.stlouisfed.org/series/UNRATE{loc(locator)}"


def x_line(text="发布 2.0 版。"):
    return f"- {text} — `raw/{DATE}/x/01.json` · https://x.com/i/status/{XPOST_ID}"


def quote_line(q="The method handles long documents well.", raw="arxiv/cs.AI.xml", url=None):
    url = url or f"https://arxiv.org/abs/{ARXIV_ID}v1"
    return f"> 「{q}」 — `raw/{DATE}/{raw}` · {url}"


def source_line():
    return f"来源：`raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1"


# r12：内部清单只认本机真实名单（调用方不得传入替代值）；测试统一替换加载函数为占位词
import markjin.selfcheck as _sc_mod, markjin.approvals as _ap_mod  # noqa: E402
_sc_mod.load_internal_terms = lambda: list(DUMMY_INTERNAL)
_ap_mod.load_internal_terms = lambda: list(DUMMY_INTERNAL)


def evaluate_for_tests(sc, draft, state, records, now, pair=None, correction=None):
    """r16：只给测试用。生产代码不导入。按 route_pr 的同一组合（诊断 + 状态变更 + publishable）
    对内存里的记录求值；生产路径的 publishable 只由 route_pr 设置。"""
    from markjin import route as R
    from markjin.statechange import draft_change
    d = R._diagnose(sc, draft, state, records, now, pair, correction)
    if d.state in ("ARCHIVED", "DEFERRED") and "E-ROUTE-ARCHIVED-REUSE" not in d.codes:
        if d.state == "DEFERRED":
            d.state_change = draft_change(draft, "deferred", "I-DEFERRED", now)
        else:
            d.state_change = draft_change(draft, "archived", next(c for c in d.codes if c.startswith("A-")), now)
    d.publishable = d.state == "APPROVED"
    return d
