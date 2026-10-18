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


# #87 撤回、不在 fred/ 目录下的三个文件（#90 r2 MEDIUM；Issue #92 起由 RETRACTIONS 读取，并在内置底线清单中）
OLD_SHA = "f771767be92964e118712144856a32d9b2e4d1a2"   # #87 合并前的 main，三个文件仍在
RETRACTED = ("raw/2026-10-11/nbs-gdp/fred-CHNGDPNQDSMEI.csv",
             "raw/2026-10-11/nbs-gdp/annual-reconciliation.csv",
             "raw/2026-10-11/nbs-gdp/annual-reconciliation.md")
KEPT = ("raw/2026-10-11/nbs-gdp/nbs-t20260716_1964142.html", "raw/2026-10-11/nbs-gdp/PROVENANCE.md",
        "raw/2026-10-11/nbs-gdp/README.md", "raw/2026-10-11/nbs-gdp/query-log.jsonl")
ORG = "markjin-lab/markjin-data"


def forms(path):
    return {"blob": f"https://github.com/{ORG}/blob/{OLD_SHA}/{path}",
            "blob-short": f"https://github.com/{ORG}/blob/{OLD_SHA[:7]}/{path}#L2",
            "raw": f"https://raw.githubusercontent.com/{ORG}/{OLD_SHA}/{path}",
            "github-raw": f"https://github.com/{ORG}/raw/{OLD_SHA}/{path}",
            "relative": f"`{path}`",
            "relative-up": f"[见存档](../{path})"}


class FredRetractedPaths(unittest.TestCase):
    def codes(self, s, date=NEW, repo=None, fm=""):
        repo = repo or NEW_REPO
        # 链接写在带 arxiv 来源的断言行里：修复前 blob、raw 两种链接此写法自检为 PASS（#90 r2 复现）
        return run(fm + f"# 日报 {date}\n" + arx(date, f"模型在 MMLU 上达到 90% 准确率（对照 {s}）。"), date, repo)

    def test_paths_in_baseline(self):
        from markjin.selfcheck import FRED_RETRACTED_BASELINE
        self.assertTrue(set(RETRACTED) <= set(FRED_RETRACTED_BASELINE))

    def test_blob_raw_and_relative_blocked(self):
        for path in RETRACTED:
            for kind, s in forms(path).items():
                for date, repo in ((NEW, NEW_REPO), (CUT, CUT_REPO)):
                    r = self.codes(s, date, repo)
                    self.assertEqual(r["status"], "FAIL", (path, kind, r["error_codes"]))
                    self.assertIn("E-FRED-CITED", r["error_codes"], (path, kind))

    def test_case_and_invisible_chars(self):
        for s in (forms(RETRACTED[2])["blob"].upper().replace("HTTPS://GITHUB.COM", "https://github.com"),
                  forms(RETRACTED[1])["raw"].replace("annual-", "annual-\ufe0f")):
            self.assertIn("E-FRED-CITED", self.codes(s)["error_codes"], s)

    def test_correction_of_old_draft(self):
        fm = "---\ntitle: x\ncorrects: daily-2026-01-05\ncorrected_at: 2026-10-17\n---\n"
        for path in RETRACTED:
            for kind in ("blob", "raw", "relative"):
                r = self.codes(forms(path)[kind], DATE, OLD_REPO, fm)
                self.assertIn("E-FRED-CITED", r["error_codes"], (path, kind))

    def test_other_nbs_gdp_files_not_blocked(self):
        # 正常引用其他 nbs-gdp 文件不误拦（只看 E-FRED-CITED；其他回放规则另由现有检查负责）
        for path in KEPT:
            for kind, s in forms(path).items():
                r = self.codes(s)
                self.assertNotIn("E-FRED-CITED", r["error_codes"], (path, kind))
                if kind != "relative":                       # 反引号相对路径另受回放规则（E-REPLAY-006）约束，与本项无关
                    self.assertEqual(r["status"], "PASS", (path, kind, r["error_codes"]))
        for s in ("raw/2026-10-11/nbs-gdp/annual-reconciliation-notes.txt", "raw/2026-10-19/nbs-gdp/annual-reconciliation.csv",
                  "raw/2026-10-11/nbs-gdp/CHNGDPNQDSMEI.html", "国家统计局年度核算（annual reconciliation）"):
            self.assertNotIn("E-FRED-CITED", self.codes(f"`{s}`")["error_codes"], s)


# —— #90 r4（r3 MEDIUM）：撤回路径按完整路径段匹配，相似文件名、其他日期目录不误拦
class FredRetractedBoundary(unittest.TestCase):
    codes = FredRetractedPaths.codes

    def test_suffix_and_other_names_not_blocked(self):
        for path in RETRACTED:
            for suf in (".notes", ".bak", ".orig", "x", "2", "-old", "_v2", "/README.md", ".d/x"):
                for kind in ("blob", "raw", "github-raw", "relative", "relative-up"):
                    s = forms(path + suf)[kind]
                    self.assertNotIn("E-FRED-CITED", self.codes(s)["error_codes"], s)
        for s in ("raw/2026-10-11/nbs-gdp/annual-reconciliation.csv.notes", "raw/2026-10-11/nbs-gdp/annual-reconciliation.md.bak",
                  "raw/2026-10-11/nbs-gdp/fred-CHNGDPNQDSMEI.csv.notes", "raw/2026-10-11/nbs-gdp/annual-reconciliation.mdx",
                  "见 raw/2026-10-11/nbs-gdp/annual-reconciliation.md.bak。", "xraw/2026-10-11/nbs-gdp/annual-reconciliation.csv",
                  "draw/2026-10-11/nbs-gdp/annual-reconciliation.md", "my_raw/2026-10-11/nbs-gdp/annual-reconciliation.md"):
            self.assertNotIn("E-FRED-CITED", self.codes(s)["error_codes"], s)

    def test_other_date_dirs_not_blocked(self):
        for day in ("2026-10-10", "2026-10-12", "2026-10-18", "2026-10-19", "2025-10-11"):
            for path in RETRACTED:
                p2 = path.replace("2026-10-11", day)
                for kind, s in forms(p2).items():
                    self.assertNotIn("E-FRED-CITED", self.codes(s)["error_codes"], (p2, kind))
        for s in ("raw/2026-10-111/nbs-gdp/annual-reconciliation.csv", "raw/2026-10-11-old/nbs-gdp/annual-reconciliation.csv",
                  "raw/2026-10-11/nbs-gdp-old/annual-reconciliation.csv", "raw/x2026-10-11/nbs-gdp/annual-reconciliation.csv"):
            self.assertNotIn("E-FRED-CITED", self.codes(s)["error_codes"], s)

    def test_anchor_query_and_punctuation_blocked(self):
        for path in RETRACTED:
            for s in (forms(path)["blob"] + "#L10", forms(path)["blob"] + "#L10-L12", forms(path)["raw"] + "?raw=1",
                      forms(path)["github-raw"] + "#L10", f"见 {path}#L10 。", f"见 {path}。", f"见 {path}，另见", f"见 {path}.",
                      f"（{path}）", f"「{path}」", f'"{path}"', f"'{path}'", f"<{forms(path)['blob']}>", f"**{path}**",
                      f"| {path} |", f"见 {path}；", f"见 {path}: 第 2 行", f"[存档]({path}#L10)", path):
                r = self.codes(s)
                self.assertEqual(r["status"], "FAIL", (s, r["error_codes"]))
                self.assertIn("E-FRED-CITED", r["error_codes"], s)


# —— #90 r4：E-FRED-CITED 只查和 base（main）相比新增或改动的行；更正节里逐字等于固定写法的撤回说明行不报
NOTE = ("*补充说明（2026-10-18）：原 FRED raw 文件已撤回（见 raw/2026-10-15/RETRACTIONS.md，data PR #87）；"
        "上文采集范围描述的是撤回前的历史，本期未选用 FRED 数据。*")
OLD_META = "- FRED：本期未选用（raw/2026-10-15/fred/ 五个序列已采集，无需单列）。"


def digest(meta=OLD_META, tail=""):
    return f"# 日报 {NEW}\n\n{meta}\n\n" + arx(NEW) + "\n\n## 出处\n\n1. 论文页\n" + tail


def run_base(text, base, date=NEW, repo=None):
    return check_text(text, repo or NEW_REPO, date, "daily", link_checker=lambda u: True, base_text=base)


OLD_HEAD = "\n## 更正 2026-10-18：本次修订的具体内容见下方更正说明。\n\n*更正说明（2026-10-18）：只改措辞。*\n"
NEW_HEAD = "\n## 更正\n\n**2026-10-18**：只改措辞。\n"


class FredChangedLines(unittest.TestCase):
    def fred_lines(self, r):
        return [e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"]

    def test_unchanged_old_line_not_reported(self):
        base = digest()
        self.assertEqual(self.fred_lines(run_base(base, base)), [])
        new = base.replace("1. 论文页", "1. arXiv 论文页")          # 只改别处
        self.assertEqual(self.fred_lines(run_base(new, base)), [])
        self.assertEqual(self.fred_lines(run_base(base, None)), [3])   # 取不到 base：全部行都查
        self.assertEqual(self.fred_lines(run_base(new, digest(meta="- 其他说明。"))), [3])   # 该行在 base 上不存在 = 新增
        self.assertEqual(self.fred_lines(run_base(new.replace("五个序列", "5 个序列"), base)), [3])   # 改动的行照查

    def test_cross_line_unchanged_not_reported_new_reported(self):
        base = digest(meta="数据取自圣路易斯联储\n经济数据。")
        self.assertEqual(self.fred_lines(run_base(base + "\n新增一行。", base)), [])
        new = digest(meta="数据取自圣路易斯联储\n经济数据库。")
        self.assertEqual(self.fred_lines(run_base(new, base)), [0])
        base2 = digest(meta="数据取自圣路易斯联储\n其他。")
        self.assertEqual(self.fred_lines(run_base(digest(meta="数据取自圣路易斯联储\n经济数据。"), base2)), [0])

    def test_new_line_citing_fred_dir_reported(self):
        base = digest(meta="- 其他说明。")
        for add in ("见 `raw/2026-10-19/fred/UNRATE.json`。", fred(NEW), "见 raw/2026-10-15/fred/UNRATE.json 。",
                    "见 https://fred.stlouisfed.org/series/UNRATE", "见 raw/2026-10-11/nbs-gdp/annual-reconciliation.csv#L10"):
            for tail in ("", OLD_HEAD, NEW_HEAD):
                new = digest(meta="- 其他说明。", tail=tail + "\n" + add + "\n")
                r = run_base(new, base)
                self.assertIn("E-FRED-CITED", r["error_codes"], (add, tail))
                self.assertEqual(r["status"], "FAIL", (add, r["error_codes"]))

    def test_note_exempt_in_correction_section(self):
        base = digest(meta="- 其他说明。")
        for head in (OLD_HEAD, NEW_HEAD, "\n## Corrections\n\n**2026-10-18**: wording only.\n",
                     "\n## Correction 2026-10-18: see below.\n"):
            for day in ("2026-10-15", "2026-10-18", "2026-10-10"):
                note = NOTE.replace("2026-10-15", day)
                new = digest(meta="- 其他说明。", tail=head + "\n" + note + "\n")
                self.assertEqual(self.fred_lines(run_base(new, base)), [], (head, day))
                self.assertEqual(self.fred_lines(run_base(new, None)), [], (head, day))   # 不和 base 比时同样豁免

    def test_note_variants_reported(self):
        base = digest(meta="- 其他说明。")
        variants = [
            NOTE.replace("历史，", "历史，，"), NOTE.replace("本期未选用", "本期也未选用"),          # 多一个字
            NOTE.replace("采集范围", "“已采集”"),                                                  # #89 当前写法
            NOTE.replace("PR #87", "PR #88"), NOTE.replace("PR #87", "PR #870"), NOTE.replace("data PR", "Data PR"),
            NOTE.replace("2026-10-15", "2026-1-15"), NOTE.replace("2026-10-15", "2026/10/15"),
            NOTE.replace("2026-10-15", "20261015"), NOTE.replace("2026-10-15", "2026-13-01"),
            NOTE.replace("2026-10-15", "2026-02-30"), NOTE.replace("2026-10-15", "<日期>"),
            NOTE.replace("（2026-10-18）", "（2026-10-19）"),
            NOTE.replace("（见", "(见"), NOTE.replace("RETRACTIONS.md", "RETRACTIONS.MD"),
            NOTE.strip("*"), "*" + NOTE + "*", " " + NOTE, NOTE + " ", "- " + NOTE, "> " + NOTE, NOTE + "另见 FRED。",
            NOTE.replace("FRED raw", "FRED\u200b raw"), NOTE.replace("FRED raw", "FRED\ufe0f raw"),
        ]
        for v in variants:
            for head in (OLD_HEAD, NEW_HEAD):
                new = digest(meta="- 其他说明。", tail=head + "\n" + v + "\n")
                r = run_base(new, base)
                self.assertIn("E-FRED-CITED", r["error_codes"], (v, head))

    def test_note_outside_correction_section_reported(self):
        base = digest(meta="- 其他说明。")
        for new in (digest(meta=NOTE),                                                          # 不在更正节（正文开头）
                    digest(meta="- 其他说明。", tail="\n" + NOTE + "\n"),                          # 「## 出处」节里
                    digest(meta="- 其他说明。", tail=OLD_HEAD + "\n## 附录\n\n" + NOTE + "\n"),     # 更正节之后另起标题
                    digest(meta="- 其他说明。", tail=NEW_HEAD + "\n附录\n---\n\n" + NOTE + "\n"),  # Setext 标题结束更正节
                    digest(meta="- 其他说明。", tail="\n## 更正说明\n\n" + NOTE + "\n"),          # 不是更正标题
                    digest(meta="- 其他说明。", tail="\n### 更正\n\n" + NOTE + "\n"),             # 新格式只认二级标题
                    digest(meta="- 其他说明。", tail="\n## 数据截至 2026-10-18\n\n" + NOTE + "\n"),
                    digest(meta="- 其他说明。", tail="\n更正 2026-10-18：\n\n" + NOTE + "\n")):   # 不是标题
            r = run_base(new, base)
            self.assertIn("E-FRED-CITED", r["error_codes"], new[-80:])

    def test_note_exempt_but_other_new_fred_line_reported(self):
        base = digest(meta="- 其他说明。")
        new = digest(meta="- 其他说明。", tail=OLD_HEAD + "\n" + NOTE + "\n\n*另：FRED 数据见附表。*\n")
        r = run_base(new, base)
        self.assertEqual(self.fred_lines(r), [len(new.splitlines())])

    def test_cli_base_from_git(self):
        import json, shutil, subprocess, sys
        root = repo_for(NEW, files_for())
        g = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        shutil.rmtree(root / ".git")
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        (root / "digest").mkdir()
        f = root / "digest" / "x.md"
        f.write_text(digest(), encoding="utf-8")
        subprocess.run(g + ["add", "-A"], check=True)
        subprocess.run(g + ["commit", "-qm", "base"], check=True)
        f.write_text(digest(tail=OLD_HEAD + "\n" + NOTE + "\n"), encoding="utf-8")
        cli = str(Path(__file__).resolve().parent.parent / "scripts" / "selfcheck.py")

        def codes(*extra):
            out = subprocess.run([sys.executable, cli, str(f), "--repo", str(root), "--date", NEW, "--card-type", "daily",
                                  "--json", "--no-link-check", *extra], capture_output=True, text=True)
            return [e["line"] for e in json.loads(out.stdout)["errors"] if e["code"] == "E-FRED-CITED"]
        self.assertEqual(codes(), [])                        # 默认和 main 比：旧行未改、撤回说明豁免
        self.assertEqual(codes("--no-base"), [3])
        self.assertEqual(codes("--base", "no-such-ref"), [3])  # 取不到 base：全部行都查
        self.assertEqual(codes("--base=-x"), [3])
        f.write_text(digest(tail=OLD_HEAD + "\n" + NOTE + "\n见 `raw/2026-10-19/fred/UNRATE.json`。\n"), encoding="utf-8")
        self.assertEqual(codes(), [len(f.read_text(encoding="utf-8").splitlines())])


# —— #90 r4 MEDIUM 1：首界、末界按明确分隔符判断，Unicode 文件名字符（如中文）不算分隔符
class FredRetractedUnicodeBoundary(unittest.TestCase):
    codes = FredRetractedPaths.codes

    def test_unicode_counterexamples_not_blocked(self):
        for path in RETRACTED:
            variants = [path + suf for suf in (".备份", "备份", ".备份.txt", "..备份", ".ｂａｋ")]
            variants += [pre + path for pre in ("备份", "旧", "ｘ", "é", "数据")]
            for p2 in variants:
                for kind in ("blob", "raw", "github-raw", "relative", "relative-up"):
                    s = forms(p2)[kind]
                    self.assertNotIn("E-FRED-CITED", self.codes(s)["error_codes"], s)
            for s in (f"见 {path}.备份", f"见 备份{path}", f"见备份{path}", f"见{path}"):
                self.assertNotIn("E-FRED-CITED", self.codes(s)["error_codes"], s)

    def test_explicit_separators_still_blocked(self):
        for path in RETRACTED:
            for s in (f"见：{path}", f"见（{path}）", f"「{path}」。", f"见 {path}。备份另存", f"见 {path}.", f"见 {path}...",
                      f"见 {path}，", f"见 {path}—另见", f"url={path}", f"见:{path}", f"见\u3000{path}", f"见 ../{path}"):
                self.assertIn("E-FRED-CITED", self.codes(s)["error_codes"], s)


# —— #90 r4 MEDIUM 2：更正标题只在去掉 front matter 后的等行数可见文本里认；围栏、注释、HTML 块里的伪标题不豁免
class FredNoteVisibleHeading(unittest.TestCase):
    fred_lines = FredChangedLines.fred_lines

    def lines_for(self, tail, fm=""):
        base = digest(meta="- 其他说明。")
        new = fm + digest(meta="- 其他说明。", tail=tail)
        return self.fred_lines(run_base(new, fm + base)), len(new.splitlines())

    def test_fenced_pseudo_heading_reported(self):
        for fence in ("```", "~~~", "````"):
            got, n = self.lines_for(f"\n{fence}\n## 更正\n{fence}\n\n" + NOTE + "\n")
            self.assertEqual(got, [n], fence)
            got, n = self.lines_for(f"\n{fence}\n## 更正 2026-10-18：见下方。\n{fence}\n" + NOTE + "\n")
            self.assertEqual(got, [n], fence)

    def test_comment_pseudo_heading_reported(self):
        for tail in ("\n<!--\n## 更正\n-->\n\n" + NOTE + "\n", "\n<!-- ## 更正 -->\n\n" + NOTE + "\n",
                     "\n<!--\n## Corrections\n-->\n" + NOTE + "\n", "\n<div>\n## 更正\n</div>\n\n" + NOTE + "\n"):
            got, n = self.lines_for(tail)
            self.assertEqual(got, [n], tail)

    def test_front_matter_pseudo_heading_reported(self):
        # front matter 块标量里缩进的「## 更正」：剥离前会被当成标题，其后的说明行（front matter 结束后、正文第一个标题前）被豁免
        fm = "---\ntitle: x\nsummary: |\n  ## 更正\n---\n"
        new = fm + NOTE + "\n" + f"# 日报 {NEW}\n\n" + arx(NEW) + "\n"
        r = run_base(new, None)
        self.assertIn(6, self.fred_lines(r))

    def test_real_heading_with_front_matter_still_exempt(self):
        fm = "---\ntitle: x\n---\n"
        got, _n = self.lines_for(OLD_HEAD + "\n" + NOTE + "\n", fm)
        self.assertEqual(got, [])
        got, _n = self.lines_for("\n```\ncode\n```\n" + NEW_HEAD + "\n" + NOTE + "\n<!-- 注释 -->\n")
        self.assertEqual(got, [])

    def test_note_inside_hidden_block_reported(self):
        got, n = self.lines_for(OLD_HEAD + "\n<div>\n" + NOTE + "\n</div>\n")
        self.assertIn(n - 1, got)

    def test_misaligned_visible_text_not_exempt(self):
        from unittest import mock
        import markjin.route as route
        real = route.visible_text
        with mock.patch.object(route, "visible_text", lambda t, **kw: real(t, **kw) + "\n"):
            got, n = self.lines_for(OLD_HEAD + "\n" + NOTE + "\n")
        self.assertEqual(got, [n])


# —— Issue #92：撤回路径从各日 RETRACTIONS.md 的「FRED 撤回」节读取（待定 A、B 已定）
ROW = ("| {p} | 无（本地衍生文件） | " + "0" * 64 + " | 2026-10-19 10:00 SGT (UTC+8) | FRED 衍生数据 |")
TABLE_HEAD = "| path | source_url | sha256 | removed_at | reason |\n|---|---|---|---|---|\n"
NEWP = f"raw/{NEW}/bea-gdp/fred-derived.csv"
OTHERP = f"raw/{NEW}/nasa-news/feed.xml"


def retractions_doc(*sections):
    return f"# {NEW} 撤回记录（RETRACTIONS）\n\n本文件登记撤回的 raw 文件。\n\n" + "\n".join(sections)


def section(title, *paths, extra=""):
    return f"## {title}\n\n" + TABLE_HEAD + "".join(ROW.format(p=p) + "\n" for p in paths) + extra + "\n"


def repo_with(doc, day=NEW, raw_bytes=None):
    root = repo_for(NEW, files_for())
    d = root / "raw" / day
    d.mkdir(parents=True, exist_ok=True)
    if raw_bytes is not None:
        (d / "RETRACTIONS.md").write_bytes(raw_bytes)
    elif doc is not None:
        (d / "RETRACTIONS.md").write_text(doc, encoding="utf-8")
    return root


def cite(path):
    return f"# 日报 {NEW}\n" + arx(NEW, f"模型在 MMLU 上达到 90% 准确率（对照 `{path}`）。")


class FredRetractionsIndex(unittest.TestCase):
    def codes(self, repo, path=NEWP, date=NEW):
        r = check_text(cite(path).replace(NEW, date) if date != NEW else cite(path), repo, date, "daily",
                       link_checker=lambda u: True)
        return r

    def unreadable(self, r):
        return [(e.get("file"), e["line"]) for e in r["errors"] if e["code"] == "E-RETRACTIONS-UNREADABLE"]

    def test_new_section_paths_blocked(self):
        for title in (f"{NEW} FRED 撤回（王总决定）", f"{NEW} FRED 撤回补充：bea-gdp 衍生表", "FRED撤回"):
            repo = repo_with(retractions_doc(section(title, NEWP)))
            for kind, s in forms(NEWP).items():
                r = check_text(f"# 日报 {NEW}\n" + arx(NEW, f"模型在 MMLU 上达到 90% 准确率（对照 {s}）。"), repo, NEW, "daily",
                               link_checker=lambda u: True)
                self.assertIn("E-FRED-CITED", r["error_codes"], (title, kind))
                self.assertEqual([e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"], [2], (title, kind))
                self.assertEqual(self.unreadable(r), [])
            for s in (NEWP + ".备份", NEWP + ".bak", "备份" + NEWP, NEWP.replace(NEW, "2026-10-20")):
                self.assertNotIn("E-FRED-CITED", self.codes(repo, s)["error_codes"], s)
        self.assertNotIn("E-FRED-CITED", self.codes(repo_with(None))["error_codes"])   # 未登记时不拦

    def test_other_sections_not_read(self):
        doc = retractions_doc(section(f"{NEW} NASA 撤回（版权）", OTHERP), section(f"{NEW} FRED 撤回（王总决定）", NEWP),
                              section("保留说明", OTHERP))
        repo = repo_with(doc)
        r = self.codes(repo, OTHERP)
        self.assertNotIn("E-FRED-CITED", r["error_codes"])
        self.assertEqual(self.unreadable(r), [])
        self.assertIn("E-FRED-CITED", self.codes(repo, NEWP)["error_codes"])

    def test_section_ends_at_same_or_higher_heading(self):
        doc = retractions_doc(section(f"{NEW} FRED 撤回（王总决定）", NEWP, extra="\n### 附表\n\n" + TABLE_HEAD + ROW.format(p=NEWP + "2") + "\n"),
                              "# 其他\n\n" + TABLE_HEAD + ROW.format(p=OTHERP) + "\n")
        repo = repo_with(doc)
        self.assertIn("E-FRED-CITED", self.codes(repo, NEWP + "2")["error_codes"])   # 下级标题仍属本节
        self.assertNotIn("E-FRED-CITED", self.codes(repo, OTHERP)["error_codes"])

    def test_fenced_or_commented_heading_ignored(self):
        doc = retractions_doc(section(f"{NEW} FRED 撤回（王总决定）", NEWP, extra="\n```\n## 其他\n```\n\n" + TABLE_HEAD + ROW.format(p=NEWP + "2") + "\n"),
                              "<!--\n## FRED 撤回\n-->\n")
        repo = repo_with(doc)
        r = self.codes(repo, NEWP + "2")
        self.assertIn("E-FRED-CITED", r["error_codes"])
        self.assertEqual(self.unreadable(r), [])

    def test_missing_file_is_normal(self):
        repo = repo_for(NEW, files_for())
        r = run(f"# 日报 {NEW}\n" + arx(NEW), NEW, repo)
        self.assertEqual(r["status"], "PASS", r["error_codes"])
        self.assertEqual(self.unreadable(r), [])

    def test_unreadable_file_fails_closed(self):
        r = self.codes(repo_with(None, raw_bytes=b"## FRED \xff\xfe\n"))
        self.assertEqual(self.unreadable(r), [(f"raw/{NEW}/RETRACTIONS.md", 0)])
        self.assertEqual(r["status"], "FAIL")
        repo = repo_for(NEW, files_for())
        (repo / "raw" / NEW / "RETRACTIONS.md").mkdir()
        r = run(f"# 日报 {NEW}\n" + arx(NEW), NEW, repo)
        self.assertEqual(self.unreadable(r), [(f"raw/{NEW}/RETRACTIONS.md", 0)])
        self.assertEqual(r["status"], "FAIL")
        self.assertIn("E-RETRACTIONS-UNREADABLE", ERROR_CODES)

    def test_empty_section_fails_closed(self):
        for body in ("本节暂无。\n", TABLE_HEAD, "raw/2026-10-19/bea-gdp/x.csv 已撤回（不在表格里）。\n"):
            doc = retractions_doc(f"## {NEW} FRED 撤回补充：空\n\n" + body, section("其他", OTHERP))
            r = run(f"# 日报 {NEW}\n" + arx(NEW), NEW, repo_with(doc))
            lines = doc.split("\n")
            want = [lines.index(f"## {NEW} FRED 撤回补充：空") + 1]
            if body.startswith("raw/"):
                want.append(lines.index(body.rstrip("\n")) + 1)   # 表格以外的路径行另判格式不对
            self.assertEqual(self.unreadable(r), [(f"raw/{NEW}/RETRACTIONS.md", n) for n in want], body)
            self.assertEqual(r["status"], "FAIL")

    def test_bad_rows_fail_closed(self):
        for bad in [ROW.format(p=p) for p in (f"`{NEWP}`", "raw/2026-10-18/bea-gdp/x.csv", "fred/UNRATE.json",
                                                f"raw/{NEW}/../x.csv", f"raw/{NEW}/./x.csv", f"raw/{NEW}/a b.csv",
                                                f"raw/{NEW}/", "", f"raw/{NEW}/dir/")] + [f"| {NEWP} |", f"| {NEWP} | x |"]:
            doc = retractions_doc(section(f"{NEW} FRED 撤回（王总决定）", NEWP, extra=bad + "\n"))
            r = self.codes(repo_with(doc))
            line = doc.split("\n").index(bad) + 1
            self.assertEqual(self.unreadable(r), [(f"raw/{NEW}/RETRACTIONS.md", line)], bad)
            self.assertIn("E-FRED-CITED", r["error_codes"], bad)        # 已解析出的路径照拦
            self.assertEqual(r["status"], "FAIL")

    def test_pipe_optional_rows_and_stray_lines(self):
        # #93 r1 MEDIUM：省略首侧（或首尾）竖线的表体行同样是表格行，须解析或报错，不得静默跳过
        a, b, c = (f"raw/{NEW}/bea/{x}.csv" for x in "abc")
        for row_b in (f"{b} | x | h | t | r |", f"{b} | x | h | t | r", f"  {b}|x|h|t|r"):
            doc = retractions_doc(section(f"{NEW} FRED 撤回（王总决定）", a, extra=row_b + "\n"))
            repo = repo_with(doc)
            for p in (a, b):
                r = self.codes(repo, p)
                self.assertIn("E-FRED-CITED", r["error_codes"], (row_b, p))
                self.assertEqual(self.unreadable(r), [], row_b)
        for bad in (f"{b} | x |", f"{b}", f"- {b}", f"`{b}`", f"> {b} | x | h | t | r |", f"{b} | x | h | t | r | 多 |"):
            doc = retractions_doc(section(f"{NEW} FRED 撤回（王总决定）", a, extra=bad + "\n"))
            r = self.codes(repo_with(doc), a)
            line = doc.split("\n").index(bad) + 1
            self.assertEqual(self.unreadable(r), [(f"raw/{NEW}/RETRACTIONS.md", line)], bad)
            self.assertEqual(r["status"], "FAIL")
        # 表格以外（空行之后）的竖线行、路径行也判格式不对
        for stray in (f"{c} | x | h | t | r |", f"另见 {c}。", "| 补充 | 说明 |"):
            doc = retractions_doc(section(f"{NEW} FRED 撤回（王总决定）", a, extra="\n" + stray + "\n"))
            r = self.codes(repo_with(doc), a)
            line = doc.split("\n").index(stray) + 1
            self.assertEqual(self.unreadable(r), [(f"raw/{NEW}/RETRACTIONS.md", line)], stray)
        # 表头第一格不是 path、分隔行列数不对
        for head in ("| file | source_url | sha256 | removed_at | reason |\n|---|---|---|---|---|\n",
                     "| path | source_url | sha256 | removed_at | reason |\n|---|---|\n"):
            doc = retractions_doc(f"## {NEW} FRED 撤回（王总决定）\n\n" + head + ROW.format(p=a) + "\n")
            r = self.codes(repo_with(doc), a)
            line = doc.split("\n").index(head.split("\n")[0]) + 1
            self.assertIn((f"raw/{NEW}/RETRACTIONS.md", line), self.unreadable(r), head)
        # 表头、分隔行省略首尾竖线也认
        doc = retractions_doc(f"## {NEW} FRED 撤回（王总决定）\n\npath | source_url\n--- | :---:\n{a} | x\n{b} | y\n")
        r = self.codes(repo_with(doc), b)
        self.assertIn("E-FRED-CITED", r["error_codes"])
        self.assertEqual(self.unreadable(r), [])

    def test_bad_rows_outside_fred_section_ignored(self):
        doc = retractions_doc(section("其他撤回", OTHERP, extra="| `坏行` |\n"), section(f"{NEW} FRED 撤回（王总决定）", NEWP))
        r = run(f"# 日报 {NEW}\n" + arx(NEW), NEW, repo_with(doc))
        self.assertEqual(self.unreadable(r), [])
        self.assertEqual(r["status"], "PASS", r["error_codes"])

    def test_not_checked_before_cutoff(self):
        r = run(f"# 日报 {DATE}\n" + arxiv_line(), DATE, repo_with(None, raw_bytes=b"\xff"))
        self.assertEqual(self.unreadable(r), [])

    def test_base_retractions_union(self):
        repo = repo_with(None)
        doc = retractions_doc(section(f"{NEW} FRED 撤回（王总决定）", NEWP))
        r = check_text(cite(NEWP), repo, NEW, "daily", link_checker=lambda u: True,
                       base_retractions=[(f"raw/{NEW}/RETRACTIONS.md", doc)])
        self.assertIn("E-FRED-CITED", r["error_codes"])
        r = check_text(cite(NEWP), repo, NEW, "daily", link_checker=lambda u: True,
                       base_retractions=[(f"raw/{NEW}/RETRACTIONS.md", None)])
        self.assertEqual(self.unreadable(r), [(f"raw/{NEW}/RETRACTIONS.md", 0)])


# 内置底线清单 = main 上 9 个 RETRACTIONS.md 现有的 FRED 撤回路径；删掉 RETRACTIONS.md 仍然拦
REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_DAYS = [f"2026-10-{d:02d}" for d in range(10, 19)]


class FredRetractionsBaseline(unittest.TestCase):
    def test_baseline_equals_main_files(self):
        from markjin.selfcheck import FRED_RETRACTED_BASELINE, parse_fred_retractions
        got = set()
        for day in BASELINE_DAYS:
            paths, bad = parse_fred_retractions((REPO_ROOT / "raw" / day / "RETRACTIONS.md").read_text(encoding="utf-8"), day)
            self.assertEqual(bad, [], day)
            self.assertTrue(paths, day)
            got |= paths
        self.assertEqual(set(FRED_RETRACTED_BASELINE), got)
        self.assertEqual(len(FRED_RETRACTED_BASELINE), 83)
        self.assertFalse(any("nasa-news" in p or "prx-quantum" in p or "openfda" in p for p in got))   # 10-12 其他节不读

    def test_deleted_retractions_still_blocked_by_baseline(self):
        from markjin.selfcheck import FRED_RETRACTED_BASELINE
        repo = repo_for("2026-10-11", {"nbs-gdp/README.md": "x"})            # 10-11 目录在，RETRACTIONS.md 已删
        nonfred = [p for p in FRED_RETRACTED_BASELINE if "/fred/" not in p]
        self.assertEqual(sorted(nonfred), sorted(RETRACTED))
        for path in nonfred:
            for kind, s in forms(path).items():
                r = check_text(f"# 日报 {NEW}\n" + arx(NEW, f"模型在 MMLU 上达到 90% 准确率（对照 {s}）。"), repo, NEW, "daily",
                               link_checker=lambda u: True)
                self.assertIn("E-FRED-CITED", r["error_codes"], (path, kind))
                self.assertNotIn("E-RETRACTIONS-UNREADABLE", r["error_codes"])

    def test_real_repo_reads_clean(self):
        r = run(f"# 日报 {NEW}\n" + arx(NEW), NEW, REPO_ROOT)
        self.assertNotIn("E-RETRACTIONS-UNREADABLE", r["error_codes"])


# #89 已合并（adc9973）：main 上四份 digest 的文末补充说明不报 E-FRED-CITED（选项 b：只查新增或改动的行）
PR89_NOTES = {"2026-10-15": 140, "2026-10-16": 139, "2026-10-17": 141, "2026-10-18": 146}


class Pr89DigestNotes(unittest.TestCase):
    def test_real_digest_notes_not_reported(self):
        for day, line in PR89_NOTES.items():
            p = REPO_ROOT / "digest" / f"{day}.md"
            text = p.read_text(encoding="utf-8")
            self.assertEqual(text.splitlines()[line - 1], NOTE.replace("2026-10-15", day), day)
            for date in (day, NEW):
                for base in (text, None):
                    r = check_text(text, REPO_ROOT, date, "daily", link_checker=lambda u: True, rel=f"digest/{day}.md",
                                   base_text=base)
                    lines = [e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"]
                    self.assertNotIn(line, lines, (day, date, base is None))
                    if base is not None:
                        self.assertEqual(lines, [], (day, date))
                    self.assertNotIn("E-RETRACTIONS-UNREADABLE", r["error_codes"], (day, date))

    def test_cli_git_base_retractions(self):
        import json, shutil, subprocess, sys
        root = repo_with(retractions_doc(section(f"{NEW} FRED 撤回（王总决定）", NEWP)))
        g = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        shutil.rmtree(root / ".git")
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        (root / "digest").mkdir()
        f = root / "digest" / "x.md"
        f.write_text(f"# 日报 {NEW}\n", encoding="utf-8")
        subprocess.run(g + ["add", "-A"], check=True)
        subprocess.run(g + ["commit", "-qm", "base"], check=True)
        (root / "raw" / NEW / "RETRACTIONS.md").unlink()                    # 工作树里删掉，main 上仍在
        f.write_text(cite(NEWP), encoding="utf-8")
        cli = str(REPO_ROOT / "scripts" / "selfcheck.py")

        def out(*extra):
            return subprocess.run([sys.executable, cli, str(f), "--repo", str(root), "--date", NEW, "--card-type", "daily",
                                   "--no-link-check", *extra], capture_output=True, text=True)
        r = json.loads(out("--json").stdout)
        self.assertIn("E-FRED-CITED", r["error_codes"])
        r = json.loads(out("--json", "--no-base").stdout)
        self.assertNotIn("E-FRED-CITED", r["error_codes"])
        (root / "raw" / NEW / "RETRACTIONS.md").write_bytes(b"\xff")
        txt = out("--no-base").stdout
        self.assertIn(f"raw/{NEW}/RETRACTIONS.md:L0 E-RETRACTIONS-UNREADABLE", txt)


if __name__ == "__main__":
    unittest.main()
