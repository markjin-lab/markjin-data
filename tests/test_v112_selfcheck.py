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


# #87 撤回、不在 fred/ 目录下的三个文件（#90 r2 MEDIUM；Grok Bot 2026-10-18 21:01 SGT 决定写死这三个路径）
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

    def test_paths_match_constant(self):
        from markjin.selfcheck import FRED_RETRACTED_PATHS
        self.assertEqual(tuple(FRED_RETRACTED_PATHS), RETRACTED)

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
                      f"| {path} |", f"见{path}；", f"见 {path}: 第 2 行", f"[存档]({path}#L10)", path):
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


if __name__ == "__main__":
    unittest.main()
