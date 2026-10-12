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


if __name__ == "__main__":
    unittest.main()
