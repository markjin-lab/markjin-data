"""#9 自检反例测试。每个用例同时断言 status、low_risk 与错误码。"""
import hashlib, json, os, tempfile, unittest
from pathlib import Path
from helpers import (ARXIV_LOC, FRED_LOC, quote_line, source_line, make_repo, arxiv_line, fred_line, x_line, write_manifest, DUMMY_INTERNAL,
                     DATE, ARXIV_ID, FILES)
from markjin.selfcheck import check_text, check_file, compute_low_risk
from markjin.internal import parse_internal_list, load_internal_terms as _real_load
import markjin.selfcheck as _sc

# r12：check_text 不再接受替代词表；测试把本机名单加载函数替换为占位名单（不是真实内部主题）
_sc.load_internal_terms = lambda: list(DUMMY_INTERNAL)

REPO = make_repo()
TITLE = f"# 日报 {DATE}\n"


def run(text, repo=None, date=DATE, card_type="daily", **kw):
    kw.setdefault("link_checker", lambda u: True)
    return check_text(text, REPO if repo is None else repo, date, card_type, **kw)


class T(unittest.TestCase):
    def expect(self, r, status, low_risk, code=None, absent=None):
        self.assertEqual(r["status"], status, r["error_codes"])
        self.assertIs(r["low_risk"], low_risk, r["error_codes"])
        if code:
            self.assertIn(code, r["error_codes"])
        if absent:
            self.assertNotIn(absent, r["error_codes"])


class Whitelist(T):
    def test_clean_low_risk(self):
        r = run(TITLE + quote_line() + "\n" + source_line())
        self.expect(r, "PASS", True); self.assertEqual(r["error_codes"], [])
        self.assertEqual(r["counts"]["quotes"], 1); self.assertEqual(r["counts"]["other"], 0)
        # 结构化断言（转述）保留来源绑定检查，但不在低风险白名单内
        self.expect(run(TITLE + arxiv_line()), "PASS", False, "R-STRUCTURE")

    def test_no_assertion_not_low_risk(self):
        self.expect(run(TITLE), "PASS", False, "R-NO-ASSERTION")

    def test_card_type_required(self):
        for ct in (None, "", "Daily", "weekly"):
            self.expect(run(arxiv_line(), card_type=ct), "FAIL", False, "E-SELFCHECK-CARDTYPE")

    def test_signal_card_never_low_risk(self):
        self.expect(run(arxiv_line(), card_type="signal"), "PASS", False, "R-SIGNAL-CARD")

    def test_non_whitelist_blocks_not_low_risk(self):
        # 结构白名单：非固定栏目标题、段落、front matter、注释，即使中性，也一律非低风险
        for doc in ("# 重大突破\n", "---\nhas_inference: false\n---\n", TITLE + "<!-- 说明 -->\n"):
            self.expect(run(doc + quote_line()), "PASS", False, "R-STRUCTURE")
        # 无来源的普通段落：按无来源块规则判 UNCLEAR（不发布，有批准记录也不行）
        self.expect(run(TITLE + "这是一段普通说明文字。\n" + quote_line()), "UNCLEAR", False, "E-INFER-UNCLEAR")

    def test_judgment_in_heading_paragraph_comment(self):
        for doc in ("# 显然的突破\n", TITLE + "<!-- 预计 -->\n"):
            self.expect(run(doc + arxiv_line()), "PASS", False, "R-INFERENCE")
        # 无来源的转述/判断段落：硬错误（拿到批准记录也不得发布）
        for doc in (TITLE + "这意味着格局变化。\n", "---\nnote: 有望\n---\n", TITLE + "作者声称该模型已经超过所有基线。\n"):
            self.expect(run(doc + quote_line()), "FAIL", False, "E-REPLAY-001")

    def test_numbered_plus_star_lists_structured(self):
        src = f"— `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1 〔原文：{ARXIV_LOC}〕"   # #32
        for pre in ("1. ", "2) ", "+ ", "* "):
            self.expect(run(TITLE + f"{pre}模型在 MMLU 上达到 90% 准确率。 {src}"), "PASS", False, "R-STRUCTURE")
            self.expect(run(TITLE + f"{pre}模型可能达到 90% 准确率。 {src}"), "PASS", False, "R-INFERENCE")

    def test_quote_table_with_source_unstructured(self):
        src = f"— `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1"
        for pre in ("> ", "| "):
            # #32：非结构化行无法写明原文支持位置 → 日报硬拦；信号卡照旧只标 R-UNSTRUCTURED
            self.expect(run(TITLE + f"{pre}模型在 MMLU 上达到 90% 准确率。 {src}"), "FAIL", False, "E-SUPPORT-LOCATOR-MISSING")
            self.expect(run(TITLE + f"{pre}模型在 MMLU 上达到 90% 准确率。 {src}", card_type="signal"), "PASS", False, "R-UNSTRUCTURED")

    def test_numbered_quote_table_without_source(self):
        # 无来源且无法判别 → UNCLEAR（可达，不发布）；含数字或推断/转述词却无来源 → FAIL
        for ln in ("1. 某模型很强。", "+ 某模型很强。", "> 某模型很强。", "| 某模型 | 很强 |"):
            self.expect(run(TITLE + ln), "UNCLEAR", False, "E-INFER-UNCLEAR")
        for ln in ("1. 某模型达到 90%。", "- 作者声称方法优于所有基线。", "> 预计明年发布。"):
            self.expect(run(TITLE + ln), "FAIL", False, "E-REPLAY-001")

    def test_table_header_is_free_text(self):
        src = f"`raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1"
        r = run(TITLE + "| 项 | 来源 |\n|---|---|\n" + f"| 90% MMLU | {src} |")
        self.expect(r, "FAIL", False, "E-SUPPORT-LOCATOR-MISSING")   # #32：表格行无法写明原文支持位置
        r = run(TITLE + "| 项 | 来源 |\n|---|---|\n" + f"| 90% MMLU | {src} |", card_type="signal")
        self.expect(r, "PASS", False, "R-UNSTRUCTURED")
        r = run(TITLE + "| 预计 | 来源 |\n|---|---|\n" + f"| 90% MMLU | {src} |")
        self.expect(r, "FAIL", False, "E-REPLAY-001")   # 表头是无来源的判断文字

    def test_support_unverified(self):
        # #32：日报中数字与原文支持位置不符 → 硬拦；信号卡照旧只标 R-SUPPORT-UNVERIFIED
        self.expect(run(arxiv_line("模型在 GSM8K 上达到 95% 准确率。")), "FAIL", False, "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(arxiv_line("模型在 GSM8K 上达到 95% 准确率。"), card_type="signal"), "PASS", False, "R-SUPPORT-UNVERIFIED")
        # 无数字：没有可核对项 → 保守判定为“来源支持未证实”，不是低风险
        self.expect(run(arxiv_line("模型很强。")), "PASS", False, "R-SUPPORT-UNVERIFIED")

    def test_recompute_low_risk_rejects_forged(self):
        r = run(TITLE + arxiv_line("作者声称达到 90% MMLU。"))
        forged = dict(r, low_risk=True)
        self.assertFalse(compute_low_risk(forged))
        for k in ("counts", "flags", "status", "card_type"):
            bad = dict(r); bad.pop(k); self.assertFalse(compute_low_risk(bad), k)
        self.assertFalse(compute_low_risk({"status": None}))


class Inference(T):
    def test_judgment_words(self):
        for w in ["推断将成为主流", "可能改变训练范式", "显然更好", "有望商用", "预计明年发布",
                  "It is likely better", "The results suggest gains", "Obviously strong"]:
            self.expect(run(arxiv_line(f"MMLU 90%，{w}。")), "PASS", False, "R-INFERENCE")

    def test_reported_words(self):
        for w in ["作者声称", "官方表示", "据悉", "The team stated", "It was reported", "According to the paper",
                  "据报道"]:
            r = run(arxiv_line(f"{w} MMLU 90%。"))
            self.expect(r, "PASS", False, "R-INFERENCE", absent="E-INFER-UNCLEAR")

    def test_zero_width_fullwidth_and_spaces(self):
        for w in ["可\u200b能", "可 能", "ｌｉｋｅｌｙ", "声\u2060称", "显\ufeff然", "预\u00ad计"]:
            self.expect(run(arxiv_line(f"MMLU 90% {w}。")), "PASS", False, "R-INFERENCE")

    def test_inference_in_title_quote_table(self):
        for doc in ("# 日报 有望\n", "> 意味着变化\n" , "| 预计 | x |\n|---|---|\n"):
            r = run(doc + arxiv_line())
            self.assertFalse(r["low_risk"]); self.assertIn("R-INFERENCE", r["error_codes"])
            self.assertIn(r["status"], ("PASS", "FAIL"))

    def test_cross_line_split(self):
        self.expect(run(TITLE + "显\n然\n" + arxiv_line()), "UNCLEAR", False, "R-INFERENCE")

    def test_reported_without_source_fail(self):
        self.expect(run("- 作者声称方法优于所有基线。"), "FAIL", False, "E-REPLAY-001")


class Lexicon(T):
    def test_no_single_char_false_positive(self):
        for w in ("模型名称为 Foo", "表示学习方法提升 90% MMLU", "称重"):
            self.expect(run(arxiv_line(f"{w}，MMLU 90%。")), "PASS", False, "R-STRUCTURE", absent="R-INFERENCE")

    def test_us_treasury_and_bull_bear(self):
        # 协调决定 10-11：宏观词表补“美债”；“看多”“看空”属宏观观点硬拦
        self.expect(run(arxiv_line("美债收益率 MMLU 90%。")), "PASS", False, "R-MACRO")
        for w in ("看多美债", "看空美债"):
            r = run(arxiv_line(f"{w}，MMLU 90%。"))
            self.assertEqual(r["status"], "FAIL"); self.assertFalse(r["low_risk"])
            self.assertIn("E-BLOCK-MACRO-OPINION", r["error_codes"])

    def test_lexicon_json_strict(self):
        import json as _j
        from markjin import selfcheck as S
        lx = S.load_lexicon()
        self.assertTrue(all(len(t) >= 2 for k in S.LEXICON_KEYS for t in lx[k]))
        d = Path(tempfile.mkdtemp())
        for bad in ("{", _j.dumps({**lx, "version": 2}), _j.dumps({**lx, "judgment": ["称"]}),
                    _j.dumps({k: v for k, v in lx.items() if k != "macro"}), _j.dumps({**lx, "invest": []})):
            (d / "l.json").write_text(bad, encoding="utf-8")
            with self.assertRaises(S.LexiconError):
                S.load_lexicon(d / "l.json")
        old = S.LEX; S.LEX = None
        try:
            self.expect(run(arxiv_line()), "FAIL", False, "E-SELFCHECK-LEXICON")
        finally:
            S.LEX = old


class Sources(T):
    def test_missing_raw_file(self):
        r = run(f"- 90% — `raw/{DATE}/arxiv/nope.xml` · https://arxiv.org/abs/{ARXIV_ID}")
        self.expect(r, "FAIL", False, "E-REPLAY-002")

    def test_sha_mismatch(self):
        repo = make_repo(); p = repo / f"raw/{DATE}/arxiv/cs.AI.xml"; p.write_text(p.read_text() + " ")
        self.expect(run(arxiv_line(), repo=repo), "FAIL", False, "E-REPLAY-003")

    def test_id_not_in_archive(self):
        r = run(f"- MMLU 90% — `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/2610.99999v1")
        self.expect(r, "FAIL", False, "E-REPLAY-004")

    def test_unknown_url_type(self):
        for u in ("https://example.com/a", "http://arxiv.org/abs/2610.00001", "https://arxiv.org/pdf/2610.00001",
                  "https://evil.com/arxiv.org/abs/2610.00001"):
            r = run(f"- MMLU 90% — `raw/{DATE}/arxiv/cs.AI.xml` · {u}")
            self.expect(r, "FAIL", False, "E-REPLAY-005")

    def test_kind_mismatch_and_wrong_date(self):
        r = run(f"- 90% — `raw/{DATE}/x/01.json` · https://arxiv.org/abs/{ARXIV_ID}")
        self.expect(r, "FAIL", False, "E-REPLAY-006")
        r = run(arxiv_line(), date="2026-01-06")
        self.expect(r, "FAIL", False, "E-REPLAY-006")
        r = run(f"- 90% — `raw/{DATE}/arxiv/../arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}")
        self.expect(r, "FAIL", False, "E-REPLAY-006")

    def test_free_text_sources(self):
        src = f"`raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1"
        self.expect(run(TITLE + f"来源：{src} ；见 https://github.com/markjin-lab/markjin-data/blob/x/raw\n" + arxiv_line()), "PASS", False, "R-STRUCTURE")
        # raw 与来源 URL 必须成对：只有 raw、只有说明性仓库链接以外的 raw → E-REPLAY-006
        self.expect(run(TITLE + f"来源：`raw/{DATE}/arxiv/cs.AI.xml`，见 https://github.com/markjin-lab/markjin-data/blob/x/raw\n" + arxiv_line()), "FAIL", False, "E-REPLAY-006")
        # 类型错配（x 文件配 arxiv URL）→ E-REPLAY-006；ID 不在存档 → E-REPLAY-004
        self.expect(run(TITLE + f"补充：`raw/{DATE}/x/01.json` · https://arxiv.org/abs/{ARXIV_ID}v1\n" + arxiv_line()), "FAIL", False, "E-REPLAY-006")
        self.expect(run(TITLE + f"补充：`raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/2610.99999\n" + arxiv_line()), "FAIL", False, "E-REPLAY-004")
        self.expect(run(TITLE + f"来源：`raw/{DATE}/`\n" + arxiv_line()), "FAIL", False, "E-REPLAY-002")   # 目录不是来源
        self.expect(run(TITLE + "见 https://example.com/x\n" + arxiv_line()), "FAIL", False, "E-REPLAY-005")
        self.expect(run(TITLE + "见 `raw/2026-01-04/arxiv/`\n" + arxiv_line()), "FAIL", False, "E-REPLAY-006")

    def test_loose_unpaired(self):
        r = run(TITLE + f"1. 90% `raw/{DATE}/arxiv/cs.AI.xml` https://arxiv.org/abs/{ARXIV_ID} https://x.com/i/status/1")
        self.expect(r, "FAIL", False, "E-REPLAY-006")

    def test_source_in_paragraph_checked(self):
        r = run(TITLE + f"见 `raw/{DATE}/arxiv/nope.xml` · https://arxiv.org/abs/{ARXIV_ID}\n" + arxiv_line())
        self.expect(r, "FAIL", False, "E-REPLAY-002")

    def test_x_only(self):
        # r6（协调方定）：日报断言只有 X 来源 → 硬拦 E-X-ONLY；信号卡仍只标 R-X-ONLY
        self.expect(run(x_line()), "FAIL", False, "E-X-ONLY")
        self.expect(run(x_line(), card_type="signal"), "PASS", False, "R-X-ONLY")

    def test_raw_undecodable(self):
        files = dict(FILES); repo = make_repo(files)
        p = repo / f"raw/{DATE}/arxiv/cs.AI.xml"; data = b"\xff\xfe" + ARXIV_ID.encode()
        p.write_bytes(data)
        m = repo / f"raw/{DATE}/MANIFEST.sha256"
        m.write_text(m.read_text().replace(hashlib.sha256(files["arxiv/cs.AI.xml"].encode()).hexdigest(),
                                           hashlib.sha256(data).hexdigest()))
        self.expect(run(arxiv_line(), repo=repo), "FAIL", False, "E-REPLAY-READ")


class Manifest(T):
    def bad(self, content):
        repo = make_repo(); (repo / f"raw/{DATE}/MANIFEST.sha256").write_text(content)
        return run(arxiv_line(), repo=repo)

    def test_duplicate_line(self):
        repo = make_repo(); m = repo / f"raw/{DATE}/MANIFEST.sha256"
        first = m.read_text().splitlines()[0]
        self.expect(self.bad(m.read_text() + first + "\n"), "FAIL", False, "E-MANIFEST-PARSE")

    def test_illegal_lines(self):
        good = make_repo(); text = (good / f"raw/{DATE}/MANIFEST.sha256").read_text()
        for junk in ("garbage\n", "abc  ./x\n", "  \t\n#comment\n", "0" * 64 + "  ../escape\n", "0" * 64 + " ./one-space\n"):
            if junk.strip() == "":
                continue
            self.expect(self.bad(text + junk), "FAIL", False, "E-MANIFEST-PARSE")

    def test_empty_manifest(self):
        self.expect(self.bad(""), "FAIL", False, "E-MANIFEST-PARSE")

    def test_missing_manifest(self):
        repo = make_repo(); (repo / f"raw/{DATE}/MANIFEST.sha256").unlink()
        self.expect(run(arxiv_line(), repo=repo), "FAIL", False, "E-REPLAY-003")

    def test_manifest_undecodable(self):
        repo = make_repo(); (repo / f"raw/{DATE}/MANIFEST.sha256").write_bytes(b"\xff\xff")
        self.expect(run(arxiv_line(), repo=repo), "FAIL", False, "E-REPLAY-READ")


class Counts(T):
    def test_counts_match(self):
        # counts 注释计数照常核对，但注释本身不在结构白名单内：不得低风险
        self.expect(run(TITLE + "<!-- counts: quotes=1 other=1 -->\n" + quote_line()), "PASS", False, "R-STRUCTURE")
        self.expect(run(TITLE + "<!-- counts: quotes=1 -->\n" + quote_line()), "PASS", False, "R-STRUCTURE")
        self.expect(run(TITLE + "<!-- counts: quotes=1 other=0 -->\n" + quote_line()), "FAIL", False, "E-COUNT-001")

    def test_counts_mismatch(self):
        self.expect(run(TITLE + "<!-- counts: assertions=5 -->\n" + arxiv_line()), "FAIL", False, "E-COUNT-001")

    def test_counts_invalid(self):
        for c in ("<!-- counts: assertions=1 -->\n<!-- counts: assertions=1 -->",
                  "<!-- counts: bogus=1 -->", "<!-- counts: assertions=1 assertions=1 -->",
                  "<!-- counts: assertions=x -->", "<!-- counts: assertions=-1 -->",
                  "前文 <!-- counts: assertions=1 -->", "<!--counts:assertions=1-->"):
            self.expect(run(TITLE + c + "\n" + arxiv_line()), "FAIL", False, "E-COUNT-002")


class Macro(T):
    def test_macro_never_low_risk(self):
        self.expect(run(fred_line()), "PASS", False, "R-MACRO")

    def test_macro_by_whole_document(self):
        # 观点写在另一行（非 FRED 断言行），整篇为宏观 → 硬拦
        for op in ("预计", "看多", "看涨", "看好", "加配", "减配", "有望回落"):
            r = run(TITLE + fred_line() + f"\n{op}后续走势。")
            self.expect(r, "FAIL", False, "E-BLOCK-MACRO-OPINION")

    def test_macro_term_only_in_paragraph(self):
        r = run(TITLE + "美联储议息。\n" + arxiv_line("MMLU 90%，可能改变格局。"))
        self.expect(r, "FAIL", False, "E-BLOCK-MACRO-OPINION")

    def test_fund_ratio(self):
        for t in ("建议将三成资金投入股票。", "建议将 30% 资金投入股票。", "应当把一半积蓄配置到债券。"):
            r = run(TITLE + fred_line() + "\n" + t)
            self.expect(r, "FAIL", False, "E-BLOCK-MACRO-OPINION")
            self.assertIn("E-BLOCK-INVEST", r["error_codes"])

    def test_fund_ratio_cross_line(self):
        r = run(TITLE + fred_line() + "\n建议将三成\n资金投入股票。")
        self.expect(r, "FAIL", False, "E-BLOCK-MACRO-OPINION"); self.assertIn("E-BLOCK-INVEST", r["error_codes"])

    def test_cross_line_opinion(self):
        self.expect(run(TITLE + fred_line() + "\n看\n多"), "FAIL", False, "E-BLOCK-MACRO-OPINION")

    def test_zero_width_opinion(self):
        self.expect(run(fred_line("UNRATE 4.2%，看\u200b涨。")), "FAIL", False, "E-BLOCK-MACRO-OPINION")

    def test_unrecognized_macro_not_low_risk(self):
        self.expect(run(TITLE + "宏观环境平稳。\n" + arxiv_line()), "UNCLEAR", False, "R-MACRO")


class MacroArithmetic(T):
    SRC = f" — `raw/{DATE}/fred/UNRATE.json` · https://fred.stlouisfed.org/series/UNRATE 〔原文：{FRED_LOC}〕"   # #32

    def test_pure_arithmetic_allowed(self):
        for t in ("UNRATE 4.2%，较上月 4.0% 差值 +0.2 个百分点（推断：由原始数据计算；算式：4.2-4.0=0.2）",
                  "UNRATE 同比 +0.2（由原始数据计算，算式：4.2 - 4.0 = 0.2）",
                  "UNRATE 环比 5%（按原始数据计算；算式：(4.2/4.0-1)×100=5%）"):
            r = run(TITLE + "- " + t + self.SRC)
            self.expect(r, "PASS", False, "R-MACRO")
            self.assertNotIn("E-BLOCK-MACRO-OPINION", r["error_codes"])

    def test_missing_formula_blocked(self):
        r = run(TITLE + "- UNRATE 同比 +0.2（推断：由原始数据计算）" + self.SRC)
        self.expect(r, "FAIL", False, "E-BLOCK-MACRO-OPINION")
        r = run(TITLE + "- UNRATE 同比 +0.2（由原始数据计算）" + self.SRC)
        self.expect(r, "FAIL", False, "E-BLOCK-MACRO-OPINION")

    def test_missing_source_blocked(self):
        r = run(TITLE + fred_line() + "\nUNRATE 同比 +0.2（推断：由原始数据计算；算式：4.2-4.0=0.2）")
        self.expect(r, "FAIL", False, "E-BLOCK-MACRO-OPINION")

    def test_opinion_prediction_causal_still_blocked(self):
        for extra in ("，预计继续上升", "，看多", "，由于就业走弱", "，导致股市下跌"):
            r = run(TITLE + f"- UNRATE 差值 +0.2（由原始数据计算；算式：4.2-4.0=0.2）{extra}" + self.SRC)
            self.expect(r, "FAIL", False, "E-BLOCK-MACRO-OPINION")


class Links(T):
    def test_link_unchecked_not_low_risk(self):
        self.expect(run(TITLE + arxiv_line(), link_checker=None), "PASS", False, "R-LINK-UNCHECKED")

    def test_link_unreachable_not_low_risk(self):
        self.expect(run(TITLE + arxiv_line(), link_checker=lambda u: False), "PASS", False, "R-LINK-UNREACHABLE")

    def test_link_checker_error_not_low_risk(self):
        def boom(u):
            raise OSError("down")
        self.expect(run(TITLE + arxiv_line(), link_checker=boom), "PASS", False, "R-LINK-UNREACHABLE")

    def test_link_ok(self):
        seen = []
        self.expect(run(TITLE + quote_line(), link_checker=lambda u: seen.append(u) or True), "PASS", True)
        self.assertEqual(seen, [f"https://arxiv.org/abs/{ARXIV_ID}v1"])


class Blocks(T):
    def test_invest_words(self):
        for w in ["建议买入", "仓位提升", "目标价 100", "$NVDA 大涨", "600519.SH", "we buy the dip", "加配"]:
            self.expect(run(arxiv_line(w)), "FAIL", False, "E-BLOCK-INVEST")

    def test_invest_in_title_and_quote(self):
        for doc in ("# 买入\n" + arxiv_line(), TITLE + "> 建议卖出\n" + arxiv_line()):
            self.expect(run(doc), "FAIL", False, "E-BLOCK-INVEST")

    def test_long_context_not_invest(self):
        r = run(arxiv_line("MMLU 90%, long context 1M tokens, position embeddings。"))
        # #32：1M 不在原文支持位置里 → 只因 E-SUPPORT-LOCATOR-MISMATCH 失败，不是投资措辞
        self.assertNotIn("E-BLOCK-INVEST", r["error_codes"]); self.assertEqual([e["code"] for e in r["errors"]], ["E-SUPPORT-LOCATOR-MISMATCH"])
        r = run(arxiv_line("MMLU 90%, long context 1M tokens, position embeddings。"), card_type="signal")
        self.assertNotIn("E-BLOCK-INVEST", r["error_codes"]); self.assertEqual(r["status"], "PASS")

    def test_medical(self):
        self.expect(run(arxiv_line("MMLU 90%，临床可用。")), "PASS", False, "R-MEDICAL")

    def test_internal_blocked_everywhere_not_echoed(self):
        for doc in ("# 样例内部词甲\n" + arxiv_line(), TITLE + "> 样例内部词乙\n" + arxiv_line(),
                    TITLE + "样例内部\n词甲\n" + arxiv_line(), arxiv_line("样例\u200b内部词甲 90% MMLU")):
            r = run(doc)
            self.expect(r, "FAIL", False, "E-BLOCK-INTERNAL")
            self.assertNotIn("样例内部词", repr(r))

    def test_internal_list_missing(self):
        # r12：调用方传入任何替代值（含非空、看似合法的词表）→ 直接报错，只认本机真实名单
        for bad in (None, [], [""], ["  "], ["\u200b"], "abc", [1], ["无关占位词"], ("样例内部词甲",), DUMMY_INTERNAL):
            with self.assertRaises(ValueError, msg=repr(bad)):
                run(arxiv_line(), internal_terms=bad)

    def test_internal_list_load_fail_closed(self):
        d = Path(tempfile.mkdtemp()); old = os.environ.get("MARKJIN_INTERNAL_DIR")
        os.environ["MARKJIN_INTERNAL_DIR"] = str(d)
        fake = _sc.load_internal_terms; _sc.load_internal_terms = _real_load
        try:
            self.expect(run(arxiv_line(), internal_terms="load"), "FAIL", False, "E-INTERNAL-LIST-MISSING")
            (d / "topics-private.md").write_text("| 名称 | 识别条件 |\n|---|---|\n| a | b |\n")
            self.expect(run(arxiv_line(), internal_terms="load"), "FAIL", False, "E-INTERNAL-LIST-MISSING")
        finally:
            _sc.load_internal_terms = fake
            if old is None: os.environ.pop("MARKJIN_INTERNAL_DIR")
            else: os.environ["MARKJIN_INTERNAL_DIR"] = old


class InternalListParse(unittest.TestCase):
    H = "| 名称 | 识别条件 | 来源 |\n|---|---|---|\n"

    def test_ok(self):
        r = parse_internal_list("\n" + self.H + "| 甲甲 | 条件一 | 来源一 |\n\n")
        self.assertEqual(r["names"], ["甲甲"]); self.assertEqual(set(r["protected"]), {"甲甲", "条件一", "来源一"})
        # 协调决定：表外不允许任何文字（标题、说明都不行）
        for pre in ("说明\n\n", "# 内部清单\n", "注：x\n"):
            self.assertIsNone(parse_internal_list(pre + self.H + "| 甲甲 | 条件一 | 来源一 |\n"))
        self.assertIsNone(parse_internal_list(self.H + "| 甲甲 | 条件一 | 来源一 |\n\n附注\n"))

    def test_reject(self):
        bad = ["", "无表格", self.H, "| 名称 | 来源 |\n|---|---|\n| a | b |\n",
               self.H + "| a | b |\n", self.H + "| a | b | c | d |\n", self.H + "| a |  | c |\n",
               self.H + "| a | b | c |\n| a | b2 | c2 |\n", self.H + "| a | b | c\n",
               self.H + "| a | b | c |\n\n" + self.H + "| d | e | f |\n",
               "| 名称 | 识别条件 | 来源 |\n| x | y | z |\n| a | b | c |\n",
               "| 别的 | 识别条件 | 来源 |\n|---|---|---|\n| a | b | c |\n",
               "| 主题 | 状态 | 来源 |\n|---|---|---|\n| a | b | c |\n"]
        for b in bad:
            self.assertIsNone(parse_internal_list(b), repr(b))


class Inputs(T):
    def test_empty(self):
        self.expect(run("  "), "FAIL", False, "E-SELFCHECK-INPUT")

    def test_read_error(self):
        self.expect(check_file("/nonexistent/x.md", REPO, DATE, "daily", link_checker=lambda u: True),
                    "FAIL", False, "E-SELFCHECK-READ")
        p = Path(tempfile.mkdtemp()) / "bad.md"; p.write_bytes(b"\xff\xfe- x")
        self.expect(check_file(p, REPO, DATE, "daily"), "FAIL", False, "E-SELFCHECK-READ")

    def test_repo_and_date_required(self):
        self.expect(run(arxiv_line(), repo=Path("/nonexistent")), "FAIL", False, "E-SELFCHECK-REPO")
        self.expect(check_text(arxiv_line(), None, DATE, "daily"),
                    "FAIL", False, "E-SELFCHECK-REPO")
        for d in (None, "", "2026-02-30", "2026-13-01", "20260105"):
            self.expect(run(arxiv_line(), date=d), "FAIL", False, "E-SELFCHECK-DATE")


if __name__ == "__main__":
    unittest.main()


class R3Counter(unittest.TestCase):
    """r3 审查反例：每例同时断言 status、low_risk、错误码。"""
    expect = Whitelist.expect

    def test_reported_without_numbers_not_low_risk(self):
        r = run("# 重大突破\n" + arxiv_line("作者称该模型优于所有现有方法。"))
        self.assertFalse(r["low_risk"])
        self.expect(run(TITLE + arxiv_line("该方法优于现有方法。")), "PASS", False, "R-SUPPORT-UNVERIFIED")

    def test_macro_opinion_words_blocked(self):
        for w in ("经济前景乐观。", "应持有黄金。", "建议加配债券。", "通胀前景向好。", "outlook is optimistic."):
            self.expect(run(TITLE + fred_line() + "\n" + w), "FAIL", False, "E-BLOCK-MACRO-OPINION")
            self.expect(run(TITLE + fred_line("UNRATE 为 4.2%，" + w)), "FAIL", False, "E-BLOCK-MACRO-OPINION")

    def test_macro_arith_needs_marker_and_formula(self):
        for t in ("UNRATE 同比为 4.2%。", "UNRATE 环比 4.2 个百分点。", "UNRATE 差值 4.2。",
                  "UNRATE 同比 4.2%（由原始数据计算）。", "UNRATE 同比 4.2%（算式：4.2-0=4.2）。"):
            self.expect(run(TITLE + fred_line(t)), "FAIL", False, "E-BLOCK-MACRO-OPINION")
        ok = run(TITLE + fred_line("UNRATE 同比 4.2%（由原始数据计算；算式：(4.2-0)=4.2）。"))
        self.assertNotIn("E-BLOCK-MACRO-OPINION", ok["error_codes"]); self.assertFalse(ok["low_risk"])

    def test_entities_decoded_before_checks(self):
        ent = "".join(f"&#x{ord(c):x};" for c in "显然，该模型有望超过全部基线。")
        r = run(TITLE + arxiv_line() + "\n" + ent)
        self.assertTrue(r["flags"]["has_inference"]); self.assertFalse(r["low_risk"]); self.assertIn("R-INFERENCE", r["error_codes"])
        ent2 = "".join(f"&#x{ord(c):x};" for c in "建议加配")
        self.expect(run(TITLE + fred_line() + "\n" + ent2), "FAIL", False, "E-BLOCK-MACRO-OPINION")
        dbl = ent2.replace("&", "&amp;")
        self.expect(run(TITLE + fred_line() + "\n" + dbl), "FAIL", False, "E-BLOCK-MACRO-OPINION")

    def test_free_text_links_checked(self):
        r = run(TITLE + f"详见 https://github.com/markjin-lab/markjin-data/blob/x/README.md\n" + arxiv_line(),
                link_checker=lambda u: "github.com" not in u)
        self.expect(r, "PASS", False, "R-LINK-UNREACHABLE")

    def test_number_boundary(self):
        # #32：9、0.9 不被原文支持位置中的 90 支持 → 日报硬拦
        self.expect(run(TITLE + arxiv_line("该模型得分为 9。")), "FAIL", False, "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(TITLE + arxiv_line("该模型得分为 0.9%。")), "FAIL", False, "E-SUPPORT-LOCATOR-MISMATCH")
        self.expect(run(TITLE + arxiv_line("该模型在 MMLU 达到 90%。")), "PASS", False, "R-STRUCTURE", absent="R-SUPPORT-UNVERIFIED")

    def test_internal_malformed_row(self):
        H = "| 名称 | 识别条件 | 来源 |\n|---|---|---|\n"
        self.assertIsNone(parse_internal_list(H + "| 甲甲 | 条件一 | 来源一 |\n乙乙 | 条件二 | 来源二 |\n"))
        self.assertIsNone(parse_internal_list(H + "| 甲甲 | 条件一 | 来源一 |\n\n附注 a | b\n"))

    def test_missing_date_not_low_risk(self):
        r = run(TITLE + quote_line()); self.assertTrue(r["low_risk"])
        for v in ("DEL", None, "2026-02-30", 20260105):
            x = dict(r)
            if v == "DEL": x.pop("date")
            else: x["date"] = v
            self.assertFalse(compute_low_risk(x))


class FormulaVerify(unittest.TestCase):
    expect = Whitelist.expect

    def test_verify_formula_unit(self):
        from markjin.selfcheck import verify_formula
        ok = ["算式：(334.131/323.291-1)×100=3.35", "算式：(334.131/323.291-1)×100=3.35%", "算式：4.2-4.1=0.1",
              "算式: (5.22 − 4.73)=0.49", "算式：10÷4=2.5", "算式：(4.2-0)=4.2"]
        bad = ["算式：(334.131/323.291-1)×100=3.36", "算式：4.2+4.2=4.2",
               "算式：1/0=1", "算式：__import__('os')=1", "算式：2**3=8", "算式：4.2-=1"]
        for t in ok: self.assertTrue(verify_formula(t), t)
        for t in bad: self.assertFalse(verify_formula(t), t)

    def test_wrong_formula_blocked(self):
        self.expect(run(TITLE + fred_line("UNRATE 同比 4.2%（由原始数据计算；算式：4.2+4.2=4.2）。")),
                    "FAIL", False, "E-FORMULA-MISMATCH")
        ok = run(TITLE + fred_line("UNRATE 同比 4.2%（由原始数据计算；算式：(4.2-0)=4.2）。"))
        self.assertNotIn("E-FORMULA-MISMATCH", ok["error_codes"]); self.assertEqual(ok["status"], "PASS"); self.assertFalse(ok["low_risk"])


from helpers import XPOST_ID  # noqa: E402


class StructureWhitelist(T):
    """王总 10-11：低风险 = 只有 标题 + 原文直引 + 来源链接。"""

    def test_pure_quote_positive(self):
        for doc in (TITLE + quote_line(),
                    TITLE + "\n" + quote_line() + "\n\n" + source_line() + "\n",
                    TITLE + quote_line('handles long documents') + "\n",
                    TITLE + f'> "The method handles long documents well." — `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1'):
            r = run(doc); self.expect(r, "PASS", True); self.assertEqual(r["error_codes"], [])

    def test_counter_examples(self):
        cases = [
            TITLE + "作者称该方法优于基线。\n" + quote_line(),                          # 转述判断段落
            TITLE + "- 作者称该方法优于基线 — `raw/" + DATE + "/arxiv/cs.AI.xml` · https://arxiv.org/abs/" + ARXIV_ID + "v1\n",
            TITLE + "经济一定会复苏。\n" + quote_line(),                                # 宏观判断
            TITLE + "看好黄金。\n" + quote_line(),                                      # 仓位/观点
            TITLE + "&#x8fd9;&#x610f;&#x5473;&#x7740;&#x683c;&#x5c40;&#x53d8;&#x5316;\n" + quote_line(),  # 实体编码判断句
            TITLE + quote_line("The model reaches 95% accuracy on MMLU."),             # 夹带原文没有的字
            TITLE + quote_line("The model clearly reaches 90% accuracy on MMLU."),
            TITLE + quote_line() + "\n这个结果令人印象深刻，值得关注。\n",               # 有标题但带评语段落
            TITLE + quote_line("release 2.0", raw="arxiv/cs.AI.xml"),                  # 引文不在该 ID 条目里
            TITLE + quote_line("MMLU"),                                                 # 太短
        ]
        for doc in cases:
            r = run(doc); self.assertIs(r["low_risk"], False, doc)
        hard = {2: "E-BLOCK-MACRO-OPINION", 3: "E-BLOCK-MACRO-OPINION"}
        for idx, code in hard.items():
            r = run(cases[idx]); self.assertEqual(r["status"], "FAIL", r["error_codes"]); self.assertIn(code, r["error_codes"])
        r = run(cases[4]); self.assertIn("R-STRUCTURE", r["error_codes"]); self.assertIn("R-INFERENCE", r["error_codes"])
        for idx in (5, 6, 8, 9):
            r = run(cases[idx]); self.assertEqual(r["status"], "PASS"); self.assertIn("R-QUOTE-UNVERIFIED", r["error_codes"])
        r = run(cases[7]); self.assertEqual(r["status"], "UNCLEAR"); self.assertIn("R-STRUCTURE", r["error_codes"])

    def test_verbatim_only_for_daily(self):
        r = run(TITLE + quote_line(), card_type="signal")
        self.assertFalse(r["low_risk"]); self.assertIn("R-SIGNAL-CARD", r["error_codes"])
        self.assertIn("R-QUOTE-UNVERIFIED", r["error_codes"])

    def test_quote_binding_and_links(self):
        self.expect(run(TITLE + quote_line(url="https://arxiv.org/abs/2610.99999")), "FAIL", False, "E-REPLAY-004")
        self.expect(run(TITLE + quote_line(raw="x/01.json")), "FAIL", False, "E-REPLAY-006")
        self.expect(run(TITLE + quote_line(), link_checker=lambda u: False), "PASS", False, "R-LINK-UNREACHABLE")
        self.expect(run(TITLE + quote_line(), link_checker=None), "PASS", False, "R-LINK-UNCHECKED")
        # X 原文直引：逐字核对可以通过，但 X 只是线索 → 非低风险
        r = run(TITLE + quote_line("release 2.0", raw="x/01.json", url=f"https://x.com/i/status/{XPOST_ID}"))
        self.assertNotIn("R-QUOTE-UNVERIFIED", r["error_codes"]); self.expect(r, "FAIL", False, "E-X-ONLY")

    def test_inference_word_in_genuine_quote_blocks_low_risk(self):
        from helpers import make_repo, FILES
        files = dict(FILES); files["arxiv/cs.AI.xml"] = (f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id>"
                                                        "<summary>Our method likely outperforms prior work by 3 points.</summary></entry></feed>")
        repo = make_repo(files)
        r = run(TITLE + quote_line("Our method likely outperforms prior work by 3 points."), repo=repo)
        # 协调决定（10-11）：直引里带判断词同样不算低风险
        self.assertEqual(r["status"], "PASS"); self.assertIn("R-INFERENCE", r["error_codes"]); self.assertIs(r["low_risk"], False)


class R6Fixes(T):
    def repo_with(self, xml=None, xjson=None):
        from helpers import make_repo, FILES
        f = dict(FILES)
        if xml is not None: f["arxiv/cs.AI.xml"] = xml
        if xjson is not None: f["x/01.json"] = xjson
        return make_repo(f)

    def test_arxiv_exact_entry_and_version(self):
        u1 = f"https://arxiv.org/abs/{ARXIV_ID}v1"
        self.expect(run(TITLE + quote_line(url=u1)), "PASS", True)
        self.expect(run(TITLE + quote_line(url=f"https://arxiv.org/abs/{ARXIV_ID}")), "PASS", True)    # 无版本：按基础 ID
        self.expect(run(TITLE + quote_line(url=f"https://arxiv.org/abs/{ARXIV_ID}v2")), "FAIL", False, "E-REPLAY-004")
        # 摘要里提到 ID 不算：只认条目自身 <id>
        xml = ("<feed><entry><id>http://arxiv.org/abs/2610.00002v1</id><summary>Compared with " + ARXIV_ID +
               ", Model A reaches 90% accuracy on MMLU.</summary></entry></feed>")
        repo = self.repo_with(xml=xml)
        self.expect(run(TITLE + quote_line("Model A reaches 90% accuracy on MMLU.", url=u1), repo=repo), "FAIL", False, "E-REPLAY-004")
        self.expect(run(TITLE + arxiv_line(), repo=repo), "FAIL", False, "E-REPLAY-004")
        # 跨 <title>/<summary> 拼接不算
        xml2 = (f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id><title>Big Model</title>"
                "<summary>reaches 90% accuracy on MMLU.</summary></entry></feed>")
        r = run(TITLE + quote_line("Big Model reaches 90%"), repo=self.repo_with(xml=xml2))
        self.assertFalse(r["low_risk"]); self.assertIn("R-QUOTE-UNVERIFIED", r["error_codes"])

    def test_x_only_own_id_field(self):
        xj = '{"data": [{"id": "999", "text": "see ' + XPOST_ID + ' release 2.0 now"}]}'
        r = run(TITLE + quote_line("release 2.0 now", raw="x/01.json", url=f"https://x.com/i/status/{XPOST_ID}"),
                repo=self.repo_with(xjson=xj))
        self.expect(r, "FAIL", False, "E-REPLAY-004")

    def test_negation_truncation(self):
        xml = (f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id><summary>The model does not outperform the baseline. "
               "It reaches 90% accuracy only if tuned. 该方法并非优于基线方法。 模型达到 90% 准确率。</summary></entry></feed>")
        repo = self.repo_with(xml=xml)
        bad = ["outperform the baseline.", "It reaches 90% accuracy", "优于基线方法。"]
        for q in bad:
            r = run(TITLE + quote_line(q), repo=repo)
            self.assertFalse(r["low_risk"], q); self.assertIn("R-QUOTE-UNVERIFIED", r["error_codes"], q)
        ok = ["The model does not outperform the baseline.", "模型达到 90% 准确率。", "It reaches 90% accuracy only if tuned."]
        for q in ok:
            r = run(TITLE + quote_line(q), repo=repo)
            self.assertNotIn("R-QUOTE-UNVERIFIED", r["error_codes"], q)
        from markjin.selfcheck import quote_in_source
        self.assertFalse(quote_in_source(["We did not see gains on MMLU tasks"], "see gains on MMLU tasks"))
        self.assertFalse(quote_in_source(["仅在小模型上有效果提升明显"], "在小模型上有效果提升明显"))
        self.assertFalse(quote_in_source(["accuracy improves unless data is noisy"], "accuracy improves"))
        self.assertTrue(quote_in_source(["Accuracy improves with scale and data"], "improves with scale"))

    def test_position_sentence_blocked(self):
        for d in ("组合的股票权重为 30%。", "黄金仓位占比 20%。", "portfolio weight in equities is 60%."):
            r = run(TITLE + d + "\n" + quote_line())
            self.assertEqual(r["status"], "FAIL", d); self.assertFalse(r["low_risk"])
            self.assertTrue({"E-BLOCK-INVEST", "E-BLOCK-MACRO-OPINION"} & set(r["error_codes"]), (d, r["error_codes"]))

    def test_compare_arith_rule(self):
        self.expect(run(TITLE + fred_line("UNRATE 比上期高 4.2%。")), "FAIL", False, "E-BLOCK-MACRO-OPINION")
        self.expect(run(TITLE + fred_line("UNRATE 较上月下降 0.1。")), "FAIL", False, "E-BLOCK-MACRO-OPINION")
        ok = run(TITLE + fred_line("UNRATE 比上期高 0.1（由原始数据计算；算式：4.2-4.1=0.1）。"))
        self.assertEqual(ok["status"], "PASS", ok["error_codes"])
        self.expect(run(TITLE + fred_line("UNRATE 比上期高 0.2（由原始数据计算；算式：4.2-4.1=0.2）。")), "FAIL", False, "E-FORMULA-MISMATCH")

    def test_macro_opinion_more(self):
        for d in ("黄金应该配置。", "经济形势很好。"):
            r = run(TITLE + fred_line() + "\n" + d)
            self.assertEqual(r["status"], "FAIL", d)
            self.assertTrue({"E-BLOCK-MACRO-OPINION", "E-BLOCK-INVEST"} & set(r["error_codes"]), (d, r["error_codes"]))

    def test_symlink_raw_rejected(self):
        import os, tempfile
        from helpers import make_repo, write_manifest
        repo = make_repo()
        ext = Path(tempfile.mkdtemp()) / "a.xml"
        ext.write_text(open(repo / "raw" / DATE / "arxiv/cs.AI.xml").read())
        os.remove(repo / "raw" / DATE / "arxiv/cs.AI.xml"); os.symlink(ext, repo / "raw" / DATE / "arxiv/cs.AI.xml")
        # 内容未变，MANIFEST 哈希仍匹配：只有符号链接这一点不同
        self.expect(run(TITLE + quote_line(), repo=repo), "FAIL", False, "E-REPLAY-SYMLINK")
        repo2 = make_repo(); d = repo2 / "raw" / DATE
        real = Path(tempfile.mkdtemp()) / "arxiv"; os.rename(d / "arxiv", real); os.symlink(real, d / "arxiv")
        self.expect(run(TITLE + quote_line(), repo=repo2), "FAIL", False, "E-REPLAY-SYMLINK")


class R8Fixes(T):
    """第 8 轮（10-11 02:32 决定）：情态词、否定窗口、arXiv 版本/嵌套 id、仓位句式、医疗/宗教、标题判断、免责声明。"""
    def repo_with(self, xml):
        from helpers import make_repo, FILES
        f = dict(FILES); f["arxiv/cs.AI.xml"] = xml
        return make_repo(f)

    def xml(self, summary, extra=""):
        return (f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id><summary>{summary}</summary></entry>{extra}</feed>")

    def test_modal_words_block_low_risk(self):
        for q in ("The model may outperform the baseline.", "The model could outperform the baseline.",
                  "The model might outperform the baseline.", "Results suggest the model outperforms the baseline.",
                  "The model likely outperforms the baseline.", "该模型可能优于基线方法。", "该模型或将超过基线方法。",
                  "该模型有望超过基线方法。"):
            r = run(TITLE + quote_line(q), repo=self.repo_with(self.xml(q)))
            self.assertEqual(r["status"], "PASS", (q, r["error_codes"])); self.assertIs(r["low_risk"], False, q)
            self.assertIn("R-INFERENCE", r["error_codes"], q)
        # 反例对照：无情态词的整句直引仍为低风险；mayor 不是 may
        q = "The mayor handles long documents well."
        self.expect(run(TITLE + quote_line(q), repo=self.repo_with(self.xml(q))), "PASS", True)

    def test_negation_window_skips_adverbs(self):
        from markjin.selfcheck import quote_in_source
        self.assertFalse(quote_in_source(["The model does not consistently outperform the baseline"], "outperform the baseline"))
        self.assertFalse(quote_in_source(["It is not always clearly better than the baseline"], "better than the baseline"))
        self.assertFalse(quote_in_source(["该方法并不总是优于基线方法"], "优于基线方法"))
        self.assertFalse(quote_in_source(["该方法仅明显优于基线方法"], "优于基线方法"))
        # r8 起按句判断：同一句里引文之前任意远的否定/限定词都挡住（不再有固定窗口）
        self.assertFalse(quote_in_source(["该方法仅在少数情况下优于基线方法"], "下优于基线方法"))
        self.assertFalse(quote_in_source(["It was not trained on code data and then reaches 90% accuracy"], "reaches 90% accuracy"))
        # 上一句的否定词不影响
        self.assertTrue(quote_in_source(["It does not use code. The model reaches 90% accuracy"], "The model reaches 90% accuracy"))
        # 完整句子不受窗口限制
        self.assertTrue(quote_in_source(["Not all runs. The model reaches 90% accuracy."], "The model reaches 90% accuracy."))
        r = run(TITLE + quote_line("outperform the baseline."),
                repo=self.repo_with(self.xml("The model does not consistently outperform the baseline.")))
        self.assertFalse(r["low_risk"]); self.assertIn("R-QUOTE-UNVERIFIED", r["error_codes"])

    def test_versionless_link_multiple_versions_unclear(self):
        two = (f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id><summary>The method handles long documents well.</summary></entry>"
               f"<entry><id>http://arxiv.org/abs/{ARXIV_ID}v2</id><summary>The method handles long documents well.</summary></entry></feed>")
        repo = self.repo_with(two)
        r = run(TITLE + quote_line(url=f"https://arxiv.org/abs/{ARXIV_ID}"), repo=repo)
        self.expect(r, "UNCLEAR", False, "E-REPLAY-VERSION-UNCLEAR")
        self.expect(run(TITLE + quote_line(url=f"https://arxiv.org/abs/{ARXIV_ID}v2"), repo=repo), "PASS", True)
        # 只有一个版本时，无版本链接照常
        self.expect(run(TITLE + quote_line(url=f"https://arxiv.org/abs/{ARXIV_ID}")), "PASS", True)

    def test_nested_id_not_entry_id(self):
        xml = (f"<feed><entry><summary><id>http://arxiv.org/abs/{ARXIV_ID}v1</id></summary>"
               "<title>The model reaches 90% accuracy on MMLU.</title></entry></feed>")
        r = run(TITLE + quote_line(), repo=self.repo_with(xml))
        self.expect(r, "FAIL", False, "E-REPLAY-004")
        # 带 Atom 命名空间的真实格式照常识别
        ns = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/' + ARXIV_ID +
              'v1</id><summary>The method handles long documents well.</summary></entry></feed>')
        self.expect(run(TITLE + quote_line(), repo=self.repo_with(ns)), "PASS", True)
        self.expect(run(TITLE + quote_line(), repo=self.repo_with("<feed><entry>")), "FAIL", False, "E-REPLAY-READ")

    def test_buy_worthy_and_holding_ratio_blocked(self):
        for d in ("美债值得购买。", "这只基金值得买。", "股票持有六成。", "债券持有百分之三十。", "股票持有 6 成。", "满仓持有七成。"):
            r = run(TITLE + quote_line() + "\n" + d)
            self.assertEqual(r["status"], "FAIL", d); self.assertFalse(r["low_risk"])
            self.assertTrue({"E-BLOCK-INVEST", "E-BLOCK-MACRO-OPINION"} & set(r["error_codes"]), (d, r["error_codes"]))
        r = run(TITLE + fred_line() + "\n" + "美债值得购买。")
        self.assertEqual(r["status"], "FAIL")

    def test_medical_and_religion_not_low_risk(self):
        for q, codes in (("中医研究采用文本分类方法。", {"R-MEDICAL"}), ("针灸研究采用文本分类方法。", {"R-MEDICAL"}),
                         ("中药与经络研究采用文本分类方法。", {"R-MEDICAL"}), ("方剂研究采用文本分类方法。", {"R-MEDICAL"}),
                         ("Acupuncture improves sleep quality.", {"R-MEDICAL"}),
                         ("佛学文本研究采用文本分类方法。", {"R-MEDICAL", "R-RELIGION"}),
                         ("佛教文本研究采用文本分类方法。", {"R-RELIGION"})):
            r = run(TITLE + quote_line(q), repo=self.repo_with(self.xml(q)))
            self.assertEqual(r["status"], "PASS", (q, r["error_codes"]))   # 可以公开：不硬拦
            self.assertIs(r["low_risk"], False, q)
            self.assertTrue(codes <= set(r["error_codes"]), (q, r["error_codes"]))

    def test_heading_judgment(self):
        for h in ("# 方法 A 优于现有方法", "## 模型可能超过基线"):
            r = run(h + "\n" + quote_line())
            self.assertEqual(r["status"], "PASS"); self.assertFalse(r["low_risk"])
            self.assertIn("R-STRUCTURE", r["error_codes"], h)
        r = run("---\ntitle: 方法 A 优于现有方法\n---\n" + TITLE + quote_line())
        self.assertFalse(r["low_risk"]); self.assertIn("R-STRUCTURE", r["error_codes"])
        self.expect(run(TITLE + quote_line()), "PASS", True)    # 固定栏目名照常

    def test_disclaimer_and_connective(self):
        ok = run(TITLE + fred_line() + "\n本文不含投资建议。")
        self.assertNotIn("E-BLOCK-MACRO-OPINION", ok["error_codes"]); self.assertEqual(ok["status"], "PASS", ok["error_codes"])
        ok2 = run(TITLE + fred_line("UNRATE 为 4.2%，所以该序列取值为 4.2。"))
        self.assertNotIn("E-BLOCK-MACRO-OPINION", ok2["error_codes"])
        # 只放行精确原文；“见顶”仍拦
        for d in ("本文不含投资建议，但建议关注。", "本文不含投资建议，利率已见顶。", "利率已见顶。"):
            self.expect(run(TITLE + fred_line() + "\n" + d), "FAIL", False, "E-BLOCK-MACRO-OPINION")


class UnsourcedBlocks(T):
    """无来源块规则：不命中词表、也没有来源的事实段落，不得发布（UNCLEAR；含数字/推断 → FAIL）。"""
    def test_unsourced_fact_paragraph(self):
        r = run(TITLE + quote_line() + "\n研究团队发布了新模型。")
        self.expect(r, "UNCLEAR", False, "E-INFER-UNCLEAR")
        r = run(TITLE + quote_line() + "\n研究团队发布的模型达到 95% 准确率。")
        self.expect(r, "FAIL", False, "E-REPLAY-001")
        # 免责声明、front matter 字段不算事实段落
        r = run("---\ntitle: 日报\n---\n" + TITLE + quote_line() + "\n本文不含投资建议。")
        self.assertNotIn("E-INFER-UNCLEAR", r["error_codes"]); self.assertEqual(r["status"], "PASS", r["error_codes"])


class R7Review(T):
    """第 7 轮审查意见（10-11 07:14 决定）：分号不算句末、推测词类表、资产仓位句式、front matter/表头数字。"""
    def repo_with(self, xml):
        from helpers import make_repo, FILES
        f = dict(FILES); f["arxiv/cs.AI.xml"] = xml
        return make_repo(f)

    def xml(self, summary):
        return f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id><summary>{summary}</summary></entry></feed>"

    def test_semicolon_not_sentence_end(self):
        from markjin.selfcheck import quote_in_source
        src = "The model outperforms the baseline; only if fine-tuned."
        self.assertFalse(quote_in_source([src], "The model outperforms the baseline;"))
        self.assertFalse(quote_in_source(["该模型优于基线；仅在微调后成立。"], "该模型优于基线；"))
        r = run(TITLE + quote_line("The model outperforms the baseline;"), repo=self.repo_with(self.xml(src)))
        self.assertIs(r["low_risk"], False); self.assertIn("R-QUOTE-UNVERIFIED", r["error_codes"])
        # 对照：句号结尾的完整句仍可低风险
        ok = "The method handles long documents well."
        self.expect(run(TITLE + quote_line(ok), repo=self.repo_with(self.xml(ok + " Only if fine-tuned."))), "PASS", True)

    def test_speculative_class_table(self):
        for q in ("The model seems to outperform the baseline.", "The model appears to outperform the baseline.",
                  "Results suggests the model outperforms the baseline.", "Results indicate the model outperforms the baseline.",
                  "The data indicated a 90% gain on MMLU.", "The model is likely better than the baseline.",
                  "The model apparently outperforms the baseline.", "The model would outperform the baseline.",
                  "该模型似乎优于基线方法。", "看来该模型优于基线方法。", "实验表明该模型优于基线方法。"):
            r = run(TITLE + quote_line(q), repo=self.repo_with(self.xml(q)))
            self.assertEqual(r["status"], "PASS", (q, r["error_codes"])); self.assertIs(r["low_risk"], False, q)
            self.assertIn("R-INFERENCE", r["error_codes"], q)
        q = "The method handles long documents well."     # 对照：无推测词
        self.expect(run(TITLE + quote_line(q), repo=self.repo_with(self.xml(q))), "PASS", True)

    def test_asset_advice_and_ratio_blocked(self):
        bad = ("美债应当持有。", "股票应该买。", "黄金值得配置。", "债券建议持有。", "国债应该配置。", "美元值得买入。",
               "房产建议购买。", "基金值得持有。", "应当持有美债。", "美债持有半数。", "股票占六成。",
               "黄金持有 30%。", "债券占比 40%。", "基金持仓一半。")
        for d in bad:
            r = run(TITLE + quote_line() + "\n" + d)
            self.assertEqual(r["status"], "FAIL", d); self.assertFalse(r["low_risk"])
            self.assertIn("E-BLOCK-INVEST", r["error_codes"], (d, r["error_codes"]))
            r = run(TITLE + fred_line() + "\n" + d)
            self.assertEqual(r["status"], "FAIL", d)
        # 宏观评价
        r = run(TITLE + fred_line() + "\n美债很有吸引力。")
        self.assertIn("E-BLOCK-MACRO-OPINION", r["error_codes"])
        # 对照：资产词本身、纯事实不拦
        r = run(TITLE + fred_line("美债 10 年期收益率为 4.2。"))
        self.assertNotIn("E-BLOCK-INVEST", r["error_codes"])

    def test_numbers_in_front_matter_and_table_header(self):
        r = run("---\ntitle: 模型达到 95%\n---\n" + TITLE + quote_line())
        self.expect(r, "FAIL", False, "E-REPLAY-001")
        r = run("---\nscore: 95\n---\n" + TITLE + quote_line())
        self.expect(r, "FAIL", False, "E-REPLAY-001")
        r = run(TITLE + quote_line() + "\n| MMLU 95% | 来源 |\n|---|---|\n")
        self.assertEqual(r["status"], "FAIL"); self.assertIn("E-REPLAY-001", r["error_codes"])
        # 对照：日期字段不算数字断言
        r = run("---\ntitle: 日报\ndate: 2026-01-05\npublishDate: 2026-01-05T08:00:00+08:00\n---\n" + TITLE + quote_line())
        self.assertNotIn("E-REPLAY-001", r["error_codes"]); self.assertEqual(r["status"], "PASS", r["error_codes"])


class R8Review(T):
    """第 8 轮审查意见（10-11 07:45 决定）：逗号/分号后的限定语、按句否定、预测情态、仓位事实句、股市主题、
    front matter 日期字段白名单与真伪、空 repo、FRED 内容核对、词表重读、免责声明精确句。"""
    def repo_with(self, xml):
        from helpers import make_repo, FILES
        f = dict(FILES); f["arxiv/cs.AI.xml"] = xml
        return make_repo(f)

    def xml(self, summary):
        return f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id><summary>{summary}</summary></entry></feed>"

    def test_qualifier_after_comma_or_semicolon(self):
        from markjin.selfcheck import quote_in_source
        for src, q in (("The model outperforms the baseline, but only if fine-tuned.", "The model outperforms the baseline"),
                       ("The model outperforms the baseline; only if fine-tuned.", "The model outperforms the baseline"),
                       ("该模型优于基线；仅在微调后成立。", "该模型优于基线"),
                       ("该模型优于基线，但仅限英文任务。", "该模型优于基线")):
            self.assertFalse(quote_in_source([src], q), q)
            r = run(TITLE + quote_line(q), repo=self.repo_with(self.xml(src)))
            self.assertEqual(r["status"], "PASS"); self.assertIs(r["low_risk"], False)
            self.assertIn("R-QUOTE-UNVERIFIED", r["error_codes"])

    def test_negation_by_sentence_not_word_window(self):
        from markjin.selfcheck import quote_in_source
        src = "The system does not quite very consistently produce an output."
        self.assertFalse(quote_in_source([src], "produce an output."))
        r = run(TITLE + quote_line("produce an output."), repo=self.repo_with(self.xml(src)))
        self.assertEqual(r["status"], "PASS"); self.assertIs(r["low_risk"], False); self.assertIn("R-QUOTE-UNVERIFIED", r["error_codes"])
        self.assertFalse(quote_in_source(["该方法在多数常见的英文基准上并非稳定地优于基线方法。"], "优于基线方法。"))
        # 对照：否定在上一句，引文为本句完整片段且本句无否定 → 可低风险
        ok = "It does not use code. The method handles long documents well."
        self.expect(run(TITLE + quote_line("The method handles long documents well."), repo=self.repo_with(self.xml(ok))), "PASS", True)

    def test_prediction_modal_full_quote(self):
        for q in ("The model will outperform the baseline.", "The model is going to outperform the baseline.",
                  "The model shall outperform the baseline.", "该模型将会超过基线方法。", "该模型必将超过基线方法。"):
            r = run(TITLE + quote_line(q), repo=self.repo_with(self.xml(q)))
            self.assertEqual(r["status"], "PASS", (q, r["error_codes"])); self.assertIs(r["low_risk"], False, q)
            self.assertIn("R-INFERENCE", r["error_codes"], q)
        q = "The willow dataset handles long documents well."   # willow 不是 will
        self.expect(run(TITLE + quote_line(q), repo=self.repo_with(self.xml(q))), "PASS", True)

    def test_position_fact_and_suitability_hard_blocked(self):
        # 仓位事实句：即使是原文直引、来源齐全，也硬拦（FAIL ⇒ 有人工批准也不能发布）
        for q in ("黄金是组合资产的一半。", "股票为持仓的30%。", "组合的一半是黄金。", "美债占组合六成。"):
            r = run(TITLE + quote_line(q), repo=self.repo_with(self.xml(q)))
            self.expect(r, "FAIL", False, "E-BLOCK-INVEST")
        for t in ("美债适合长期持有。", "黄金适宜配置。", "债券宜于买入。"):
            r = run(TITLE + fred_line() + "\n- " + t + f" — `raw/{DATE}/fred/UNRATE.json` · https://fred.stlouisfed.org/series/UNRATE")
            self.expect(r, "FAIL", False, "E-BLOCK-INVEST")
            self.assertIn("E-BLOCK-MACRO-OPINION", r["error_codes"])
        # 对照：资产词 + 事实但无比例/建议 → 不硬拦（股票类另由 R-STOCK 挡低风险）
        q = "黄金的原子序数为79。"
        r = run(TITLE + quote_line(q), repo=self.repo_with(self.xml(q)))
        self.assertNotIn("E-BLOCK-INVEST", r["error_codes"])

    def test_stock_fact_quote_not_low_risk(self):
        for q in ("股票收盘价为10元。", "The stock closed at 10 dollars.", "该公司A股今日涨停。"):
            r = run(TITLE + quote_line(q), repo=self.repo_with(self.xml(q)))
            self.expect(r, "PASS", False, "R-STOCK")

    def test_front_matter_date_key_whitelist_and_validity(self):
        q = quote_line()
        for fm in ("score: 2026-01-05", "claim: 2026-10-11", "result: 2026-02-30", "date: 2026-99-99",
                   "date: 2026-02-30", "publishDate: 2026-01-05T25:00:00Z"):
            r = run(f"---\n{fm}\n---\n" + TITLE + q)
            self.expect(r, "FAIL", False, "E-REPLAY-001")
        for fm in ("date: 2026-01-05", "publishDate: 2026-01-05T09:30:00+08:00", "lastmod: '2026-01-05'"):
            r = run(f"---\n{fm}\n---\n" + TITLE + q)
            self.assertNotIn("E-REPLAY-001", r["error_codes"], fm); self.assertEqual(r["status"], "PASS", fm)
            self.assertIs(r["low_risk"], False)

    def test_empty_repo_rejected(self):
        cwd = os.getcwd()
        try:
            os.chdir(REPO)
            for repo in ("", "   "):
                r = check_text(TITLE + quote_line(), repo, DATE, "daily", link_checker=lambda u: True)
                self.expect(r, "FAIL", False, "E-SELFCHECK-REPO")
        finally:
            os.chdir(cwd)
        r = check_text(TITLE + quote_line(), None, DATE, "daily", link_checker=lambda u: True)
        self.expect(r, "FAIL", False, "E-SELFCHECK-REPO")

    def test_fred_content_checked(self):
        from helpers import make_repo, FILES
        for body in ('not json', '{"series_id": "CPIAUCSL", "value": "4.2"}', '{"value": "4.2"}'):
            f = dict(FILES); f["fred/UNRATE.json"] = body
            r = run(TITLE + fred_line(), repo=make_repo(f))
            self.assertEqual(r["status"], "FAIL", body); self.assertIs(r["low_risk"], False)
            self.assertTrue({"E-REPLAY-READ", "E-REPLAY-004"} & set(r["error_codes"]), body)
        self.expect(run(TITLE + fred_line()), "PASS", False, "R-MACRO")

    def test_lexicon_reread_each_run(self):
        import markjin.selfcheck as sc
        orig = sc.LEXICON_PATH
        bad = Path(tempfile.mkdtemp()) / "lexicon.json"
        try:
            sc.load_lexicon.__defaults__ = (bad,)        # 模拟“导入后磁盘词表被删除”
            self.expect(run(TITLE + quote_line()), "FAIL", False, "E-SELFCHECK-LEXICON")
            bad.write_text("{broken", encoding="utf-8")   # 改坏
            self.expect(run(TITLE + quote_line()), "FAIL", False, "E-SELFCHECK-LEXICON")
        finally:
            sc.load_lexicon.__defaults__ = (orig,)
        self.expect(run(TITLE + quote_line()), "PASS", True)

    def test_disclaimer_exact(self):
        ok = run(TITLE + fred_line() + "\n本文不含投资建议。")
        self.assertNotIn("E-BLOCK-MACRO-OPINION", ok["error_codes"]); self.assertEqual(ok["status"], "PASS")
        for d in ("本文不含投资建议。。", "本文不含投资建议..", "。本文不含投资建议"):
            r = run(TITLE + fred_line() + "\n" + d)
            self.assertNotEqual(r["status"], "PASS", d); self.assertIs(r["low_risk"], False)


    def test_disclaimer_en_exact(self):
        # 英文版固定免责声明（协调决定 10-11）：只放行精确原文，至多一个句号
        from markjin import selfcheck as SC
        for d in ("本文不含投资建议", "This article does not constitute investment advice", "本文不含投资建议.", "This article does not constitute investment advice。"):
            self.assertFalse(SC.disclaimer_line(d), d)   # 整体验收 r2：句末标点也须逐字一致
        for d in ("This article does not constitute investment advice.",):
            for base in (fred_line(), quote_line()):
                ok = run(TITLE + base + "\n" + d)
                self.assertEqual(ok["status"], "PASS", d)
                self.assertNotIn("E-BLOCK-MACRO-OPINION", ok["error_codes"]); self.assertNotIn("E-INFER-UNCLEAR", ok["error_codes"])
        bad = {"This article does not constitute investment advice. Buy now.": "E-BLOCK-INVEST",
               "This article does not constitute investment advice, but bonds look cheap.": "E-BLOCK-MACRO-OPINION"}
        for d, code in bad.items():
            r = run(TITLE + fred_line() + "\n" + d)
            self.assertEqual(r["status"], "FAIL", d); self.assertIs(r["low_risk"], False); self.assertIn(code, r["error_codes"])
        for d in ("This article does not constitute investment advice..", "this article does not constitute investment advice.",
                  "This article does not constitute investment advice!"):
            r = run(TITLE + fred_line() + "\n" + d)
            self.assertNotEqual(r["status"], "PASS", d); self.assertIs(r["low_risk"], False)

class R9Structural(T):
    """第 9 轮（10-11 09:07 决定）：结构性收紧。直引含数字/百分比/分数/货币价格、比较级、情态/预测、大写实体或代号
    → 只移出低风险（R-QUOTE-*），不硬拦；硬拦只留明确买卖建议与仓位比例句（含中英文变体）；分句器不在数字中间断开。"""
    def repo_with(self, xml):
        from helpers import make_repo, FILES
        f = dict(FILES); f["arxiv/cs.AI.xml"] = xml
        return make_repo(f)

    def xml(self, summary):
        return f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id><summary>{summary}</summary></entry></feed>"

    def q(self, text):
        return run(TITLE + quote_line(text), repo=self.repo_with(self.xml(text)))

    def test_structural_classes_not_low_risk(self):
        cases = {
            "R-QUOTE-NUMERIC": ("The model reaches 90% accuracy on the benchmark.", "Shares closed at 120 dollars.",
                                "黄金占组合资产的五分之一。", "每股收于一百二十元。", "Prices rose sharply this week.",
                                "The method uses half the memory."),
            "R-QUOTE-COMPARATIVE": ("The method is superior to the baseline.", "The model outperforms prior work.",
                                    "该方法优于基线方法。", "The approach is faster than the baseline."),
            "R-QUOTE-MODAL": ("The model should outperform the baseline.", "Inflation will rise.",
                              "The method can handle long documents.", "该方法将改变研究方式。"),
            "R-QUOTE-ENTITY": ("NVIDIA traded at record levels.", "The team at OpenAI released the method.",
                               "The method was tested on AAPL data."),
        }
        for code, qs in cases.items():
            for t in qs:
                r = self.q(t)
                self.assertIs(r["low_risk"], False, t); self.assertIn(code, r["error_codes"], t)
                self.assertNotEqual(r["status"], "UNCLEAR", t)
        # 对照：无上述结构的整句直引仍为低风险
        for t in ("The method handles long documents well.", "该方法处理长文档。", "We release the code and data."):
            self.expect(self.q(t), "PASS", True)

    def test_structural_classes_not_hard_blocked(self):
        # 只是移出低风险，不硬拦（不 FAIL）
        for t in ("NVIDIA traded at 120 dollars per share.", "The method is superior to the baseline.",
                  "The model should outperform the baseline."):
            r = self.q(t)
            self.assertEqual(r["status"], "PASS", (t, r["error_codes"])); self.assertIs(r["low_risk"], False)
            self.assertFalse([c for c in r["error_codes"] if c.startswith("E-BLOCK")], t)

    def test_position_ratio_hard_block_variants(self):
        for t in ("Treasury bonds are half the portfolio.", "Stocks make up 30% of the portfolio.",
                  "Gold accounts for a third of holdings.", "Investors should buy gold.", "You should sell bonds now.",
                  "Allocate 20% of your portfolio to bonds.", "黄金占组合资产的五分之一。", "股票占组合三分之二。",
                  "组合的四分之一配置在美债。", "债券仓位为 1/3。"):
            r = self.q(t)
            self.assertEqual(r["status"], "FAIL", (t, r["error_codes"])); self.assertIs(r["low_risk"], False)
            self.assertIn("E-BLOCK-INVEST", r["error_codes"], t)
        for t in ("The model uses half the memory.", "We keep 30% of the data for testing."):
            self.assertNotIn("E-BLOCK-INVEST", self.q(t)["error_codes"], t)

    def test_macro_prediction_not_low_risk(self):
        r = self.q("Inflation will rise.")
        self.assertIs(r["low_risk"], False); self.assertIn("R-MACRO", r["error_codes"]); self.assertIn("R-QUOTE-MODAL", r["error_codes"])

    def test_sentence_splitter_ignores_decimal_point(self):
        from markjin.selfcheck import quote_in_source
        src = "Only if version 2.0 works, the device produces an output."
        self.assertFalse(quote_in_source([src], "the device produces an output."))
        self.assertFalse(quote_in_source(["Unless the 3.5 release ships, the tool produces a report."], "the tool produces a report."))
        r = run(TITLE + quote_line("the device produces an output."), repo=self.repo_with(self.xml(src)))
        self.assertIs(r["low_risk"], False); self.assertIn("R-QUOTE-UNVERIFIED", r["error_codes"])
        # 真正的句末仍然断句：上一句的否定不影响下一句完整引文
        self.assertTrue(quote_in_source(["It does not use 2.0 code. The method handles long documents well."],
                                        "The method handles long documents well."))
        # 小数点不算句末：引文以 "2." 结尾不是完整句
        self.assertFalse(quote_in_source(["The tool needs version 2.0 not 1.0."], "The tool needs version 2."))


class R10Translation(T):
    """t141u（经 Grok Bot 转达）：出现“译文：”行即 R-TRANSLATION，不算低风险；不硬拦。"""
    S = "The method uses a simple encoder."
    repo_with = R9Structural.repo_with; xml = R9Structural.xml; q = R9Structural.q

    def test_baseline_low_risk(self):
        r = self.q(self.S)
        self.assertEqual(r["status"], "PASS"); self.assertIs(r["low_risk"], True)
        self.assertNotIn("R-TRANSLATION", r["error_codes"])

    def test_translation_line_not_low_risk(self):
        for tl in ("译文：该方法使用一个简单的编码器。", "> 译文:该方法使用简单编码器。", "  译文 ： 该方法使用简单编码器。"):
            md = TITLE + quote_line(self.S) + "\n" + tl + "\n"
            r = run(md, repo=self.repo_with(self.xml(self.S)))
            self.assertIs(r["low_risk"], False, tl); self.assertIn("R-TRANSLATION", r["error_codes"], tl)
            self.assertNotIn("E-BLOCK-INVEST", r["error_codes"])

    def test_word_inside_sentence_not_translation(self):
        r = run(TITLE + quote_line(self.S) + "\n本文的译文：无\n", repo=self.repo_with(self.xml(self.S)))
        self.assertNotIn("R-TRANSLATION", r["error_codes"])


class R11HardBlocks(T):
    """r11（t161u 后）：硬拦中英一致；英文单词写的仓位比例、英文资产评价句硬拦；裸 buy 不误拦。low_risk 只作参考。"""
    repo_with = R9Structural.repo_with; xml = R9Structural.xml; q = R9Structural.q

    def test_spelled_en_ratio_blocked(self):
        for t in ("Treasury bonds account for forty percent of the portfolio.", "Stocks make up two-thirds of the portfolio.",
                  "Gold is three quarters of their holdings.", "Bonds represent twenty-five percent of the portfolio."):
            r = self.q(t); self.assertEqual(r["status"], "FAIL", t); self.assertIn("E-BLOCK-INVEST", r["error_codes"], t)
            self.assertIs(r["low_risk"], False)

    def test_en_asset_evaluation_blocked(self):
        for t in ("Treasury yields are attractive.", "US stocks look cheap.", "Bonds are overvalued now.", "Gold remains a bargain."):
            r = self.q(t); self.assertEqual(r["status"], "FAIL", t); self.assertIn("E-BLOCK-MACRO-OPINION", r["error_codes"], t)

    def test_quote_macro_prediction_consistent(self):
        for t in ("Inflation will rise.", "通胀将会上升。"):
            r = self.q(t)
            self.assertNotEqual(r["status"], "FAIL", (t, r["error_codes"])); self.assertIs(r["low_risk"], False, t)
            self.assertIn("R-MACRO", r["error_codes"], t)

    def test_free_text_macro_prediction_consistent(self):
        for t in ("Inflation will rise.", "通胀将会上升。"):
            r = run(TITLE + t + "\n" + quote_line())
            self.assertEqual(r["status"], "FAIL", (t, r["error_codes"]))

    def test_bare_buy_not_blocked(self):
        for t in ("This paper studies buy signals.", "We present a dataset of buy and sell orders."):
            r = self.q(t); self.assertNotIn("E-BLOCK-INVEST", r["error_codes"], t); self.assertNotEqual(r["status"], "FAIL", t)
        for t in ("Investors should buy gold.", "It is time to buy now.", "Analysts issued a strong buy rating."):
            r = self.q(t); self.assertIn("E-BLOCK-INVEST", r["error_codes"], t)

    def test_non_asset_evaluation_not_blocked(self):
        r = self.q("The results are attractive for parsing.")
        self.assertNotIn("E-BLOCK-MACRO-OPINION", r["error_codes"])


class R12HardBlockVariants(T):
    """r12：评价/机会类说法硬拦（宏观稿任何位置；非宏观稿与明确资产词同行），以及各硬拦变体的正反例。
    每个用例同时断言 status、low_risk 与目标错误码。"""
    MAC = "E-BLOCK-MACRO-OPINION"
    INV = "E-BLOCK-INVEST"

    def blocked(self, line, code, macro=False):
        r = run(TITLE + (fred_line() if macro else quote_line()) + "\n" + line + "\n")
        self.expect(r, "FAIL", False, code)

    def not_blocked(self, line, macro=False):
        r = run(TITLE + (fred_line() if macro else quote_line()) + "\n" + line + "\n")
        self.assertNotIn(self.MAC, r["error_codes"], line); self.assertNotIn(self.INV, r["error_codes"], line)
        self.assertIs(r["low_risk"], False)

    def test_macro_opportunity_en(self):
        for s in ("Treasury yields offer an excellent opportunity.", "This is an attractive entry point.",
                  "Rates now present a compelling case.", "Long bonds are a bargain here.", "There is significant upside.",
                  "> 「Treasury yields offer an excellent opportunity.」"):
            self.blocked(s, self.MAC, macro=True)

    def test_macro_opportunity_zh(self):
        for s in ("美债收益率值得配置。", "当前是难得的机会。", "人民币资产很有吸引力。", "估值处于低估区间。", "上涨空间很大。"):
            self.blocked(s, self.MAC, macro=True)

    def test_asset_opportunity_non_macro(self):
        for s, c in (("Gold offers an excellent opportunity.", self.MAC), ("Bitcoin is undervalued.", self.MAC),
                     ("黄金是很好的机会。", self.MAC), ("现在的股票很便宜。", self.MAC)):
            self.blocked(s, c)

    def test_no_misblock_non_macro(self):
        for s in ("Our method yields excellent results.", "This opens an opportunity for future work.",
                  "值得注意的是，该模型在长文本上更稳定。", "机会成本在文中被定义为放弃的收益。",
                  "The stock of knowledge is rich.", "uses half the memory", "30% of the data is synthetic.",
                  "黄金样本占30%。", "buy signals are studied in the paper."):
            self.not_blocked(s)

    def test_disclaimer_not_blocked_in_macro(self):
        for d in ("本文不含投资建议。", "This article does not constitute investment advice."):
            r = run(TITLE + fred_line() + "\n" + d)
            self.assertNotIn(self.MAC, r["error_codes"]); self.assertNotIn(self.INV, r["error_codes"])

    def test_position_variants_still_blocked(self):
        for s in ("黄金占30%。", "黄金占比三成。", "组合的一半是黄金。", "股票为持仓的30%。", "建议持有美债。",
                  "Gold is half the portfolio.", "Bonds make up forty percent of the portfolio.",
                  "Investors should buy gold now.", "Allocate two-thirds of your portfolio to stocks."):
            self.blocked(s, self.INV)

    def test_eval_variants_still_blocked(self):
        for s in ("Treasury yields are attractive.", "Gold looks cheap.", "Stocks are overvalued."):
            self.blocked(s, self.MAC)


class R13Boundary(R12HardBlockVariants):
    """r13：英文仓位句 in our portfolio；科研文本不误拦；HTML 注释中的来源回放。"""
    def test_position_in_portfolio(self):
        for s in ("Gold is twenty percent in our portfolio.", "Stocks are 30% in my portfolio.",
                  "Bonds make up two-thirds of our holdings.", "Treasuries are half within the portfolio."):
            self.blocked(s, self.INV)

    def test_science_text_not_blocked(self):
        for s in ("Gold nanoparticles provide excellent contrast.", "The gold-standard assay yields excellent results.",
                  "Oil droplets show attractive optical properties.", "Silver electrodes give compelling stability."):
            self.not_blocked(s)

    def test_ambiguous_asset_with_market_context_blocked(self):
        for s in ("Gold prices offer an excellent opportunity.", "Oil futures look attractive to investors.",
                  "Gold offers an excellent opportunity.", "Silver is undervalued."):
            self.blocked(s, self.MAC)

    def test_comment_sources_replayed(self):
        r = run(TITLE + quote_line() + "\n<!-- 见 raw/" + DATE + "/arxiv/missing.xml · https://arxiv.org/abs/2610.00001v1 -->\n")
        self.assertEqual(r["status"], "FAIL"); self.assertIs(r["low_risk"], False)
        self.assertTrue({"E-REPLAY-002", "E-REPLAY-006"} & set(r["error_codes"]), r["error_codes"])
        r = run(TITLE + quote_line() + "\n<!-- https://example.com/x -->\n")
        self.expect(r, "FAIL", False, "E-REPLAY-005")


class R12TranslationPrefix(T):
    def test_list_prefixed_translation(self):
        for p in ("译文：", "> 译文：", "- 译文：", "* 译文：", "+ 译文：", "1. 译文：", "2) 译文：", "3、译文：", "> - 译文:"):
            r = run(TITLE + quote_line() + "\n" + p + "这是一段译文。\n")
            self.assertIn("R-TRANSLATION", r["error_codes"], p); self.assertIs(r["low_risk"], False)
        r = run(TITLE + quote_line() + "\n本段讨论译文：质量。\n")
        self.assertNotIn("R-TRANSLATION", r["error_codes"])


class R13Fred(unittest.TestCase):
    def _run(self, name, obj, sid="CPIAUCSL"):
        import tempfile, hashlib
        from markjin.selfcheck import check_text
        d = Path(tempfile.mkdtemp()); r = d / "raw" / "2026-10-10" / "fred"; r.mkdir(parents=True)
        b = json.dumps(obj).encode(); (r / name).write_bytes(b)
        (d / "raw" / "2026-10-10" / "MANIFEST.sha256").write_text(hashlib.sha256(b).hexdigest() + "  fred/" + name + "\n")
        txt = "- CPIAUCSL 2026-08 为 334.131。— `raw/2026-10-10/fred/%s` · https://fred.stlouisfed.org/series/%s\n" % (name, sid)
        return check_text(txt, repo=d, date="2026-10-10", card_type="daily", link_checker=lambda u: True, internal_terms="load")

    def test_observations_without_series_id_bound_by_filename(self):
        out = self._run("CPIAUCSL.json", {"observations": [{"date": "2026-08-01", "value": "334.131"}]})
        self.assertNotIn("E-REPLAY-004", out["error_codes"])

    def test_filename_mismatch_fails(self):
        out = self._run("UNRATE.json", {"observations": [{"date": "2026-08-01", "value": "334.131"}]})
        self.assertEqual(out["status"], "FAIL"); self.assertIn("E-REPLAY-004", out["error_codes"])

    def test_self_reported_id_must_match(self):
        out = self._run("CPIAUCSL.json", {"series_id": "UNRATE", "observations": [{"date": "2026-08-01", "value": "334.131"}]})
        self.assertEqual(out["status"], "FAIL"); self.assertIn("E-REPLAY-004", out["error_codes"])


class CorrectionFrontMatter(unittest.TestCase):
    def test_correction_fields_not_assertions(self):
        repo = make_repo()
        body = "# 日报 2026-01-05\n" + arxiv_line("作者声称 MMLU 90%。") + "\n"
        ok = "---\ncorrects: daily-2026-01-05-d1\ncorrected_at: 2026-01-06\n---\n" + body
        out = check_text(ok, repo, "2026-01-05", "daily", link_checker=lambda u: True, internal_terms="load")
        self.assertEqual(out["status"], "PASS", out["errors"]); self.assertFalse(compute_low_risk(out))
        for bad in ("corrects: daily 2026 年 1 月 5 日", "corrected_at: 2026-01-06 已发布 3 篇", "note: 2026-01-06 共 3 篇"):
            t = "---\n" + bad + "\n---\n" + body
            out = check_text(t, repo, "2026-01-05", "daily", link_checker=lambda u: True, internal_terms="load")
            self.assertEqual(out["status"], "FAIL", bad)


class R14Formula(unittest.TestCase):
    def test_approx_chain(self):
        from markjin.selfcheck import verify_formula, FORMULA_RE
        ok = "算式：(334.131/323.291-1)×100≈3.353（四舍五入到小数点后三位）≈3.35%"
        self.assertEqual(FORMULA_RE.search("x" + ok + "，即").group(0), ok)
        self.assertTrue(verify_formula(ok))
        self.assertTrue(verify_formula("算式：(334.131/323.291-1)×100=3.353"))
        for bad in ("算式：(334.131/323.291-1)×100≈3.353≈3.36%", "算式：(334.131/323.291-1)×100≈3.354（四舍五入到小数点后三位）≈3.35%",
                    "算式：(334.131/323.291-1)×100=3.3≈3.35%"):
            self.assertFalse(verify_formula(FORMULA_RE.search(bad).group(0)), bad)


class R15FormulaIntegration(unittest.TestCase):
    def _run(self, formula):
        repo = make_repo()
        line = fred_line("UNRATE 差值 +0.2（由原始数据计算；算式：" + formula + "）")
        return check_text("# 日报 2026-01-05\n" + line + "\n", repo, "2026-01-05", "daily",
                          link_checker=lambda u: True, internal_terms="load")

    def test_last_value_verified_after_normalization(self):
        bad = self._run("4.2-4.0≈0.2（四舍五入到小数点后一位）≈9.99%")
        self.assertEqual(bad["status"], "FAIL"); self.assertFalse(bad["low_risk"])
        self.assertIn("E-FORMULA-MISMATCH", bad["error_codes"])
        bad2 = self._run("4.2-4.0=0.2 ≈ 0.3")
        self.assertIn("E-FORMULA-MISMATCH", bad2["error_codes"])
        ok = self._run("4.2-4.0≈0.20（四舍五入到小数点后二位）≈0.2")
        self.assertNotIn("E-FORMULA-MISMATCH", ok["error_codes"], ok["errors"])


class FinalR3SelfLink(T):
    """整体验收 r3 HIGH：本组织 GitHub 说明链接不能解除无来源检查。"""
    def test_self_link_does_not_source_numbers(self):
        from helpers import quote_line
        for extra in ("模型准确率达到95%。详见 https://github.com/markjin-lab/markjin-data",
                      "据称模型更好，详见 https://github.com/markjin-lab/markjin-data/blob/main/README.md",
                      "- 模型准确率达到95% https://github.com/markjin-lab/markjin-data"):
            r = run(TITLE + quote_line() + "\n" + extra + "\n")
            self.assertEqual(r["status"], "FAIL", extra); self.assertIs(r["low_risk"], False)
            self.assertIn("E-REPLAY-001", r["error_codes"], extra)

    def test_pointer_line_still_allowed(self):
        from helpers import quote_line
        r = run(TITLE + quote_line() + "\n详见 https://github.com/markjin-lab/markjin-data\n")
        self.assertNotIn("E-REPLAY-001", r["error_codes"])


class FinalR5Formula(T):
    """整体验收 r5 HIGH：算式字段里 FORMULA_RE 消费之后剩下的后缀（x≈9.99 等）不得放过。"""
    SRC = f" — `raw/{DATE}/fred/UNRATE.json` · https://fred.stlouisfed.org/series/UNRATE"

    def test_unconsumed_suffix_rejected(self):
        for f in ("4.2-4.0=0.2x≈9.99", "4.2-4.0=0.2 x≈9.99", "4.2-4.0=0.2abc", "4.2-4.0=0.2 9.99",
                  "4.2-4.0=0.2*50", "4.2-4.0=0.2_≈9.99", "4.2-4.0=0.2%≈9.99"):
            r = run(TITLE + f"- UNRATE 差值 +0.2（由原始数据计算；算式：{f}）" + self.SRC)
            self.assertEqual(r["status"], "FAIL", f); self.assertIs(r["low_risk"], False)
            self.assertIn("E-FORMULA-MISMATCH", r["error_codes"], f)

    def test_suffix_before_separator_ok(self):
        for f in ("4.2-4.0=0.2", "4.2-4.0=0.2 ", "(4.2/4.0-1)×100=5%"):
            r = run(TITLE + f"- UNRATE 差值 +0.2（由原始数据计算；算式：{f}）" + self.SRC)
            self.assertNotIn("E-FORMULA-MISMATCH", r["error_codes"], (f, r["errors"]))
        r = run(TITLE + "- UNRATE 差值 +0.2（由原始数据计算；算式：4.2-4.0=0.2；来源见下）" + self.SRC)
        self.assertNotIn("E-FORMULA-MISMATCH", r["error_codes"], r["errors"])

    def test_suffix_helper(self):
        from markjin.selfcheck import formula_suffix_bad
        self.assertFalse(formula_suffix_bad(""))
        self.assertFalse(formula_suffix_bad("）— `raw/x`"))
        self.assertFalse(formula_suffix_bad(" ；后文"))
        self.assertTrue(formula_suffix_bad("x≈9.99）"))
        self.assertTrue(formula_suffix_bad(" 9.99"))


class FinalR5XOnly(T):
    """协调方 r6 决定：日报断言只有 X 来源 → 硬拦；有可重新核验来源的不拦；无断言日报只标记。"""
    def test_x_only_assertion_blocked(self):
        r = run(TITLE + x_line())
        self.expect(r, "FAIL", False, "E-X-ONLY")
        r = run(TITLE + quote_line("release 2.0", raw="x/01.json", url=f"https://x.com/i/status/{XPOST_ID}"))
        self.expect(r, "FAIL", False, "E-X-ONLY")

    def test_x_plus_replayable_not_blocked(self):
        # #32（迁移自旧库 #51）：非 X 来源（arXiv）不含 2.0，不能解除 X-only → 硬拦
        line = (f"- 发布 2.0 版。 — `raw/{DATE}/x/01.json` · https://x.com/i/status/{XPOST_ID}"
                f" · `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1")
        r = run(TITLE + line)
        self.assertIn("E-X-ONLY", r["error_codes"], r["errors"])
        # 非 X 来源经原文支持位置核对确实支撑 → 不拦
        line = (f"- 模型在 MMLU 上达到 90% 准确率。 — `raw/{DATE}/x/01.json` · https://x.com/i/status/{XPOST_ID}"
                f" ; `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1 〔原文：{ARXIV_LOC}〕")
        r = run(TITLE + line)
        self.assertNotIn("E-X-ONLY", r["error_codes"], r["errors"]); self.assertEqual(r["status"], "PASS", r["errors"])

    def test_no_assertion_only_flagged(self):
        self.expect(run(TITLE), "PASS", False, "R-NO-ASSERTION")

    def test_signal_card_not_hard_blocked(self):
        r = run(x_line(), card_type="signal")
        self.assertNotIn("E-X-ONLY", r["error_codes"]); self.assertIn("R-X-ONLY", r["error_codes"])


class FinalR6XOnlyAllEntries(T):
    """整体验收 r6 BLOCKER 2：所有取来源的入口都经过同一个 X-only 判定。"""
    XSRC = f"`raw/{DATE}/x/01.json` · https://x.com/i/status/{XPOST_ID}"

    def test_paragraph_x_only_blocked(self):
        r = run(TITLE + quote_line() + f"\n发布 2.0 版。见 {self.XSRC}\n")
        self.expect(r, "FAIL", False, "E-X-ONLY")

    def test_heading_and_comment_x_only_blocked(self):
        for extra in (f"## 发布 2.0 版 {self.XSRC}\n", f"<!-- 发布 2.0 版 {self.XSRC} -->\n"):
            r = run(TITLE + quote_line() + "\n" + extra)
            self.assertIn("E-X-ONLY", r["error_codes"], extra); self.assertEqual(r["status"], "FAIL", extra)

    def test_paragraph_mixed_sources_not_blocked(self):
        # #32：段落里 X + 不支撑 2.0 的 arXiv → 仍判 E-X-ONLY；arXiv 实际含断言数字 → 不拦
        r = run(TITLE + quote_line() + f"\n发布 2.0 版。见 {self.XSRC} 与 `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1\n")
        self.assertIn("E-X-ONLY", r["error_codes"], r["errors"])
        # #32 r2：段落里非 X 来源没写支持位置 → 不再算支撑（MISSING + E-X-ONLY）；写了并核对通过 → 不拦
        r = run(TITLE + quote_line() + f"\n模型达到 90%。见 {self.XSRC} 与 `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1\n")
        self.assertIn("E-X-ONLY", r["error_codes"], r["errors"]); self.assertIn("E-SUPPORT-LOCATOR-MISSING", r["error_codes"])
        r = run(TITLE + quote_line() + f"\n模型达到 90%。见 {self.XSRC} 与 `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1 〔原文：{ARXIV_LOC}〕\n")
        self.assertNotIn("E-X-ONLY", r["error_codes"], r["errors"]); self.assertEqual(r["status"], "PASS", r["errors"])

    def test_pure_source_line_only_flagged(self):
        r = run(TITLE + quote_line() + f"\n来源：{self.XSRC}\n")
        self.assertNotIn("E-X-ONLY", r["error_codes"]); self.assertIn("R-X-ONLY", r["error_codes"])

    def test_signal_paragraph_not_hard_blocked(self):
        r = run(f"发布 2.0 版。见 {self.XSRC}\n", card_type="signal")
        self.assertNotIn("E-X-ONLY", r["error_codes"])

    def test_every_source_entry_calls_x_flags(self):
        # 源码层面锁定：每个 check_pair 调用所在函数/分支之后都有 _x_flags（err 为必填参数）
        import inspect, markjin.selfcheck as S
        sig = inspect.signature(S._x_flags)
        for k in ("err", "line", "card_type"):
            self.assertIs(sig.parameters[k].default, inspect.Parameter.empty, k)
        src = inspect.getsource(S)
        self.assertEqual(src.count("ctx.check_pair("), 5)   # 直引、来源行、结构化断言、段落/标题/注释、非结构化行
        self.assertEqual(src.count("_x_flags(") - 1, 5)       # 5 个调用点（去掉定义行），与 5 个取来源入口一一对应


class FinalR7Medical(T):
    """整体验收 r7 BLOCKER 2：医疗类从严。词表补常见简称与英文；front matter 分类标记兜底。"""

    def test_abbrev_and_english_terms_flag_medical(self):
        for line in ("TCM is used in this protocol.", "Herbal formulas were compared.", "研究比较了针灸与方剂。",
                     "Qigong practice was observed.", "研究涉及中成药。"):
            r = run(TITLE + quote_line() + "\n" + line + "\n")
            self.assertTrue(r["flags"]["medical"], line); self.assertIn("R-MEDICAL", r["error_codes"], line)

    def test_ascii_terms_use_word_boundaries(self):
        for line in ("The team at CMU released it.", "Herbst et al. released it."):
            r = run(TITLE + quote_line() + "\n" + line + "\n")
            self.assertFalse(r["flags"]["medical"], line)

    def test_front_matter_markers_flag_medical(self):
        for fm in ("categories: [健康]", "categories:\n  - Health", "tags: [ai, 中医]", "section: medical",
                   "type: TCM", "topics: wellness"):
            r = run("---\n" + fm + "\n---\n" + TITLE + quote_line())
            self.assertTrue(r["flags"]["medical"], fm); self.assertIn("R-MEDICAL", r["error_codes"], fm)

    def test_front_matter_non_category_keys_ignored(self):
        r = run("---\ntitle: health of the codebase\ntags: [ai]\n---\n" + TITLE + quote_line())
        self.assertFalse(r["flags"]["medical"])


class FinalR7Fred(T):
    """整体验收 r7 MEDIUM 2：FRED 自报了非字符串系列 ID → E-REPLAY-004，不当成未自报。"""

    def test_invalid_self_reported_ids_rejected(self):
        from helpers import make_repo, FILES
        for body in ('{"series_id": 123, "observations": []}', '{"series_id": "", "observations": []}',
                     '{"meta": {"series_id": null}, "observations": []}', '{"seriess": [{"id": 5}], "observations": []}',
                     '{"seriess": "UNRATE", "observations": []}', '{"seriess": [1], "observations": []}'):
            f = dict(FILES); f["fred/UNRATE.json"] = body
            r = run(TITLE + fred_line(), repo=make_repo(f))
            self.assertIn("E-REPLAY-004", r["error_codes"], body); self.assertEqual(r["status"], "FAIL", body)

    def test_missing_id_still_binds_by_filename(self):
        from helpers import make_repo, FILES
        f = dict(FILES); f["fred/UNRATE.json"] = FILES["fred/UNRATE.json"]
        self.assertNotIn("E-REPLAY-004", run(TITLE + fred_line(), repo=make_repo(f))["error_codes"])

    def test_low_risk_doc_matches_code(self):
        import markjin.selfcheck as S
        self.assertEqual(S.ANNOTATION_CODES, ())
        self.assertNotIn("除纯标注", S.__doc__); self.assertNotIn("只允许纯标注", S.compute_low_risk.__doc__)


class FinalR8(T):
    """整体验收 r8：front matter 按 yaml.safe_load 解析结果判分类，锚点/别名/合并键 fail-closed；英文仓位句须同句有资产词。"""

    def test_alias_anchor_merge_fail_closed(self):
        for fm in ("note: &topic Health\ncategories: *topic", "base: &b {tags: [ai]}\nmeta:\n  <<: *b",
                   "x: &a ai\ncategories: [*a]", "categories: !!str &c ai"):
            r = run("---\n" + fm + "\n---\n" + TITLE + quote_line())
            self.assertIn("E-SELFCHECK-FM-ALIAS", r["error_codes"], fm); self.assertEqual(r["status"], "FAIL", fm)
            self.assertTrue(r["flags"]["medical"], fm)

    def test_unparseable_front_matter_fail_closed(self):
        r = run("---\ncategories: [Health\n---\n" + TITLE + quote_line())
        self.assertIn("E-SELFCHECK-FM-ALIAS", r["error_codes"]); self.assertTrue(r["flags"]["medical"])

    def test_parsed_values_used(self):
        for fm in ('categories: "Health"', "categories: {main: 中医}", "Tags:\n  - x\n  - [TCM]", "categories: \"he\\u0061lth\""):
            r = run("---\n" + fm + "\n---\n" + TITLE + quote_line())
            self.assertTrue(r["flags"]["medical"], fm); self.assertNotIn("E-SELFCHECK-FM-ALIAS", r["error_codes"], fm)
        r = run("---\ntitle: health\ncategories: [ai]\n---\n" + TITLE + quote_line())
        self.assertFalse(r["flags"]["medical"])

    def test_fm_categories_is_yaml_based(self):
        import inspect, markjin.selfcheck as S
        self.assertIn("safe_load", inspect.getsource(S.fm_categories))
        self.assertFalse(hasattr(S, "fm_medical"))

    def test_technical_allocation_not_position(self):
        import markjin.selfcheck as S
        for t in ("Memory allocation is 30%.", "The attention weight is 0.3%.", "GPU exposure at 80% utilization.",
                  "Memory allocation is 30%. Gold was not studied."):
            self.assertFalse(S.en_alloc_position(t), t)
            r = run(TITLE + quote_line() + "\n" + t + "\n")
            self.assertNotIn("E-BLOCK-INVEST", r["error_codes"], t)

    def test_asset_allocation_still_position(self):
        import markjin.selfcheck as S
        for t in ("Equity allocation is 30%.", "The portfolio weight is 40%.", "Gold exposure at 10%.", "现金 allocation is 20%."):
            self.assertTrue(S.en_alloc_position(t), t)
            r = run(TITLE + quote_line() + "\n" + t + "\n")
            self.assertIn("E-BLOCK-INVEST", r["error_codes"], t)


class FinalR9(T):
    """整体验收 r9 BLOCKER：front matter 用原始行（保留缩进）解析；解析出的宏观、宗教类别与正文词表取并集。"""

    def test_nested_mapping_keeps_indentation(self):
        for fm in ("categories:\n  main: Health", "categories:\n  - sub:\n      - 中医"):
            r = run("---\n" + fm + "\n---\n" + TITLE + quote_line())
            self.assertTrue(r["flags"]["medical"], fm); self.assertNotIn("E-SELFCHECK-FM-ALIAS", r["error_codes"], fm)

    def test_macro_and_religion_categories_flag(self):
        for fm, k in (("categories: [macro]", "macro"), ("categories:\n  - 宏观", "macro"), ("tags: [religion]", "religion"),
                      ("categories:\n  main: 佛学", "religion")):
            r = run("---\n" + fm + "\n---\n" + TITLE + quote_line())
            self.assertTrue(r["flags"][k], fm)

    def test_plain_daily_category_no_flags(self):
        r = run("---\ncategories: [daily]\n---\n" + TITLE + quote_line())
        self.assertFalse(r["flags"]["macro"] or r["flags"]["religion"] or r["flags"]["medical"])


class FinalR10(T):
    """整体验收 r10：分类键共用一份定义；front matter 的 macro 类别启用整篇宏观硬拦；缺 PyYAML 结构化失败。"""

    def test_shared_category_keys(self):
        from markjin import fmkeys, selfcheck
        self.assertIs(selfcheck.FM_CATEGORY_KEYS, fmkeys.FM_CATEGORY_KEYS)
        for k in ("categories", "tags", "keywords", "type", "series", "section"):
            self.assertIn(k, fmkeys.FM_CATEGORY_KEYS)

    def test_keywords_medical_and_macro(self):
        r = run("---\nkeywords: [TCM]\n---\n" + TITLE + quote_line())
        self.assertTrue(r["flags"]["medical"])
        r = run("---\nKeywords: [macro]\n---\n" + TITLE + quote_line())
        self.assertTrue(r["flags"]["macro"])

    def test_fm_macro_category_triggers_whole_doc_opinion_block(self):
        for fm in ("categories: [macro]", "keywords:\n  - 宏观"):
            r = run("---\n" + fm + "\n---\n" + TITLE + quote_line() + "\n增长前景乐观。")
            self.assertIn("E-BLOCK-MACRO-OPINION", r["error_codes"], fm)
        # 对照：没有 macro 类别时这句不会因整篇宏观而被拦
        r = run("---\ncategories: [daily]\n---\n" + TITLE + quote_line() + "\n增长前景乐观。")
        self.assertFalse(r["flags"]["macro"])

    def test_fm_macro_category_alone_is_not_an_error(self):
        r = run("---\ncategories: [macro]\n---\n" + TITLE + quote_line())
        self.assertNotIn("E-BLOCK-MACRO-OPINION", r["error_codes"]); self.assertTrue(r["flags"]["macro"])

    def test_missing_pyyaml_structured_fail(self):
        import sys
        saved = sys.modules.get("yaml")
        sys.modules["yaml"] = None          # import yaml → ImportError
        try:
            r = run("---\ncategories: [daily]\n---\n" + TITLE + quote_line())
        finally:
            if saved is None:
                sys.modules.pop("yaml", None)
            else:
                sys.modules["yaml"] = saved
        self.assertEqual(r["status"], "FAIL"); self.assertIn("E-DEP-PYYAML", r["error_codes"])
        self.assertTrue(r["flags"]["medical"])

    def test_requirements_declares_pyyaml(self):
        from pathlib import Path
        req = (Path(__file__).resolve().parent.parent / "requirements.txt").read_text()
        self.assertRegex(req, r"(?im)^PyYAML\b")


class FinalR11(T):
    """整体验收 r11：同句每个“算式：”都验算；原始 JSON（FRED、X 等）重复键一律判失败；json 入口清单。"""

    def _f(self, formula_part):
        return run(TITLE + fred_line("UNRATE 差值 +0.2（由原始数据计算；" + formula_part + "）"))

    def test_second_malformed_formula_fails(self):
        for fp in ("算式：4.2-4.0=0.2；算式：4.2-4.0=未知", "算式：4.2-4.0=0.2；算式：", "算式：4.2-4.0=0.2，算式:abc"):
            r = self._f(fp)
            self.assertEqual(r["status"], "FAIL", fp); self.assertIn("E-FORMULA-MISMATCH", r["error_codes"], fp)

    def test_second_wrong_value_fails(self):
        r = self._f("算式：4.2-4.0=0.2；算式：4.2-4.1=0.2")
        self.assertIn("E-FORMULA-MISMATCH", r["error_codes"])

    def test_two_good_formulas_pass(self):
        r = self._f("算式：4.2-4.0=0.2；算式：4.0+0.2=4.2")
        self.assertNotIn("E-FORMULA-MISMATCH", r["error_codes"], r["errors"])

    def test_fred_duplicate_series_id_fails(self):
        from helpers import make_repo, FILES
        for body in ('{"series_id":"OTHER","series_id":"UNRATE","observations":[{"value":"4.2"}]}',
                     '{"seriess":[{"id":"OTHER","id":"UNRATE"}],"observations":[]}',
                     '{"series_id":"UNRATE","value":"4.1","value":"4.2"}'):
            f = dict(FILES); f["fred/UNRATE.json"] = body
            r = run(TITLE + fred_line(), repo=make_repo(f))
            self.assertEqual(r["status"], "FAIL", body); self.assertIn("E-REPLAY-READ", r["error_codes"], body)

    def test_x_json_duplicate_key_fails(self):
        from helpers import make_repo, FILES, XPOST_ID
        f = dict(FILES); f["x/01.json"] = f'{{"id": "{XPOST_ID}", "text": "x", "text": "release 2.0"}}'
        good = run(TITLE + x_line(), repo=make_repo(FILES))
        bad = run(TITLE + x_line(), repo=make_repo(f))
        self.assertEqual(bad["status"], "FAIL"); self.assertNotEqual(set(good["error_codes"]), set(bad["error_codes"]))

    def test_lexicon_duplicate_key_fails(self):
        import tempfile, markjin.selfcheck as S
        from pathlib import Path
        p = Path(tempfile.mkdtemp()) / "lx.json"; p.write_text('{"version": 1, "version": 1}', encoding="utf-8")
        with self.assertRaises(S.LexiconError):
            S.load_lexicon(p)

    def test_strictjson(self):
        from markjin import strictjson
        with self.assertRaises(strictjson.DuplicateKeyError):
            strictjson.loads('{"a": {"b": 1, "b": 2}}')
        with self.assertRaises(ValueError):
            strictjson.loads('[{"a": 1, "a": 1}]')
        self.assertEqual(strictjson.loads('{"a": [1, {"b": 2}]}'), {"a": [1, {"b": 2}]})

    def test_no_plain_json_loads_in_selfcheck(self):
        import re, markjin.selfcheck as S
        from pathlib import Path
        src = Path(S.__file__).read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"(?<![A-Za-z_])json\.loads?\(", src), [])


class FinalR12Scope(T):
    """整体验收 r12 MEDIUM：数字支持只在被引用的条目内核对，同一 raw 里其他条目的数字不算。"""

    def test_other_entry_numbers_not_support(self):
        from helpers import make_repo, FILES, ARXIV_ID
        feed = (f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id><summary>The model reaches 90% accuracy.</summary></entry>"
                "<entry><id>http://arxiv.org/abs/2601.99999v1</id><summary>Another model reaches 95% accuracy.</summary></entry></feed>")
        f = dict(FILES); f["arxiv/cs.AI.xml"] = feed
        repo = make_repo(f)
        bad = run(TITLE + arxiv_line("模型在 MMLU 上达到 95% 准确率。"), repo=repo)
        self.assertIn("R-SUPPORT-UNVERIFIED", bad["error_codes"])
        ok = run(TITLE + arxiv_line("模型在 MMLU 上达到 90% 准确率。"), repo=repo)
        self.assertNotIn("R-SUPPORT-UNVERIFIED", ok["error_codes"])

    def test_x_other_post_numbers_not_support(self):
        from helpers import make_repo, FILES, XPOST_ID
        f = dict(FILES); f["x/01.json"] = (f'{{"data": [{{"id": "{XPOST_ID}", "text": "release 2.0"}}, '
                                           f'{{"id": "1", "text": "release 3.5"}}]}}')
        r = run(TITLE + x_line("发布 3.5 版。"), repo=make_repo(f))
        self.assertIn("R-SUPPORT-UNVERIFIED", r["error_codes"])


class FinalR13Scope(T):
    """整体验收 r13 MEDIUM：FRED 按引用的那一期观测与 vintage 核数字；其他来源入口带上断言原文。"""

    OBS = ('{"realtime_start":"2026-01-02","realtime_end":"2026-01-02","observations":['
           '{"realtime_start":"2025-12-01","realtime_end":"2026-01-02","date":"2025-11-01","value":"4.2"},'
           '{"realtime_start":"2026-01-02","realtime_end":"2026-01-02","date":"2025-12-01","value":"5.0"},'
           '{"realtime_start":"2025-12-01","realtime_end":"2026-01-01","date":"2025-12-01","value":"4.9"}]}')

    def repo(self):
        from helpers import make_repo, FILES
        f = dict(FILES); f["fred/UNRATE.json"] = self.OBS
        return make_repo(f)

    def flag(self, claim):
        return "R-SUPPORT-UNVERIFIED" in run(TITLE + fred_line(claim), repo=self.repo())["error_codes"]

    def test_fred_observation_scope(self):
        self.assertTrue(self.flag("UNRATE 2025-11 为 5.0%。"))          # 5.0 属于另一期观测
        self.assertFalse(self.flag("UNRATE 2025-11 为 4.2%。"))
        self.assertTrue(self.flag("UNRATE 为 4.2%。"))                   # 多条观测、没写日期 → 不算支持

    def test_fred_vintage_scope(self):
        self.assertFalse(self.flag("UNRATE 2025-12 为 5.0%（vintage: 2026-01-02）。"))
        self.assertTrue(self.flag("UNRATE 2025-12 为 4.9%（vintage: 2026-01-02）。"))   # 4.9 属于旧 vintage
        self.assertFalse(self.flag("UNRATE 2025-12 为 4.9%（vintage: 2025-12-15）。"))

    def test_paragraph_source_carries_claim(self):
        from helpers import ARXIV_ID
        para = f"\n模型在 MMLU 上达到 95% 准确率，见 `raw/{DATE}/arxiv/cs.AI.xml` https://arxiv.org/abs/{ARXIV_ID}v1\n"
        r = run(TITLE + para)
        self.assertIn("R-SUPPORT-UNVERIFIED", r["error_codes"], r["error_codes"])
        ok = run(TITLE + para.replace("95%", "90%"))
        self.assertNotIn("R-SUPPORT-UNVERIFIED", ok["error_codes"], ok["error_codes"])


class FinalR15LongForm(T):
    """整体验收 r15（审查 bot 定）：front matter 统一按 yaml.safe_load 解析值判断；tongyi 长文豁免日报断言句式检查，
    豁免只看 type 与路径且须一致（不一致 fail-closed）；硬拦照旧。样本为合成 fixture（不含正文）。"""

    SAMPLE = Path(__file__).resolve().parent / "fixtures" / "tongyi-sample" / "sample-a.md"
    REL = "tongyi/sample-a.md"

    def text(self):
        return self.SAMPLE.read_text(encoding="utf-8")

    def ecodes(self, r):
        return [c for c in r["error_codes"] if c.startswith("E-")]

    def test_sample_sha(self):
        import hashlib
        self.assertEqual(hashlib.sha256(self.SAMPLE.read_bytes()).hexdigest(),
                         "8b8a4b6338e6ea6c413cc1929373e859fcd45e28dbf5056068bb4bd14abf89fc")

    def test_sample_passes_as_tongyi(self):
        r = run(self.text(), rel=self.REL)
        self.assertEqual(self.ecodes(r), [], r["errors"])
        r = run(self.text(), rel="content/posts/tongyi/sample-a.md")
        self.assertEqual(self.ecodes(r), [], r["errors"])

    def test_type_path_mismatch_fails(self):
        for rel in ("daily/2026-10-11.md", None, "tongyi/x/y.md", "../tongyi/x.md"):
            r = run(self.text(), rel=rel)
            self.assertIn("E-TONGYI-MISMATCH", r["error_codes"], rel)
            self.assertIn("E-INFER-UNCLEAR", r["error_codes"], rel)          # 照常跑日报检查
        plain = self.text().replace("type: tongyi\n", "")
        r = run(plain, rel=self.REL)
        self.assertIn("E-TONGYI-MISMATCH", r["error_codes"])                  # 路径是 tongyi、type 不是

    def test_daily_claiming_tongyi_fails(self):
        t = "---\ntype: tongyi\n---\n" + TITLE + "\n这是一段没有来源的推断，市场会上涨 10%。\n"
        r = run(t, rel="daily/2026-10-11.md")
        self.assertEqual(r["status"], "FAIL"); self.assertIn("E-TONGYI-MISMATCH", r["error_codes"])

    def test_hard_blocks_still_apply(self):
        base = self.text()
        for line, code in (("建议买入沪深300ETF。", "E-BLOCK-INVEST"), ("满仓。", "E-BLOCK-INVEST")):
            r = run(base.replace("本文不含投资建议。", line + "\n\n本文不含投资建议。"), rel=self.REL)
            self.assertIn(code, r["error_codes"], line)
        from helpers import x_line
        r = run(base + "\n" + x_line() + "\n", rel=self.REL)
        self.assertIn("E-X-ONLY", r["error_codes"])

    def test_quoted_front_matter_values(self):
        for corrects, ca in (('"daily-2026-01-05-d1"', '"2026-01-06"'), ("'daily-2026-01-05-d1'", "'2026-01-06'"),
                             ("daily-2026-01-05-d1", "2026-01-06")):
            t = f"---\ncorrects: {corrects}\ncorrected_at: {ca}\n---\n" + INFER_OK
            r = run(t)
            self.assertNotIn("E-REPLAY-001", [e["code"] for e in r["errors"] if e["line"] in (2, 3)], (corrects, ca))
        t = '---\ncorrected_at: "2026-02-30"\n---\n' + INFER_OK                 # 不是真实日期 → 照常当数字
        self.assertIn("E-REPLAY-001", [e["code"] for e in run(t)["errors"] if e["line"] == 2])
        t = '---\ndate: "2026-01-05"\n---\n' + INFER_OK                         # 日期字段带引号同样放行
        self.assertNotIn("E-REPLAY-001", [e["code"] for e in run(t)["errors"] if e["line"] == 2])


    # —— r15 BLOCKER 修正：豁免只在正文句式检查；front matter、表头等位置无来源数字照常报错
    def fm_insert(self, line):
        t = self.text(); assert t.startswith("---\n")
        return "---\n" + line + "\n" + t[4:]

    def test_front_matter_number_still_fails(self):
        for line in ("score: 95", 'score: "95"', "rank: 3"):
            r = run(self.fm_insert(line), rel=self.REL)
            self.assertEqual(r["status"], "FAIL", line)
            self.assertIn("E-REPLAY-001", [e["code"] for e in r["errors"] if e["line"] == 2], line)

    FM_VARIANTS = ("score:\n  - 95", "score:\n- 95", "score: [95]", 'score: [ "x", 95 ]', "score: {a: 95}",
                   "note: |\n  得分 95", "note: >\n  得分 95", "note: |-\n  95", "score: !!int 95", 'note: "95"',
                   'note: "<!-- 95 -->"', "note: <!-- 95 -->", 'note: "-->95"', "note: |\n  <!-- 95 -->")

    def test_front_matter_any_yaml_form_never_exempt(self):
        # r16 BLOCKER：列表、flow 列表/映射、块标量等任何 front matter 写法里的无来源数字都不豁免
        for v in self.FM_VARIANTS:
            r = run(self.fm_insert(v), rel=self.REL)
            self.assertEqual(r["status"], "FAIL", v); self.assertIn("E-REPLAY-001", r["error_codes"], v)

    def test_front_matter_inference_still_fails(self):
        r = run(self.fm_insert("summary: 预计市场会回落"), rel=self.REL)
        self.assertIn("E-REPLAY-001", [e["code"] for e in r["errors"] if e["line"] == 2])

    def test_table_header_number_still_fails(self):
        t = self.text().replace("本文不含投资建议。", "| 2025 年 95 分 | 说明 |\n|---|---|\n| 甲 | 乙 |\n\n本文不含投资建议。")
        r = run(t, rel=self.REL)
        self.assertEqual(r["status"], "FAIL"); self.assertIn("E-REPLAY-001", r["error_codes"])

    def test_body_sentence_exempt_only(self):
        t = self.text().replace("本文不含投资建议。", "这一段没有来源，含数字 95。\n\n本文不含投资建议。")
        self.assertEqual(self.ecodes(run(t, rel=self.REL)), [])                              # 正文句式：豁免
        self.assertIn("E-REPLAY-001", run(t, rel="daily/2026-10-11.md")["error_codes"])         # 非 tongyi 路径：不豁免

    def test_more_hard_blocks_still_apply(self):
        base = self.text()
        cases = (("样例内部词甲。", "E-BLOCK-INTERNAL"), ("美联储议息，预计后续走势回落。", "E-BLOCK-MACRO-OPINION"),
                 ("建议卖出。", "E-BLOCK-INVEST"), ("仓位加到八成。", "E-BLOCK-INVEST"))
        for line, code in cases:
            r = run(base.replace("本文不含投资建议。", line + "\n\n本文不含投资建议。"), rel=self.REL)
            self.assertEqual(r["status"], "FAIL", line); self.assertIn(code, r["error_codes"], line)


INFER_OK = TITLE + arxiv_line()
