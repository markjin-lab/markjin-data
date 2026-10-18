"""#32（迁移自旧库 #51）：原文支持位置门禁。每例同时断言 status 与错误码。"""
import unittest
from helpers import make_repo, arxiv_line, fred_line, x_line, DATE, ARXIV_ID, XPOST_ID, ARXIV_LOC, FRED_LOC, FILES
from markjin.selfcheck import check_text

REPO = make_repo()
T = f"# 日报 {DATE}\n"
XSRC = f"`raw/{DATE}/x/01.json` · https://x.com/i/status/{XPOST_ID}"
ASRC = f"`raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1"


def run(text, card_type="daily", repo=REPO):
    return check_text(text, repo, DATE, card_type, link_checker=lambda u: True)


class Base(unittest.TestCase):
    def expect(self, r, status, *codes, absent=()):
        self.assertEqual(r["status"], status, r["errors"])
        for c in codes:
            self.assertIn(c, r["error_codes"])
        for c in absent:
            self.assertNotIn(c, r["error_codes"])


class SupportLocator(Base):

    def test_supported_passes(self):
        self.expect(run(T + arxiv_line()), "PASS", absent=("E-SUPPORT-LOCATOR-MISSING", "E-SUPPORT-LOCATOR-MISMATCH"))
        self.expect(run(T + fred_line()), "PASS", absent=("E-SUPPORT-LOCATOR-MISMATCH",))

    def test_missing_locator_blocked(self):
        self.expect(run(T + arxiv_line(locator=None)), "FAIL", "E-SUPPORT-LOCATOR-MISSING")
        self.expect(run(T + fred_line(locator=None)), "FAIL", "E-SUPPORT-LOCATOR-MISSING")
        # 信号卡不在本门禁范围（另须王总批准），只保留原有提示
        self.expect(run(arxiv_line(locator=None), card_type="signal"), "PASS", absent=("E-SUPPORT-LOCATOR-MISSING",))

    def test_locator_not_in_source_blocked(self):
        # 位置是编造的（原文里没有这句）
        self.expect(run(T + arxiv_line(locator="The model reaches 90% accuracy on GSM8K.")), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_same_number_other_metric_blocked(self):
        # 反例一：同一个数字、指标不同。旧逻辑只核数字，90 出现在条目里就算支持，连 R-SUPPORT-UNVERIFIED 都不报
        r = run(T + arxiv_line("模型在 GSM8K 上达到 90% 准确率。"))
        self.expect(r, "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_same_number_other_object_blocked(self):
        files = dict(FILES)
        files["arxiv/cs.AI.xml"] = (f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id><summary>"
                                    "GPT-4 reaches 90% accuracy on MMLU. Our model reaches 75% accuracy on MMLU.</summary></entry></feed>")
        repo = make_repo(files)
        # 反例一（对象不同）：原文里 90% 属于 GPT-4，断言写成本文模型；位置只摘了本文模型那一句 → 数字不在位置里
        r = run(T + arxiv_line("本文模型 (Ours) 在 MMLU 上达到 90%。", locator="Our model reaches 75% accuracy on MMLU."), repo=repo)
        self.expect(r, "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        # 位置摘的是 GPT-4 那一句、断言写别的代号 → 代号不在位置里
        r = run(T + arxiv_line("Llama-3 在 MMLU 上达到 90%。", locator="GPT-4 reaches 90% accuracy on MMLU."), repo=repo)
        self.expect(r, "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        # 对照：代号、指标、数字都对得上 → 通过
        r = run(T + arxiv_line("GPT-4 在 MMLU 上达到 90%。", locator="GPT-4 reaches 90% accuracy on MMLU."), repo=repo)
        self.expect(r, "PASS")

    def test_x_plus_unsupporting_nonx_blocked(self):
        # 反例二（旧库 #51）：X 条目含 2.0，arXiv 条目不含 2.0；两份存档、链接都合法
        self.expect(run(T + f"- 发布 2.0 版。 — {XSRC} ; {ASRC} 〔原文：{ARXIV_LOC}〕"), "FAIL", "E-X-ONLY", "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(T + f"- 发布 2.0 版。 — {XSRC} ; {ASRC}"), "FAIL", "E-X-ONLY", "E-SUPPORT-LOCATOR-MISSING")
        # 非结构化行、段落里的同类写法同样硬拦
        self.expect(run(T + f"- 发布 2.0 版。 — {XSRC} · {ASRC}"), "FAIL", "E-X-ONLY")
        self.expect(run(T + f"发布 2.0 版。见 {XSRC} 与 {ASRC}\n"), "FAIL", "E-X-ONLY")

    def test_x_plus_supporting_nonx_passes(self):
        r = run(T + f"- 模型在 MMLU 上达到 90% 准确率。 — {XSRC} ; {ASRC} 〔原文：{ARXIV_LOC}〕")
        self.expect(r, "PASS", absent=("E-X-ONLY",))

    def test_x_locator_does_not_count(self):
        # X 条目带位置也不能支撑断言
        self.expect(run(T + f"- 发布 2.0 版。 — {XSRC} 〔原文：release 2.0〕"), "FAIL", "E-X-ONLY")

    def test_qualitative_claim_still_flagged_for_codex(self):
        # 无数字的定性断言：位置成立即放行，但仍标 R-SUPPORT-UNVERIFIED，语义支持由 Codex 逐条审查
        r = run(T + arxiv_line("该方法能很好地处理长文档。", locator="The method handles long documents well."))
        self.expect(r, "PASS", "R-SUPPORT-UNVERIFIED")


def custom_repo(summary):
    files = dict(FILES)
    files["arxiv/cs.AI.xml"] = f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id><summary>{summary}</summary></entry></feed>"
    return make_repo(files)


class ParagraphHeading(Base):
    """#32 r2：段落、标题、注释里的来源同样须逐来源写明支持位置并核对通过。"""
    def test_paragraph_same_number_other_metric_blocked(self):
        # N1：段落里同数字不同指标
        self.expect(run(T + f"模型在 GSM8K 上达到 90%。见 {ASRC}\n"), "FAIL", "E-SUPPORT-LOCATOR-MISSING")
        self.expect(run(T + f"模型在 GSM8K 上达到 90%。见 {ASRC} 〔原文：{ARXIV_LOC}〕\n"), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_heading_same_number_other_metric_blocked(self):
        # N2：标题里同数字不同指标
        self.expect(run(T + f"## 模型在 GSM8K 上达到 90% {ASRC}\n"), "FAIL", "E-SUPPORT-LOCATOR-MISSING")
        self.expect(run(T + f"## 模型在 GSM8K 上达到 90% {ASRC} 〔原文：{ARXIV_LOC}〕\n"), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(T + f"<!-- 模型在 GSM8K 上达到 90% {ASRC} -->\n" + arxiv_line()), "FAIL", "E-SUPPORT-LOCATOR-MISSING")

    def test_paragraph_heading_qualitative_x_plus_nonx_blocked(self):
        # N3、N9：无数字的定性断言，X + 非 X，旧逻辑“有非 X 来源就算支撑” → 现在必须有位置
        for doc in (f"该方法远超所有对手。见 {XSRC} 与 {ASRC}\n", f"## 该方法远超所有对手 {XSRC} {ASRC}\n"):
            self.expect(run(T + doc), "FAIL", "E-X-ONLY", "E-SUPPORT-LOCATOR-MISSING")

    def test_paragraph_with_valid_locator_passes(self):
        r = run(T + f"模型在 MMLU 上达到 90%。见 {ASRC} 〔原文：{ARXIV_LOC}〕\n")
        self.expect(r, "PASS", "R-SUPPORT-REVIEW", absent=("E-SUPPORT-LOCATOR-MISSING", "E-SUPPORT-LOCATOR-MISMATCH"))

    def test_pure_citation_line_not_assertion(self):
        # 只有“来源/见”和链接、没有断言文字的段落不要求位置
        self.expect(run(T + f"来源：{ASRC} ；见 https://github.com/markjin-lab/markjin-data/blob/x/raw\n" + arxiv_line()), "PASS")


class SemanticChecks(Base):
    """#32 r2：单位/倍数、否定、位置过短、人工审查提示、中文对象名与单大写字母专名。"""
    def test_percent_vs_times_blocked(self):
        # N7：原文 90%，断言写 90 倍
        self.expect(run(T + arxiv_line("模型在 MMLU 上提升 90 倍。")), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        repo = custom_repo("The model is 3x faster on MMLU.")
        self.expect(run(T + arxiv_line("模型在 MMLU 上快 3%。", locator="The model is 3x faster on MMLU."), repo=repo),
                    "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(T + arxiv_line("模型在 MMLU 上快 3 倍。", locator="The model is 3x faster on MMLU."), repo=repo), "PASS")

    def test_percent_vs_points_blocked(self):
        repo = custom_repo("Accuracy on MMLU rose by 5 percentage points.")
        self.expect(run(T + arxiv_line("MMLU 准确率提高 5%。", locator="Accuracy on MMLU rose by 5 percentage points."), repo=repo),
                    "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_negation_blocked(self):
        # N4：原文“未能达到”，断言写“达到”；反之亦然
        repo = custom_repo("The model fails to reach 90% accuracy on MMLU.")
        loc = "The model fails to reach 90% accuracy on MMLU."
        self.expect(run(T + arxiv_line("模型在 MMLU 上达到 90% 准确率。", locator=loc), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(T + arxiv_line("模型在 MMLU 上未能达到 90% 准确率。", locator=loc), repo=repo), "PASS")
        self.expect(run(T + arxiv_line("模型在 MMLU 上未能达到 90% 准确率。")), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_short_locator_hinted(self):
        # N8：极短摘录 → 提示
        r = run(T + arxiv_line("模型在 MMLU 上达到 90%。", locator="reaches 90% accuracy on MMLU"))
        self.expect(r, "PASS", "R-SUPPORT-REVIEW", absent=("R-LOCATOR-SHORT",))
        r = run(T + arxiv_line("MMLU 90%。", locator="90% accuracy"))
        self.assertIn("E-SUPPORT-LOCATOR-MISMATCH", r["error_codes"])   # 片段里没有 MMLU
        r = run(T + arxiv_line("达到 90%。", locator="90% accuracy"))
        self.expect(r, "PASS", "R-LOCATOR-SHORT", "R-SUPPORT-REVIEW")

    def test_numeric_pass_keeps_review_hint(self):
        r = run(T + arxiv_line())
        self.expect(r, "PASS", "R-SUPPORT-REVIEW")
        self.assertFalse(r["low_risk"])

    def test_chinese_object_substitution_hinted(self):
        # N5：原文是“该模型”，断言把对象换成“对照组”——机器核不了中文对象名，至少给提示
        r = run(T + arxiv_line("对照组在 MMLU 上达到 90% 准确率。"))
        self.expect(r, "PASS", "R-SUPPORT-ENTITY", "R-SUPPORT-REVIEW")

    def test_single_capital_name_hinted(self):
        # N6：Llama 只有一个大写字母，不算代号；不在位置里 → 提示（机器不硬拦，交 Codex）
        r = run(T + arxiv_line("Llama 在 MMLU 上达到 90% 准确率。"))
        self.expect(r, "PASS", "R-SUPPORT-ENTITY")
        repo = custom_repo("Llama reaches 90% accuracy on MMLU.")
        r = run(T + arxiv_line("Llama achieves 90% on MMLU.", locator="Llama reaches 90% accuracy on MMLU."), repo=repo)
        self.expect(r, "PASS", absent=("R-SUPPORT-ENTITY",))



FSRC = f"`raw/{DATE}/fred/UNRATE.json` · https://fred.stlouisfed.org/series/UNRATE"


def fred_repo(series=None, drop=False):
    files = dict(FILES)
    if drop:
        files.pop("fred/UNRATE.series.json")
    elif series is not None:
        files["fred/UNRATE.series.json"] = series
    return make_repo(files)


class FredUnits(Base):
    """#32 r3：FRED 序列单位存档并用于核对；拿不到单位时带单位的断言不能自动通过。"""
    def test_percent_series(self):
        self.expect(run(T + fred_line("UNRATE 为 4.2%。")), "PASS", "R-SUPPORT-REVIEW")
        self.expect(run(T + fred_line("UNRATE 为 4.2。")), "PASS")
        self.expect(run(T + fred_line("UNRATE 为 4.2 倍。")), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")       # F2
        self.expect(run(T + fred_line("UNRATE 为 4.2 个百分点。")), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_units_missing_or_unregistered(self):
        repo = fred_repo(drop=True)
        self.expect(run(T + fred_line("UNRATE 为 4.2%。"), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(T + fred_line("UNRATE 为 4.2。"), repo=repo), "PASS")    # 不带单位的断言只核数字
        repo = make_repo(dict(FILES))
        (repo / "raw" / DATE / "fred" / "UNRATE.series.json").write_text('{"id": "UNRATE", "units": "Times"}')  # 改了但没重登 MANIFEST
        self.expect(run(T + fred_line("UNRATE 为 4.2%。"), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_units_other_classes(self):
        repo = fred_repo('{"id": "UNRATE", "units": "Percentage Points"}')
        r = run(T + fred_line("UNRATE 为 4.2 个百分点。"), repo=repo)   # “个百分点”另被宏观措辞规则拦，这里只看单位门禁
        self.assertNotIn("E-SUPPORT-LOCATOR-MISMATCH", r["error_codes"], r["errors"])
        self.expect(run(T + fred_line("UNRATE 为 4.2%。"), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        repo = fred_repo('{"seriess": [{"id": "UNRATE", "units": "Index 1982-1984=100"}]}')
        self.expect(run(T + fred_line("UNRATE 为 4.2%。"), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(T + fred_line("UNRATE 为 4.2。"), repo=repo), "PASS")
        repo = fred_repo('{"id": "OTHER", "units": "Percent"}')
        self.expect(run(T + fred_line("UNRATE 为 4.2%。"), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")


class ChineseNumerals(Base):
    """#32 r3：中文数字先规范化再比较；解析不了的不能自动通过。"""
    def test_percent_words(self):
        self.expect(run(T + arxiv_line("模型在 MMLU 上准确率为百分之九十五。")), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(T + arxiv_line("模型在 MMLU 上准确率为九成五。")), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(T + arxiv_line("模型在 MMLU 上准确率为百分之九十。")), "PASS")
        self.expect(run(T + arxiv_line("模型在 MMLU 上准确率达九成。")), "PASS")

    def test_unparsable_not_auto_pass(self):
        for t in ("模型在 MMLU 上准确率为百分之九十几。", "模型在 MMLU 上准确率达九成多。"):
            self.expect(run(T + arxiv_line(t)), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_chinese_times_vs_percent(self):
        self.expect(run(T + arxiv_line("模型在 MMLU 上提升九十倍。")), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")


class NegationByClause(Base):
    """#32 r3：否定按具体说法核对，不整行判断。"""
    def test_unchanged_not_negation(self):
        r = run(T + fred_line("UNRATE 为 4.2%，失业率不变。"))      # P1：不因“不变”被当成否定误拦（语义仍交 Codex）
        self.assertNotIn("E-SUPPORT-LOCATOR-MISMATCH", r["error_codes"], r["errors"])

    def test_without_equals_no_need(self):
        loc = "Without fine-tuning, the model reaches 90% accuracy on MMLU."
        repo = custom_repo(loc)
        self.expect(run(T + arxiv_line("无需微调，模型在 MMLU 上达到 90% 准确率。", locator=loc), repo=repo), "PASS")   # P2
        # r4：without 只否定“微调”，不否定“达到 90%”。“经过微调”与 without 的矛盾属于前提语义，机器不硬拦，
        # 只保留人工审查提示，交 Codex 核对（见 PR 说明“局限”）
        r = run(T + arxiv_line("经过微调，模型在 MMLU 上达到 90% 准确率。", locator=loc), repo=repo)
        self.assertNotIn("E-SUPPORT-LOCATOR-MISMATCH", r["error_codes"]); self.assertIn("R-SUPPORT-REVIEW", r["error_codes"])

    def test_double_negation(self):
        loc = "The model is able to reach 90% accuracy on MMLU."
        repo = custom_repo(loc)
        self.expect(run(T + arxiv_line("模型并非不能在 MMLU 上达到 90%。", locator=loc), repo=repo), "PASS")   # C8
        loc2 = "The model did not fail to reach 90% accuracy on MMLU."
        repo2 = custom_repo(loc2)
        self.expect(run(T + arxiv_line("模型在 MMLU 上达到了 90%。", locator=loc2), repo=repo2), "PASS")          # 英文双重否定
        self.expect(run(T + arxiv_line("模型在 MMLU 上未能达到 90%。", locator=loc2), repo=repo2), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_negation_still_blocks(self):
        loc = "The model fails to reach 90% accuracy on MMLU."
        repo = custom_repo(loc)
        self.expect(run(T + arxiv_line("模型在 MMLU 上达到 90% 准确率。", locator=loc), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")


class ObjectPairing(Base):
    """#32 r4：先按对象配对分句，配不出唯一一句就判错配。原文两个分句都含“90% 和 MMLU”。"""
    LOC = "Model A reaches 90% accuracy on MMLU, while Model B fails to reach 90% accuracy on MMLU."

    def test_b_negative_direction(self):
        repo = custom_repo(self.LOC)
        self.expect(run(T + arxiv_line("Model B 在 MMLU 上未能达到 90% 准确率。", locator=self.LOC), repo=repo), "PASS")
        self.expect(run(T + arxiv_line("Model B 在 MMLU 上达到 90% 准确率。", locator=self.LOC), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_a_positive_direction(self):
        repo = custom_repo(self.LOC)
        self.expect(run(T + arxiv_line("Model A 在 MMLU 上达到 90% 准确率。", locator=self.LOC), repo=repo), "PASS")
        self.expect(run(T + arxiv_line("Model A 在 MMLU 上未能达到 90% 准确率。", locator=self.LOC), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_ambiguous_pairing_mismatch(self):
        # 断言不写是哪个模型：两个分句都配得上，不唯一 → 错配（两个方向都拦）
        repo = custom_repo(self.LOC)
        for c in ("模型在 MMLU 上达到 90% 准确率。", "模型在 MMLU 上未能达到 90% 准确率。"):
            self.expect(run(T + arxiv_line(c, locator=self.LOC), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")


class ImplicitNegation(Base):
    """#32 r4：no longer 与隐性否定（难以、未曾、尚待；hardly、never、yet to、remains to be）硬拦。"""
    def _pair(self, loc, good, bad):
        repo = custom_repo(loc)
        self.expect(run(T + arxiv_line(good, locator=loc), repo=repo), "PASS")
        self.expect(run(T + arxiv_line(bad, locator=loc), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_no_longer(self):
        self._pair("The model no longer reaches 90% accuracy on MMLU.", "模型在 MMLU 上已不再达到 90% 准确率。", "模型在 MMLU 上仍达到 90% 准确率。")

    def test_hardly(self):
        self._pair("The model hardly reaches 90% accuracy on MMLU.", "模型在 MMLU 上难以达到 90% 准确率。", "模型在 MMLU 上达到 90% 准确率。")

    def test_nanyi_vs_positive_source(self):
        self._pair("The model reaches 90% accuracy on MMLU.", "模型在 MMLU 上达到 90% 准确率。", "模型在 MMLU 上难以达到 90% 准确率。")

    def test_never(self):
        self._pair("The model has never reached 90% accuracy on MMLU.", "模型在 MMLU 上未曾达到 90% 准确率。", "模型在 MMLU 上曾达到 90% 准确率。")

    def test_yet_to(self):
        self._pair("The model has yet to reach 90% accuracy on MMLU.", "模型在 MMLU 上尚未达到 90% 准确率。", "模型在 MMLU 上已达到 90% 准确率。")

    def test_remains_to_be(self):
        self._pair("Whether the model reaches 90% on MMLU remains to be verified.", "模型能否在 MMLU 上达到 90% 尚待验证。", "模型在 MMLU 上达到 90% 已经验证。")


class BasisPoints(Base):
    """#32 r4：基点 / basis points / bp 是独立单位，100 bp = 1 个百分点。"""
    def test_25bp_vs_25pct_mismatch(self):
        loc = "The policy rate on FY2025 was raised by 25% according to the MMLU-Bench report."
        repo = custom_repo(loc)
        self.expect(run(T + arxiv_line("FY2025 政策利率上调 25 个基点。", locator=loc), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_025pp_vs_25bp_pass(self):
        loc = "The policy rate on FY2025 was raised by 25 basis points according to the MMLU-Bench report."
        repo = custom_repo(loc)
        # 单位核对通过（不出 LOCATOR-MISMATCH）；“百分点”措辞另会触发既有宏观观点规则，与本门禁无关，单独核定
        r = run(T + arxiv_line("FY2025 政策利率上调 0.25 个百分点。", locator=loc), repo=repo)
        self.assertNotIn("E-SUPPORT-LOCATOR-MISMATCH", r["error_codes"], r["errors"]); self.assertIn("R-SUPPORT-REVIEW", r["error_codes"])
        self.expect(run(T + arxiv_line("FY2025 政策利率上调 25 bp。", locator=loc), repo=repo), "PASS")
        self.expect(run(T + arxiv_line("FY2025 政策利率上调 0.25%。", locator=loc), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")


class WithoutScoped(Base):
    """#32 r4：without / 无需 按被否定的动作配对，前置、后置都覆盖。"""
    PRE = "Without fine-tuning, the model reaches 90% accuracy on MMLU."
    POST = "The model reaches 90% accuracy on MMLU without fine-tuning."

    def test_all_orders_pass(self):
        for loc in (self.PRE, self.POST):
            repo = custom_repo(loc)
            for c in ("无需微调，模型在 MMLU 上达到 90% 准确率。", "模型无需微调即在 MMLU 上达到 90% 准确率。",
                      "模型在 MMLU 上达到 90% 准确率，无需微调。", "模型在 MMLU 上达到 90% 准确率。"):
                self.expect(run(T + arxiv_line(c, locator=loc), repo=repo), "PASS")

    def test_main_verb_negation_still_blocks(self):
        for loc in (self.PRE, self.POST):
            repo = custom_repo(loc)
            self.expect(run(T + arxiv_line("模型无需微调，但在 MMLU 上未能达到 90% 准确率。", locator=loc), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_claimed_without_absent_in_source(self):
        loc = "After fine-tuning, the model reaches 90% accuracy on MMLU."
        repo = custom_repo(loc)
        self.expect(run(T + arxiv_line("模型无需微调即在 MMLU 上达到 90% 准确率。", locator=loc), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")


class Magnitude(Base):
    """#32 r3：billion 与“亿”等量级先等价换算再比较。"""
    LOC = "Revenue on MMLU-Bench reached 3 billion dollars in FY2025."

    def test_billion_vs_yi(self):
        repo = custom_repo(self.LOC)
        self.expect(run(T + arxiv_line("FY2025 收入达到 30 亿美元。", locator=self.LOC), repo=repo), "PASS")         # P3
        self.expect(run(T + arxiv_line("FY2025 收入达到三十亿美元。", locator=self.LOC), repo=repo), "PASS")
        self.expect(run(T + arxiv_line("FY2025 收入达到 3 亿美元。", locator=self.LOC), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(T + arxiv_line("FY2025 收入达到 3000 million 美元。", locator=self.LOC), repo=repo), "PASS")


class PureCitation(Base):
    """#32 r3：纯来源说明只认固定格式；位置检查与 X-only 检查用同一个判定结果。"""
    def test_fixed_format_only(self):
        self.expect(run(T + f"见 {ASRC}\n" + arxiv_line()), "PASS")
        self.expect(run(T + f"来源：{ASRC} 与 {XSRC}\n" + arxiv_line()), "PASS", absent=("E-X-ONLY",))
        # C6：“见与和＋来源”不再算纯来源说明
        self.expect(run(T + f"见与和 {ASRC}\n" + arxiv_line()), "FAIL", "E-SUPPORT-LOCATOR-MISSING")

    def test_pure_x_citation_not_x_only(self):
        # 纯 X 引导行不是断言：只标 R-X-ONLY，不报 E-X-ONLY
        r = run(T + f"见 {XSRC}\n" + arxiv_line())
        self.expect(r, "PASS", "R-X-ONLY", absent=("E-X-ONLY",))
        # 带断言文字的 X 段落仍硬拦
        self.expect(run(T + f"发布 2.0 版。见 {XSRC}\n" + arxiv_line()), "FAIL", "E-X-ONLY")


if __name__ == "__main__":
    unittest.main()


class ObjectWindowR5(Base):
    """#32 r5（审查 r4 HIGH）：不再退回整段比否定（r8 起 FRED 也不例外）。用含对象和指标的最小连续分句窗口配对，配不唯一 → 错配。"""
    LOC = "Model A does not reach 90%; on MMLU, Model B reaches 90%."

    def test_b1_b_negative_blocked(self):
        self.expect(run(T + arxiv_line("Model B 在 MMLU 上未能达到 90%。", locator=self.LOC), repo=custom_repo(self.LOC)),
                    "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_b2_b_positive_passes(self):
        self.expect(run(T + arxiv_line("Model B 在 MMLU 上达到 90%。", locator=self.LOC), repo=custom_repo(self.LOC)),
                    "PASS", absent=("E-SUPPORT-LOCATOR-MISMATCH",))

    def test_no_object_word(self):
        loc = "The baseline did not reach 90%, while on MMLU the model reaches 90%."
        repo = custom_repo(loc)
        self.expect(run(T + arxiv_line("模型在 MMLU 上达到 90%。", locator=loc), repo=repo), "PASS")
        self.expect(run(T + arxiv_line("模型在 MMLU 上未能达到 90%。", locator=loc), repo=repo), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_two_windows_ambiguous(self):
        loc = "Model A reaches 90% on MMLU; Model B reaches 90% on GSM8K."
        self.expect(run(T + arxiv_line("模型达到 90%。", locator=loc), repo=custom_repo(loc)), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_fred_no_special_case(self):
        # r8（王总 2026-10-18 定不再经 FRED）：FRED 不再有整段兜底，与其他来源一样走最小连续分句窗口
        self.expect(run(T + fred_line()), "PASS", absent=("E-SUPPORT-LOCATOR-MISMATCH",))
        self.expect(run(T + fred_line("UNRATE 未能达到 4.2%。")), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        from markjin import selfcheck as sc
        claim = sc.norm("UNRATE 为 4.2%。")
        # 两个窗口都配得上：原先 FRED 退回整段放行，现在与其他来源一样判错配
        two = sc.norm('"series_id": "UNRATE", "value": "4.2", "series_id": "UNRATE", "value": "4.2"')
        # 否定在配对窗口之外：原先 FRED 拿整段比否定而拦下，现在只看配对窗口
        outside = sc.norm('"series_id": "UNRATE", "value": "4.2", "comment": "not seasonally adjusted"')
        for loc, ok in ((two, False), (outside, True)):
            with self.subTest(loc=loc):
                self.assertEqual(sc._neg_parity_ok(claim, loc, "fred"), sc._neg_parity_ok(claim, loc, "arxiv"))
                self.assertEqual(sc._neg_parity_ok(claim, loc, "fred")[0], ok)


class ImplicitNegationR5(Base):
    """#32 r5（审查 r4 MEDIUM）：固定说法不算否定；审慎/待定说法不计否定、给 R-SUPPORT-HEDGE；真否定仍硬拦。"""
    def _ok(self, loc, claim, *hints):
        r = run(T + arxiv_line(claim, locator=loc), repo=custom_repo(loc))
        self.expect(r, "PASS", *hints, absent=("E-SUPPORT-LOCATOR-MISMATCH",))

    def _bad(self, loc, claim):
        self.expect(run(T + arxiv_line(claim, locator=loc), repo=custom_repo(loc)), "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    INF = "Inflation is at its highest level in 40 years, never before seen at 9.1%."

    def test_h1_congwei_ruci(self):
        self._ok(self.INF, "通胀率达到 9.1%，为 40 年来最高，此前从未如此之高。")

    def test_h2_never_before(self):
        self._ok(self.INF, "通胀率达到 9.1%，为 40 年来最高。")

    def test_h3_youdai_hedge(self):
        self._ok("The figure is subject to revision at 4.2%.", "该数据为 4.2%，有待修订。", "R-SUPPORT-HEDGE")

    def test_h4_h5_yet_to_be_reviewed(self):
        loc = "Results have yet to be peer reviewed, with 90% accuracy on MMLU."
        self._ok(loc, "模型在 MMLU 上达到 90% 准确率。", "R-SUPPORT-HEDGE")
        self._ok(loc, "模型在 MMLU 上达到 90% 准确率，结果尚未经同行评审。", "R-SUPPORT-HEDGE")

    def test_h6_h7_idioms(self):
        self._ok(ARXIV_LOC, "模型在 MMLU 上达到令人难以置信的 90% 准确率。")
        self._ok(ARXIV_LOC, "模型在 MMLU 上达到无与伦比的 90% 准确率。")

    def test_real_negation_still_blocks(self):
        self._bad(ARXIV_LOC, "模型在 MMLU 上从未达到 90% 准确率。")
        self._bad(ARXIV_LOC, "模型在 MMLU 上难以达到 90% 准确率。")
        self._bad(ARXIV_LOC, "模型在 MMLU 上的准确率有待达到 90%。")
        self._bad("The model has yet to reach 90% accuracy on MMLU.", "模型在 MMLU 上达到 90% 准确率。")
        self._bad("Inflation never reached 9.1% in 40 years.", "通胀率达到 9.1%。")

    def test_hedge_dropped_or_added_blocks(self):
        self._bad("Whether the model reaches 90% on MMLU remains to be verified.", "模型在 MMLU 上达到 90% 已经验证。")
        self._bad(ARXIV_LOC, "模型在 MMLU 上达到 90% 准确率，有待核实。")


class WithoutScopeHint(Base):
    """#32 r5（审查 r4 MEDIUM W1）：原文 without X、断言没写同样的短语 → R-SUPPORT-SCOPE（人工必查）。"""
    LOC = "The model reaches 90% accuracy on MMLU without any fine-tuning."

    def test_w1_opposite_premise_flagged(self):
        r = run(T + arxiv_line("模型在 MMLU 上经过微调达到 90% 准确率。", locator=self.LOC), repo=custom_repo(self.LOC))
        self.expect(r, "PASS", "R-SUPPORT-SCOPE", "R-SUPPORT-REVIEW")

    def test_w2_same_scope_no_flag(self):
        r = run(T + arxiv_line("模型无需微调即在 MMLU 上达到 90% 准确率。", locator=self.LOC), repo=custom_repo(self.LOC))
        self.expect(r, "PASS", absent=("R-SUPPORT-SCOPE",))


class KeylessClauseR5(Base):
    """#32 r5（dry run 发现）：看板英文用例，不含数字和代号的分句按对应分句核对否定状态，不再各自与整个片段比。"""
    def test_both_sides_negated_passes(self):
        loc = "Researchers could watch the run on a live dashboard and pause or stop it at any time, but they had no cause to intervene."
        r = run(T + arxiv_line("Researchers could pause or stop the run at any time from a live dashboard, but had no cause to intervene.", locator=loc), repo=custom_repo(loc))
        self.expect(r, "PASS", absent=("E-SUPPORT-LOCATOR-MISMATCH",))

    def test_negation_only_in_claim_blocks(self):
        loc = "Researchers could watch the run on a live dashboard and pause or stop it at any time, and they did intervene."
        r = run(T + arxiv_line("Researchers could pause or stop the run at any time, but had no cause to intervene.", locator=loc), repo=custom_repo(loc))
        self.expect(r, "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")


class KeylessPairingR5(Base):
    """r5 审查 HIGH：无数字、无代号的分句也要按对象配对，不能互换否定或审慎说法。"""
    LOC = "The method is accurate on long documents; however, it is not robust to adversarial prompts."

    def test_keyless_objects_cannot_swap_negation(self):
        good = "The method is accurate on long documents, but it is not robust to adversarial prompts."
        bad = "The method is not accurate on long documents, but it is robust to adversarial prompts."
        self.expect(run(T + arxiv_line(good, locator=self.LOC), repo=custom_repo(self.LOC)), "PASS")
        self.expect(run(T + arxiv_line(bad, locator=self.LOC), repo=custom_repo(self.LOC)),
                    "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_keyless_single_clause_cannot_borrow_negation(self):
        r = run(T + arxiv_line("The method is not accurate on long documents.", locator=self.LOC), repo=custom_repo(self.LOC))
        self.expect(r, "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_keyless_model_b_cannot_borrow_a_negation(self):
        loc = "Model A is not reliable; Model B is reliable."
        self.expect(run(T + arxiv_line("Model B is not reliable.", locator=loc), repo=custom_repo(loc)),
                    "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(T + arxiv_line("Model B is reliable.", locator=loc), repo=custom_repo(loc)), "PASS")

    def test_keyless_hedge_cannot_swap(self):
        loc = "Model A remains to be verified; Model B is verified."
        self.expect(run(T + arxiv_line("Model A is verified; Model B remains to be verified.", locator=loc), repo=custom_repo(loc)),
                    "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_keyless_zh_mixed_source_blocks(self):
        r = run(T + arxiv_line("该方法在长文档上并不准确，但对对抗性提示很稳健。", locator=self.LOC), repo=custom_repo(self.LOC))
        self.expect(r, "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")


class KeylessPairingR6(Base):
    """r6 审查 HIGH：否定词、助动词与句首大写普通词不参与配对，带否定的断言分句不能因此被拉向原文里带否定的另一对象。"""

    def test_negation_word_cannot_drive_pairing(self):
        loc = "The new method does not improve recall, and the baseline improves recall clearly."
        self.expect(run(T + arxiv_line("The baseline does not improve recall.", locator=loc), repo=custom_repo(loc)),
                    "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(T + arxiv_line("The new method does not improve recall.", locator=loc), repo=custom_repo(loc)), "PASS")

    def test_sentence_initial_capital_is_not_an_object(self):
        loc = "The method is not robust; the baseline is robust."
        self.expect(run(T + arxiv_line("The baseline is not robust.", locator=loc), repo=custom_repo(loc)),
                    "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(T + arxiv_line("The baseline is robust.", locator=loc), repo=custom_repo(loc)), "PASS")

    def test_status_words_cannot_choose_the_other_object(self):
        cases = (
            ("The old system does not process audio; the replacement processes audio.", "The replacement does not process audio."),
            ("The engine is not robust; the backup is reliable.", "备份系统并不 robust."),
        )
        for loc, claim in cases:
            with self.subTest(claim=claim):
                self.expect(run(T + arxiv_line(claim, locator=loc), repo=custom_repo(loc)),
                            "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")

    def test_tied_candidates_same_state_pass(self):
        # 并列最高分的候选分句否定状态相同 → 可比（dry run：open-weight models 一句）；状态不同仍拦
        loc = "Reward models favor the construction; the judge does not license it; open-weight models use the construction more."
        self.expect(run(T + arxiv_line("Open-weight models favor the construction.", locator=loc), repo=custom_repo(loc)), "PASS")
        self.expect(run(T + arxiv_line("Open-weight models do not favor the construction.", locator=loc), repo=custom_repo(loc)),
                    "FAIL", "E-SUPPORT-LOCATOR-MISMATCH")
