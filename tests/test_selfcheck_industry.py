"""selfcheck：产业与经济数据小节（站点 industry-* 短代码块）与 E-FRED-CITED。
2026-10-25 起开放非 BEA 已批数字（王总 t549u「加快」+ Grok Bot 开放非 BEA 数字裁定）：
块内普通数值与已开放机构（federalreserve.gov）链接放行；BEA/BLS/Census/EIA 数值表述与未开放机构链接仍拦；FRED 仍拦。
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
        self.assertEqual(len(_sc.industry_blocks(doc)), 1)
        self.assertEqual(codes(doc), {})  # 开放数字后，无未开放机构标记的数值放行

    def test_shortcode_names(self):
        self.assertEqual(_sc.INDUSTRY_SHORTCODES, ("industry-data", "industry-datum", "industry-link"))


class IndustryNumber(unittest.TestCase):
    def test_pass_citations_item_cite_only(self):
        self.assertEqual(codes(TITLE + LINK_OK), {})
        self.assertEqual(codes(TITLE + LINK_OK_EN), {})

    def test_pass_digit_in_body_after_open(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}训练规模增加 3 倍对应算力需求 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {})

    def test_pass_fullwidth_digit_after_open(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}约３成对应算力需求 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {})

    def test_pass_percent_after_open(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}占比以％计的部分对应需求 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {})

    def test_pass_datum_value_neutral_publisher(self):
        doc = TITLE + data("上月", "102.3", "2026-10-17")
        self.assertEqual(codes(doc), {})

    def test_pass_frb_datum_and_link_with_numbers(self):
        doc = TITLE + ('{{< industry-data >}}\n'
                       '{{< industry-datum series="美国制造业工业生产指数" publisher="美联储理事会" '
                       'frequency="monthly" period="2026-09" value="102.3" released="2026-10-17" cite="4" >}}\n'
                       '{{< /industry-data >}}\n')
        self.assertEqual(codes(doc), {})
        doc = TITLE + ('{{< industry-link item="1" industry="manufacturing" side="demand" >}}'
                       '可对照 https://www.federalreserve.gov/releases/g17/current/default.htm 读数 102.3 [1]。'
                       '{{< /industry-link >}}\n')
        self.assertEqual(codes(doc), {})

    def test_block_bea_number_statement(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}BEA 公布的读数 2.1% 对应需求 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_block_bea_full_name_number(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}美国经济分析局读数 102.3 对应需求 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_block_bea_commerce_full_name_datum(self):
        # r1：美国商务部经济分析局 + 数值须触发 E-INDUSTRY-NUMBER
        doc = TITLE + ('{{< industry-data >}}\n'
                       '{{< industry-datum series="甲" publisher="美国商务部经济分析局" value="2.1%" cite="4" >}}\n'
                       '{{< /industry-data >}}\n')
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_block_unopened_agency_name_without_domain(self):
        # r1：未开放机构纯名称（不在 BEA/BLS/Census/EIA 四家表、无域名）同块有数值不得放行
        doc = TITLE + ('{{< industry-data >}}\n'
                       '{{< industry-datum series="甲" publisher="美国财政部" value="2.1" cite="4" >}}\n'
                       '{{< /industry-data >}}\n')
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}美国财政部读数 2.1 对应需求 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_block_frb_url_cjk_period_then_bea_number(self):
        # r2 MEDIUM：URL 去主机勿把「。BEA」吞进路径；须仍触发 E-INDUSTRY-NUMBER
        doc = TITLE + (
            '{{< industry-link item="1" industry="manufacturing" side="demand" >}}'
            '可对照 https://www.federalreserve.gov/releases/g17/current/default.htm。BEA 读数 2.1 [1]。'
            '{{< /industry-link >}}\n'
        )
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_block_frb_url_cjk_clause_punct_then_bea_number(self):
        # r3 MEDIUM：NFKC 前按 ，：； 切 URL；覆盖全角与（规范化后）半角
        for punct in ("，", "：", "；", ",", ":", ";"):
            with self.subTest(punct=punct):
                doc = TITLE + (
                    '{{< industry-link item="1" industry="manufacturing" side="demand" >}}'
                    '可对照 https://www.federalreserve.gov/releases/g17/current/default.htm'
                    + punct +
                    'BEA 读数 2.1 [1]。'
                    '{{< /industry-link >}}\n'
                )
                self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1}, punct)

    def test_block_imf_publisher_without_domain(self):
        # r2 MEDIUM：未开放机构名相对 INDUSTRY_AGENCY_DOMAINS 须覆盖 IMF 等；无域名数值不得放行
        doc = TITLE + (
            '{{< industry-data >}}\n'
            '{{< industry-datum series="甲" publisher="International Monetary Fund" value="2.1" cite="4" >}}\n'
            '{{< /industry-data >}}\n'
        )
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})
        doc = TITLE + (
            '{{< industry-data >}}\n'
            '{{< industry-datum series="甲" publisher="OECD" value="2.1" cite="4" >}}\n'
            '{{< /industry-data >}}\n'
        )
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})
        doc = TITLE + (
            '{{< industry-data >}}\n'
            '{{< industry-datum series="甲" publisher="World Bank" value="2.1" cite="4" >}}\n'
            '{{< /industry-data >}}\n'
        )
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_block_white_house_and_eu_commission_publisher(self):
        # r3 MEDIUM：补 White House / 欧盟委员会 等未开放域名常用名
        doc = TITLE + (
            '{{< industry-data >}}\n'
            '{{< industry-datum series="甲" publisher="White House" value="2.1" cite="4" >}}\n'
            '{{< /industry-data >}}\n'
        )
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})
        doc = TITLE + (
            '{{< industry-data >}}\n'
            '{{< industry-datum series="甲" publisher="欧盟委员会" value="2.1" cite="4" >}}\n'
            '{{< /industry-data >}}\n'
        )
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_block_bls_number_statement(self):
        doc = TITLE + '{{< industry-link item="1" industry="energy" side="cost" >}}BLS 电价 16.5 对应成本 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1})

    def test_block_bea_domain_with_number(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" >}}见 https://www.bea.gov/data 读数 2.1 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-NUMBER": 1, "E-INDUSTRY-AGENCY-LINK": 1})

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

    def test_pass_open_federalreserve(self):
        doc = TITLE + '{{< industry-link item="1" industry="manufacturing" side="demand" >}}对应需求，见 https://www.federalreserve.gov/releases/g17/current/default.htm [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {})

    def test_block_bls_still(self):
        doc = TITLE + '{{< industry-link item="1" industry="energy" side="cost" >}}对应成本，见 https://www.bls.gov/cpi/ [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {"E-INDUSTRY-AGENCY-LINK": 1})

    def test_domain_list_contains_required(self):
        for d in ("bea.gov", "bls.gov", "census.gov", "eia.gov", "federalreserve.gov", "stats.gov.cn", "pbc.gov.cn", "customs.gov.cn", "sec.gov"):
            self.assertIn(d, _sc.INDUSTRY_AGENCY_DOMAINS)
        self.assertEqual(_sc.INDUSTRY_OPEN_AGENCY_DOMAINS, ("federalreserve.gov",))


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
        self.assertEqual(codes(doc), {})  # 开放数字后中性 publisher 数值放行

    def test_quoted_closer_in_link_param(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" inference="甲 >}} 乙" >}}正文 7 处 [1]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {})

    def test_multiple_blocks(self):
        doc = link("正文 [1]。") + "块外 12 分 [2]。\n" + link("正文第 3 项 [3]。")
        self.assertEqual(len(_sc.industry_blocks(doc)), 2)
        self.assertEqual(codes(doc), {})

    def test_nested_same_name(self):
        doc = TITLE + L + "外层 [1]。" + L + "内层 [2]。" + LE.strip() + "外层末尾 5 [3]。" + LE
        self.assertEqual(len(_sc.industry_blocks(doc)), 1)
        self.assertEqual(codes(doc), {})

    def test_percent_delimiter_form(self):
        doc = TITLE + '{{% industry-link item="1" industry="ai" side="demand" %}}正文 9 [1]。{{% /industry-link %}}\n'
        self.assertEqual(codes(doc), {})


class R4NumberExemption(unittest.TestCase):           # 只豁免 industry-* 自身的 cite/item 参数与正文真实 [n]
    def test_value_bracketed_not_exempt(self):
        # 开放后中性 publisher 的数值放行；本例验证解析仍把 value 当块内文字（不因方括号豁免 cite）
        doc = TITLE + '{{< industry-data >}}\n{{< industry-datum series="甲" value="[123]" cite="4" >}}\n{{< /industry-data >}}\n'
        self.assertEqual(codes(doc), {})
        doc_bea = TITLE + '{{< industry-data >}}\n{{< industry-datum series="甲" publisher="BEA" value="[123]" cite="4" >}}\n{{< /industry-data >}}\n'
        self.assertEqual(codes(doc_bea), {"E-INDUSTRY-NUMBER": 1})

    def test_data_cite_param_not_exempt(self):
        doc = TITLE + '{{< industry-datum series="甲" data-cite="123" cite="4" >}}\n'
        self.assertEqual(codes(doc), {})
        doc_bea = TITLE + '{{< industry-datum series="甲" publisher="BEA" data-cite="123" cite="4" >}}\n'
        self.assertEqual(codes(doc_bea), {"E-INDUSTRY-NUMBER": 1})

    def test_body_cite_text_not_exempt(self):
        self.assertEqual(codes(link('正文 cite="123" [1]。')), {})
        self.assertEqual(codes(link('正文 BEA cite="123" [1]。')), {"E-INDUSTRY-NUMBER": 1})

    def test_cite_param_bad_format_not_exempt(self):
        doc = TITLE + '{{< industry-datum series="甲" cite="12.5" >}}\n'
        self.assertEqual(codes(doc), {})
        doc_bea = TITLE + '{{< industry-datum series="甲" publisher="BEA" cite="12.5" >}}\n'
        self.assertEqual(codes(doc_bea), {"E-INDUSTRY-NUMBER": 1})

    def test_cite_param_of_other_shortcode_not_exempt(self):
        self.assertEqual(codes(link('正文 {{< ref cite="123" >}} [1]。')), {})
        self.assertEqual(codes(link('正文 BLS {{< ref cite="123" >}} [1]。')), {"E-INDUSTRY-NUMBER": 1})

    def test_bracket_too_long_not_exempt(self):
        self.assertEqual(codes(link("正文 [1234]。")), {})
        self.assertEqual(codes(link("正文 Census [1234]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_pass_real_cite_and_item(self):
        doc = TITLE + '{{< industry-link item="12" industry="ai" side="demand" >}}正文 [1][2]。{{< /industry-link >}}\n'
        self.assertEqual(codes(doc), {})
        doc = TITLE + '{{< industry-data >}}\n{{< industry-datum series="甲" value="x" cite="4, 5" >}}\n{{< /industry-data >}}\n'
        self.assertEqual(codes(doc), {})


class R4UnicodeDigits(unittest.TestCase):
    def test_arabic_indic_open(self):
        self.assertEqual(codes(link("正文 ١٢ 项 [1]。")), {})

    def test_devanagari_open(self):
        self.assertEqual(codes(link("正文 ३ 项 [1]。")), {})

    def test_superscript_and_circled_open(self):
        self.assertEqual(codes(link("正文 ² 项 [1]。")), {})
        self.assertEqual(codes(link("正文 ① 项 [1]。")), {})

    def test_entity_digit_open(self):
        self.assertEqual(codes(link("正文 &#49; 项 [1]。")), {})

    def test_percent_variants_open(self):
        for p in ("﹪", "٪", "‰", "؉"):
            self.assertEqual(codes(link(f"正文以{p}计 [1]。")), {}, p)

    def test_closed_agency_still_blocks_unicode_digit(self):
        self.assertEqual(codes(link("正文 BEA ١٢ 项 [1]。")), {"E-INDUSTRY-NUMBER": 1})
        self.assertEqual(codes(link("正文 EIA ³ 项 [1]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_pass_no_digits(self):
        self.assertEqual(codes(link("正文没有任何数值 [1]。")), {})


class R4HostBoundaries(unittest.TestCase):
    def test_pass_suffix_lookalike(self):
        self.assertEqual(codes(link("见 https://bea.gov.example/x [1]。")), {})
        self.assertEqual(codes(link("见 bea.gov.example [1]。")), {})

    def test_pass_suffix_lookalike_with_number(self):
        # r1 低：名称匹配排除 URL 主机，避免 bea.gov.example + 数值误报 E-INDUSTRY-NUMBER
        self.assertEqual(codes(link("见 https://bea.gov.example/x 读数 2.1 [1]。")), {})
        self.assertEqual(codes(link("见 bea.gov.example 读数 2.1 [1]。")), {})
        # r2 低：裸域名路径中的 BEA 片段勿误报
        self.assertEqual(codes(link("见 bea.gov.example/BEA/data 读数 2.1 [1]。")), {})

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


class R5MalformedShortcode(unittest.TestCase):
    def test_unclosed_quote_does_not_swallow(self):
        doc = TITLE + '前文 {{< ref note="未闭合 >}}\n' + link("正文 42 项 [1]。")
        c = codes(doc)
        self.assertNotIn("E-INDUSTRY-NUMBER", c)  # 开放后无未开放机构标记的数值放行
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
        self.assertEqual(codes(link('正文 <span data-value="[123]">词</span> [1]。')), {})
        self.assertEqual(codes(link('正文 BEA <span data-value="[123]">词</span> [1]。')), {"E-INDUSTRY-NUMBER": 1})

    def test_double_bracket_blocked(self):
        self.assertEqual(codes(link("正文 [[123]] [1]。")), {})
        self.assertEqual(codes(link("正文 BLS [[123]] [1]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_code_span_blocked(self):
        self.assertEqual(codes(link("正文 `[12]` [1]。")), {})
        self.assertEqual(codes(link("正文 Census `[12]` [1]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_link_text_blocked(self):
        self.assertEqual(codes(link("正文 [12](https://example.org) [1]。")), {})
        self.assertEqual(codes(link("正文 EIA [12](https://example.org) [1]。")), {"E-INDUSTRY-NUMBER": 1})

    def test_attr_without_tag_blocked(self):
        self.assertEqual(codes(link('正文 x="[12]" [1]。')), {})
        self.assertEqual(codes(link('正文 BEA x="[12]" [1]。')), {"E-INDUSTRY-NUMBER": 1})

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


# ---------------------------------------------------------------- r6 后的收窄版（Grok Bot 16:48）
class R7FredAllowlist(unittest.TestCase):
    REL = "digest/2026-10-15.md"

    def text(self):
        return (_ROOT / self.REL).read_text(encoding="utf-8")

    def fred(self, text, rel):
        # 模拟可信入口核定路径；测放行逻辑时用 trust_repo_rel，测伪造时直接传普通字符串
        trusted = _sc.trust_repo_rel(rel) if rel is not None else None
        r = _sc.check_text(text, _ROOT, "2026-10-15", "daily", link_checker=lambda u: True, rel=trusted)
        return [e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"]

    def test_listed_lines_pass(self):
        for rel in ("digest/2026-10-15.md", "digest/2026-10-16.md", "digest/2026-10-17.md", "digest/2026-10-18.md"):
            self.assertEqual(self.fred((_ROOT / rel).read_text(encoding="utf-8"), rel), [], rel)

    def test_one_char_changed_blocked(self):
        L = self.text().split("\n")
        L[4] = L[4].replace("FRED", "FRED ", 1)
        self.assertEqual(self.fred("\n".join(L), self.REL), [5])

    def test_different_line_number_blocked(self):
        self.assertEqual(self.fred("\n" + self.text(), self.REL), [6, 141])

    def test_copied_into_new_digest_blocked(self):     # 真实存在、但不在清单里的 digest 文件（临时仓库目录）
        with _tmp.TemporaryDirectory() as d:
            (_P(d) / "digest").mkdir()
            f = _P(d) / "digest" / "2026-10-20.md"
            f.write_text(self.text(), encoding="utf-8")
            self.assertTrue(f.is_file())
            r = _sc.check_file(str(f), d, "2026-10-20", "daily", link_checker=lambda u: True)
            self.assertEqual([e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"], [5, 140])

    def test_listed_path_in_temp_repo_same_text_passes(self):   # 放行只看受检文本，不看磁盘上是不是原文件
        with _tmp.TemporaryDirectory() as d:
            (_P(d) / "digest").mkdir()
            f = _P(d) / "digest" / "2026-10-15.md"
            f.write_text(self.text(), encoding="utf-8")
            r = _sc.check_file(str(f), d, "2026-10-15", "daily", link_checker=lambda u: True)
            self.assertEqual([e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"], [])

    def test_path_matches_but_checked_line_differs_blocked(self):
        L = self.text().split("\n")
        L[139] = L[139] + " "
        self.assertEqual(self.fred("\n".join(L), self.REL), [140])
        with _tmp.TemporaryDirectory() as d:
            (_P(d) / "digest").mkdir()
            f = _P(d) / "digest" / "2026-10-15.md"
            f.write_text("\n".join(L), encoding="utf-8")
            r = _sc.check_file(str(f), d, "2026-10-15", "daily", link_checker=lambda u: True)
            self.assertEqual([e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"], [140])

    def test_unnormalized_rel_blocked(self):
        for rel in ("./digest/2026-10-15.md", "digest//2026-10-15.md", "/digest/2026-10-15.md", "digest\\2026-10-15.md"):
            self.assertEqual(self.fred(self.text(), rel), [5, 140], rel)

    def test_crlf_blocked(self):
        self.assertEqual(self.fred(self.text().replace("\n", "\r\n"), self.REL), [5, 140])

    def test_outside_repo_blocked(self):
        self.assertEqual(self.fred(self.text(), None), [5, 140])
        self.assertEqual(self.fred(self.text(), "../digest/2026-10-15.md"), [5, 140])

    def test_outside_repo_file_cli(self):
        with _tmp.TemporaryDirectory() as d:
            f = _P(d) / "2026-10-15.md"
            f.write_text(self.text(), encoding="utf-8")
            r = _sc.check_file(str(f), _ROOT, "2026-10-15", "daily", link_checker=lambda u: True)
            self.assertEqual([e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"], [5, 140])

    def test_forged_string_rel_check_text_blocked(self):
        """外部直接传普通字符串 rel= 不能借旧行豁免（即使路径格式合法、文本相同）。"""
        r = _sc.check_text(self.text(), _ROOT, "2026-10-15", "daily", link_checker=lambda u: True, rel=self.REL)
        self.assertEqual([e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"], [5, 140])

    def test_forged_rel_check_file_outside_blocked(self):
        """仓库外文件交给 check_file 并显式传伪造 rel= 时，不能借旧行豁免。"""
        with _tmp.TemporaryDirectory() as d:
            f = _P(d) / "2026-10-15.md"
            f.write_text(self.text(), encoding="utf-8")
            r = _sc.check_file(str(f), _ROOT, "2026-10-15", "daily", link_checker=lambda u: True, rel=self.REL)
            self.assertEqual([e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"], [5, 140])

    def test_listed_rel_file_absent_still_passes(self):
        """清单 rel 对应文件在受检仓库里不存在时，仅凭核定路径+行号+受检文本该行 sha256 仍可放行。
        若恢复旧的「文件必须存在」条件，本测试应失败。"""
        with _tmp.TemporaryDirectory() as d:
            self.assertFalse((_P(d) / self.REL).exists())
            r = _sc.check_text(self.text(), d, "2026-10-15", "daily", link_checker=lambda u: True,
                               rel=_sc.trust_repo_rel(self.REL))
            self.assertEqual([e["line"] for e in r["errors"] if e["code"] == "E-FRED-CITED"], [])
            # 直接调用底层：同样不依赖磁盘文件
            self.assertEqual(_sc.fred_cited_lines(self.text(), repo=d, rel=_sc.trust_repo_rel(self.REL)), [])

    def test_no_baseline_mechanism(self):
        import inspect
        self.assertNotIn("baseline", inspect.signature(_sc.check_text).parameters)
        self.assertFalse(hasattr(_sc, "changed_lines"))
        rc, out, err = _cli(["x.md", "--repo", ".", "--date", DATE, "--card-type", "daily", "--baseline-ref", "HEAD"])
        self.assertNotEqual(rc, 0)
        self.assertIn("unrecognized arguments", err)


def _mcodes(text):
    r = _sc.check_text(text, REPO, DATE, "daily", link_checker=lambda u: True)
    return set(r["error_codes"])


class R7NestedOpener(unittest.TestCase):
    def test_unquoted_param_nested_opener(self):
        doc = TITLE + "{{< ref x=bad{{< industry-link item=\"1\" industry=\"ai\" side=\"demand\" >}}42{{< /industry-link >}}\n"
        c = _mcodes(doc)
        self.assertIn("E-SHORTCODE-MALFORMED", c)
        self.assertNotIn("E-INDUSTRY-NUMBER", c)  # 开放后纯数值放行
        doc2 = TITLE + "{{< ref x=bad{{< industry-link item=\"1\" industry=\"ai\" side=\"demand\" >}}BEA 42{{< /industry-link >}}\n"
        self.assertIn("E-INDUSTRY-NUMBER", _mcodes(doc2))

    def test_quoted_param_nested_opener(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" inference="甲{{乙" >}}正文 [1]。{{< /industry-link >}}\n'
        self.assertIn("E-SHORTCODE-MALFORMED", _mcodes(doc))

    def test_datum_param_braces(self):
        doc = TITLE + '{{< industry-datum series="甲{{" cite="1" >}}\n'
        self.assertIn("E-SHORTCODE-MALFORMED", _mcodes(doc))

    def test_pass_closing_braces_only(self):
        doc = TITLE + '{{< industry-datum series="甲}}" value="x" cite="1" >}}\n'
        self.assertNotIn("E-SHORTCODE-MALFORMED", _mcodes(doc))


class R7HtmlAttr(unittest.TestCase):
    def test_gt_in_double_quoted_attr(self):
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link('正文 <span data-value=">[123]">词</span> [1]。')))

    def test_gt_in_single_quoted_attr(self):
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("正文 <span title='a>b'>词</span> [1]。")))

    def test_unterminated_html_tag(self):
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link('正文 <span title="a [1]。')))

    def test_pass_plain_html(self):
        self.assertNotIn("E-INDUSTRY-MARKUP", _mcodes(link('正文 <span class="x">词</span> [1]。')))

    def test_outside_block_not_this_code(self):
        self.assertNotIn("E-INDUSTRY-MARKUP", _mcodes(TITLE + '正文 <span data-value=">x">词</span> [1]。\n'))


class R7UrlStrict(unittest.TestCase):
    def test_percent_in_url(self):
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("见 https://example.org%2F@bea.gov/path [1]。")))
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("见 https://example.org/a%20b [1]。")))

    def test_userinfo_at(self):
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("见 https://user@example.org/x [1]。")))

    def test_scheme_relative_at(self):
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("见 //user@example.org/x [1]。")))

    def test_pass_plain_url(self):
        self.assertNotIn("E-INDUSTRY-MARKUP", _mcodes(link("见 https://example.org/path [1]。")))

    def test_at_in_query(self):
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("见 https://example.org/x?email=a@b [1]。")))

    def test_at_in_fragment(self):
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("见 https://example.org/x#email=a@b [1]。")))

    def test_at_in_path(self):
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("见 https://example.org/@user [1]。")))

    def test_at_bare_token(self):
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("联系 a@bea.gov [1]。")))
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("见 user@example.org/x [1]。")))

    def test_at_fullwidth_and_entity(self):
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("联系 a＠b [1]。")))
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("联系 a&#64;b [1]。")))

    def test_at_outside_block_not_this_code(self):
        self.assertNotIn("E-INDUSTRY-MARKUP", _mcodes(TITLE + "联系 a@b [1]。\n"))

    def test_url_in_param(self):
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" inference="见 https://a@example.org" >}}正文 [1]。{{< /industry-link >}}\n'
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(doc))

    def test_at_commercial_at(self):
        """小写商业符号 ﹫ 独立反例。"""
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("联系 a﹫b [1]。")))

    def test_at_commat_entity(self):
        """HTML 实体 &commat; 独立反例。"""
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(link("联系 a&commat;b [1]。")))

    def test_at_in_plain_param(self):
        """普通短代码参数值（非 URL）里的 @ 独立反例。"""
        doc = TITLE + '{{< industry-link item="1" industry="ai" side="demand" inference="联系 a@b" >}}正文 [1]。{{< /industry-link >}}\n'
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(doc))

    def test_at_in_datum_param(self):
        """industry-datum 参数里的 @ 独立反例。"""
        doc = TITLE + '{{< industry-datum series="a@b" cite="1" >}}\n'
        self.assertIn("E-INDUSTRY-MARKUP", _mcodes(doc))


if __name__ == "__main__":
    unittest.main()
