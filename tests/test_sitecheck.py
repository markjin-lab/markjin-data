"""站点 PR 页面更正检查（scripts/check-site-corrections.py / markjin.sitecheck，Grok Bot 2026-10-18）。"""
import datetime as dt
import json
import io
import os
import re
import runpy
import shutil
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
CLOCK = "2026-10-18T12:00:00+08:00"
HAVE_HUGO = shutil.which("hugo") is not None
HUGO_VER = (re.search(r"v(\d+\.\d+\.\d+)", subprocess.run(["hugo", "version"], capture_output=True, text=True).stdout).group(1)
            if HAVE_HUGO else "0.0.0")
HUGO_TOML = ('baseURL = "https://example.test/"\ndefaultContentLanguage = "zh"\n'
             '[languages.zh]\nweight = 1\n[languages.en]\nweight = 2\n')
LAYOUTS = {"layouts/_default/single.html": "<p>{{ .Title }}</p>{{ .Content }}\n",
           "layouts/_default/list.html": "<p>{{ .Title }}</p>\n",
           "layouts/index.html": "<p>home</p>\n"}
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
        self.write("hugo.toml", HUGO_TOML)
        self.write(".github/workflows/hugo.yml", f"env: {{HUGO_VERSION: {HUGO_VER}}}\n")
        for rel, body in LAYOUTS.items():
            self.write(rel, body)

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


@unittest.skipUnless(HAVE_HUGO, "需要 hugo")
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
        return S.check_range(str(self.s.d), self.base, head, today=today, clock=CLOCK)

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

    def test_same_day_second_correction_with_new_heading_passes(self):
        self.s.write(P, corr())
        self.base = self.s.commit("first correction")
        self.s.write(P, corr(body="第 2 条：再改。") + "\n## 更正 2026-10-17（二）：再次修订。\n")
        self.assertTrue(self.run_check()["ok"])

    def test_same_day_second_correction_reusing_old_heading_fails(self):
        self.s.write(P, corr())
        self.base = self.s.commit("first correction")
        self.s.write(P, corr(body="第 2 条：再改。"))
        self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-NOTE"])

    def test_next_day_correction_keeping_old_date_and_heading_fails(self):
        self.s.write(P, corr(at="2026-10-17"))
        self.base = self.s.commit("first correction")
        self.s.write(P, corr(at="2026-10-17", body="第 2 条：次日再改。"))
        self.assertEqual(self.codes(self.run_check(today=dt.date(2026, 10, 18))), ["E-ROUTE-CORRECTION-NOTE"])

    def test_next_day_correction_with_new_date_and_heading_passes(self):
        self.s.write(P, corr(at="2026-10-17"))
        self.base = self.s.commit("first correction")
        self.s.write(P, corr(at="2026-10-18", body="第 2 条：次日再改。"))
        self.assertTrue(self.run_check()["ok"])

    def test_uses_merge_base_when_main_advanced(self):
        self.s.write(P, corr())
        head = self.s.commit("head")
        self.s.git("checkout", "-q", "main")
        self.s.write("content/posts/daily/2026-10-18.md", ORIG.replace("10-16", "10-18"))
        main2 = self.s.commit("main advanced")
        out = S.check_range(str(self.s.d), main2, head, today=TODAY, clock=CLOCK)
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

    def test_page_date_same_day_other_time_or_zone(self):
        for d in ("2026-10-16T06:00:00+08:00", "2026-10-15T21:00:00Z", "2026-10-16"):
            self.s.write(P, corr(date=d))
            self.assertEqual(self.codes(self.run_check()), ["E-ROUTE-CORRECTION-DATE"], d)

    def test_plain_yaml_date_unchanged_passes(self):
        self.s.write(P, ORIG.replace("date: 2026-10-16T05:00:00+08:00", "date: 2026-10-16"))
        self.base = self.s.commit("plain date")
        self.s.write(P, corr(date="2026-10-16"))
        self.assertTrue(self.run_check()["ok"])

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


@unittest.skipUnless(HAVE_HUGO, "需要 hugo")
class PublishStateTest(SiteCheckTest):
    """r1 HIGH 2 / MEDIUM 3：“已发布”按 Hugo 实际构建判定。"""
    UNPUB = ("draft: true\n", "publishDate: 2026-12-01T00:00:00+08:00\n", "expiryDate: 2026-10-01T00:00:00+08:00\n",
             "build:\n  render: never\n")

    def test_unpublishing_published_page_with_valid_correction_fields(self):
        for extra in self.UNPUB + ("url: /moved/\n",):
            self.s.write(P, corr(extra=extra))
            self.assertIn("E-SITE-PAGE-DELETED", self.codes(self.run_check()), extra)

    def test_future_date_unpublishes(self):
        self.s.write(P, corr(date="2026-12-01T05:00:00+08:00"))
        self.assertIn("E-SITE-PAGE-DELETED", self.codes(self.run_check()))

    def test_unpublished_at_base_edit_without_correction_passes(self):
        for extra in self.UNPUB:
            self.s.git("checkout", "-q", "main")
            self.s.write(P, ORIG.replace("---\n导语", extra + "---\n导语"))
            self.base = self.s.commit("unpublished base")
            self.s.git("checkout", "-q", "-B", "pr")
            self.s.write(P, ORIG.replace("---\n导语", extra + "---\n导语").replace("旧句子", "新句子"))
            out = self.run_check()
            self.assertEqual(self.codes(out), [], extra)
            self.assertFalse(next(p for p in out["pages"] if p["path"] == P)["published_at_base"])

    def test_draft_first_publish_passes(self):
        self.s.git("checkout", "-q", "main")
        self.s.write(P, ORIG.replace("---\n导语", "draft: true\n---\n导语"))
        self.base = self.s.commit("draft base")
        self.s.git("checkout", "-q", "-B", "pr")
        self.s.write(P, ORIG.replace("旧句子", "错字已改"))
        self.assertTrue(self.run_check()["ok"])

    def test_correction_of_page_unpublished_at_base(self):
        self.s.git("checkout", "-q", "main")
        self.s.write(P, ORIG.replace("---\n导语", "draft: true\n---\n导语"))
        self.base = self.s.commit("draft base")
        self.s.git("checkout", "-q", "-B", "pr")
        self.s.write(P, corr())
        self.assertIn("E-ROUTE-CORRECTION-TARGET", self.codes(self.run_check()))

    def test_cascade_draft_from_section(self):
        self.s.write("content/posts/daily/_index.md", "---\ntitle: daily\ncascade:\n  draft: true\n---\n")
        self.s.write(P, corr())
        self.assertIn("E-SITE-PAGE-DELETED", self.codes(self.run_check()))

    def test_unmappable_published_page_edit(self):
        bad = "content/posts/daily/2026-10-16-en.md"
        self.s.git("checkout", "-q", "main")
        self.s.write(bad, ORIG)
        self.base = self.s.commit("odd name")
        self.s.git("checkout", "-q", "-B", "pr")
        self.s.write(bad, corr(did="daily-2026-10-16-en"))
        self.assertIn("E-ROUTE-CORRECTION-TARGET", self.codes(self.run_check(), bad))


class PageDraftIdTest(unittest.TestCase):
    def test_mapping_is_inverse_of_site_path(self):
        for did, en in (("daily-2026-10-16", False), ("daily-2026-10-16-en", True), ("digest-2026-10-16", False),
                        ("cards-c1", False), ("cards-c1-en", True), ("tongyi-a-b", False)):
            self.assertEqual(S.page_draft_id(R.site_path(did, en)), did)

    def test_en_suffix_and_length(self):
        self.assertEqual(S.page_draft_id("content/posts/daily/a.en.md"), "daily-a-en")
        self.assertIsNone(S.page_draft_id("content/posts/daily/a-en.md"))
        self.assertIsNone(S.page_draft_id("content/posts/daily/" + "a" * 60 + ".md"))
        self.assertEqual(S.page_draft_id("content/posts/daily/" + "a" * 58 + ".md"), "daily-" + "a" * 58)

    def test_non_pages(self):
        for p in ("content/posts/daily/_index.md", "content/posts/x.md", "content/posts/a/b/c.md",
                  "content/posts/cards/c1.md", "content/posts/Daily/x.md", "content/posts/daily/X.md",
                  "content/posts/daily/a.html", "content/about.md", "content/cards/a/b.md"):
            self.assertIsNone(S.page_draft_id(p), p)


class CorrectionSectionTest(unittest.TestCase):
    """站点 Issue #71：新格式更正区。"""
    ZH = "x\n\n## 更正\n\n**2026-10-12**：甲。\n**2026-10-17**：乙。\n\n本文不含投资建议。\n"
    EN = "x\n\n## Corrections\n\n**2026-10-17**: a.\n**2026-10-18**: b.\n"

    def test_new_format_ok(self):
        self.assertTrue(R.correction_heading_ok(self.ZH, "2026-10-17", en=False))
        self.assertTrue(R.correction_heading_ok(self.ZH, "2026-10-12", en=False))
        self.assertTrue(R.correction_heading_ok(self.EN, "2026-10-18", en=True))
        self.assertTrue(R.correction_heading_ok(self.ZH, "2026-10-17"))          # en=None 中英都认

    def test_new_format_failures(self):
        self.assertFalse(R.correction_heading_ok(self.ZH, "2026-10-18", en=False))   # 无该日期条目
        self.assertFalse(R.correction_heading_ok(self.ZH, "2026-10-17", en=True))    # 语言不符
        self.assertFalse(R.correction_heading_ok(self.EN, "2026-10-18", en=False))
        self.assertFalse(R.correction_heading_ok(self.ZH + "\n## 更正\n\n**2026-10-18**：丙。\n", "2026-10-18", en=False))  # 两个标题
        self.assertFalse(R.correction_heading_ok("## 更正\n\n**2026-10-18**：后。\n**2026-10-17**：前。\n", "2026-10-17", en=False))  # 未按升序
        self.assertFalse(R.correction_heading_ok("## 更正\n\n## 别的\n\n**2026-10-17**：在别的标题下。\n", "2026-10-17", en=False))
        self.assertFalse(R.correction_heading_ok("## 更正\n\n<!-- **2026-10-17**：注释里。 -->\n", "2026-10-17", en=False))
        self.assertFalse(R.correction_heading_ok("## 更正\n\n```\n**2026-10-17**：代码块里。\n```\n", "2026-10-17", en=False))
        self.assertFalse(R.correction_heading_ok("## 更正\n\n<div hidden>\n**2026-10-17**：隐藏。\n</div>\n", "2026-10-17", en=False))
        self.assertFalse(R.correction_heading_ok("## 更正\n\n- **2026-10-17**：带列表符号。\n", "2026-10-17", en=False))
        self.assertFalse(R.correction_heading_ok("## 更正\n\n**2026-10-17**:半角冒号。\n", "2026-10-17", en=False))
        self.assertFalse(R.correction_heading_ok("## Corrections\n\n**2026-10-17**：full-width.\n", "2026-10-17", en=True))

    def test_mixing_old_heading_with_new_section_not_allowed(self):
        b = "## 更正 2026-10-17：旧标题。\n\n## 更正\n\n**2026-10-12**：甲。\n"
        self.assertFalse(R.correction_heading_ok(b, "2026-10-17", en=False))

    def test_level_and_exact_heading_text(self):
        self.assertFalse(R.correction_heading_ok("### 更正\n\n**2026-10-17**：三级标题。\n", "2026-10-17", en=False))
        self.assertFalse(R.correction_heading_ok("## 更正说明\n\n**2026-10-17**：标题字不同。\n", "2026-10-17", en=False))
        self.assertTrue(R.correction_heading_ok("## 更正 ##\n\n**2026-10-17**：闭合井号。\n", "2026-10-17", en=False))

    def test_old_format_still_accepted(self):
        self.assertTrue(R.correction_heading_ok("## 更正 2026-10-17：本次修订的具体内容见下方更正说明。\n", "2026-10-17", en=False))
        self.assertTrue(R.correction_heading_ok("## Correction 2026-10-17: The note below lists the changes.\n", "2026-10-17", en=True))


OLD_SEC = ("---\ntitle: \"日报 2026-10-16\"\ndate: 2026-10-16T05:00:00+08:00\ncorrected_at: 2026-10-17\ncorrects: daily-2026-10-16\n---\n"
           "*本文于 2026-10-16、2026-10-17 更正，说明见文末。*\n\n导语。\n\n## 出处\n\n1. 来源\n\n"
           "*更正说明（2026-10-16）：首次更正。*\n\n## 更正 2026-10-17：本次修订的具体内容见下方更正说明。\n\n"
           "*更正说明（2026-10-17）：只改措辞。*\n\n本文不含投资建议。\n")
NEW_SEC = ("---\ntitle: \"日报 2026-10-16\"\ndate: 2026-10-16T05:00:00+08:00\ncorrected_at: 2026-10-17\ncorrects: daily-2026-10-16\n---\n"
           "*本文于 2026-10-16、2026-10-17 更正，说明见文末。*\n\n导语。\n\n## 出处\n\n1. 来源\n\n"
           "## 更正\n\n**2026-10-16**：首次更正。\n**2026-10-17**：只改措辞。\n\n本文不含投资建议。\n")
OLD_SEC_EN = ("---\ntitle: \"Daily 2026-10-16\"\ndate: 2026-10-16T05:00:00+08:00\ncorrected_at: 2026-10-18\ncorrects: daily-2026-10-16-en\n---\n"
              "*This article was corrected on 2026-10-17 and 2026-10-18; see the notes at the end.*\n\nLead.\n\n"
              "## Correction 2026-10-17: The note below lists the changes in this revision.\n\n*Correction note (2026-10-17): a.*\n\n"
              "## Correction 2026-10-18: The note below lists the changes in this revision.\n\n*Correction note (2026-10-18): b.*\n")
NEW_SEC_EN = ("---\ntitle: \"Daily 2026-10-16\"\ndate: 2026-10-16T05:00:00+08:00\ncorrected_at: 2026-10-18\ncorrects: daily-2026-10-16-en\n---\n"
              "*This article was corrected on 2026-10-17 and 2026-10-18; see the notes at the end.*\n\nLead.\n\n"
              "## Corrections\n\n**2026-10-17**: a.\n**2026-10-18**: b.\n")


class MigrationOnlyTest(unittest.TestCase):
    """Issue #71 例外：只把旧格式更正区改成新格式、不动其他内容，不算新更正。"""
    def test_pure_migration(self):
        self.assertTrue(S.format_migration_only(OLD_SEC, NEW_SEC, False))
        self.assertTrue(S.format_migration_only(OLD_SEC_EN, NEW_SEC_EN, True))

    def test_top_line_whitelist(self):
        self.assertTrue(S.format_migration_only(OLD_SEC, NEW_SEC.replace("说明见文末。", "说明见文末「更正」。"), False))
        self.assertTrue(S.format_migration_only(OLD_SEC_EN, NEW_SEC_EN.replace("see the notes at the end", "see Corrections at the end"), True))
        self.assertFalse(S.format_migration_only(OLD_SEC, NEW_SEC.replace("本文于 2026-10-16、2026-10-17 更正", "本文于 2026-10-17 更正"), False))
        self.assertFalse(S.format_migration_only(OLD_SEC, NEW_SEC.replace("说明见文末。", "详见文末。"), False))

    def test_not_migration(self):
        bad = {
            "正文改字": NEW_SEC.replace("导语。", "导语！"),
            "front matter 改动": NEW_SEC.replace('title: "日报 2026-10-16"', 'title: "日报"'),
            "corrected_at 改动": NEW_SEC.replace("corrected_at: 2026-10-17", "corrected_at: 2026-10-18"),
            "说明改字": NEW_SEC.replace("只改措辞。", "只改措辞和标点。"),
            "少一条": NEW_SEC.replace("**2026-10-16**：首次更正。\n", ""),
            "多一条": NEW_SEC.replace("**2026-10-17**：只改措辞。\n", "**2026-10-17**：只改措辞。\n**2026-10-18**：新。\n"),
            "日期改动": NEW_SEC.replace("**2026-10-16**", "**2026-10-15**"),
            "未按升序": NEW_SEC.replace("**2026-10-16**：首次更正。\n**2026-10-17**：只改措辞。",
                                     "**2026-10-17**：只改措辞。\n**2026-10-16**：首次更正。"),
            "更正区后正文改动": NEW_SEC.replace("本文不含投资建议。", "本文不构成投资建议。"),
            "空行变化": NEW_SEC.replace("1. 来源\n\n## 更正", "1. 来源\n\n\n## 更正"),
            "两个新标题": NEW_SEC.replace("\n本文不含", "\n## 更正\n\n本文不含"),
        }
        for k, v in bad.items():
            self.assertFalse(S.format_migration_only(OLD_SEC, v, False), k)

    def test_old_region_must_be_only_corrections(self):
        old = OLD_SEC.replace("*更正说明（2026-10-16）：首次更正。*\n\n", "*更正说明（2026-10-16）：首次更正。*\n\n正文夹在中间。\n\n")
        self.assertFalse(S.format_migration_only(old, NEW_SEC, False))

    def test_no_old_notes(self):
        self.assertFalse(S.format_migration_only(NEW_SEC, NEW_SEC, False))


@unittest.skipUnless(HAVE_HUGO, "需要 hugo")
class MigrationViaCheckTest(unittest.TestCase):
    def setUp(self):
        self.s = SiteRepo()
        self.s.write(P, OLD_SEC)
        self.s.write(PEN, OLD_SEC_EN)
        self.base = self.s.commit("base")

    def run_check(self):
        head = self.s.commit("head")
        return {p["path"]: p["codes"] for p in S.check_range(str(self.s.d), self.base, head, today=TODAY, clock=CLOCK)["pages"]}

    def test_pure_migration_passes(self):
        self.s.write(P, NEW_SEC); self.s.write(PEN, NEW_SEC_EN)
        self.assertEqual(self.run_check(), {P: [], PEN: []})

    def test_migration_with_body_edit_is_ordinary_correction(self):
        self.s.write(P, NEW_SEC.replace("导语。", "导语！"))
        self.assertEqual(self.run_check()[P], ["E-ROUTE-CORRECTION-NOTE"])     # 同日、未新增条目

    def test_migration_with_note_edit_is_ordinary_correction(self):
        self.s.write(PEN, NEW_SEC_EN.replace("**2026-10-18**: b.", "**2026-10-18**: b, reworded."))
        self.assertEqual(self.run_check()[PEN], ["E-ROUTE-CORRECTION-NOTE"])

    def test_migration_plus_new_dated_entry_is_valid_correction(self):
        self.s.write(PEN, NEW_SEC_EN.replace("corrected_at: 2026-10-18", "corrected_at: 2026-10-18")
                     .replace("Lead.", "Lead, fixed.").replace("**2026-10-18**: b.\n", "**2026-10-18**: b.\n**2026-10-18**: lead fixed.\n"))
        self.assertEqual(self.run_check()[PEN], [])

    def test_new_format_next_correction(self):
        self.s.write(P, NEW_SEC); self.base = self.s.commit("migrated")
        self.s.write(P, NEW_SEC.replace("corrected_at: 2026-10-17", "corrected_at: 2026-10-18").replace("导语。", "导语！")
                     .replace("**2026-10-17**：只改措辞。\n", "**2026-10-17**：只改措辞。\n**2026-10-18**：导语改标点。\n"))
        self.assertEqual(self.run_check()[P], [])
        self.s.write(P, NEW_SEC.replace("corrected_at: 2026-10-17", "corrected_at: 2026-10-18").replace("导语。", "导语！"))
        self.assertEqual(self.run_check()[P], ["E-ROUTE-CORRECTION-NOTE"])     # 新日期没有条目


class R2FormatTest(unittest.TestCase):
    """PR #52 r2 MEDIUM 2/4/5。"""
    def test_old_heading_plus_valid_new_section_fails(self):
        b = "## 更正 2026-10-17：旧标题。\n\n## 更正\n\n**2026-10-17**：乙。\n"
        self.assertFalse(R.correction_heading_ok(b, "2026-10-17", en=False))

    def test_both_language_headings_fail(self):
        b = "## 更正\n\n**2026-10-17**：乙。\n\n## Corrections\n\n**2026-10-17**: b.\n"
        self.assertFalse(R.correction_heading_ok(b, "2026-10-17", en=False))
        self.assertFalse(R.correction_heading_ok(b, "2026-10-17", en=True))

    def test_malformed_entry_in_section_fails(self):
        for bad in ("**2026-10-18**:半角冒号。", "**2026-99-99**：非法日期。", "**2026-10-18** ：多空格。"):
            b = "## 更正\n\n**2026-10-17**：乙。\n" + bad + "\n"
            self.assertFalse(R.correction_heading_ok(b, "2026-10-17", en=False), bad)
        self.assertTrue(R.correction_heading_ok("## 更正\n\n**2026-10-17**：乙。\n\n本文不含投资建议。\n", "2026-10-17", en=False))

    def test_migration_old_heading_date_mismatch(self):
        old = OLD_SEC.replace("## 更正 2026-10-17：", "## 更正 2026-10-18：")
        self.assertFalse(S.format_migration_only(old, NEW_SEC, False))

    def test_migration_extra_old_heading_same_date(self):
        old = OLD_SEC.replace("*更正说明（2026-10-17）：只改措辞。*",
                              "*更正说明（2026-10-17）：只改措辞。*\n\n## 更正 2026-10-17：本次修订的具体内容见下方更正说明。")
        self.assertFalse(S.format_migration_only(old, NEW_SEC, False))

    def test_migration_old_heading_with_substantive_text(self):
        old = OLD_SEC.replace("## 更正 2026-10-17：本次修订的具体内容见下方更正说明。", "## 更正 2026-10-17：删去了第 3 条。")
        self.assertFalse(S.format_migration_only(old, NEW_SEC, False))
        old2 = OLD_SEC.replace("## 更正 2026-10-17：本次修订的具体内容见下方更正说明。", "## 更正 2026-10-17：只改措辞。")
        self.assertTrue(S.format_migration_only(old2, NEW_SEC, False))   # 与说明行完全相同的不算丢失
        old3 = OLD_SEC.replace("## 更正 2026-10-17：本次修订的具体内容见下方更正说明。", "## 更正 2026-10-17")
        self.assertTrue(S.format_migration_only(old3, NEW_SEC, False))

    def test_top_line_whitelist_only_before_first_heading(self):
        mid = "*本文于 2026-10-16、2026-10-17 更正，说明见文末。*"
        old = OLD_SEC.replace("导语。\n\n## 出处", "导语。\n\n## 出处\n\n" + mid)
        new = NEW_SEC.replace("导语。\n\n## 出处", "导语。\n\n## 出处\n\n" + mid.replace("文末。", "文末「更正」。"))
        self.assertFalse(S.format_migration_only(old, new, False))
        old2 = OLD_SEC.replace("导语。", mid + "\n\n导语。")             # 首个标题前出现两行同形句
        new2 = NEW_SEC.replace("导语。", mid + "\n\n导语。").replace("说明见文末。*\n\n*本文", "说明见文末「更正」。*\n\n*本文", 1)
        self.assertFalse(S.format_migration_only(old2, new2, False))


@unittest.skipUnless(HAVE_HUGO, "需要 hugo")
class R2CheckTest(unittest.TestCase):
    """PR #52 r2 HIGH 1、MEDIUM 3、LOW 6/7。"""
    def setUp(self):
        self.s = SiteRepo()
        self.s.write(P, ORIG)
        self.s.write("content/posts/daily/_index.md", "---\ntitle: daily\n---\n")
        self.base = self.s.commit("base")

    def check(self):
        head = self.s.commit("head")
        return S.check_range(str(self.s.d), self.base, head, today=TODAY, clock=CLOCK)

    def test_section_cascade_unpublishes_child(self):
        self.s.write("content/posts/daily/_index.md", "---\ntitle: daily\ncascade:\n  draft: true\n---\n")
        out = self.check()
        self.assertFalse(out["ok"])
        self.assertIn({"path": P, "status": "indirect", "draft_id": "daily-2026-10-16", "published_at_base": True,
                       "codes": ["E-SITE-PAGE-DELETED"]}, out["pages"])

    def test_root_cascade_unpublishes_child(self):
        self.s.write("content/_index.md", "---\ntitle: home\ncascade:\n  build:\n    render: never\n---\n")
        out = self.check()
        self.assertEqual([p["codes"] for p in out["pages"] if p["path"] == P], [["E-SITE-PAGE-DELETED"]])

    def test_config_permalink_change_detected(self):
        self.s.write("hugo.toml", HUGO_TOML + "[permalinks]\nposts = \"/p/:slug/\"\n")
        self.assertFalse(self.check()["ok"])

    def test_unrelated_config_change_passes(self):
        self.s.write("hugo.toml", HUGO_TOML.replace('baseURL', 'title = "x"\nbaseURL'))
        self.s.write("layouts/_default/list.html", "<p>list2</p>\n")
        out = self.check()
        self.assertTrue(out["ok"], out); self.assertEqual(out["pages"], [])

    def test_new_format_same_day_unrelated_dated_heading(self):
        sec = ORIG.replace("---\n导语", "corrected_at: 2026-10-17\ncorrects: daily-2026-10-16\n---\n导语") + "\n## 更正\n\n**2026-10-17**：首次。\n"
        self.s.write(P, sec); self.base = self.s.commit("corrected")
        self.s.write(P, sec.replace("旧句子", "新句子") + "\n## 其他 2026-10-17\n")
        self.assertEqual([p["codes"] for p in self.check()["pages"] if p["path"] == P], [["E-ROUTE-CORRECTION-NOTE"]])
        self.s.write(P, sec.replace("旧句子", "新句子").replace("**2026-10-17**：首次。\n", "**2026-10-17**：首次。\n**2026-10-17**：再改。\n"))
        self.assertTrue(self.check()["ok"])

    def test_missing_or_unparseable_deploy_workflow(self):
        for body in (None, "env: {}\n"):
            if body is None:
                self.s.rm(".github/workflows/hugo.yml")
            else:
                self.s.write(".github/workflows/hugo.yml", body)
            self.base = self.s.commit("wf")
            self.s.write(P, ORIG.replace("旧", "新" + str(body)))
            with self.assertRaises(S.SiteInputError):
                self.check()

    def test_oserror_is_json_input_error(self):
        self.s.write(P, ORIG.replace("旧", "新"))
        head = self.s.commit("edit")
        from unittest import mock
        out, argv = io.StringIO(), sys.argv
        sys.argv = [str(CLI), "--site-repo", str(self.s.d), "--base", self.base, "--head", head]
        try:
            with mock.patch("markjin.sitecheck.tempfile.TemporaryDirectory", side_effect=OSError("no tmp")), \
                    mock.patch("sys.stdout", out), self.assertRaises(SystemExit) as cm:
                runpy.run_path(str(CLI), run_name="__main__")
        finally:
            sys.argv = argv
        self.assertEqual(cm.exception.code, 1)
        self.assertEqual(json.loads(out.getvalue())["codes"], ["E-SITE-INPUT"])


class R3FormatTest(unittest.TestCase):
    """PR #52 r3 MEDIUM 3/4、LOW 5。"""
    def test_unrelated_dated_heading_not_old_correction_heading(self):
        self.assertFalse(R.correction_heading_ok("## 数据截至 2026-10-17\n\n正文。\n", "2026-10-17", en=False))
        self.assertTrue(R.correction_heading_ok("## 更正 2026-10-17：说明见下。\n", "2026-10-17", en=False))
        self.assertTrue(R.correction_heading_ok("## 更正 <b>2026-10-17</b>\n", "2026-10-17", en=False))
        self.assertTrue(R.correction_heading_ok("## Correction 2026-10-17: see below.\n", "2026-10-17", en=True))
        self.assertEqual(S._corrections_dated(corr() + "\n## 数据截至 2026-10-17\n", "2026-10-17", False), 1)

    def test_partial_date_entries_are_malformed(self):
        for bad in ("**2026-1-18**：畸形。", "**2026-10-18*：畸形。", "*2026-10-18*：畸形。", "2026-10-18：没加粗。", "** 2026-10-18**：空格。"):
            b = "## 更正\n\n**2026-10-17**：乙。\n" + bad + "\n"
            self.assertFalse(R.correction_heading_ok(b, "2026-10-17", en=False), bad)

    def test_prefixed_entries_malformed_plain_text_ok(self):
        for bad in ("- **2026-10-18**：第二次。", "> **2026-10-18**：引用。", "1. **2026-10-18**：编号。", "* **2026-1-18**：残缺。"):
            b = "## 更正\n\n**2026-10-17**：乙。\n" + bad + "\n"
            self.assertFalse(R.correction_heading_ok(b, "2026-10-17", en=False), bad)
        for ok in ("* 1. 免责声明。", "2026年之后数据待核。", "本文不含投资建议。"):
            b = "## 更正\n\n**2026-10-17**：乙。\n\n" + ok + "\n"
            self.assertTrue(R.correction_heading_ok(b, "2026-10-17", en=False), ok)

    def test_task_list_entries_and_date_led_prose(self):
        for bad in ("- [ ] **2026-10-18**：遗漏。", "1. [x] **2026-10-18**：遗漏。", "2026-10-18：没加粗。"):
            b = "## 更正\n\n**2026-10-17**：乙。\n" + bad + "\n"
            self.assertFalse(R.correction_heading_ok(b, "2026-10-17", en=False), bad)
        for ok in ("2026年10月以来，数据持续上升。", "2026-10-18 的数据仍待核。"):
            b = "## 更正\n\n**2026-10-17**：乙。\n\n" + ok + "\n"
            self.assertTrue(R.correction_heading_ok(b, "2026-10-17", en=False), ok)

    def test_code_block_cannot_pose_as_migration(self):
        fm = OLD_SEC.split("---\n", 2)
        head = "---\n" + fm[1] + "---\n"
        old = head + "导语。\n\n### 更正 2026-10-17：合法。\n\n```\n*更正说明（2026-10-16）：代码样本。*\n```\n"
        new = head + "导语。\n\n### 更正 2026-10-17：合法。\n\n```\n## 更正\n\n**2026-10-16**：代码样本。\n```\n"
        self.assertFalse(S.format_migration_only(old, new, False))
        self.assertTrue(S.format_migration_only(OLD_SEC, NEW_SEC, False))

    def test_setext_heading_ends_top_area(self):
        mid = "*本文于 2026-10-16、2026-10-17 更正，说明见文末。*"
        old = OLD_SEC.replace(mid + "\n\n导语。", "标题\n=====\n\n" + mid + "\n\n导语。")
        new = NEW_SEC.replace(mid + "\n\n导语。", "标题\n=====\n\n" + mid.replace("文末。", "文末「更正」。") + "\n\n导语。")
        self.assertNotEqual(old, OLD_SEC)
        self.assertFalse(S.format_migration_only(old, new, False))
        self.assertTrue(S.format_migration_only(old, new.replace("文末「更正」。", "文末。"), False))


@unittest.skipUnless(HAVE_HUGO, "需要 hugo")
class R3CheckTest(unittest.TestCase):
    def setUp(self):
        self.s = SiteRepo()

    def check(self, base):
        head = self.s.commit("head")
        return {p["path"]: p["codes"] for p in S.check_range(str(self.s.d), base, head, today=TODAY, clock=CLOCK)["pages"]}

    def test_baseurl_host_change_detected(self):
        self.s.write(P, ORIG); base = self.s.commit("base")
        self.s.write("hugo.toml", HUGO_TOML.replace("https://example.test/", "https://other.test/"))
        self.assertEqual(self.check(base).get(P), ["E-SITE-PAGE-DELETED"])

    def test_migration_still_checks_new_section(self):
        self.s.write(P, OLD_SEC + "\n## Corrections\n"); base = self.s.commit("base")
        self.s.write(P, NEW_SEC + "\n## Corrections\n")
        self.assertTrue(S.format_migration_only(OLD_SEC + "\n## Corrections\n", NEW_SEC + "\n## Corrections\n", False))
        self.assertEqual(self.check(base)[P], ["E-ROUTE-CORRECTION-NOTE"])

    def test_cross_day_reuses_prewritten_entry(self):
        base_txt = NEW_SEC.replace("**2026-10-17**：只改措辞。\n", "**2026-10-17**：只改措辞。\n**2026-10-18**：预先写好。\n")
        self.s.write(P, base_txt); base = self.s.commit("base")
        self.s.write(P, base_txt.replace("corrected_at: 2026-10-17", "corrected_at: 2026-10-18").replace("导语。", "导语！"))
        self.assertEqual(self.check(base)[P], ["E-ROUTE-CORRECTION-NOTE"])
        self.s.write(P, base_txt.replace("corrected_at: 2026-10-17", "corrected_at: 2026-10-18").replace("导语。", "导语！")
                     .replace("**2026-10-18**：预先写好。\n", "**2026-10-18**：预先写好。\n**2026-10-18**：导语改标点。\n"))
        self.assertEqual(self.check(base)[P], [])

    def test_code_block_migration_via_check(self):
        fm = OLD_SEC.split("---\n", 2)
        head = "---\n" + fm[1] + "---\n"
        self.s.write(P, head + "导语。\n\n### 更正 2026-10-17：合法。\n\n```\n*更正说明（2026-10-16）：代码样本。*\n```\n")
        base = self.s.commit("base")
        self.s.write(P, head + "导语。\n\n### 更正 2026-10-17：合法。\n\n```\n## 更正\n\n**2026-10-16**：代码样本。\n```\n")
        self.assertEqual(self.check(base)[P], ["E-ROUTE-CORRECTION-NOTE"])

    def test_old_format_unrelated_dated_heading_same_day(self):
        self.s.write(P, corr()); base = self.s.commit("base")
        self.s.write(P, corr(body="第 2 条：又一句。") + "\n## 数据截至 2026-10-17\n")
        self.assertEqual(self.check(base)[P], ["E-ROUTE-CORRECTION-NOTE"])


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

    @unittest.skipUnless(HAVE_HUGO, "需要 hugo")
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

    def test_argument_errors_are_json_input_errors(self):
        for args in (["--site-repo", str(self.s.d), "--pr", "1", "--head", "x"], ["--head", "x"], []):
            r = subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1, args)
            self.assertEqual(json.loads(r.stdout)["codes"], ["E-SITE-INPUT"], args)

    def test_head_base_mode_does_not_change_refs(self):
        before = self.s.git("for-each-ref")
        self.s.write(P, ORIG.replace("旧", "新"))
        head = self.s.commit("edit")
        before = self.s.git("for-each-ref")
        self.cli("--base", self.base, "--head", head)
        self.assertEqual(self.s.git("for-each-ref"), before)

    def test_non_utf8_path_is_input_error(self):
        name = b"content/posts/daily/\xff.md"
        (self.s.d / os.fsdecode(name)).parent.mkdir(parents=True, exist_ok=True)
        (self.s.d / os.fsdecode(name)).write_text("x\n")
        head = self.s.commit("bad name")
        rc, out = self.cli("--base", self.base, "--head", head)
        self.assertEqual(rc, 1); self.assertEqual(out["codes"], ["E-SITE-INPUT"])

    def test_non_utf8_content_is_input_error(self):
        (self.s.d / P).write_bytes(b"---\ntitle: x\n---\n\xff\xfe\n")
        head = self.s.commit("bad content")
        rc, out = self.cli("--base", self.base, "--head", head)
        self.assertEqual(rc, 1); self.assertEqual(out["codes"], ["E-SITE-INPUT"])

    def test_missing_hugo_is_input_error(self):
        self.s.write(P, ORIG.replace("旧", "新"))
        head = self.s.commit("edit")
        r = subprocess.run([sys.executable, str(CLI), "--site-repo", str(self.s.d), "--base", self.base, "--head", head],
                           capture_output=True, text=True, env={**os.environ, "MARKJIN_HUGO": "/nonexistent/hugo"})
        self.assertEqual(r.returncode, 1); self.assertEqual(json.loads(r.stdout)["codes"], ["E-SITE-INPUT"])

    @unittest.skipUnless(HAVE_HUGO, "需要 hugo")
    def test_hugo_version_must_match_deploy_workflow(self):
        self.s.write(".github/workflows/hugo.yml", "env: {HUGO_VERSION: 0.1.0}\n")
        self.base = self.s.commit("wf")
        self.s.write(P, ORIG.replace("旧", "新"))
        head = self.s.commit("edit")
        rc, out = self.cli("--base", self.base, "--head", head)
        self.assertEqual(rc, 1); self.assertEqual(out["codes"], ["E-SITE-INPUT"])


class ReadFailureTest(unittest.TestCase):
    def test_modified_page_unreadable_fails_closed(self):
        s = SiteRepo(); s.write(P, ORIG); base = s.commit("b"); s.write(P, corr()); head = s.commit("h")
        with self.assertRaises(S.SiteInputError):
            S.check_page(str(s.d), base, "0" * 40, P, "M", TODAY, {P: "/posts/daily/2026-10-16/"}, {})
        with self.assertRaises(S.SiteInputError):
            S.check_page(str(s.d), "0" * 40, head, P, "M", TODAY, {}, {})


class CodesTest(unittest.TestCase):
    def test_codes_registered(self):
        import inspect
        src = inspect.getsource(S)
        for c in ("E-SITE-CORRECTION-MISSING", "E-SITE-PAGE-DELETED", "E-SITE-INPUT", "E-ROUTE-CORRECTION-NOTE",
                  "E-ROUTE-CORRECTION-DATE", "E-ROUTE-CORRECTION-TARGET", "E-ROUTE-CORRECTION-INVALID", "E-ROUTE-FRONT-MATTER"):
            self.assertIn(c, ERROR_CODES); self.assertIn(c, src)


if __name__ == "__main__":
    unittest.main()
