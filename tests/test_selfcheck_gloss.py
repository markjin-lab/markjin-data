"""selfcheck 括号句豁免（scope-r4，最小版本）：表 A 单行、表 B 行类别、表 C 不放宽回归、表 E tongyi 路径、表 D 10-19 digest。
每条用例单独成一个测试方法，便于与声明逐条对照。"""
import collections, importlib.util, subprocess, types, unittest
from pathlib import Path
from helpers import make_repo, DUMMY_INTERNAL, DATE
import markjin.selfcheck as _sc

# r3 LOW 2：括号句代码在 selfcheck.py 里（真实模块路径），这里只起短名字
g = types.SimpleNamespace(ZH_RE=_sc.GLOSS_ZH_RE, EN_RE=_sc.GLOSS_EN_RE, find_glosses=_sc.gloss_find,
                          strip_glosses=_sc.gloss_strip, has_label=_sc.gloss_has_label)

_sc.load_internal_terms = lambda: list(DUMMY_INTERNAL)
REPO = make_repo()
TITLE = f"# 日报 {DATE}\n"
ROOT = Path(__file__).resolve().parent.parent


def Z(b, pre="某事实 [2]。"):
    return f"{pre}（本站补充的通用解释：{b}。）"


def E(b, pre="A fact [2]. "):
    return f"{pre}(General explanation added by this site: {b}.)"


def exempt(line):
    gl = g.find_glosses(line)
    return bool(gl) and all(not r for *_, r in gl) and not g.has_label(g.strip_glosses(line))


def reasons(line):
    return [r for *_, r in g.find_glosses(line)]


# ---------------------------------------------------------------- 表 A-1 正例（应豁免）
POS = {
    # r2 保留
    "zh_1019_adv": Z("对抗训练一般指在训练中特意加入专门用来诱使模型出错的输入，让模型学会抵御这类输入"),
    "zh_1019_norm": Z("标准化分数一般指把不同量表或尺度上的原始分数换算到同一尺度上，便于相互比较"),
    "zh_1019_zeroshot": Z("零样本提示一般指只给模型任务说明、不给任何示例答案，就让它直接完成任务"),
    "en_1019_adv": E("adversarial training usually means deliberately adding inputs designed to make a model fail during training, so that the model learns to resist them"),
    "en_1019_norm": E("a normalized score usually means a raw score converted onto a common scale so that results from different scales can be compared"),
    "en_1019_zeroshot": E("zero-shot prompting usually means giving a model only the task instructions, with no worked examples, and asking it to perform the task directly"),
    "zh_shifen": Z("这类方法十分常用"),
    "zh_lunwenfuxian": Z("论文复现一般指按公开描述重新实现并重跑实验"),
    "zh_yangbenwenben": Z("零样本文本分类一般指不给示例就让模型给文本分类"),
    "zh_jibengongzuo": Z("注意力机制的基本工作方式是给输入的不同部分分配权重"),
    "zh_yanjiurenyuan": Z("研究人员常用基准测试来比较模型"),
    "zh_Xplatform": Z("X 平台上的帖子一般指用户公开发布的短文"),
    "zh_zhelei_fangfa": Z("这类方法一般指先训练再微调的做法"),
    "zh_zhege_ci": Z("这个词一般指训练中加入的干扰输入"),
    "en_paper_generic": E("paper reproduction usually means re-running published experiments from a paper's description"),
    "en_researchers": E("researchers often use benchmarks to compare models"),
    "en_they_model": E("they usually mean that the model is trained again on new data"),
    "en_onehot": E("one-hot encoding usually means marking a category with a single active position"),
    # r3 HIGH 1：中文数字规则的误伤正例（取舍见声明 §三-2）
    "zh_yiban": Z("微调一般指在已训练好的模型上继续训练"),
    "zh_tongyi": Z("统一接口一般指各模块使用相同的调用方式"),
    "zh_danyi": Z("单一模型一般指只用一个模型完成任务"),
    "zh_zhiyi": Z("过拟合是常见问题之一"),
    "zh_yizhong": Z("微调一般指在已训练好的模型上用一种新数据继续训练"),
    "zh_yige": Z("集成学习一般指把多个模型的输出合成一个结果"),
    "zh_yizhi": Z("对齐一般指让模型行为与人的意图保持一致"),
    "zh_yiding": Z("鲁棒性一般指模型在一定扰动下仍能正常工作"),
    "zh_yixie": Z("数据增强一般指对已有样本做一些变换来扩充数据"),
    "zh_jinyibu": Z("微调一般指在已有模型上进一步训练"),
    "zh_weiyi": Z("主键一般指能唯一标识一条记录的字段"),
    "zh_tongyi2": Z("归一化一般指把数值换算到同一范围"),
    "zh_yiqi": Z("多任务学习一般指把几个相关任务放在一起训练"),
    "zh_yizhi2": Z("收敛一般指训练损失一直下降并趋于稳定"),
    "zh_yiyi": Z("映射一般指输入与输出之间一一对应的关系"),
    "zh_wanyi": Z("备份一般指为防万一而另存的副本"),
    "zh_yidian_adjacent": Z("有一点一般指数量很少"),          # “一点”后紧接“一般”，不因拼接误拦
    "en_manifold": E("a manifold usually means a smooth surface in a higher space"),
}

# ---------------------------------------------------------------- 表 A-2 反例（应不豁免，标签残留 → E-GLOSS-FORMAT）
NEG = {
    # r3 HIGH 1：中文裸数词、序数
    "zh_yibai": (Z("批量大小一般指一百条左右的样本"), "number-word"),
    "zh_jiushi": (Z("准确率一般指九十上下的分数"), "number-word"),
    "zh_yiyi_num": (Z("参数规模一般指一亿量级"), "number-word"),
    "zh_liangqian": (Z("词表一般有两千词"), "number-word"),
    "zh_qianyi": (Z("大模型一般指千亿参数的模型"), "number-word"),
    "zh_lingdianwu": (Z("丢弃率一般取零点五"), "number-word"),
    "zh_sanshiyu": (Z("基准一般包含三十余项任务"), "number-word"),
    "zh_shiyuci": (Z("训练一般重复十余次"), "number-word"),
    "zh_shangwan": (Z("数据集一般有上万条样本"), "number-word"),
    "zh_shuyiqianji": (Z("参数一般数以千计"), "number-word"),
    "zh_yinian": (Z("预训练一般持续一年"), "number-word"),
    "zh_disan": (Z("评测一般排在第三"), "number-word"),
    "zh_diyi": (Z("评测一般排在第一"), "number-word"),
    "zh_liangcheng": (Z("这类输入一般占两成"), "number-word"),
    "zh_baifenzhi": (Z("一般指误差低于百分之二十"), "number-word"),
    "zh_sanbei": (Z("一般比原来快三倍"), "number-word"),
    "zh_liangzhong": (Z("一般分为两种做法"), "number-word"),
    "zh_yiban_half": (Z("一般只有一半样本被标注"), "number-word"),
    "zh_yici": (Z("推理一般只需一次前向计算"), "number-word"),
    "zh_shiyizhong": (Z("一般分为十一种"), "number-word"),
    "zh_sanshiyiban": (Z("参数一般三十一般不超过"), "number-word"),
    "en_tenfold": (E("it usually means a tenfold gain"), "number-word"),
    "en_first_layer": (E("it usually means the first layer"), "number-word"),
    # 百分号
    "pct_ascii": (Z("一般指误差低于 %"), "percent"),
    "pct_fullwidth": (Z("一般指误差低于％"), "percent"),
    "pct_entity": (Z("一般指误差低于&percnt;"), "percent"),
    "pct_small": (Z("一般指误差低于﹪"), "percent"),
    "pct_en_entity": (E("it usually means an error below &percnt;"), "percent"),
    # 英文数词、序数、罗马数字（大小写）
    "en_zero": (E("it usually means zero errors"), "number-word"),
    "en_one": (E("it usually means one model"), "number-word"),
    "en_one_another": (E("calibration usually means making scores comparable with one another"), "number-word"),
    "en_ten": (E("it usually means ten layers"), "number-word"),
    "en_billion_upper": (E("it usually means a Billion parameters"), "number-word"),
    "en_first": (E("it usually ranks first"), "number-word"),
    "en_third_upper": (E("it usually ranks Third"), "number-word"),
    "en_twentypct": (E("it usually means a twenty percent drop"), "number-word"),
    "en_half": (E("it usually means about half of the inputs"), "number-word"),
    "en_twice": (E("it usually runs twice as fast"), "number-word"),
    "en_threefold": (E("it usually means a threefold gain"), "number-word"),
    "en_type_iii": (E("it usually means a type iii error"), "roman"),
    "en_phase_II": (E("it usually means a Phase II trial"), "roman"),
    "en_bare_iv": (E("it usually means grade iv"), "roman"),
    "en_level_III": (E("it usually means a level III risk"), "roman"),
    "zh_roman_uni": (Z("一般指Ⅲ级风险"), "roman"),
    "zh_roman_ascii": (Z("一般指 III 级风险"), "roman"),
    "zh_roman_lower": (Z("一般指 iii 期试验"), "roman"),
    "zh_fullwidth_digit": (Z("一般指１０个样本"), "digit"),
    "zh_digit": (Z("一般指约 0"), "digit"),
    # r3 HIGH 2：指向本篇方法 / 模型 / 工作
    "zh_benmoxing": (Z("本模型一般指换算后的分数"), "paper"),
    "zh_benfangfa": (Z("本方法一般指先训练再微调"), "paper"),
    "zh_gaifangfa": (Z("该方法一般指先训练再微调"), "paper"),
    "zh_gaimoxing": (Z("该模型一般指一种语言模型"), "paper"),
    "zh_suotifangfa": (Z("所提方法一般指先训练再微调"), "paper"),
    "zh_suotichude": (Z("所提出的框架一般指先训练再微调"), "paper"),
    "zh_benyanjiu": (Z("本研究中的分数一般指换算后的分数"), "paper"),
    "zh_bengongzuo": (Z("本工作中的分数一般指换算后的分数"), "paper"),
    "zh_women": (Z("我们说的分数一般指换算后的分数"), "paper"),
    "zh_zheyifangfa": (Z("这一方法一般指先训练再微调"), "paper"),
    "zh_cifangfa": (Z("此方法一般指先训练再微调"), "paper"),
    "en_proposed_method": (E("the proposed method usually means training twice"), "paper"),
    "en_proposed_model": (E("the proposed model usually means a language model"), "paper"),
    "en_proposed_approach": (E("the proposed approach usually means fine-tuning"), "paper"),
    "en_this_method": (E("this method usually means fine-tuning"), "paper"),
    "en_this_model": (E("this model usually means a language model"), "paper"),
    "en_this_approach": (E("this approach usually means fine-tuning"), "paper"),
    "en_this_work": (E("in this work it usually means a converted score"), "paper"),
    "en_present_study": (E("in the present study it usually means a converted score"), "paper"),
    "en_present_work": (E("in the present work it usually means a converted score"), "paper"),
    "en_our_method": (E("our method usually means fine-tuning"), "paper"),
    # 定论② 原有（r2 保留）
    "zh_gaiwen": (Z("该文所说的分数一般指换算后的分数"), "paper"),
    "zh_wenzhong": (Z("文中的分数一般指换算后的分数"), "paper"),
    "zh_benwen": (Z("本文的分数一般指换算后的分数"), "paper"),
    "zh_gailunwen": (Z("该论文所说的分数一般指换算后的分数"), "paper"),
    "zh_lunwenzhong": (Z("论文中的分数一般指换算后的分数"), "paper"),
    "zh_zhaiyao": (Z("摘要所说的分数一般指换算后的分数"), "paper"),
    "zh_zw_space": (Z("本\u200b文的分数一般指换算后的分数"), "paper"),
    "en_authors_bare": (E("authors usually mean a converted score"), "paper"),
    "en_researchers_the": (E("the researchers usually mean a converted score"), "paper"),
    "en_preprint": (E("in this preprint it usually means a converted score"), "paper"),
    "en_thepaper": (E("in the paper it usually means a converted score"), "paper"),
    "en_abstract": (E("the abstract uses it to mean a converted score"), "paper"),
    # Grok Bot 10:13「作者」：单独出现、非白名单复合词照拦
    "zh_author_bare": (Z("作者所说的分数一般指换算后的分数"), "paper"),
    "zh_author_yuan": (Z("原作者所说的分数一般指换算后的分数"), "paper"),
    "zh_author_men": (Z("作者们一般用它指换算后的分数"), "paper"),
    "zh_author_zhuzuozhe": (Z("著作者一般指写书的人"), "paper"),
    "zh_author_wl_not_mask_bengongzuo": (Z("本工作者一般指参与本项目的人"), "paper"),
    # Grok Bot 15:21 最小版本：任何「作者」都拦，没有白名单
    "zh_author_xiezuozhe": (Z("写作者一般指以写作为业的人"), "paper"),
    "zh_author_gongzuozhe": (Z("医疗工作者一般指在医疗机构从事诊疗与护理的人员"), "paper"),
    "zh_author_chuangzuozhe": (Z("内容创作者一般指在平台上发布原创内容的人"), "paper"),
    "zh_author_hezuozhe": (Z("开源合作者一般指共同维护开源项目的人"), "paper"),
    "zh_author_xiezuozhe2": (Z("协作者一般指在同一项目中分工配合的人"), "paper"),
    "zh_author_yuanchuangzuozhe": (Z("原创作者一般指首先创作作品的人"), "paper"),
    "zh_author_after_de": (Z("医疗行业的工作者一般指医务人员"), "paper"),
    # r3 HIGH 4：“作”“者”之间插 VS16、组合符
    "zh_author_vs16": (Z("作\ufe0f者所说的分数一般指换算后的分数"), "paper"),
    "zh_author_combining": (Z("作\u0301者所说的分数一般指换算后的分数"), "paper"),
    "zh_author_vs16_gongzuozhe": (Z("工作\ufe0f者一般指上班的人"), "paper"),
    # 「文本摘要」照拦（定论②）
    "zh_wenbenzhaiyao": (Z("文本摘要一般指把长文压缩成短文"), "paper"),
    # r2 HIGH 3（保留）：解码、归一化后复验
    "zh_halfdot": (Z("一般指把分数换算到同一尺度上. 这样便于比较"), "multi-sentence"),
    "zh_fwdot": (Z("一般指把分数换算到同一尺度上．这样便于比较"), "multi-sentence"),
    "zh_period_ent": (Z("一般指换算&period;便于比较"), "multi-sentence"),
    "zh_paren_ent": (Z("一般指换算&lpar;见下&rpar;"), "bracket"),
    "zh_cite_ent": (Z("一般指换算&#91;3&#93;"), "bracket"),
    "en_cjkdot": (E("it usually means conversion。It helps comparison"), "multi-sentence"),
    "en_period_ent": (E("it usually means conversion&period; It helps comparison"), "multi-sentence"),
    "en_paren_ent": (E("it usually means conversion &lpar;see below&rpar;"), "bracket"),
    "en_nested_label": (E("it usually means &#26412;&#31449;&#34917;&#20805;&#30340;&#36890;&#29992;&#35299;&#37322; text"), "nested-label"),
    # r3 HIGH 3：逐个引注核对紧邻前文（定论③）
    "pos_punct_only": (Z("一般指换算后的分数", pre="某事实。[2]。"), "position"),
    "pos_punct_only_en": (E("it usually means a converted score", pre="A fact. [2]. "), "position"),
    "pos_list_punct": (Z("一般指换算后的分数", pre="- 。[2]。"), "position"),
    "pos_listonly": ("- [2]。（本站补充的通用解释：一般指换算后的分数。）", "position"),
    "pos_cite_after_cite": (Z("一般指换算后的分数", pre="某事实 [2]。[3]。"), "position"),
    # r3 HIGH 3：单独的下划线、只有数字不算事实句片段
    "pos_underscore": (Z("一般指换算后的分数", pre="_ [2]。"), "position"),
    "pos_underscore_en": (E("it usually means a converted score", pre="_ [2]. "), "position"),
    "pos_number_only": (Z("一般指换算后的分数", pre="- 3 [2]。"), "position"),
}

# 第二处括号句：前一处括号句不算事实句（只断言第二处）
SECOND = {
    "zh_second_after_gloss": ("某事实 [2]。（本站补充的通用解释：甲一般指乙。）[3]。（本站补充的通用解释：丙一般指丁。）", [[], ["position"]]),
    "en_second_after_gloss": ("A fact [2]. (General explanation added by this site: x usually means y.) [3]. (General explanation added by this site: z usually means w.)", [[], ["position"]]),
    "zh_second_after_punct": ("。[2]。（本站补充的通用解释：甲一般指乙。）", [["position"]]),
}
# 一行两处都合规（10-19 第 44 行写法）与连续引注
BOTH_OK = {
    "zh_two_facts": "事实甲 [2]。（本站补充的通用解释：甲一般指乙。）事实乙 [3]。（本站补充的通用解释：丙一般指丁。）",
    "en_two_facts": "Fact A [2]. (General explanation added by this site: x usually means y.) Fact B [3]. (General explanation added by this site: z usually means w.)",
    "zh_multi_cite": "某事实 [1][2]。（本站补充的通用解释：甲一般指乙。）",
}
# 正则本身不匹配（标签残留）/ 改写标签（不残留，交审稿人）
NOMATCH = {
    "cite_inside": Z("一般指换算 [3]"),
    "linestart": "（本站补充的通用解释：一般指换算后的分数。）",
    "nocite": "某事实。（本站补充的通用解释：一般指换算后的分数。）",
    "halfwidth": "某事实 [2]。(本站补充的通用解释:一般指换算后的分数。)",
    "entity_paren": "某事实 [2]。&#xff08;本站补充的通用解释：一般指换算后的分数。&#xff09;",
    "zw_in_label": "某事实 [2]。（本站补充的\u200b通用解释：一般指换算后的分数。）",
    "en_case": "A fact [2]. (General Explanation added by this site: it usually means a score.)",
    "en_nospace": "A fact [2]. (General explanation added by this site:it usually means a score.)",
    "en_url": E("see https&colon;//example.org"),        # body 字符类排除 “.”，链接使正则不匹配
    "adjacent_no_cite": "某事实 [2]。（本站补充的通用解释：甲一般指乙。）（本站补充的通用解释：丙一般指丁。）",
}


class TableA(unittest.TestCase):
    def test_regexes_compile(self):
        self.assertTrue(g.ZH_RE.pattern and g.EN_RE.pattern)

    def test_no_author_whitelist(self):               # 15:21 最小版本：不设白名单
        self.assertFalse(hasattr(_sc, "GLOSS_AUTHOR_WHITELIST"))


def _mk_pos(line):
    def t(self):
        self.assertTrue(exempt(line), reasons(line))
    return t


def _mk_neg(line, why):
    def t(self):
        rs = reasons(line)
        self.assertFalse(exempt(line), rs)
        self.assertTrue(g.has_label(g.strip_glosses(line)))
        self.assertTrue(any(why in r for r in rs), rs)
    return t


def _mk_second(line, exp):
    def t(self):
        self.assertEqual(reasons(line), exp)
        self.assertTrue(g.has_label(g.strip_glosses(line)))
    return t


def _mk_both(line):
    def t(self):
        rs = reasons(line)
        self.assertTrue(len(rs) >= 1 and all(not r for r in rs), rs)
        self.assertFalse(g.has_label(g.strip_glosses(line)))
    return t


def _mk_nomatch(line):
    def t(self):
        self.assertFalse(exempt(line))
        self.assertTrue(g.has_label(g.strip_glosses(line)))
    return t


for k, v in POS.items():
    setattr(TableA, f"test_pos_{k}", _mk_pos(v))
for k, (v, why) in NEG.items():
    setattr(TableA, f"test_neg_{k}", _mk_neg(v, why))
for k, (v, exp) in SECOND.items():
    setattr(TableA, f"test_second_{k}", _mk_second(v, exp))
for k, v in BOTH_OK.items():
    setattr(TableA, f"test_both_ok_{k}", _mk_both(v))
for k, v in NOMATCH.items():
    setattr(TableA, f"test_nomatch_{k}", _mk_nomatch(v))


def test_rewritten_label_not_recognized():
    line = "某事实 [2]。（本站补充解释：一般指换算后的分数。）"
    assert g.find_glosses(line) == [] and not g.has_label(line)   # 第二节第 6 条：交审稿人


# ---------------------------------------------------------------- 表 B / C：check_text（普通日报）
def run(text, **kw):
    kw.setdefault("link_checker", lambda u: True)
    r = _sc.check_text(text, REPO, DATE, "daily", **kw)
    c = collections.Counter(e["code"] for e in r["errors"])
    return r["status"], dict(sorted(c.items())), r


GZ = "（本站补充的通用解释：对抗训练一般指在训练中特意加入诱使模型出错的输入。）"
GE = "(General explanation added by this site: adversarial training usually means adding inputs designed to make a model fail.)"
F = "CATCH 是一种训练方法 [2]。"
U1 = {"E-INFER-UNCLEAR": 1, "E-REPLAY-001": 1}
TABLE_B = {
    "para_ok": (TITLE + F + GZ + "\n", "FAIL", U1),
    "para_no_gloss": (TITLE + F + "\n", "FAIL", U1),
    "para_ok_en": (TITLE + "CATCH is a training method [2]. " + GE + "\n", "FAIL", U1),
    "para_modal_in_gloss": (TITLE + F + "（本站补充的通用解释：对抗训练可能指在训练中加入诱使模型出错的输入。）\n", "FAIL", U1),
    "list_ok": (TITLE + "- " + F + GZ + "\n", "FAIL", U1),
    "para_bad_position": (TITLE + "CATCH 是一种训练方法。" + GZ + "\n", "FAIL", {"E-GLOSS-FORMAT": 1, "E-INFER-UNCLEAR": 1}),
    "para_alone": (TITLE + GZ + "\n", "FAIL", {"E-GLOSS-FORMAT": 1, "E-INFER-UNCLEAR": 1}),
    "para_alone_en": (TITLE + GE + "\n", "FAIL", {"E-GLOSS-FORMAT": 1, "E-INFER-UNCLEAR": 1}),
    "para_rewritten": (TITLE + F + "（本站补充解释：对抗训练一般指在训练中加入诱使模型出错的输入。）\n", "FAIL", U1),
    "para_split_label": (TITLE + F + "（本站补充的\n通用解释：对抗训练一般指加入诱使模型出错的输入。）\n", "FAIL",
                         {"E-GLOSS-FORMAT": 1, "E-INFER-UNCLEAR": 2, "E-REPLAY-001": 1}),
    "heading": (TITLE + "## 方法 [2]。" + GZ + "\n", "FAIL", {"E-GLOSS-FORMAT": 1}),
    "front_matter": ("---\nlist_summary: " + F + GZ + "\n---\n" + TITLE, "FAIL", {"E-GLOSS-FORMAT": 1, "E-REPLAY-001": 1}),
    "html_comment": (TITLE + "<!-- " + F + GZ + " -->\n", "FAIL", {"E-GLOSS-FORMAT": 1}),
    "source_line": (TITLE + "来源：" + GZ + "\n", "FAIL", {"E-GLOSS-FORMAT": 1, "E-INFER-UNCLEAR": 1}),
    "quote_block": (TITLE + "> " + F + GZ + "\n", "FAIL", {"E-GLOSS-FORMAT": 1, **U1}),
    "table_row": (TITLE + "| 列 |\n|---|\n| " + F + GZ + " |\n", "FAIL", {"E-GLOSS-FORMAT": 1, **U1}),
    "correction_paraphrase": (TITLE + "## 更正\n\n**2026-10-19**：术语处补充了本站通用解释，已标明。\n", "FAIL", U1),
    "correction_verbatim": (TITLE + "## 更正\n\n**2026-10-19**：术语处补充了“本站补充的通用解释”括号句。\n", "FAIL", {"E-GLOSS-FORMAT": 1, **U1}),
    "code_fence_ok": (TITLE + "```\n" + F + GZ + "\n```\n", "FAIL", {"E-INFER-UNCLEAR": 3, "E-REPLAY-001": 1}),
    "code_fence_bad": (TITLE + "```\n" + F + "（本站补充的通用解释：两成。）\n```\n", "FAIL", {"E-GLOSS-FORMAT": 1, "E-INFER-UNCLEAR": 3, "E-REPLAY-001": 1}),
    # r3 HIGH 3：整篇层面
    "para_punct_only": (TITLE + "CATCH 是一种训练方法。[2]。" + GZ + "\n", "FAIL", {"E-GLOSS-FORMAT": 1, **U1}),
    "para_second_gloss": (TITLE + F + GZ + "[3]。（本站补充的通用解释：微调一般指继续训练。）\n", "FAIL", {"E-GLOSS-FORMAT": 1, **U1}),
}
TABLE_C = {
    "internal": (TITLE + F + "（本站补充的通用解释：这里说的" + DUMMY_INTERNAL[0] + "一般指一类输入。）\n", {"E-BLOCK-INTERNAL": 1, **U1}, []),
    "invest": (TITLE + F + "（本站补充的通用解释：买入一般指交易中取得资产。）\n", {"E-BLOCK-INVEST": 1, **U1}, []),
    "macro": (TITLE + "通胀相关的训练方法 [2]。（本站补充的通用解释：前景乐观一般指人们预期情况好转。）\n", {"E-BLOCK-MACRO-OPINION": 1, **U1}, ["R-MACRO"]),
    "medical": (TITLE + F + "（本站补充的通用解释：临床一般指直接面向病人的环节。）\n", U1, ["R-MEDICAL"]),
    "stock": (TITLE + F + "（本站补充的通用解释：股市一般指买卖股份的市场。）\n", U1, ["R-MACRO", "R-STOCK"]),
    "religion": (TITLE + F + "（本站补充的通用解释：佛教一般指一种宗教传统。）\n", U1, ["R-RELIGION"]),
    "cross_internal": (TITLE + F + GZ + DUMMY_INTERNAL[0][:3] + "\n" + DUMMY_INTERNAL[0][3:] + "相关说明 [2]。\n",
                       {"E-BLOCK-INTERNAL": 1, "E-INFER-UNCLEAR": 2, "E-REPLAY-001": 2}, []),
    "cross_invest": (TITLE + F + GZ + "建议买\n入相关资产 [2]。\n", {"E-BLOCK-INVEST": 1, "E-INFER-UNCLEAR": 2, "E-REPLAY-001": 2}, []),
    "cross_macro": (TITLE + "通胀相关的训练方法 [2]。" + GZ + "前景\n乐观 [2]。\n",
                    {"E-BLOCK-MACRO-OPINION": 2, "E-INFER-UNCLEAR": 2, "E-REPLAY-001": 2}, ["R-MACRO"]),
    "same_line_number": (TITLE + "CATCH 提升 12 分 [2]。" + GZ + "\n", U1, []),
}


class TableB(unittest.TestCase):
    pass


class TableC(unittest.TestCase):
    pass


def _mk_b(doc, status, codes):
    def t(self):
        st, c, r = run(doc)
        c.pop("E-INTERNAL-LIST-MISSING", None)
        self.assertEqual((st, c), (status, codes), r["errors"])
    return t


def _mk_c(doc, codes, soft):
    def t(self):
        st, c, r = run(doc)
        self.assertEqual(c, codes, r["errors"])
        got = [x for x in r["error_codes"] if x in ("R-MEDICAL", "R-STOCK", "R-RELIGION", "R-MACRO")]
        self.assertEqual(sorted(got), sorted(soft))
    return t


for k, (d, s, c) in TABLE_B.items():
    setattr(TableB, f"test_{k}", _mk_b(d, s, c))
for k, (d, c, soft) in TABLE_C.items():
    setattr(TableC, f"test_{k}", _mk_c(d, c, soft))


# ---------------------------------------------------------------- 表 E：tongyi 长文路径（E-INFER-UNCLEAR / E-REPLAY-001 豁免，E-GLOSS-FORMAT 照报）
class TableE_Tongyi(unittest.TestCase):
    SAMPLE = Path(__file__).resolve().parent / "fixtures" / "tongyi-sample" / "sample-a.md"
    REL = "tongyi/sample-a.md"

    def doc(self, para):
        return self.SAMPLE.read_text(encoding="utf-8").replace("本文不含投资建议。", para + "\n\n本文不含投资建议。")

    def ecodes(self, para):
        st, c, r = run(self.doc(para), rel=self.REL)
        return st, sorted(k for k in c if k.startswith("E-"))

    def test_baseline_ok_gloss_passes(self):
        self.assertEqual(self.ecodes(F + GZ), ("PASS", []))

    def test_yiyi_not_pass(self):                     # r3 HIGH 1：含「一亿」不能整篇 PASS
        self.assertEqual(self.ecodes(F + "（本站补充的通用解释：大模型一般指参数达到一亿以上的模型。）"), ("FAIL", ["E-GLOSS-FORMAT"]))

    def test_percent_not_pass(self):
        self.assertEqual(self.ecodes(F + "（本站补充的通用解释：误差一般指低于％的部分。）"), ("FAIL", ["E-GLOSS-FORMAT"]))

    def test_ordinal_not_pass(self):
        self.assertEqual(self.ecodes(F + "（本站补充的通用解释：评测一般排在第三。）"), ("FAIL", ["E-GLOSS-FORMAT"]))

    def test_en_type_iii_not_pass(self):
        self.assertEqual(self.ecodes("CATCH is a method [2]. (General explanation added by this site: it usually means a type iii error.)"),
                         ("FAIL", ["E-GLOSS-FORMAT"]))

    def test_benmoxing_not_pass(self):                # r3 HIGH 2：「本模型」
        self.assertEqual(self.ecodes(F + "（本站补充的通用解释：本模型一般指在训练中加入诱使模型出错的输入。）"), ("FAIL", ["E-GLOSS-FORMAT"]))

    def test_en_proposed_method_not_pass(self):
        self.assertEqual(self.ecodes("CATCH is a method [2]. (General explanation added by this site: the proposed method usually means fine-tuning.)"),
                         ("FAIL", ["E-GLOSS-FORMAT"]))

    def test_punct_only_not_pass(self):               # r3 HIGH 3
        self.assertEqual(self.ecodes("CATCH 是一种训练方法。[2]。" + GZ), ("FAIL", ["E-GLOSS-FORMAT"]))

    def test_second_gloss_not_pass(self):
        self.assertEqual(self.ecodes(F + GZ + "[3]。（本站补充的通用解释：微调一般指继续训练。）"), ("FAIL", ["E-GLOSS-FORMAT"]))

    def test_author_compound_fails(self):             # 15:21 最小版本：「工作者」也拦
        self.assertEqual(self.ecodes(F + "（本站补充的通用解释：医疗工作者一般指在医疗机构从事诊疗与护理的人员。）"), ("FAIL", ["E-GLOSS-FORMAT"]))

    def test_author_bare_fails(self):
        self.assertEqual(self.ecodes(F + "（本站补充的通用解释：作者说的对抗训练一般指加入诱使模型出错的输入。）"), ("FAIL", ["E-GLOSS-FORMAT"]))

    def test_rewritten_label_passes_low1(self):       # LOW 1：tongyi 路径下改写标签改前改后均 PASS，机器不兜底，交审稿人
        self.assertEqual(self.ecodes(F + "（本站补充解释：对抗训练一般指在训练中加入诱使模型出错的输入。）"), ("PASS", []))


# ---------------------------------------------------------------- LOW 1：旧码兜底说法的核实（普通日报 / digest）
class Low1(unittest.TestCase):
    def test_daily_cited_line_gets_both_codes(self):
        for line in (F + GZ, "- " + F + GZ, F + "（本站补充解释：甲一般指乙。）"):
            st, c, r = run(TITLE + line + "\n")
            self.assertEqual({k: c.get(k) for k in U1}, U1, line)

    def test_daily_line_with_url_is_not_covered(self):   # 同行带 URL 走来源分支，不报两个旧码：说法限定为“同行无 raw 路径或 URL”
        st, c, r = run(TITLE + F + "详见 https://example.org/x " + GZ + "\n")
        self.assertNotIn("E-INFER-UNCLEAR", c)


# ---------------------------------------------------------------- 表 D：10-19 digest 计数与真实改前版本相同（r3 MEDIUM 3）
# “改前”取 PR base 的 main 提交 BEFORE_REV 上的 selfcheck.py（不取 HEAD：提交后会变成自己与自己比）；
# 拿不到该提交时（浅克隆）退回固定计数 DIGEST_1019_BEFORE（即在 BEFORE_REV 上实测的值）。
BEFORE_REV = "d709439fd6c8268a77c82aef2ba12e25df4c84b6"
DIGEST_1019_BEFORE = {"E-INFER-UNCLEAR": 82, "E-REPLAY-001": 67, "E-BLOCK-MACRO-OPINION": 2, "E-REPLAY-006": 4}


class TableD(unittest.TestCase):
    def _before_module(self):
        try:
            src = subprocess.run(["git", "-C", str(ROOT), "show", f"{BEFORE_REV}:scripts/markjin/selfcheck.py"],
                                 capture_output=True, text=True, check=True).stdout
        except Exception:                                          # noqa: BLE001
            return None
        p = ROOT / "scripts" / "markjin" / "_selfcheck_before_for_test.py"   # 同目录：词表路径按 __file__ 解析
        p.write_text(src, encoding="utf-8")
        try:
            spec = importlib.util.spec_from_file_location("markjin._selfcheck_before_for_test", p)
            m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        finally:
            p.unlink()
        m.load_internal_terms = lambda: list(DUMMY_INTERNAL)
        return m

    def test_digest_1019_unchanged(self):
        text = (ROOT / "digest" / "2026-10-19.md").read_text(encoding="utf-8")
        cnt = lambda mod: dict(collections.Counter(e["code"] for e in mod.check_text(text, ROOT, "2026-10-19", "daily",
                                                                                 link_checker=lambda u: True)["errors"]))
        before = self._before_module()
        if before is not None:
            self.assertEqual(cnt(before), DIGEST_1019_BEFORE)
        self.assertEqual(cnt(_sc), DIGEST_1019_BEFORE)
        labelled = [l for l in text.splitlines() if g.has_label(l)]
        self.assertEqual(sum(len(g.find_glosses(l)) for l in labelled), 3)
        self.assertTrue(all(not g.has_label(g.strip_glosses(l)) for l in labelled))


if __name__ == "__main__":
    unittest.main()
