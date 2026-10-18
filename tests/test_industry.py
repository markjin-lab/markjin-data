"""路线图 v1.12 产业与经济数据自检（industry.py 与 selfcheck 接入）测试。样例只用中性词与占位序列。"""
import hashlib, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from helpers import make_repo, quote_line, fred_line, arxiv_line, DATE, FILES
from markjin.selfcheck import check_text
from markjin.codes import ERROR_CODES
from markjin import industry

TITLE = f"# 日报 {DATE}\n"
NEUTRAL = ["中性词甲", "样例短语乙", "Ⅻ"]   # 占位词，不是任何真实内部用语
SHA = "a" * 64
REPO = make_repo()
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def run(text, repo=None, **kw):
    kw.setdefault("link_checker", lambda u: True)
    return check_text(text, REPO if repo is None else repo, DATE, "daily", **kw)


def codes(r):
    return r["error_codes"]


def term_file(lines, where=None):
    d = Path(where or tempfile.mkdtemp())
    d.mkdir(parents=True, exist_ok=True)
    p = d / "terms.txt"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def fred_repo(extra):
    files = dict(FILES)
    files.update(extra)
    return make_repo(files)


class Codes(unittest.TestCase):
    def test_registered(self):
        for c in ("E-FRED-NOT-ARCHIVED", "E-BRANCH-METHOD-MISSING", "E-BRANCH-AGGREGATE", "E-CANDIDATE-DATA-CITED",
                  "E-INTERNAL-LABEL", "E-INTERNAL-TERM", "E-INTERNAL-TERM-LIST", "R-INDUSTRY-STRAINED"):
            self.assertIn(c, ERROR_CODES)


class Headings(unittest.TestCase):
    def test_section_whitelisted(self):
        for h in ("## 产业与经济数据", "## Industry and economic data", "### industry  and economic DATA"):
            r = run(TITLE + h + "\n" + quote_line())
            self.assertEqual(r["counts"]["free_text"], 0, h)
            self.assertNotIn("R-STRUCTURE", codes(r), h)
        r = run(TITLE + "## 产业数据杂谈\n" + quote_line())
        self.assertIn("R-STRUCTURE", codes(r))


class FredArchive(unittest.TestCase):
    def test_archived_code_passes(self):
        self.assertNotIn("E-FRED-NOT-ARCHIVED", codes(run(TITLE + fred_line())))
        self.assertNotIn("E-FRED-NOT-ARCHIVED", codes(run(TITLE + quote_line() + "\n对照序列（FRED UNRATE，月度）。")))

    def test_unarchived_code_fails(self):
        for ln in ("对照序列（FRED SAMPLEX1，月度）。", "见 https://fred.stlouisfed.org/series/samplex1 。",
                   "FRED：SAMPLEX1", "见 https://fred.stlouisfed.org/graph/?id=SAMPLEX1 。"):
            r = run(TITLE + quote_line() + "\n" + ln)
            self.assertEqual(r["status"], "FAIL", ln)
            self.assertIn("E-FRED-NOT-ARCHIVED", codes(r), ln)

    def test_non_code_words_ignored(self):
        self.assertEqual(industry.fred_codes("通过 FRED API 取数，FRED series 页面，FRED 2026 年度更新，FRED Q3"), [])
        self.assertNotIn("E-FRED-NOT-ARCHIVED", codes(run(TITLE + quote_line() + "\nFRED 2026 年度更新。")))

    def test_graph_link_all_ids(self):
        self.assertEqual(industry.fred_codes("https://fred.stlouisfed.org/graph/?g=1&id=UNRATE,SAMPLEX1&id=samplex2"),
                         ["UNRATE", "SAMPLEX1", "SAMPLEX2"])
        r = run(TITLE + quote_line() + "\n见 https://fred.stlouisfed.org/graph/?id=UNRATE,SAMPLEX1 。")
        self.assertIn("E-FRED-NOT-ARCHIVED", codes(r))
        # 紧跟标点或 Markdown 链接括号
        self.assertEqual(industry.fred_codes("见 https://fred.stlouisfed.org/graph/?id=SAMPLEX1。"), ["SAMPLEX1"])
        self.assertEqual(industry.fred_codes("[图](https://fred.stlouisfed.org/graph/?id=UNRATE,SAMPLEX1)"), ["UNRATE", "SAMPLEX1"])

    def test_bad_sha_future_date_other_series(self):
        body = '{"series_id": "SAMPLEX1", "observations": []}'
        good = fred_repo({"fred/SAMPLEX1.json": body})
        ln = TITLE + quote_line() + "\n对照序列（FRED SAMPLEX1，月度）。"
        self.assertNotIn("E-FRED-NOT-ARCHIVED", codes(run(ln, repo=good)))
        # 字节与 MANIFEST 不一致
        (good / "raw" / DATE / "fred" / "SAMPLEX1.json").write_text(body + " ", encoding="utf-8")
        self.assertIn("E-FRED-NOT-ARCHIVED", codes(run(ln, repo=good)))
        # 存档自报的是别的序列
        other = fred_repo({"fred/SAMPLEX1.json": '{"series_id": "SAMPLEX2", "observations": []}'})
        self.assertIn("E-FRED-NOT-ARCHIVED", codes(run(ln, repo=other)))
        # 只有晚于稿件日期的存档
        fut = make_repo()
        day = fut / "raw" / "2099-01-01"
        (day / "fred").mkdir(parents=True)
        (day / "fred" / "SAMPLEX1.json").write_text(body, encoding="utf-8")
        (day / "MANIFEST.sha256").write_text(f"{hashlib.sha256(body.encode()).hexdigest()}  ./fred/SAMPLEX1.json\n", encoding="utf-8")
        self.assertIn("E-FRED-NOT-ARCHIVED", codes(run(ln, repo=fut)))

    def test_round2_and_observations_archive(self):
        r2 = fred_repo({"round2/fred/SAMPLEX1.json": '{"observations": [{"date": "2026-01-01", "value": "1"}]}'})
        self.assertNotIn("E-FRED-NOT-ARCHIVED", codes(run(TITLE + quote_line() + "\nFRED SAMPLEX1", repo=r2)))


class Candidate(unittest.TestCase):
    def test_candidate_hosts(self):
        for ln in ("数据见 https://www.eia.gov/sample 。", "见 https://api.bea.gov/x?y=1", "https://data.stats.gov.cn/a",
                   f"见 `raw/{DATE}/sample-agency/a.json`", f"见 `raw/{DATE}/round2/sample-agency/a.json`"):
            r = run(TITLE + quote_line() + "\n" + ln)
            self.assertIn("E-CANDIDATE-DATA-CITED", codes(r), ln)
            self.assertEqual(r["status"], "FAIL", ln)

    def test_text_citation(self):
        for ln in ("据 EIA 数据，样例库存上升。", "国家统计局公布10月样例增加值为6.5%。", "According to BEA figures, the sample rose.",
                   "样例公司月度营收为 10 亿元。", "样例公司8月营收同比增长20%。",
                   "The National Bureau of Statistics reported sample output of 6.5%.", "The sample firm posted August revenue of 6.5 billion.",
                   "样例公司月度营收见 https://example.com/ir/monthly-revenue-2026-08 。", "详见 https://example.com/ir/monthly_sales"):
            self.assertIn("E-CANDIDATE-DATA-CITED", codes(run(TITLE + quote_line() + "\n" + ln)), ln)
            # 与正常来源配对的结构化断言同样拦
            self.assertIn("E-CANDIDATE-DATA-CITED", codes(run(TITLE + arxiv_line(ln))), ln)
        for ln in ("SEC 起诉了一家样例公司。", "财政部宣布一项样例政策。", "The BEAM model is fast.", "据财政部公告，样例新规明年生效。",
                   "财政部宣布 2027 年起实施样例新规。", "样例公司将于下周公布 8 月营收。"):
            self.assertFalse(industry.candidate_cited(ln), ln)

    def test_verified_quote_exempt_from_text_checks(self):
        aid = "2610.00009"
        body = (f"<feed><entry><id>http://arxiv.org/abs/{aid}v1</id><summary>We train on EIA data for the sample grid. "
                "If the sample condition fails, this classification does not hold.</summary></entry></feed>")
        files = dict(FILES)
        files["arxiv/cs.LG.xml"] = body
        repo = make_repo(files)
        url = f"https://arxiv.org/abs/{aid}v1"
        for q in ("We train on EIA data for the sample grid.", "If the sample condition fails, this classification does not hold."):
            r = run(TITLE + quote_line(q, raw="arxiv/cs.LG.xml", url=url), repo=repo)
            self.assertNotIn("E-CANDIDATE-DATA-CITED", codes(r), q)
            self.assertNotIn("E-INTERNAL-LABEL", codes(r), q)
        # 同样的话不作逐字直引（转述）照拦
        r = run(TITLE + quote_line() + "\n作者用 EIA 数据训练。\n若样例条件不满足，此归类不成立。", repo=repo)
        self.assertIn("E-CANDIDATE-DATA-CITED", codes(r))
        self.assertIn("E-INTERNAL-LABEL", codes(r))

    def test_regular_sources_not_flagged(self):
        for ln in ("https://notbea.gov/a", "https://example.org/eia.gov", f"`raw/{DATE}/fulltext/a.md`"):
            self.assertFalse(industry.candidate_cited(ln), ln)
        self.assertNotIn("E-CANDIDATE-DATA-CITED", codes(run(TITLE + arxiv_line() + "\n" + fred_line())))


class Label(unittest.TestCase):
    def test_sentence_pattern(self):
        for ln in ("若样例条件不满足，此归类不成立。", "若样例条件不满足，则此分类就不成立。",
                   "If the sample condition fails, this classification does not hold."):
            r = run(TITLE + quote_line() + "\n" + ln)
            self.assertIn("E-INTERNAL-LABEL", codes(r), ln)
        r = run(TITLE + quote_line() + "\n若样例条件\n不满足，此归类不成立。")
        self.assertIn("E-INTERNAL-LABEL", codes(r))

    def test_neutral_text(self):
        for t in ("若样例条件满足，结果成立。该分类方法见论文第 3 节。", "模型的内部分类器效果更好。",
                  "The internal classification layers are frozen."):
            self.assertFalse(industry.internal_label(t), t)
        self.assertTrue(industry.internal_label("样例条目的内部分类标签"))


class InternalTerm(unittest.TestCase):
    def setUp(self):
        os.environ.pop(industry.ENV_PRIVATE_TERMS, None)

    tearDown = setUp

    def test_skipped_without_list(self):
        r = run(TITLE + quote_line())
        self.assertEqual(r["internal_term_check"], "skipped")
        self.assertNotIn("E-INTERNAL-TERM", codes(r))
        r = run(TITLE + quote_line(), private_terms=str(Path(tempfile.mkdtemp()) / "missing.txt"))
        self.assertEqual(r["internal_term_check"], "skipped")

    def test_hits_count_only(self):
        p = term_file(NEUTRAL)
        r = run(TITLE + quote_line() + "\n这里有中性词甲。\n还有中 性 词 甲与样例短语乙。", private_terms=str(p))
        self.assertEqual(r["internal_term_check"], "loaded")
        self.assertEqual(r["internal_term_hits"], 2)
        self.assertEqual(sum(1 for e in r["errors"] if e["code"] == "E-INTERNAL-TERM"), 2)
        self.assertTrue(all(e["line"] == 0 for e in r["errors"] if e["code"] == "E-INTERNAL-TERM"))
        dump = json.dumps(r, ensure_ascii=False)
        for t in NEUTRAL:
            self.assertNotIn(t, dump)
        self.assertEqual(r["status"], "FAIL")

    def test_env_var_and_cross_line(self):
        os.environ[industry.ENV_PRIVATE_TERMS] = str(term_file(NEUTRAL))
        r = run(TITLE + quote_line() + "\n样例短\n语乙")
        self.assertEqual(r["internal_term_hits"], 1)

    def test_compat_characters_not_folded(self):
        p = str(term_file(NEUTRAL))
        self.assertEqual(run(TITLE + quote_line() + "\n版本 XII 发布。", private_terms=p)["internal_term_hits"], 0)
        self.assertEqual(run(TITLE + quote_line() + "\n版本 Ⅻ 发布。", private_terms=p)["internal_term_hits"], 1)
        self.assertEqual(run(TITLE + quote_line() + "\n版本 ⅻ 发布。", private_terms=p)["internal_term_hits"], 0)

    def test_list_in_git_repo_or_checked_repo_rejected(self):
        g = Path(tempfile.mkdtemp())
        (g / ".git").mkdir()
        for p in (term_file(NEUTRAL, g / "sub"), term_file(NEUTRAL, REPO / "private")):
            r = run(TITLE + quote_line(), private_terms=str(p))
            self.assertIn("E-INTERNAL-TERM-LIST", codes(r))
            self.assertEqual(r["internal_term_check"], "error")
            self.assertEqual(r["status"], "FAIL")

    def test_symlink_list_rejected(self):
        real = term_file(NEUTRAL)
        d = Path(tempfile.mkdtemp())
        (d / "link.txt").symlink_to(real)
        (d / "dirlink").symlink_to(real.parent, target_is_directory=True)
        for p in (d / "link.txt", d / "dirlink" / "terms.txt", d / "dirlink" / ".." / Path(d.name) / "link.txt",
                  real.parent / ".." / real.parent.name / "terms.txt"):
            r = run(TITLE + quote_line(), private_terms=str(p))
            self.assertIn("E-INTERNAL-TERM-LIST", codes(r), p)
            self.assertEqual(r["internal_term_check"], "error")

    def test_empty_or_bad_list_rejected(self):
        for body in (b"\n  \n", b"\xff\xfe"):
            d = Path(tempfile.mkdtemp())
            (d / "t.txt").write_bytes(body)
            self.assertIn("E-INTERNAL-TERM-LIST", codes(run(TITLE + quote_line(), private_terms=str(d / "t.txt"))))
        self.assertIn("E-INTERNAL-TERM-LIST", codes(run(TITLE + quote_line(), private_terms=tempfile.mkdtemp())))

    def test_cli_reports_without_terms(self):
        repo = make_repo()
        draft = repo / "daily" / f"{DATE}.md"
        draft.parent.mkdir()
        draft.write_text(TITLE + quote_line() + "\n这里有中性词甲。\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != industry.ENV_PRIVATE_TERMS}
        base = [sys.executable, str(SCRIPTS / "selfcheck.py"), str(draft), "--repo", str(repo), "--date", DATE,
                "--card-type", "daily", "--no-link-check"]
        out = subprocess.run(base + ["--private-terms", str(term_file(NEUTRAL))], capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 1)
        self.assertIn("命中 1", out.stdout)
        for t in NEUTRAL:
            self.assertNotIn(t, out.stdout + out.stderr)
        out = subprocess.run(base, capture_output=True, text=True, env=env)
        self.assertIn("已跳过", out.stdout)


ARCH_BODY = '{"series_id": "IPG2211S", "observations": [{"date": "2026-09-01", "value": "100.0"}]}'
ARCH_SHA = hashlib.sha256(ARCH_BODY.encode()).hexdigest()
BREPO = fred_repo({"fred/IPG2211S.json": ARCH_BODY})


def branch(**kw):
    row = {"observed_variable": "IPG2211S 2026 年 10 月读数的同比（%，(本期/上年同期−1)×100，保留两位小数，季调序列）",
           "unit": "%", "data_source": "FRED IPG2211S",
           "endpoint_method": "a = 近 12 期同比的 25% 分位数，b = 近 12 期同比的 75% 分位数",
           "input_version": "realtime_start 2026-10-17", "raw_sha256": [ARCH_SHA], "date": DATE}
    row.update(kw)
    return row


def cb(row, repo=None):
    return industry.check_branch(row, BREPO if repo is None else repo)


class Branch(unittest.TestCase):
    def test_complete_row(self):
        self.assertEqual(cb(branch()), [])
        self.assertEqual(cb(branch(raw_sha256=ARCH_SHA)), [])

    def test_method_missing(self):
        bad = [dict(observed_variable="IPG2211S 读数的同比（%，(本期/上年同期−1)×100，保留两位小数，季调序列）"),   # 无目标观测期
               dict(observed_variable="IPG2211S 2026 年 10 月读数（%，保留两位小数，季调序列）"),                  # 无公式、基期
               dict(observed_variable="IPG2211S 2026 年 10 月读数的同比（%，(本期/上年同期−1)×100，季调序列）"),  # 无舍入
               dict(observed_variable="IPG2211S 2026 年 10 月读数的同比（%，(本期/上年同期−1)×100，保留两位小数）"),  # 无季调口径
               dict(observed_variable="IPG2211S 2026 年 10 月读数（公式，基期，季调，保留两位小数）"),          # 只有关键词
               dict(data_source="FRED SAMPLEX1"), dict(data_source="样例机构"),                                  # 来源与观测变量不符
               dict(unit=""), dict(unit="NA"), dict(unit="无"), dict(endpoint_method=""), dict(endpoint_method=None),
               dict(endpoint_method="按样例分位数方法计算端点"), dict(endpoint_method="a=1，b=2"),               # 没写计算式 / 裸数值
               dict(input_version="最新"), dict(input_version="2026-10-17"), dict(input_version="发布 2026-99-99"),
               dict(raw_sha256=[]), dict(raw_sha256=["xyz"]), dict(raw_sha256=None),
               dict(raw_sha256=[SHA]), dict(raw_sha256=[ARCH_SHA, SHA])]                                        # 未登记的原件
        for kw in bad:
            self.assertIn("E-BRANCH-METHOD-MISSING", cb(branch(**kw)), kw)
        self.assertIn("E-BRANCH-METHOD-MISSING", cb(None))
        self.assertIn("E-BRANCH-METHOD-MISSING", cb(branch(), repo=make_repo()))          # 仓库里没有该序列存档
        self.assertIn("E-BRANCH-METHOD-MISSING", cb(branch(date="2026-01-01")))           # 只有晚于登记日的存档
        for d in (None, "", "bogus", "2026-99-99"):                                         # 登记日缺失或无效
            row = branch(); row.pop("date") if d is None else row.update(date=d)
            self.assertIn("E-BRANCH-METHOD-MISSING", cb(row), d)
        for ep in ("a = 样例方法 1", "a = 样例方法 1，b = 样例方法 2", "a = 近 12 期同比的 25% 分位数，b = 样例方法 2"):
            self.assertIn("E-BRANCH-METHOD-MISSING", cb(branch(endpoint_method=ep)), ep)
        for ep in ("a = 上期读数 × (1 + 2%)", "a = last 12 months mean minus 1.5 standard deviation"):
            self.assertEqual(cb(branch(endpoint_method=ep)), [], ep)

    def test_aggregate(self):
        for kw in (dict(data_source="FRED INDPRO"),
                   dict(observed_variable="TCU 2026 年 10 月读数的环比（%，(本期/上期−1)×100，保留两位小数，季调序列）")):
            self.assertIn("E-BRANCH-AGGREGATE", cb(branch(**kw)), kw)
        self.assertNotIn("E-BRANCH-AGGREGATE", cb(branch(data_source="FRED TCUX")))
        self.assertNotIn("E-BRANCH-AGGREGATE", cb(branch()))


class Strained(unittest.TestCase):
    def test_count(self):
        self.assertEqual(industry.strained_count("VERDICT zh: APPROVED\nR-INDUSTRY-STRAINED: 2\n"), 2)
        self.assertIsNone(industry.strained_count("VERDICT zh: APPROVED\n"))
        self.assertIsNone(industry.strained_count("R-INDUSTRY-STRAINED: 1\nR-INDUSTRY-STRAINED: 3"))
        self.assertIsNone(industry.strained_count("R-INDUSTRY-STRAINED: 2\nR-INDUSTRY-STRAINED: 2"))
        self.assertIsNone(industry.strained_count(None))

    def test_record_to_ledger(self):
        repo = make_repo()
        (repo / "review" / "ledger").mkdir(parents=True)
        self.assertIsNone(industry.record_strained(repo, DATE, "VERDICT zh: APPROVED\n"))
        p = industry.record_strained(repo, DATE, "VERDICT zh: APPROVED\nR-INDUSTRY-STRAINED: 3\n")
        self.assertEqual([json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()],
                         [{"count": 3, "date": DATE, "error_code": "R-INDUSTRY-STRAINED"}])

    def test_cli(self):
        repo = make_repo()
        (repo / "review" / "ledger").mkdir(parents=True)
        res = Path(tempfile.mkdtemp()) / "result.txt"
        cmd = [sys.executable, str(SCRIPTS / "record-industry-strained.py"), str(res), "--repo", str(repo), "--date", DATE]
        res.write_text("VERDICT zh: APPROVED\n", encoding="utf-8")
        self.assertEqual(subprocess.run(cmd, capture_output=True, text=True).returncode, 1)
        self.assertFalse((repo / "review" / "ledger" / f"{DATE}.jsonl").exists())
        res.write_text("VERDICT zh: APPROVED\nR-INDUSTRY-STRAINED: 0\n", encoding="utf-8")
        self.assertEqual(subprocess.run(cmd, capture_output=True, text=True).returncode, 0)
        rows = [json.loads(l) for l in (repo / "review" / "ledger" / f"{DATE}.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows, [{"count": 0, "date": DATE, "error_code": "R-INDUSTRY-STRAINED"}])


if __name__ == "__main__":
    unittest.main()
