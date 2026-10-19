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


if __name__ == "__main__":
    unittest.main()
