"""selfcheck：产业与经济数据小节（站点 industry-* 短代码块）与 E-FRED-CITED（Grok Bot 2026-10-19 15:28 裁定）。
每条规则至少一个拦截例和一个放行例；用例文字为中性占位内容。"""
import collections, unittest
from helpers import make_repo, DUMMY_INTERNAL, DATE
import markjin.selfcheck as _sc

_sc.load_internal_terms = lambda: list(DUMMY_INTERNAL)
REPO = make_repo()
TITLE = f"# 日报 {DATE}\n\n"
NEW = ("E-INDUSTRY-NUMBER", "E-INDUSTRY-AGENCY-LINK", "E-FRED-CITED", "E-BLOCK-INTERNAL")


def codes(text):
    r = _sc.check_text(text, REPO, DATE, "daily", link_checker=lambda u: True)
    c = collections.Counter(e["code"] for e in r["errors"])
    return {k: v for k, v in c.items() if k in NEW}


LINK_OK = '{{< industry-link item="1" industry="ai" side="demand" >}}来源里的训练规模对应算力需求 [1]。{{< /industry-link >}}\n'
LINK_OK_EN = '{{< industry-link item="2" industry="energy" side="cost" >}}The source\'s compute figure maps to electricity cost [2].{{< /industry-link >}}\n'
DATA = ('{{< industry-data >}}\n{{< industry-datum series="美国某序列" publisher="某机构" frequency="monthly" period="@P" value="@V" '
        'released="@R" cite="4" >}}\n{{< /industry-data >}}\n')


def data(p, v, r):
    return DATA.replace("@P", p).replace("@V", v).replace("@R", r)


class IndustryBlocks(unittest.TestCase):
    def test_blocks_recognized_without_heading(self):
        doc = TITLE + LINK_OK + data("上月", "x", "x")
        self.assertEqual(len(_sc.industry_blocks(doc)), 2)

    def test_unclosed_block_runs_to_end(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}正文 [1]。\n后面一行 3 项\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_shortcode_names(self):
        self.assertEqual(_sc.INDUSTRY_SHORTCODES, ("industry-data", "industry-datum", "industry-link"))


class IndustryNumber(unittest.TestCase):
    def test_pass_citations_item_cite_only(self):
        self.assertEqual(codes(TITLE + LINK_OK), {})
        self.assertEqual(codes(TITLE + LINK_OK_EN), {})

    def test_block_digit_in_body(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}训练规模增加 3 倍对应算力需求 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_block_fullwidth_digit(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}约３成对应算力需求 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_block_percent(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}占比以％计的部分对应需求 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_block_datum_value(self):
        doc = TITLE + data("上月", "102.3", "2026-10-17")
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_number_outside_block_not_this_code(self):
        doc = TITLE + "某模型在基准上得分 12 分 [1]。\n" + LINK_OK
        self.assertNotIn("E-INDUSTRY-NUMBER", codes(doc))


class IndustryAgencyLink(unittest.TestCase):
    def test_block_agency_url(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}对应需求，见 https://www.bea.gov/data [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-AGENCY-LINK": 1})

    def test_block_agency_subdomain_cn(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}对应需求，见 data.stats.gov.cn [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-AGENCY-LINK": 1})

    def test_pass_non_agency_url(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}对应需求，见 https://arxiv.org/abs/x [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {})

    def test_pass_lookalike_domain(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}对应需求，见 https://notbea.gov.example/x [1]。{{< /industry-link >}}\n'
        self.assertNotIn("E-INDUSTRY-AGENCY-LINK", codes(doc))

    def test_domain_list_contains_required(self):
        for d in ("bea.gov", "bls.gov", "census.gov", "eia.gov", "federalreserve.gov", "stats.gov.cn", "pbc.gov.cn", "customs.gov.cn", "sec.gov"):
            self.assertIn(d, _sc.INDUSTRY_AGENCY_DOMAINS)


class IndustryInternalTerm(unittest.TestCase):           # 内部用语沿用 E-BLOCK-INTERNAL
    def test_block_internal_term_in_block(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}这里说的' + DUMMY_INTERNAL[0] + '对应需求 [1]。{{< /industry-link >}}\n'
        self.assertIn("E-BLOCK-INTERNAL", codes(doc))

    def test_pass_no_internal_term(self):
        self.assertNotIn("E-BLOCK-INTERNAL", codes(TITLE + LINK_OK))

    def test_no_separate_codes(self):
        self.assertNotIn("E-INTERNAL-TERM", _sc.ERROR_CODES if hasattr(_sc, "ERROR_CODES") else {})
        from markjin.codes import ERROR_CODES
        self.assertNotIn("E-INTERNAL-TERM", ERROR_CODES)
        self.assertNotIn("R-INDUSTRY-STRAINED", ERROR_CODES)


class FredCited(unittest.TestCase):
    def test_block_fred_url(self):
        self.assertEqual(codes(TITLE + "某说明见 https://fred.stlouisfed.org/series/X [1]。\n"), {"E-FRED-CITED": 1})

    def test_block_fred_subdomain(self):
        self.assertEqual(codes(TITLE + "某说明见 https://api.fred.stlouisfed.org/x [1]。\n"), {"E-FRED-CITED": 1})

    def test_block_fred_word(self):
        self.assertEqual(codes(TITLE + "某序列取自 FRED [1]。\n"), {"E-FRED-CITED": 1})

    def test_pass_name_fred(self):
        self.assertEqual(codes(TITLE + "Fred 与 Alfredo 讨论了某模型 [1]。\n"), {})

    def test_pass_no_fred(self):
        self.assertEqual(codes(TITLE + "某模型的说明 [1]。\n"), {})


L = '{{< industry-link item="1" industry="ai" side="demand" >}}'
LE = '{{< /industry-link >}}\n'


def link(body):
    return TITLE + L + body + LE


class R4ShortcodeParsing(unittest.TestCase):          # 引号里含 }}、多块、嵌套
    def test_quoted_closer_in_param(self):
        doc = TITLE + '{{< industry-data >}}\n{{< industry-datum series="甲}}" value="x" cite="1" >}}\n{{< /industry-data >}}\n'
        self.assertEqual(len(_sc.industry_blocks(doc)), 1)
        self.assertEqual(codes(doc), {})

    def test_quoted_closer_with_number(self):
        doc = TITLE + '{{< industry-datum series="甲}}" value="123" cite="1" >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_quoted_closer_in_link_param(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" inference="甲 >}} 乙" >}}正文 7 处 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_multiple_blocks(self):
        doc = link("正文 [1]。") + "块外 12 分 [2]。\n" + link("正文第 3 项 [3]。")
        self.assertEqual(len(_sc.industry_blocks(doc)), 2)
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_nested_same_name(self):
        doc = TITLE + L + "外层 [1]。" + L + "内层 [2]。" + LE.strip() + "外层末尾 5 [3]。" + LE
        self.assertEqual(len(_sc.industry_blocks(doc)), 1)
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_percent_delimiter_form(self):
        doc = TITLE + '{{% industry-link item="1" industry="ai" side="demand" %}}正文 9 [1]。{{% /industry-link %}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})


class R4NumberExemption(unittest.TestCase):           # 只豁免 industry-* 自身的 cite/item 参数与正文真实 [n]
    def test_value_bracketed_not_exempt(self):
        doc = TITLE + '{{< industry-data >}}\n{{< industry-datum series="甲" value="[123]" cite="4" >}}\n{{< /industry-data >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_data_cite_param_not_exempt(self):
        doc = TITLE + '{{< industry-datum series="甲" data-cite="123" cite="4" >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_body_cite_text_not_exempt(self):
        self.assertEqual(codes(link('正文 cite="123" [1]。')), {"E-INDUSTRY-NUMBER": 1})

    def test_cite_param_bad_format_not_exempt(self):
        doc = TITLE + '{{< industry-datum series="甲" cite="12.5" >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_cite_param_of_other_shortcode_not_exempt(self):
        self.assertEqual(codes(link('正文 {{< ref cite="123" >}} [1]。')), {"E-INDUSTRY-NUMBER": 1})

    def test_bracket_too_long_not_exempt(self):
        self.assertEqual(codes(link("正文 [1234]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_pass_real_cite_and_item(self):
        doc = TITLE + '{{< industry-link item="12" industry="ai" side="demand" >}}正文 [1][2]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {})
        doc = TITLE + '{{< industry-data >}}\n{{< industry-datum series="甲" value="x" cite="4, 5" >}}\n{{< /industry-data >}}\n'
        self.assertEqual(codes(doc), {})


class R4UnicodeDigits(unittest.TestCase):
    def test_arabic_indic(self):
        self.assertEqual(codes(link("正文 ١٢ 项 [1]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_devanagari(self):
        self.assertEqual(codes(link("正文 ३ 项 [1]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_superscript_and_circled(self):
        self.assertEqual(codes(link("正文 ² 项 [1]。")), {"E-INDUSTRY-NUMBER": 1})
        self.assertEqual(codes(link("正文 ① 项 [1]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_entity_digit(self):
        self.assertEqual(codes(link("正文 &#49; 项 [1]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_percent_variants(self):
        for p in ("﹪", "٪", "‰", "؉"):
            self.assertEqual(codes(link(f"正文以{p}计 [1]。")), {"E-INDUSTRY-NUMBER": 1}, p)

    def test_pass_no_digits(self):
        self.assertEqual(codes(link("正文没有任何数值 [1]。")), {})


class R4HostBoundaries(unittest.TestCase):
    def test_pass_suffix_lookalike(self):
        self.assertEqual(codes(link("见 https://bea.gov.example/x [1]。")), {})
        self.assertEqual(codes(link("见 bea.gov.example [1]。")), {})

    def test_pass_prefix_lookalike(self):
        self.assertEqual(codes(link("见 https://notbea.gov/x [1]。")), {})

    def test_ideographic_dots(self):
        for h in ("bea。gov", "bea．gov", "bea｡gov", "ｂｅａ.ｇｏｖ"):
            self.assertEqual(codes(link(f"见 {h} [1]。")), {"E-INDUSTRY-AGENCY-LINK": 1}, h)

    def test_sentence_final_dot(self):
        self.assertEqual(codes(link("见 bea.gov. [1]")), {"E-INDUSTRY-AGENCY-LINK": 1})

    def test_uppercase_and_subdomain(self):
        self.assertEqual(codes(link("见 HTTPS://APPS.BEA.GOV/x [1]。")), {"E-INDUSTRY-AGENCY-LINK": 1})

    def test_url_with_userinfo_port(self):
        self.assertEqual(codes(link("见 https://u@www.bls.gov:443/x [1]。")), {"E-INDUSTRY-AGENCY-LINK": 1, "E-INDUSTRY-NUMBER": 1})

    def test_agency_in_shortcode_param(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" inference="见 census.gov" >}}正文 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-AGENCY-LINK": 1})


class R4FredBaseline(unittest.TestCase):              # Grok Bot 15:43：只管新增或改动的行
    OLD = TITLE + "某说明 [1]。\n采集范围含 FRED 序列 [2]。\n结尾 [9]。\n"

    def run_b(self, text, baseline):
        r = _sc.check_text(text, REPO, DATE, "daily", link_checker=lambda u: True, baseline=baseline)
        return [e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"]

    def test_old_line_passes(self):
        self.assertEqual(self.run_b(self.OLD + "新增一行 [3]。\n", self.OLD), [])

    def test_changed_line_blocked(self):
        new = self.OLD.replace("采集范围含 FRED 序列", "采集范围含 FRED 两个序列")
        self.assertEqual(self.run_b(new, self.OLD), [4])

    def test_new_line_blocked(self):
        self.assertEqual(self.run_b(self.OLD + "另见 https://fred.stlouisfed.org/x [3]。\n", self.OLD), [6])

    def test_moved_old_line_same_text_passes(self):
        new = TITLE + "采集范围含 FRED 序列 [2]。\n某说明 [1]。\n结尾 [9]。\n"
        self.assertEqual(self.run_b(new, self.OLD), [3])          # 位置变动的行按改动处理（拿不准就拦）

    def test_no_baseline_checks_all(self):
        self.assertEqual(self.run_b(self.OLD, None), [4])

class R4FredMarks(unittest.TestCase):
    def test_vs16_inserted(self):
        self.assertEqual(codes(TITLE + "某序列取自 FRE\ufe0fD [1]。\n"), {"E-FRED-CITED": 1})

    def test_combining_inserted(self):
        self.assertEqual(codes(TITLE + "某序列取自 FRE\u0301D [1]。\n"), {"E-FRED-CITED": 1})

    def test_cf_inserted(self):
        self.assertEqual(codes(TITLE + "某序列取自 FR\u200bED [1]。\n"), {"E-FRED-CITED": 1})

    def test_fullwidth(self):
        self.assertEqual(codes(TITLE + "某序列取自 ＦＲＥＤ [1]。\n"), {"E-FRED-CITED": 1})

    def test_fred_host_ideographic_dot(self):
        self.assertEqual(codes(TITLE + "见 fred。stlouisfed。org [1]。\n"), {"E-FRED-CITED": 1})

    def test_pass_fred_host_lookalike(self):
        self.assertEqual(codes(TITLE + "见 https://fred.stlouisfed.org.example/x [1]。\n"), {})

    def test_pass_lowercase_and_name(self):
        self.assertEqual(codes(TITLE + "Fred 与 fred 讨论了某模型 [1]。\n"), {})


# ---------------------------------------------------------------- r5 修正（最后一轮，从严）
import json as _json, os as _os, subprocess as _subp, sys as _sys, tempfile as _tmp
from pathlib import Path as _P
_ROOT = _P(__file__).resolve().parent.parent
_ENV = {**_os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _cli(args, cwd=None):
    p = _subp.run([_sys.executable, str(_ROOT / "scripts" / "selfcheck.py"), *args], capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout, p.stderr


class R5Cli(unittest.TestCase):
    OLD = TITLE + "某说明 [1]。\n采集范围含 FRED 序列 [2]。\n结尾 [9]。\n"

    def repo(self, d, publish=True):
        g = ["git", "-C", d]
        _subp.run(["git", "init", "-q", d], check=True)
        f = _P(d) / "digest.md"
        f.write_text(self.OLD, encoding="utf-8")
        _subp.run(g + ["add", "."], check=True, env=_ENV)
        _subp.run(g + ["commit", "-qm", "old"], check=True, env=_ENV)
        if publish:
            _subp.run(g + ["update-ref", "refs/remotes/origin/main", "HEAD"], check=True)
        return f

    def args(self, f, d, *extra):
        return [str(f), "--repo", d, "--date", DATE, "--card-type", "daily", "--json", "--no-link-check", *extra]

    def test_ancestor_ref_old_line_passes_new_line_blocked(self):
        with _tmp.TemporaryDirectory() as d:
            f = self.repo(d)
            f.write_text(self.OLD + "新增 FRED [3]。\n", encoding="utf-8")
            rc, out, _ = _cli(self.args(f, d, "--baseline-ref", "HEAD"))
            self.assertEqual([e["line"] for e in _json.loads(out)["errors"] if e["code"] == "E-FRED-CITED"], [6])

    def test_non_ancestor_ref_rejected(self):           # 含新稿的提交不在 origin/main 上：拒绝
        with _tmp.TemporaryDirectory() as d:
            f = self.repo(d)
            f.write_text(self.OLD + "新增 FRED [3]。\n", encoding="utf-8")
            _subp.run(["git", "-C", d, "commit", "-qam", "new"], check=True, env=_ENV)
            rc, out, _ = _cli(self.args(f, d, "--baseline-ref", "HEAD"))
            self.assertEqual(rc, 3)
            self.assertEqual(_json.loads(out)["errors"][0]["code"], "E-SELFCHECK-INPUT")

    def test_no_origin_main_rejected(self):
        with _tmp.TemporaryDirectory() as d:
            f = self.repo(d, publish=False)
            rc, out, _ = _cli(self.args(f, d, "--baseline-ref", "HEAD"))
            self.assertEqual(rc, 3)

    def test_bad_ref_rejected(self):
        with _tmp.TemporaryDirectory() as d:
            f = self.repo(d)
            rc, out, _ = _cli(self.args(f, d, "--baseline-ref", "nosuchref"))
            self.assertEqual((rc, _json.loads(out)["status"]), (3, "INPUT-ERROR"))

    def test_file_baseline_flag_gone(self):
        with _tmp.TemporaryDirectory() as d:
            f = self.repo(d)
            rc, out, err = _cli(self.args(f, d, "--baseline", str(f)))
            self.assertNotEqual(rc, 0)
            self.assertIn("unrecognized arguments", err)

    def test_baseline_not_utf8(self):
        with _tmp.TemporaryDirectory() as d:
            f = self.repo(d)
            f.write_bytes(b"\xff\xfe bad")
            _subp.run(["git", "-C", d, "commit", "-qam", "bin"], check=True, env=_ENV)
            _subp.run(["git", "-C", d, "update-ref", "refs/remotes/origin/main", "HEAD"], check=True)
            f.write_text(self.OLD, encoding="utf-8")
            rc, out, _ = _cli(self.args(f, d, "--baseline-ref", "HEAD"))
            self.assertEqual(rc, 3)
            self.assertEqual(_json.loads(out)["errors"][0]["code"], "E-SELFCHECK-INPUT")

    def test_draft_outside_repo(self):
        with _tmp.TemporaryDirectory() as d, _tmp.TemporaryDirectory() as d2:
            self.repo(d)
            f2 = _P(d2) / "x.md"
            f2.write_text(self.OLD, encoding="utf-8")
            rc, out, _ = _cli(self.args(f2, d, "--baseline-ref", "HEAD"))
            self.assertEqual((rc, _json.loads(out)["errors"][0]["code"]), (3, "E-SELFCHECK-INPUT"))

    def test_relative_draft_outside_repo(self):
        with _tmp.TemporaryDirectory() as d, _tmp.TemporaryDirectory() as d2:
            self.repo(d)
            (_P(d2) / "x.md").write_text(self.OLD, encoding="utf-8")
            rc, out, _ = _cli(["x.md", "--repo", d, "--date", DATE, "--card-type", "daily", "--json", "--no-link-check",
                               "--baseline-ref", "HEAD"], cwd=d2)
            self.assertEqual(rc, 3)


class R5FredPosition(unittest.TestCase):              # 只有同一行号、逐字相同且前后行都相同才放行
    OLD = "# 日报\n\nA [1]。\n采集含 FRED [2]。\nB [3]。\n"

    def lines(self, new):
        r = _sc.check_text(new, REPO, DATE, "daily", link_checker=lambda u: True, baseline=self.OLD)
        return [e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"]

    def test_unchanged_passes(self):
        self.assertEqual(self.lines(self.OLD), [])

    def test_swap_blocked(self):
        self.assertEqual(self.lines("# 日报\n\nA [1]。\nB [3]。\n采集含 FRED [2]。\n"), [5])

    def test_move_up_blocked(self):
        self.assertEqual(self.lines("# 日报\n\n采集含 FRED [2]。\nA [1]。\nB [3]。\n"), [3])

    def test_replace_neighbor_blocked(self):
        self.assertEqual(self.lines("# 日报\n\nA 改 [1]。\n采集含 FRED [2]。\nB [3]。\n"), [4])

    def test_insert_above_blocked(self):
        self.assertEqual(self.lines("# 日报\n\n新行 [9]。\nA [1]。\n采集含 FRED [2]。\nB [3]。\n"), [5])

    def test_duplicate_line_blocked(self):
        self.assertEqual(self.lines(self.OLD + "采集含 FRED [2]。\n"), [6])

    def test_append_far_below_keeps_old(self):
        self.assertEqual(self.lines(self.OLD + "\n更正说明 [4]。\n"), [])


class R5MalformedShortcode(unittest.TestCase):
    def test_unclosed_quote_does_not_swallow(self):
        doc = TITLE + '前文 {{< ref note="未闭合 >}}\n' + link("正文 42 项 [1]。")
        c = codes(doc)
        self.assertEqual(c.get("E-INDUSTRY-NUMBER"), 1)
        self.assertIn("E-SHORTCODE-MALFORMED", _sc.check_text(doc, REPO, DATE, "daily", link_checker=lambda u: True)["error_codes"])

    def test_unterminated_tag(self):
        doc = TITLE + "前文 {{< ref x\n" + link("正文 [1]。")
        r = _sc.check_text(doc, REPO, DATE, "daily", link_checker=lambda u: True)
        self.assertIn("E-SHORTCODE-MALFORMED", r["error_codes"])

    def test_bad_name(self):
        r = _sc.check_text(TITLE + "前文 {{< >}} [1]。\n", REPO, DATE, "daily", link_checker=lambda u: True)
        self.assertIn("E-SHORTCODE-MALFORMED", r["error_codes"])

    def test_pass_wellformed(self):
        r = _sc.check_text(TITLE + link("正文 [1]。"), REPO, DATE, "daily", link_checker=lambda u: True)
        self.assertNotIn("E-SHORTCODE-MALFORMED", r["error_codes"])


class R5BodyCite(unittest.TestCase):
    def test_html_attr_blocked(self):
        self.assertEqual(codes(link('正文 <span data-value="[123]">词</span> [1]。')), {"E-INDUSTRY-NUMBER": 1})

    def test_double_bracket_blocked(self):
        self.assertEqual(codes(link("正文 [[123]] [1]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_code_span_blocked(self):
        self.assertEqual(codes(link("正文 `[12]` [1]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_link_text_blocked(self):
        self.assertEqual(codes(link("正文 [12](https://example.org) [1]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_attr_without_tag_blocked(self):
        self.assertEqual(codes(link('正文 x="[12]" [1]。')), {"E-INDUSTRY-NUMBER": 1})

    def test_pass_standalone(self):
        self.assertEqual(codes(link("正文 [1][2]，另见 [3]。")), {})


class R5Hosts(unittest.TestCase):
    def test_path_not_host(self):
        self.assertEqual(codes(link("见 https://example.org/path/bea.gov [1]。")), {})

    def test_query_not_host(self):
        self.assertEqual(codes(link("见 https://example.org/?u=bea.gov [1]。")), {})

    def test_bare_path_not_host(self):
        self.assertEqual(codes(link("见 example.org/p/bea.gov [1]。")), {})

    def test_percent_encoded_dot_blocked(self):
        self.assertEqual(codes(link("见 bea%2Egov [1]。")), {"E-INDUSTRY-AGENCY-LINK": 1, "E-INDUSTRY-NUMBER": 1})   # %2E 里的 2 也算数值
        self.assertEqual(codes(link("见 https://bea%2egov/x [1]。")), {"E-INDUSTRY-AGENCY-LINK": 1, "E-INDUSTRY-NUMBER": 1})

    def test_percent_encoded_suffix_passes(self):
        self.assertNotIn("E-INDUSTRY-AGENCY-LINK", codes(link("见 bea.gov%2Eexample [1]。")))

    def test_scheme_relative(self):
        self.assertEqual(codes(link("见 //www.bls.gov/x [1]。")), {"E-INDUSTRY-AGENCY-LINK": 1})

    def test_fred_percent(self):
        self.assertEqual(codes(TITLE + "见 fred%2Estlouisfed%2Eorg [1]。\n"), {"E-FRED-CITED": 1})

    def test_fred_in_path_passes(self):
        self.assertEqual(codes(TITLE + "见 https://example.org/fred.stlouisfed.org [1]。\n"), {})


if __name__ == "__main__":
    unittest.main()
