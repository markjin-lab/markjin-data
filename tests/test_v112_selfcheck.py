"""路线图 v1.12 自检：产业与经济数据小节白名单；FRED 撤回后不得新增 FRED 链接或数据（E-FRED-CITED）。"""
import hashlib, tempfile, unittest
from pathlib import Path
from helpers import make_repo, fred_line, arxiv_line, DATE, ARXIV_ID
from markjin.selfcheck import check_text
from markjin.codes import ERROR_CODES

NEW = "2026-10-19"
CUT = "2026-10-18"
SUMMARY = "We use monthly FRED data for the method. The model reaches 90% accuracy on MMLU."


def repo_for(day, files):
    d = Path(tempfile.mkdtemp())
    (d / ".git").mkdir()
    root = d / "raw" / day
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    (root / "MANIFEST.sha256").write_text(
        "".join(f"{hashlib.sha256(b.encode()).hexdigest()}  ./{r}\n" for r, b in files.items()), encoding="utf-8")
    return d


def files_for():
    return {"arxiv/cs.AI.xml": f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id><summary>{SUMMARY}</summary></entry></feed>",
            "fred/UNRATE.json": '{"series_id": "UNRATE", "realtime_start": "2026-01-02", "value": "4.2"}'}


OLD_REPO = make_repo()
NEW_REPO = repo_for(NEW, files_for())
CUT_REPO = repo_for(CUT, files_for())


def run(text, date, repo):
    return check_text(text, repo, date, "daily", link_checker=lambda u: True)


def arx(day, text="模型在 MMLU 上达到 90% 准确率。"):
    return f"- {text} — `raw/{day}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1"


def fred(day, text="UNRATE 为 4.2%。"):
    return f"- {text} — `raw/{day}/fred/UNRATE.json` · https://fred.stlouisfed.org/series/UNRATE"


class IndustryHeading(unittest.TestCase):
    def test_heading_whitelisted(self):
        for h in ("## 产业与经济数据", "## Industry and economic data", "## industry and economic  data"):
            r = run(f"# 日报 {DATE}\n{h}\n" + arxiv_line(), DATE, OLD_REPO)
            self.assertEqual(r["counts"]["free_text"], 0, (h, r["error_codes"]))
            self.assertEqual(r["status"], "PASS", r["error_codes"])

    def test_other_heading_still_free_text(self):
        r = run(f"# 日报 {DATE}\n## 产业与经济数据观察\n" + arxiv_line(), DATE, OLD_REPO)
        self.assertEqual(r["counts"]["free_text"], 1)

    def test_heading_with_link_not_exempt(self):
        r = run(f"# 日报 {DATE}\n## 产业与经济数据 https://www.bls.gov/cpi/\n" + arxiv_line(), DATE, OLD_REPO)
        self.assertIn("E-REPLAY-005", r["error_codes"])


class FredCited(unittest.TestCase):
    def fail(self, r):
        self.assertEqual(r["status"], "FAIL", r["error_codes"])
        self.assertIn("E-FRED-CITED", r["error_codes"])

    def absent(self, r):
        self.assertNotIn("E-FRED-CITED", r["error_codes"])

    def test_code_registered(self):
        self.assertIn("E-FRED-CITED", ERROR_CODES)

    def test_link_and_raw_path_new_draft(self):
        self.fail(run(f"# 日报 {NEW}\n" + fred(NEW), NEW, NEW_REPO))
        self.fail(run(f"# 日报 {CUT}\n" + fred(CUT), CUT, CUT_REPO))
        for s in ("数据见 fred.stlouisfed.org/series/UNRATE 。", "见 https://alfred.stlouisfed.org/series?seid=UNRATE",
                  "见 https://api.stlouisfed.org/fred/series/observations", "见 https://research.stlouisfed.org/fred2/series/UNRATE",
                  "见 `raw/2026-10-19/round2/fred/UNRATE.json`", "见 HTTPS://FRED.STLOUISFED.ORG/graph/?id=PAYEMS"):
            self.fail(run(f"# 日报 {CUT}\n" + arx(CUT) + "\n" + s, CUT, CUT_REPO))

    def test_old_draft_unchanged(self):
        # 截止日以前的稿件（测试基线日期）照旧走 FRED 存档回放，不报 E-FRED-CITED
        r = run(f"# 日报 {DATE}\n" + fred_line(), DATE, OLD_REPO)
        self.absent(r)
        self.assertEqual(r["status"], "PASS", r["error_codes"])

    def test_correction_of_old_draft(self):
        # 更正稿不论 corrected_at 填什么（含截止日以前的日期）都检查；文字与链接都拦
        for corr in ("2026-10-18", "'2026-10-19'", "2026-10-17", "2026-01-05"):
            fm = f"---\ntitle: x\ncorrects: daily-2026-01-05\ncorrected_at: {corr}\n---\n"
            self.fail(run(fm + f"# 日报 {DATE}\n" + fred_line(), DATE, OLD_REPO))
            self.fail(run(fm + f"# 日报 {DATE}\n" + arxiv_line() + "\nFRED data 显示 4.2%。", DATE, OLD_REPO))
        fm = "---\ntitle: x\ncorrects: daily-2026-01-05\n---\n"
        self.fail(run(fm + f"# 日报 {DATE}\n" + arxiv_line() + "\nFRED data。", DATE, OLD_REPO))
        # 非更正的旧稿照旧
        fm = "---\ntitle: x\n---\n"
        self.absent(run(fm + f"# 日报 {DATE}\n" + fred_line(), DATE, OLD_REPO))

    def test_unparseable_front_matter_strict(self):
        fm = "---\ntitle: [unclosed\n---\n"
        self.fail(run(fm + f"# 日报 {DATE}\n" + fred_line(), DATE, OLD_REPO))

    def test_word_new_draft(self):
        for day, repo in ((NEW, NEW_REPO), (CUT, CUT_REPO)):
            for s in ("UNRATE 为 4.2%（FRED）。", "据 ALFRED 的版本数据。", "论文用的是 FRED-MD 数据集。",
                      "Data from Federal Reserve Economic Data.", "数据取自圣路易斯联储经济数据库。",
                      "UNRATE 为 4.2%（ＦＲＥＤ）。", "UNRATE 为 4.2%（FR\u200bED）。", "UNRATE 为 4.2%（FRE\ufe0fD）。",
                      "UNRATE 为 4.2%（F\u034fRED）。", "<!-- FRED -->", "| 来源 | FRED |", "## FRED 数据"):
                self.fail(run(f"# 日报 {day}\n" + arx(day) + "\n" + s, day, repo))

    def test_cross_line(self):
        fm = "---\ntitle: x\nsummary: >\n  data from Federal Reserve\n  Economic Data\n---\n"
        self.fail(run(fm + f"# 日报 {NEW}\n" + arx(NEW), NEW, NEW_REPO))
        self.fail(run(f"# 日报 {NEW}\n" + arx(NEW) + "\n数据取自圣路易斯联储\n经济数据。", NEW, NEW_REPO))

    def test_word_not_matched(self):
        for s in ("Fred Smith 发布了新模型。", "FREDDIE 不相干。", "数据取自 Federal Reserve Board。"):
            self.absent(run(f"# 日报 {NEW}\n" + arx(NEW) + "\n" + s, NEW, NEW_REPO))

    def test_old_digest_meta_line_only_on_correction(self):
        line = "- FRED：本期未选用（raw/2026-10-15/fred/ 五个序列已采集，无需单列）。"
        self.absent(run(f"# 日报 {DATE}\n" + arxiv_line() + "\n" + line, DATE, OLD_REPO))
        fm = "---\ntitle: x\ncorrects: daily-2026-01-05\ncorrected_at: 2026-10-19\n---\n"
        self.fail(run(fm + f"# 日报 {DATE}\n" + arxiv_line() + "\n" + line, DATE, OLD_REPO))

    def test_verbatim_quote_not_exempt(self):
        q = f"> 「We use monthly FRED data for the method.」 — `raw/{NEW}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1"
        self.fail(run(f"# 日报 {NEW}\n" + q, NEW, NEW_REPO))
        ok = f"> 「The model reaches 90% accuracy on MMLU.」 — `raw/{NEW}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1"
        r = run(f"# 日报 {NEW}\n" + ok, NEW, NEW_REPO)
        self.absent(r)
        self.assertEqual(r["status"], "PASS", r["error_codes"])


if __name__ == "__main__":
    unittest.main()
