"""站点 PR 页面更正检查（scripts/check-site-corrections.py / markjin.sitecheck，Grok Bot 2026-10-18）。"""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  （设置临时目录与 sys.path）
from markjin import route as R
from markjin import sitecheck as S
from markjin.codes import ERROR_CODES

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "check-site-corrections.py"
TODAY = dt.date(2026, 10, 18)
P = "content/posts/daily/2026-10-16.md"
PEN = "content/posts/daily/2026-10-16.en.md"

ORIG = '---\ntitle: "日报 2026-10-16"\ndate: 2026-10-16T05:00:00+08:00\n---\n导语。\n\n第 2 条：旧句子。\n'
ORIG_EN = '---\ntitle: "Daily 2026-10-16"\ndate: 2026-10-16T05:00:00+08:00\n---\nLead.\n\nItem 2: old sentence.\n'


def corr(did="daily-2026-10-16", at="2026-10-17", heading=None, body="第 2 条：新句子。", date="2026-10-16T05:00:00+08:00", extra=""):
    h = f"## 更正 {at}：说明见下。" if heading is None else heading
    return (f'---\ntitle: "日报 2026-10-16"\ndate: {date}\ncorrected_at: {at}\ncorrects: {did}\n{extra}---\n'
            f"导语。\n\n{body}\n\n{h}\n\n*更正说明（{at}）：改了第 2 条。*\n")


class SiteRepo:
    def __init__(self):
        self.d = Path(tempfile.mkdtemp())
        self.git("init", "-q", "-b", "main")

    def git(self, *a):
        r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *a],
                           cwd=self.d, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return r.stdout.strip()

    def write(self, rel, text):
        p = self.d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def rm(self, rel):
        self.git("rm", "-q", rel)

    def commit(self, msg="c"):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)
        return self.git("rev-parse", "HEAD")


class SiteCheckTest(unittest.TestCase):
    def setUp(self):
        self.s = SiteRepo()
        self.s.write(P, ORIG)
        self.s.write(PEN, ORIG_EN)
        self.s.write("content/posts/daily/_index.md", "---\ntitle: daily\n---\n")
        self.s.write("layouts/x.html", "<p>x</p>\n")
        self.base = self.s.commit("base")
        self.s.git("checkout", "-q", "-b", "pr")

    def run_check(self, today=TODAY):
        head = self.s.commit("head")
        return S.check_range(str(self.s.d), self.base, head, today=today)

    def codes(self, out, path=P):
        return next(p["codes"] for p in out["pages"] if p["path"] == path)

    # —— 通过
    def test_valid_correction_passes(self):
        self.s.write(P, corr())
        out = self.run_check()
        self.assertTrue(out["ok"], out)
        self.assertEqual(self.codes(out), [])

    def test_valid_en_correction_passes(self):
        self.s.write(PEN, ORIG_EN.replace("old", "new").replace("---\nLead", "corrected_at: 2026-10-18\ncorrects: daily-2026-10-16-en\n---\nLead")
                     + "\n## Correction 2026-10-18: see note.\n")
        out = self.run_check()
        self.assertTrue(out["ok"], out)

    def test_new_page_without_correction_fields_passes(self):
        self.s.write("content/posts/daily/2026-10-18.md", ORIG.replace("10-16", "10-18"))
        self.assertTrue(self.run_check()["ok"])

    def test_non_page_files_ignored(self):
        self.s.write("layouts/x.html", "<p>y</p>\n")
        self.s.write("content/posts/daily/_index.md", "---\ntitle: daily2\n---\n")
        self.s.write("content/posts/daily/notes.txt", "x\n")
        out = self.run_check()
        self.assertTrue(out["ok"])
        self.assertEqual([p["path"] for p in out["pages"]], ["content/posts/daily/_index.md"])
        self.assertEqual(out["pages"][0]["codes"], [])

    def test_second_correction_same_day_as_previous_passes(self):
        self.s.write(P, corr())
        self.base = self.s.commit("first correction")
        self.s.write(P, corr(body="第 2 条：再改。"))
        self.assertTrue(self.run_check()["ok"])

    def test_uses_merge_base_when_main_advanced(self):
        self.s.write(P, corr())
        head = self.s.commit("head")
        self.s.git("checkout", "-q", "main")
        self.s.write("content/posts/daily/2026-10-18.md", ORIG.replace("10-16", "10-18"))
        main2 = self.s.commit("main advanced")
        out = S.check_range(str(self.s.d), main2, head, today=TODAY)
        self.assertEqual(out["merge_base"], self.base)
        self.assertEqual([p["path"] for p in out["pages"]], [P])
        self.assertTrue(out["ok"])

    # —— 不通过
    def test_silent_edit_of_published_page(self):
        self.s.write(P, ORIG.replace("旧句子", "新句子"))
        out = self.run_check()
        self.assertFalse(out["ok"])
        self.assertEqual(self.codes(out), ["E-SITE-CORRECTION-MISSING"])

    def test_front_matter_only_edit_of_published_page(self):
        self.s.write(P, ORIG.replace('title: "日报 2026-10-16"', 'title: "日报 2026-10-16（改）"'))
        self.assertEqual(self.codes(self.run_check()), ["E-SITE-CORRECTION-MISSING"])

    def test_date_only_in_body_not_heading(self):
        self.s.write(P, corr(heading="## 更正说明"))
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-NOTE"])

    def test_date_only_in_link_target(self):
        self.s.write(P, corr(heading="## [更正](https://x.test/2026-10-17)"))
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-NOTE"])

    def test_hidden_heading_date(self):
        self.s.write(P, corr(heading='## 更正 <span aria-hidden="true">2026-10-17</span>'))
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-NOTE"])

    def test_heading_inside_code_fence_or_comment(self):
        self.s.write(P, corr(heading="```\n## 更正 2026-10-17\n```"))
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-NOTE"])
        self.s.write(P, corr(heading="<!--\n## 更正 2026-10-17\n-->"))
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-NOTE"])

    def test_stale_heading_after_new_correction_date(self):
        # 已有 10-17 更正的页面再次更正为 10-18，只留 10-17 的标题 → 不通过
        self.s.write(P, corr())
        self.base = self.s.commit("first correction")
        self.s.write(P, corr(at="2026-10-18", heading="## 更正 2026-10-17：旧标题。"))
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-NOTE"])

    def test_only_one_field(self):
        self.s.write(P, ORIG.replace("---\n导语", "corrected_at: 2026-10-17\n---\n导语") + "\n## 更正 2026-10-17\n")
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-INVALID"])

    def test_empty_or_non_string_fields(self):
        self.s.write(P, corr(did='""'))
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-INVALID"])
        self.s.write(P, corr(did="[a, b]"))
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-INVALID"])

    def test_corrects_mismatch(self):
        self.s.write(P, corr(did="daily-2026-10-15"))
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-TARGET"])

    def test_en_page_needs_en_draft_id(self):
        self.s.write(PEN, corr(did="daily-2026-10-16"))
        self.assertEqual(self.codes(self.run_check(), PEN), ["E-ROUTE-CORRECTION-TARGET"])

    def test_correction_of_unpublished_page(self):
        self.s.write("content/posts/daily/2026-10-18.md", corr(did="daily-2026-10-18", at="2026-10-18", date="2026-10-18"))
        self.assertIn("E-ROUTE-CORRECTION-TARGET", self.codes(self.run_check(), "content/posts/daily/2026-10-18.md"))

    def test_original_without_date(self):
        self.s.write(P, ORIG.replace("date: 2026-10-16T05:00:00+08:00\n", ""))
        self.base = self.s.commit("no date")
        self.s.write(P, corr())
        self.assertIn("E-ROUTE-CORRECTION-TARGET", self.codes(self.run_check()))

    def test_bad_dates(self):
        for at in ("2026-10-15", "2026-10-19", "17 Oct 2026"):
            self.s.write(P, corr(at=at))
            self.assertIn("E-ROUTE-CORRECTION-DATE", self.codes(self.run_check()), at)
        self.s.write(P, corr(at="2026-13-01").replace("corrected_at: 2026-13-01", 'corrected_at: "2026-13-01"'))
        self.assertIn("E-ROUTE-CORRECTION-DATE", self.codes(self.run_check()))
        self.s.write(P, corr(at="2026-13-01"))          # 不带引号的非法日期：YAML 解析失败，与 route 一致
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-FRONT-MATTER"])

    def test_corrected_at_earlier_than_previous_correction(self):
        self.s.write(P, corr(at="2026-10-18"))
        self.base = self.s.commit("first correction")
        self.s.write(P, corr(at="2026-10-17", body="第 2 条：再改。"))
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-DATE"])

    def test_page_date_changed(self):
        self.s.write(P, corr(date="2026-10-17T05:00:00+08:00"))
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-DATE"])

    def test_bad_front_matter(self):
        self.s.write(P, "---\ntitle: [unclosed\n---\nx\n")
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-FRONT-MATTER"])
        self.s.write(P, "---\ntitle: a\ntitle: b\n---\nx\n")
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-FRONT-MATTER"])

    def test_deleted_or_renamed_published_page(self):
        self.s.rm(PEN)
        out = self.run_check()
        self.assertEqual(self.codes(out, PEN), ["E-SITE-PAGE-DELETED"])
        self.s.git("mv", P, "content/posts/daily/2026-10-16-x.md")
        out = self.run_check()
        self.assertEqual(self.codes(out, P), ["E-SITE-PAGE-DELETED"])
        self.assertFalse(out["ok"])

    def test_cards_page(self):
        self.s.write("content/cards/c1.md", ORIG)
        self.base = self.s.commit("card")
        self.s.write("content/cards/c1.md", corr(did="cards-c1"))
        out = self.run_check()
        self.assertTrue(out["ok"], out)
        self.s.write("content/cards/c1.md", ORIG.replace("旧", "新"))
        self.assertEqual(self.codes(self.run_check(), "content/cards/c1.md"), ["E-SITE-CORRECTION-MISSING"])


class PageDraftIdTest(unittest.TestCase):
    def test_mapping_is_inverse_of_site_path(self):
        for did, en in (("daily-2026-10-16", False), ("daily-2026-10-16-en", True), ("digest-2026-10-16", False),
                        ("cards-c1", False), ("cards-c1-en", True), ("tongyi-a-b", False)):
            self.assertEqual(S.page_draft_id(R.site_path(did, en)), did)

    def test_non_pages(self):
        for p in ("content/posts/daily/_index.md", "content/posts/x.md", "content/posts/a/b/c.md",
                  "content/posts/cards/c1.md", "content/posts/Daily/x.md", "content/posts/daily/X.md",
                  "content/posts/daily/a.html", "content/about.md", "content/cards/a/b.md"):
            self.assertIsNone(S.page_draft_id(p), p)


class HeadingHelperTest(unittest.TestCase):
    def test_shared_helper(self):
        self.assertTrue(R.correction_heading_ok("x\n## 更正 2026-10-17\n", "2026-10-17"))
        self.assertTrue(R.correction_heading_ok("   # Correction 2026-10-17 note\n", "2026-10-17"))
        self.assertFalse(R.correction_heading_ok("更正 2026-10-17\n", "2026-10-17"))
        self.assertFalse(R.correction_heading_ok("    ## 更正 2026-10-17\n", "2026-10-17"))   # 缩进 4 格是代码块
        self.assertFalse(R.correction_heading_ok('## <span class="x">2026-10-17</span>\n', "2026-10-17"))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.s = SiteRepo()
        self.s.write(P, ORIG)
        self.base = self.s.commit("base")

    def cli(self, *args):
        r = subprocess.run([sys.executable, str(CLI), "--site-repo", str(self.s.d), *args],
                           capture_output=True, text=True, env={**os.environ})
        return r.returncode, json.loads(r.stdout)

    def test_pass_and_fail_exit_codes(self):
        self.s.write("content/posts/daily/2026-10-18.md", ORIG.replace("10-16", "10-18"))
        good = self.s.commit("new page")
        rc, out = self.cli("--base", self.base, "--head", good)
        self.assertEqual(rc, 0); self.assertTrue(out["ok"])
        self.s.write(P, ORIG.replace("旧", "新"))
        bad = self.s.commit("silent edit")
        rc, out = self.cli("--base", self.base, "--head", bad)
        self.assertEqual(rc, 1); self.assertFalse(out["ok"])
        self.assertIn("E-SITE-CORRECTION-MISSING", [c for p in out["pages"] for c in p["codes"]])

    def test_bad_ref_is_input_error(self):
        rc, out = self.cli("--base", self.base, "--head", "no-such-ref")
        self.assertEqual(rc, 1); self.assertEqual(out["codes"], ["E-SITE-INPUT"])

    def test_pr_mode_requires_canonical_remote(self):
        self.s.git("remote", "add", "origin", "https://github.com/someone/fork.git")
        rc, out = self.cli("--pr", "1")
        self.assertEqual(rc, 1); self.assertEqual(out["codes"], ["E-SITE-INPUT"])

    def test_pr_and_head_are_exclusive(self):
        r = subprocess.run([sys.executable, str(CLI), "--site-repo", str(self.s.d), "--pr", "1", "--head", "x"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


class CodesTest(unittest.TestCase):
    def test_codes_registered(self):
        import inspect
        src = inspect.getsource(S)
        for c in ("E-SITE-CORRECTION-MISSING", "E-SITE-PAGE-DELETED", "E-SITE-INPUT", "E-ROUTE-CORRECTION-NOTE",
                  "E-ROUTE-CORRECTION-DATE", "E-ROUTE-CORRECTION-TARGET", "E-ROUTE-CORRECTION-INVALID", "E-ROUTE-FRONT-MATTER"):
            self.assertIn(c, ERROR_CODES); self.assertIn(c, src)


if __name__ == "__main__":
    unittest.main()
