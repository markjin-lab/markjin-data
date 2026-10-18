"""#9 脚本自检（第 2 轮）：整篇覆盖、白名单式低风险判定、宏观整篇硬拦、来源与 raw 绑定、严格解析。

设计要点（威胁模型：防误操作、防 bot 绕过；不追求无限加严）
- 先规范化（textnorm：NFKC、去零宽/Cf、压缩空白），再在“逐行”与“整篇拼接（跨行）”两个层面匹配词表。
  词表在公开 JSON lexicon.json（与生产 bot 共用；禁止单字词；含排除短语，如“表示学习”）。
- 整篇扫描：标题、段落、各种列表、引用块、表格、HTML 注释都参与推断/投资/宏观/医疗/内部主题检查，其中的来源也做回放检查。
- t161u（现行）：日报一律过 Codex，没有自动批准；low_risk 与 R-* 只作审查参考，路由不读取。
- 低风险白名单（王总 10-11 定；t161u 后只作参考）：只允许 固定标题 + 原文直引 + 来源链接；结构化复述、列表、段落、表格、
  注释、front matter 等任何其他文本一律非低风险（R-STRUCTURE），照常做来源与硬拦检查。
- low_risk 由 compute_low_risk() 计算（参考值；路由不调用、不读取）：status=PASS、没有任何错误码或审查原因码
  （含 R-INFERENCE；ANNOTATION_CODES 为空，已取消“纯标注可忽略”的旧口径）、card_type 显式为 daily、date 合法、至少 1 条逐字核对通过的原文直引（counts.quotes ≥ 1）、
  没有白名单外的块（counts.other == 0）、除标注外的标记全为 False。结构化断言照常回放核对，但不算低风险。
- 宏观按整篇判定：任一行属宏观语境即整篇为宏观（R-MACRO，永不低风险）；整篇（含跨行）出现观点、判断、预测、
  仓位、资金比例或投入建议 → E-BLOCK-MACRO-OPINION（FAIL）。
- 输出只含错误码、行号与计数，不回显稿件文本。
- r4（按 r3 审查）：规范化先做 HTML 实体解码（多重编码也解）；断言无可核对数字 → R-SUPPORT-UNVERIFIED（空集合不算支持）；
  数字按边界比较；宏观观点/评价词（乐观、前景、应持有…）硬拦；宏观算术（同比/环比/差值…）缺标记或算式 → 硬拦；
  段落来源必须是文件、其链接也做能否打开检查；无来源且无法判别的列表项 → UNCLEAR（含数字或推断词 → FAIL）；
  结果缺有效 date → 非低风险。

硬拦边界（r13，王总经 Grok Bot 转达）：本模块只是 Codex 之前的前置硬拦，不承担语义层面的完备拦截；
词表和模式之外的观点、评价与倾向由每篇必过的 Codex 审查拦截（t161u）。PASS 不代表稿件没有观点。

状态：FAIL（含任一硬错误码）> UNCLEAR（E-INFER-UNCLEAR）> PASS。R-* 码是审查原因，不导致 FAIL。
"""
import datetime as _dt
import hashlib
import json
import xml.etree.ElementTree as ET
import re
from pathlib import Path, PurePosixPath

from .deps import DEP_CODE, have_yaml
from . import strictjson, numnorm
from .fmkeys import FM_CATEGORY_KEYS
from .internal import load_internal_terms
from .textnorm import compact, has_any, norm

CARD_TYPES = ("daily", "signal")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# —— 来源
RAW_RE = re.compile(r"`(raw/[^`\s]+)`")
URL_RE = re.compile(r"https?://[^\s)）`<>\]]+")
SRC_PAIR = r"`(raw/[^`\s]+)` · (https?://[^\s`;]+)"
# 原文支持位置（#32，迁移自旧库 #51）：结构化断言里每个来源对后面可跟 〔原文：<所引条目中支持该断言的原文片段>〕；
# 日报中，非 X 来源必须带它（缺了 E-SUPPORT-LOCATOR-MISSING），片段须是所引条目原文的连续子串，且断言里的数字
# 与拉丁字母术语（指标名、对象名、代号）都要出现在片段里（否则 E-SUPPORT-LOCATOR-MISMATCH）。
LOCATOR = r"(?: 〔原文[:：](?P<loc>[^〔〕]+)〕)?"
LOC_PAIR = SRC_PAIR + r"(?: 〔原文[:：][^〔〕]+〕)?"
STRICT_ASSERT_RE = re.compile(
    r"^(?:[-*+]|\d{1,3}[.)]) (?P<claim>[^`]+?) ?— (?P<srcs>" + LOC_PAIR + r"(?: ; " + LOC_PAIR + r")*)$")
PAIR_RE = re.compile(SRC_PAIR)
LOC_PAIR_RE = re.compile(r"`(raw/[^`\s]+)` · (https?://[^\s`;]+)" + LOCATOR)
LOCATOR_ANY_RE = re.compile(r"〔原文[:：]")
LOC_TEXT_RE = re.compile(r"〔原文[:：][^〔〕]+〕")
TERM_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9.\-]*[A-Za-z0-9](?![A-Za-z0-9])")


def claim_terms(s):
    """指标/对象代号：含两个以上大写字母或含数字的拉丁词（MMLU、GSM8K、UNRATE、GPT-4、CPI-U）；普通英文词不算。"""
    return [t for t in TERM_RE.findall(s) if sum(ch.isupper() for ch in t) >= 2 or any(ch.isdigit() for ch in t)]
# —— 低风险结构白名单（王总 10-11 定）：正文每个块只能是 标题 / 原文直引 / 来源链接
# 原文直引：> 「<原文>」 — `raw/…` · <URL>（也接受 ASCII 双引号）。引文规范化后必须是该来源条目原文的连续子串。
QUOTE_LINE_RE = re.compile(r"^> ?(?:「(?P<q1>[^「」]+)」|\"(?P<q2>[^\"]+)\") — (?P<srcs>" + SRC_PAIR + r")$")
# 来源链接：[- ]来源：`raw/…` · <URL>[ ; `raw/…` · <URL>]…
SOURCE_LINE_RE = re.compile(r"^(?:[-*+] )?(?:来源|source)[:：] ?(?P<srcs>" + SRC_PAIR + r"(?: ; " + SRC_PAIR + r")*)$", re.I)
QUOTE_MIN = 6       # 引文最少 6 个非空白字符，防止只摘一两个字断章取义
URL_KINDS = {
    "arxiv": re.compile(r"^https://arxiv\.org/abs/(\d{4}\.\d{4,5})(v\d+)?$"),
    "x": re.compile(r"^https://(?:x|twitter)\.com/(?:i|[A-Za-z0-9_]{1,15})/status/(\d{5,25})$"),
    "fred": re.compile(r"^https://fred\.stlouisfed\.org/series/([A-Z0-9]{2,30})$"),
}
MANIFEST_LINE = re.compile(r"^([0-9a-f]{64})  (?:\./)?([^\s].*)$")

# 宏观算术白名单要求的算式：形如 “算式：(334.131/323.291-1)×100=3.35%”
# r14：关系符可用 = 或 ≈；值后可带“（四舍五入到小数点后 N 位）”说明，并可再接一段 ≈/= 值（逐级舍入），每个值都验算
_FVAL = r"[=≈]\s*[+\-−]?\d+(?:\.\d+)?%?(?:\s*[（(]\s*四舍五入到小数点后[一二三四五六0-9]位\s*[）)])?"
FORMULA_RE = re.compile(r"算式[:：]\s*[0-9.()\s+\-*/×÷−]*\d[0-9.()\s]*[+\-*/×÷−][0-9.()\s+\-*/×÷−]*?" + _FVAL + r"(?:\s*" + _FVAL + r")*")

FORMULA_MARK_RE = re.compile(r"算式[:：]")
FORMULA_PARTS = re.compile(r"算式[:：]\s*(?P<expr>[^=≈]+?)\s*(?P<vals>[=≈].*)$")
_FVAL_ITEM = re.compile(r"[=≈]\s*(?P<val>[+\-−]?\d+(?:\.\d+)?)%?")


# r6（整体验收 r5 HIGH）：算式字段一直延伸到分隔符（右括号、分号、逗号、句号、换行）或来源标记（来源、raw/、URL）为止；
# FORMULA_RE 消费完之后，字段内不得再剩任何字符（如 “=0.2x≈9.99” 的 “x≈9.99”），否则所声称的最终值未经验算 → E-FORMULA-MISMATCH
_FORMULA_FIELD_END = re.compile(r"[)）;；,，。\n]|来源|raw/|https?://")


def formula_suffix_bad(rest):
    m = _FORMULA_FIELD_END.search(rest)
    field = rest[:m.start()] if m else rest
    return field.strip() != ""


def verify_formula(text):
    """验算“算式：<表达式>=<值>”。只允许数字、+ - * / ×÷− 与括号（ast 解析，不 eval）。
    计算结果按写出值的小数位四舍五入后须与写出值相等。返回 True/False。"""
    import ast
    from decimal import Decimal, ROUND_HALF_UP
    m = FORMULA_PARTS.match(text.strip())
    if not m:
        return False
    expr = m.group("expr").replace("×", "*").replace("÷", "/").replace("−", "-").strip()
    vals = [v.group("val").replace("−", "-") for v in _FVAL_ITEM.finditer(m.group("vals"))]
    if not vals:
        return False
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return Decimal(str(n.value))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand); return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Add): return a + b
            if isinstance(n.op, ast.Sub): return a - b
            if isinstance(n.op, ast.Mult): return a * b
            return a / b
        raise ValueError("disallowed")
    try:
        res = ev(tree)
    except (ValueError, ArithmeticError):
        return False
    for val in vals:                   # 每个写出的值都须等于计算结果按其小数位四舍五入
        q = Decimal(1).scaleb(-len(val.split(".")[1])) if "." in val else Decimal(1)
        if res.quantize(q, rounding=ROUND_HALF_UP) != Decimal(val):
            return False
    return True


# 比较计算（“比上期高 4.2%”“较上月下降 0.3”等）：纳入宏观算术规则（缺标记/算式/来源 → 硬拦）
COMPARE_RE = re.compile(r"(比|较|相比|相较|对比)(上期|上月|上年|去年|前期|上周|上季度?|此前|前值|上次|同期)?"
                        r"[^。；;]{0,6}?(高|低|增加|减少|上升|下降|上涨|下跌|多|少|增长|回落|提高|降低)"
                        r"[^。；;]{0,4}?\d")


# —— 结构
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
LIST_RE = re.compile(r"^(?:[-*+]|\d{1,3}[.)、])\s*")
QUOTE_RE = re.compile(r"^>")
TABLE_RE = re.compile(r"^\|")
TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?$")
COUNTS_STRICT = re.compile(r"^<!-- counts:((?: [a-z_]+=\d+)+) -->$")
COUNTS_ANY = re.compile(r"<!--\s*counts\b", re.I)
# 标题白名单：去掉日期后只允许这些固定栏目名（规范化、去空白、小写后比较）
DISCLAIMER = "本文不含投资建议。"
DISCLAIMER_EN = "This article does not constitute investment advice."   # 英文版固定免责声明（协调决定 10-11，经 Grok Bot 转达）
DISCLAIMERS = (DISCLAIMER, DISCLAIMER_EN)   # 整体验收 r2（王总定）：逐字匹配，句末标点也须一致


def disclaimer_line(s):
    return s.strip() in DISCLAIMERS
ALLOWED_HEADINGS = {"", "日报", "ai日报", "论文", "arxiv", "模型发布", "daily", "digest"}

# —— 词表：公开 JSON（lexicon.json，与生产 bot 共用）。读取或结构失败 → 抛 LexiconError（调用方 FAIL）
LEXICON_PATH = Path(__file__).with_name("lexicon.json")
LEXICON_KEYS = ("judgment", "reported", "exclude", "macro", "macro_ascii", "macro_opinion", "invest", "medical", "medical_markers", "medical_sections", "medical_ascii",
                "religion", "modal", "arith_markers", "arith_terms", "causal",
                "spec_en_verbs", "spec_en_words", "spec_zh", "assets", "stock", "fm_date_keys")


class LexiconError(RuntimeError):
    pass


def load_lexicon(path=LEXICON_PATH):
    try:
        lx = strictjson.loads(Path(path).read_bytes().decode("utf-8"))   # r11：重复键 → LexiconError
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise LexiconError("E-SELFCHECK-LEXICON") from e
    if not isinstance(lx, dict) or lx.get("version") != 1:
        raise LexiconError("E-SELFCHECK-LEXICON")
    for k in LEXICON_KEYS:
        v = lx.get(k)
        if not isinstance(v, list) or not v or not all(isinstance(t, str) and len(compact(t)) >= 2 for t in v):
            raise LexiconError("E-SELFCHECK-LEXICON")   # 每个词规范化后至少 2 个字符：禁止单字
    return lx


try:
    LEX = load_lexicon()
except LexiconError:
    LEX = None
INVEST_EN_RE = re.compile(
    # r11：裸写的 buy/sell 不再拦（“buy signals”是研究对象），只拦买卖建议的固定说法；建议句另见 FUND_RES
    r"\b(buy now|sell now|buy the dip|time to (?:buy|sell)|(?:strong )?buy rating|sell rating|"
    r"price target|stop[- ]loss|long position|short position|go long|go short|"
    r"take profit|portfolio allocation|overweight|underweight)\b", re.I)
# 资金比例与投入建议（在 compact 后的整篇文本上匹配，覆盖跨行与插空白）
FUND_RES = [
    # 持有比例 / 资产权重陈述（无“建议”前缀也算仓位表述），如“组合的股票权重为 30%”
    re.compile(r"(组合|资产|股票|债券|黄金|现金|基金|持仓|仓位|配置)[^。；;!！?？]{0,12}?(权重|仓位|比例|占比|比重|配比)"
               r"[^。；;!！?？]{0,8}?\d+(?:\.\d+)?%"),
    re.compile(r"(建议|应当?|宜|不妨|可以?|最好)[^。；;!！?？]{0,16}?"
               r"(\d+(?:\.\d+)?%|[一二三四五六七八九十两半几]成|一半|半数|全部|大部分)[^。；;!！?？]{0,8}?"
               r"(资金|资产|仓位|积蓄|存款|本金|净值)"),
    re.compile(r"(建议|应当?|宜|不妨|最好)[^。；;!！?？]{0,16}?(资金|资产|本金|积蓄|存款|仓位)"
               r"[^。；;!！?？]{0,10}?(投入|买入?|配置|配|转入|换成)"),
    re.compile(r"(allocate|put|invest)[a-z]{0,3}(\d+%|half|all|most)(of)?(your|the)?(funds|money|portfolio|savings)"),
]
# r8 MEDIUM 1：英文 weight/allocation/exposure + 比例，只有同一句里出现资产或仓位词时才算仓位表述
# （“Memory allocation is 30%.”“attention weight is 0.3%” 不拦；“Equity allocation is 30%.” 拦）
EN_ALLOC_RE = re.compile(r"(weight|allocation|exposure)(of|to|in)?[a-z]{0,20}(is|at|=)?\d+(\.\d+)?%")
EN_ASSET_RE = re.compile(r"\b(stocks?|equit(?:y|ies)|shares?|bonds?|treasur(?:y|ies)|gilts?|gold|silver|cash|portfolios?|"
                         r"funds?|etfs?|crypto(?:currenc(?:y|ies))?|bitcoin|btc|real estate|propert(?:y|ies)|commodit(?:y|ies)|"
                         r"oil|holdings?|positions?|assets?|securities|indexes|indices|s&p|nasdaq)\b", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.;!?。；！？])\s*|\n")


def en_alloc_position(text):
    """按句判断：同一句同时含“weight/allocation/exposure … N%”与资产/仓位词（英文词表或 lexicon assets）→ True。"""
    for sent in _SENT_SPLIT.split(norm(text)):
        if sent and EN_ALLOC_RE.search(compact(sent)) and (EN_ASSET_RE.search(sent) or has_any(sent, LEX["assets"])):
            return True
    return False


TICKER_RES = [
    re.compile(r"\$[A-Z]{1,5}\b"),
    re.compile(r"\((?:NASDAQ|NYSE|AMEX|HKEX|SSE|SZSE)\s*:\s*[A-Z0-9.]+\)", re.I),
    re.compile(r"\b\d{6}\.(?:SH|SZ|BJ)\b", re.I),
    re.compile(r"\b\d{4,5}\.HK\b", re.I),
]
# 持有比例（含中文数字）：如“股票持有六成”“债券持有百分之三十”
FUND_RES.append(re.compile(r"(股票|债券|美债|国债|黄金|现金|基金|股|债|仓位|组合|资产)[^。；;!！?？]{0,8}?(持有|持仓|配|仓位|拿)"
                           r"[^。；;!！?？]{0,4}?([一二三四五六七八九十两半几]成|百分之[零一二三四五六七八九十百两]+|\d+(?:\.\d+)?(?:%|成))"))
FUND_RES.append(re.compile(r"(持有|满仓|半仓|轻仓|重仓)[^。；;!！?？]{0,3}?([一二三四五六七八九十两半几]成|百分之[零一二三四五六七八九十百两]+)"))
# 推测动词与情态词类表（中英，词表 spec_*）：直引里也算推断，挡住低风险。
# 英文推测动词按词干自动覆盖 -s/-es/-ed/-ing 变形（seems/appeared/suggesting/indicates…）；情态/推测副词按词边界。
def _spec_en_re(lx):
    if not lx:
        return re.compile(r"(?!x)x")
    verbs = []
    for v in lx["spec_en_verbs"]:
        head, _, tail = v.partition(" ")
        stem = head[:-1] if head.endswith("e") else head
        verbs.append(re.escape(stem) + r"(?:e|es|s|ed|d|ing)?" + ((r"\s+" + re.escape(tail)) if tail else ""))
    words = [re.escape(w) for w in lx["spec_en_words"]]
    return re.compile(r"\b(?:" + "|".join(verbs + words) + r")\b", re.I)


MODAL_EN_RE = _spec_en_re(LEX)
# 资产 + 应当/值得/建议 + 持有/买/配置；资产 + 持有/占 + 比例：一律硬拦（compact 后匹配）
_RATIO = (r"(?:半数|一半|大半|多数|大部分|全部|[一二三四五六七八九十两半几]成|百分之[零一二三四五六七八九十百两]+|"
          r"[零一二三四五六七八九十百两\d]+分之[零一二三四五六七八九十百两\d]+|\d+/\d+|\d+(?:\.\d+)?(?:%|成))")
_ADVISE = r"(?:应当|应该|应|宜于|适宜|适合|适于|宜|值得|建议|最好|不妨|可以|可)"
_ACT = r"(?:持有|买入|买进|购买|买|配置|增持|入手|加仓|投资|布局)"
_HOLD = r"(?:持有|持仓|占比|占|比重|权重|仓位|配置|配)"
_HOLD_STRONG = r"(?:持有|持仓|比重|权重|仓位|配置|配)"


def _asset_res(lx):
    if not lx:
        return []
    a = "(?:" + "|".join(re.escape(compact(x)) for x in lx["assets"]) + ")"
    return [re.compile(a + r"[^。；;!！?？]{0,8}?" + _ADVISE + r"[^。；;!！?？]{0,4}?" + _ACT),
            re.compile(_ADVISE + r"[^。；;!！?？]{0,4}?" + _ACT + r"[^。；;!！?？]{0,6}?" + a),
            re.compile(a + r"[^。；;!！?？]{0,8}?" + _HOLD_STRONG + r"[^。；;!！?？]{0,6}?" + _RATIO),
            # r12：“占/占比”只在紧跟资产时算仓位句（“黄金占30%”拦；“黄金样本占30%”不拦）
            re.compile(a + r"(?:的)?(?:占比|占)[^。；;!！?？]{0,6}?" + _RATIO),
            # 仓位事实句：“黄金是组合资产的一半”“组合的一半是黄金”“股票为持仓的 30%”
            re.compile(a + r"[^。；;!！?？]{0,6}?(?:是|为|占|构成)[^。；;!！?？]{0,8}?(?:组合|资产|仓位|持仓|投资|portfolio)"
                       r"[^。；;!！?？]{0,6}?" + _RATIO),
            re.compile(r"(?:组合|仓位|持仓|资产配置)[^。；;!！?？]{0,6}?" + _RATIO + r"[^。；;!！?？]{0,10}?" + a)]


FUND_RES.extend(_asset_res(LEX))
# 英文仓位比例与买卖建议（compact 后：小写、无空白）：“… are half the portfolio”“30% of the portfolio”
_EN_NUM = (r"(?:(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
           r"sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|a|-)+)")
_EN_FRAC = (r"(?:one|two|three|four|five|six|seven|eight|nine|a|-)+"
            r"(?:half|halves|thirds?|quarters?|fourths?|fifths?|sixths?|sevenths?|eighths?|ninths?|tenths?)")
# r11：英文单词写的比例（forty percent、two-thirds、three quarters）同样算仓位比例
_EN_RATIO = (r"(?:half|aquarter|quarter|athird|onethird|twothirds|onefifth|onetenth|majority|most|all|"
             r"\d+(?:\.\d+)?%|\d+/\d+|\d+percent|" + _EN_NUM + r"percent|" + _EN_NUM + r"percentage|" + _EN_FRAC + r")")
FUND_RES.extend([
    re.compile(r"(?:is|are|was|were|make(?:s|up)?|madeup|represent(?:s|ed)?|account(?:s|ed)?for|comprise[sd]?|constitute[sd]?)"
               r"(?:about|around|roughly|nearly|over|under|only)?" + _EN_RATIO + r"(?:of|in|within)?(?:the|their|your|our|its|a|his|her|my)?"
               r"(?:portfolio|holdings?|allocation|assets|fund|positions?|investments?)"),
    re.compile(_EN_RATIO + r"(?:of|in|within)(?:the|their|your|our|its|a|my)?(?:portfolio|holdings?|allocation|positions?|investments?)"),   # r13：in our portfolio
    re.compile(r"(?:should|must|oughtto|recommend(?:s|ed)?|advise[sd]?|suggest(?:s|ed)?(?:that)?(?:you|investors)?)(?:to)?"
               r"(?:buy|sell|hold|short|accumulate|overweight|underweight|allocate|invest)"),
    re.compile(r"(?:allocate|put|invest|keep|hold)" + _EN_RATIO + r"(?:of)?(?:your|the|their)?(?:portfolio|money|funds|savings|assets)?(?:in|into|to)"),
])
# r11：英文资产/宏观评价句硬拦（“Treasury yields are attractive.”“Gold looks cheap.”“stocks are overvalued”）
MACRO_EVAL_EN_RE = re.compile(
    r"\b(?:is|are|was|were|look|looks|looked|seem|seems|remain|remains|appear|appears|become|becomes|stay|stays)\s+"
    r"(?:\w+\s+){0,2}?(?:attractive|unattractive|cheap|expensive|overvalued|undervalued|overpriced|underpriced|"
    r"a\s+bargain|a\s+good\s+(?:buy|deal|investment)|a\s+bad\s+investment|compelling|bullish|bearish|"
    r"good\s+value|poor\s+value|rich|stretched|oversold|overbought)\b", re.I)
ASSET_EN_RE = re.compile(r"\b(?:stocks?|equit(?:y|ies)|shares|bonds?|treasur(?:y|ies)|t-bills?|gilts|yields?|gold|silver|"
                         r"dollar|usd|real\s+estate|housing|propert(?:y|ies)|funds?|etfs?|bitcoin|crypto\w*|oil|commodit(?:y|ies)|"
                         r"currenc(?:y|ies)|markets?)\b", re.I)
# r12：评价与机会类说法。宏观稿中任何位置（含原文直引）出现即硬拦；非宏观稿与明确资产词同行时硬拦
MACRO_OPP_EN_RE = re.compile(
    r"\b(?:opportunit(?:y|ies)|excellent|attractive(?:ly)?|compelling|bargains?|cheap(?:er|est)?|undervalued|overvalued|"
    r"mispriced|worth\s+(?:buying|owning|holding|a\s+look)|good\s+(?:buy|value|entry|deal|time\s+to)|"
    r"upside|must[-\s]own|top\s+pick)\b", re.I)
MACRO_OPP_ZH_RE = re.compile(r"(?:值得(?!注意|一提)|机会(?!成本)|吸引力|便宜|低估|高估|划算|性价比|上涨空间|买点|卖点)")
_ASSET_CLEAR_EN_RE = re.compile(r"\b(?:stocks|equities|stock\s+market|bonds?|treasur(?:y|ies)|t-bills?|gilts|"
                                r"usd|real\s+estate|etfs?|bitcoin|crypto\w*|(?:treasury|bond|government)\s+yields?)\b", re.I)
# r13：gold/silver/oil/dollar/housing/commodity/currency 在科研与技术文本中常见（gold nanoparticles、gold-standard、oil droplets），
# 只有同一行出现市场语境词时才算资产；不再逐个加例外词
_ASSET_AMBIG_EN_RE = re.compile(r"\b(?:gold|silver|oil|dollar|housing|commodit(?:y|ies)|currenc(?:y|ies))\b(?!-)", re.I)
_MARKET_CTX_EN_RE = re.compile(r"(?:\$|\b(?:prices?|priced|pricing|markets?|investors?|invest(?:ing|ment|ments)?|ounces?|futures|"
                               r"portfolios?|holdings?|bullion|spot|rall(?:y|ied|ies)|traders?|trading|valuations?|returns?)\b)", re.I)


class _AssetStrict:
    """r13：明确资产词直接算；歧义商品词须同一行有市场语境。接口与正则相同（.search）。"""
    def search(self, s):
        return _ASSET_CLEAR_EN_RE.search(s) or (_ASSET_AMBIG_EN_RE.search(s) and _MARKET_CTX_EN_RE.search(s))


ASSET_STRICT_EN_RE = _AssetStrict()
_GENERIC_QUALITY_EN_RE = re.compile(r"\b(?:excellent|attractive(?:ly)?|compelling)\b", re.I)


def _asset_opportunity_en(s):
    """非宏观稿：机会/估值类说法 + 资产词。歧义商品词遇到投资专用词（opportunity、undervalued、bargain、upside…）照拦；
    只有 excellent/attractive/compelling 这类通用质量词时，须同一行有市场语境（Gold nanoparticles provide excellent contrast. 不拦）。"""
    m = MACRO_OPP_EN_RE.search(s)
    if not m:
        return False
    if ASSET_STRICT_EN_RE.search(s):
        return True
    specific = any(not _GENERIC_QUALITY_EN_RE.fullmatch(x.group(0)) for x in MACRO_OPP_EN_RE.finditer(s))
    return bool(specific and _ASSET_AMBIG_EN_RE.search(s))


CLAIM_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?%?")   # 只核对数字：断言中的数字必须全部出现在 raw 存档
NUM_RE = re.compile(r"(?<![\d.])\d+(?:\.\d+)?(?![\d])")   # 数字按边界切分：90 不支持 9，4.2 不支持 4
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")


def numbers(s: str) -> set:
    """规范化后按边界取出全部数字（去千分位逗号；去掉末尾的 .）。"""
    return {n.rstrip(".") for n in NUM_RE.findall(_THOUSANDS.sub("", norm(s)))}

TRANSLATION_RE = re.compile(r"^[ \t>*+\-]*(?:\d{1,3}[.)、][ \t]*)?[ \t>*+\-]*译文\s*[:：]", re.M)   # r12：含 + 与 1. 等列表前缀
HARD_SOFT_PREFIX = "R-"   # R-* 为审查原因（不 FAIL，但不是低风险）
FLAG_KEYS = ("has_inference", "inference_unclear", "macro", "medical", "religion", "internal", "x_only",
             "signal_card", "free_text", "unstructured", "unsupported", "link_unchecked", "link_unreachable",
             "structure_other", "quote_unverified", "stock",
             "support_review", "locator_short", "entity_unchecked", "support_scope", "support_hedge",
             "quote_numeric", "quote_comparative", "quote_modal", "quote_entity", "translation")
COUNT_KEYS = ("assertions", "structured", "replayable", "x_sourced", "macro", "inference",
              "unclear", "free_text", "quotes", "source_links", "other")
# 只做风险标注、不再作为低风险门槛的标记（王总 10-11：词表不再担负低风险门槛）
# 协调决定（10-11）：直引里带判断词同样不算低风险 → 不再有“仅标注”的标记
ANNOTATION_FLAGS = ()
ANNOTATION_CODES = ()


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def valid_date(s) -> bool:
    if not isinstance(s, str) or not DATE_RE.match(s):
        return False
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        return False
    return True


class _Ctx:
    def __init__(self, repo: Path, date: str):
        self.repo, self.date, self.manifests, self.urls = repo, date, {}, []
        self.last_text = None
        self.last_scopes = None
        self.last_units = None

    def manifest(self, day_dir: Path):
        """严格解析 MANIFEST.sha256 → (dict 或 None, 错误码或 None)。"""
        if day_dir in self.manifests:
            return self.manifests[day_dir]
        m = day_dir / "MANIFEST.sha256"
        res = None, None
        try:
            text = m.read_bytes().decode("utf-8")
        except FileNotFoundError:
            res = None, "E-REPLAY-003"
        except (OSError, UnicodeDecodeError):
            res = None, "E-REPLAY-READ"
        else:
            entries, bad = {}, False
            for ln in text.splitlines():
                if not ln.strip():
                    continue
                mm = MANIFEST_LINE.match(ln)
                if not mm:
                    bad = True; break
                name = mm.group(2)
                pp = PurePosixPath(name)
                if pp.is_absolute() or ".." in pp.parts or name != name.strip() or (name in entries and name != "RETRACTIONS.md"):
                    bad = True; break      # RETRACTIONS.md 按 raw/README.md 规则可重复登记，以最后一条为准
                entries[name] = mm.group(1)
            res = (None, "E-MANIFEST-PARSE") if bad or not entries else (entries, None)
        self.manifests[day_dir] = res
        return res

    def _fred_units(self, sid, entries):
        """#32 r3：FRED 序列单位存档 raw/<日期>/fred/<ID>.series.json（FRED series 接口原始响应或 {"id","units"}），
        必须登记在 MANIFEST 且哈希一致；读不到、未登记或不一致 → None（带单位的断言不能自动通过）。"""
        rel = f"fred/{sid}.series.json"
        f = self.repo / "raw" / self.date / "fred" / f"{sid}.series.json"
        if _has_symlink(self.repo, ("raw", self.date, "fred", f"{sid}.series.json")) or not f.is_file():
            return None
        try:
            data = f.read_bytes()
            if entries.get(rel) != _sha256(data):
                return None
            o = strictjson.loads(data.decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            return None
        if isinstance(o, dict) and isinstance(o.get("seriess"), list) and len(o["seriess"]) == 1:
            o = o["seriess"][0]
        if not isinstance(o, dict) or o.get("id") != sid:
            return None
        return o.get("units")

    def check_pair(self, raw_rel: str, url: str, claim=None):
        """一个 (raw, URL) 来源对。返回 (错误码或 None, kind, supported: bool)。"""
        kind = next((k for k, rx in URL_KINDS.items() if rx.match(url)), None)
        if kind is None:
            return "E-REPLAY-005", None, False          # 未知 URL 类型直接失败
        sid = URL_KINDS[kind].match(url).group(1)
        pp = PurePosixPath(raw_rel)
        parts = pp.parts
        if (".." in parts or len(parts) < 4 or parts[0] != "raw" or parts[1] != self.date
                or parts[2] != kind):
            return "E-REPLAY-006", kind, False          # 来源未与同日同类型 raw 文件绑定
        f = self.repo.joinpath(*parts)
        if _has_symlink(self.repo, parts) or (self.repo / "raw" / self.date / "MANIFEST.sha256").is_symlink():
            return "E-REPLAY-SYMLINK", kind, False      # raw 路径（含祖先目录）或 MANIFEST 是符号链接：一律拒绝
        entries, err = self.manifest(self.repo / "raw" / self.date)
        if not f.is_file():
            return "E-REPLAY-002", kind, False
        if err:
            return err, kind, False
        try:
            data = f.read_bytes()
            text = data.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            return "E-REPLAY-READ", kind, False
        rel = str(PurePosixPath(*parts[2:]))
        if entries.get(rel) != _sha256(data):
            return "E-REPLAY-003", kind, False
        if kind == "fred":
            try:
                fj = strictjson.loads(text)   # r11：任何重复键（含 series_id、id）→ E-REPLAY-READ 判失败
            except ValueError:
                return "E-REPLAY-READ", kind, False      # FRED 存档必须是合法 JSON
            ids = _fred_ids(fj)
            if ids:
                if ids != {sid}:
                    return "E-REPLAY-004", kind, False  # 存档自报了系列 ID，就必须唯一且等于 URL 的 ID
            elif not (isinstance(fj, dict) and isinstance(fj.get("observations"), list)
                      and PurePosixPath(rel).name == sid + ".json"):
                return "E-REPLAY-004", kind, False
            # r13：FRED observations API 原始响应不含 series_id；此时以 MANIFEST 登记的文件名 <ID>.json 绑定系列身份
            scopes = _fred_scopes(fj, text, claim)
            self.last_units = self._fred_units(sid, entries)
        else:
            ver = URL_KINDS[kind].match(url).group(2) if kind == "arxiv" else None
            scopes = select_entries(text, kind, sid, ver)
            if scopes is None:
                return "E-REPLAY-READ", kind, False
            if scopes == "AMBIGUOUS":
                return "E-REPLAY-VERSION-UNCLEAR", kind, False   # 无版本链接，存档里该 ID 有多个版本 → 不确定
            if not scopes:
                return "E-REPLAY-004", kind, False      # 没有“自身 id 字段”等于该 ID（及版本）的条目
        if url not in self.urls:
            self.urls.append(url)
        self.last_text = text
        self.last_scopes = scopes
        supported = False
        if claim is not None:
            toks = numbers(claim)
            if kind == "fred":     # r13：观测日期与 vintage 只用来选观测，不当作要核对的数字
                toks = numbers(_CLAIM_DATE_RE.sub(" ", _VINTAGE_RE.sub(" ", norm(claim))))
            # 保守判定：断言里没有可核对的数字 → 不算“来源支持”（空集合不视为支持）
            # 整体验收 r12 MEDIUM（王总定）：只在被引用的那一条里核数字——arXiv/X 为 select_entries 选出的目标条目
            # （条目 id / 版本）正文域；FRED 存档已按 series_id 绑定为单一系列（URL 不带 vintage），范围即该系列文件
            pool = set()
            for sc_text in scopes:
                pool |= numbers(sc_text)
            supported = bool(toks) and toks <= pool
        return None, kind, supported


_CLAIM_DATE_RE = re.compile(r"(?<!\d)(\d{4}-\d{2}(?:-\d{2})?)(?!\d)")
_VINTAGE_RE = re.compile(r"(?:vintage|数据版本|版本日期|realtime)\s*[:：=]?\s*(\d{4}-\d{2}-\d{2})", re.I)


def _fred_scopes(fj, text, claim):
    """整体验收 r13 MEDIUM（审查 bot 定）：FRED 只在被引用的那一期观测里核数字。
    - 存档有 observations 列表：断言写了观测日期（YYYY-MM-DD / YYYY-MM）就只取 date 以之开头的观测；写了 vintage
      （“vintage: YYYY-MM-DD”“数据版本 …”）则再要求 realtime_start ≤ vintage ≤ realtime_end；没写日期且列表不止一条
      → 范围为空（不算来源支持）。只有一条观测时即为被引用的那一条。
    - 存档是单条观测的平铺对象：范围就是这一条。"""
    if not (isinstance(fj, dict) and isinstance(fj.get("observations"), list)):
        return [text]
    obs = [o for o in fj["observations"] if isinstance(o, dict)]
    if claim is None:
        return [json.dumps(o, ensure_ascii=False) for o in obs]   # 不核数字的入口：只做身份绑定
    c = norm(claim)
    vint = _VINTAGE_RE.findall(c)
    dates = [d for d in _CLAIM_DATE_RE.findall(_VINTAGE_RE.sub(" ", c))]
    if dates:
        obs = [o for o in obs if isinstance(o.get("date"), str) and any(o["date"].startswith(d) for d in dates)]
    elif len(obs) != 1:
        return []
    for v in vint:
        obs = [o for o in obs if isinstance(o.get("realtime_start"), str) and isinstance(o.get("realtime_end"), str)
               and o["realtime_start"] <= v <= o["realtime_end"]]
    return [json.dumps(o, ensure_ascii=False) for o in obs]


def _claim_of(s):
    """非结构化行的断言原文：去掉 raw 路径与 URL（其中的日期、编号不算断言数字）。"""
    return URL_RE.sub(" ", RAW_RE.sub(" ", LOC_TEXT_RE.sub(" ", s)))


def check_text(text, repo, date, card_type, internal_terms="load", link_checker=None, rel=None):
    """自检。rel：稿件在仓库内的相对路径（整体验收 r15：tongyi 长文豁免需 type 与路径一致；不给路径按不一致处理）。
    repo、date、card_type 必须显式给出；internal_terms="load" 时从本机内部目录读取（fail-closed）。
    link_checker：url -> bool（能否打开）。为 None 时不检查链接，结果带 R-LINK-UNCHECKED（非低风险）。"""
    errors = []
    flags = {k: False for k in FLAG_KEYS}
    counts = {k: 0 for k in COUNT_KEYS}
    meta = {"card_type": card_type if card_type in CARD_TYPES else None,
            "date": date if valid_date(date) else None}

    def err(code, line=0):
        errors.append({"code": code, "line": line})

    if card_type not in CARD_TYPES:
        err("E-SELFCHECK-CARDTYPE")
    if not valid_date(date):
        err("E-SELFCHECK-DATE")
    if not isinstance(repo, (str, Path)) or not str(repo).strip() or not Path(repo).is_dir():
        err("E-SELFCHECK-REPO")
    if not isinstance(text, str) or not text.strip():
        err("E-SELFCHECK-INPUT")
    try:
        fresh = load_lexicon()
    except LexiconError:
        fresh = None
    if LEX is None or fresh != LEX:
        err("E-SELFCHECK-LEXICON")      # 每次自检重读词表：磁盘词表缺失、损坏或与已加载版本不同 → 失败（不用旧词表）
    if errors:
        return _result(errors, flags, counts, meta)
    repo = Path(repo)
    excl = [compact(t) for t in LEX["exclude"]]
    macro_ascii = re.compile(r"\b(" + "|".join(re.escape(t) for t in LEX["macro_ascii"]) + r")\b", re.I)
    med_ascii = medical_ascii_re()

    def infer(t):
        c = compact(t)
        for x in excl:
            c = c.replace(x, "")
        return (has_any(c, LEX["judgment"]) or has_any(c, LEX["reported"]) or has_any(c, LEX["modal"])
                or has_any(c, LEX["spec_zh"]) or bool(MODAL_EN_RE.search(t)))

    def judge(t):   # 宏观硬拦用：判断/预测词（不含转述词）
        c = compact(t)
        for x in excl:
            c = c.replace(x, "")
        # r11（中英口径一致）：英文推测/情态（will、may、likely…，MODAL_EN_RE）与中文推测词（spec_zh）同等对待
        return has_any(c, LEX["judgment"]) or has_any(c, LEX["spec_zh"]) or bool(MODAL_EN_RE.search(t))
    arith_re = re.compile(r"(?:推断[:：]\s*)?(?:" + "|".join(re.escape(m) for m in LEX["arith_markers"]) + ")")
    arith_terms = [compact(t) for t in LEX["arith_terms"]]
    arith_term_re = re.compile(r"\b(?:yoy|mom)\b", re.I)

    def is_arith(s):
        c = compact(s)
        return (any(t in c for t in arith_terms if t not in ("yoy", "mom")) or bool(arith_term_re.search(s))
                or bool(COMPARE_RE.search(c)))

    def macro_text(i, s):
        """宏观算术白名单：标记（由原始数据计算…）+ 算式 + 数据来源三者齐全时，去掉标记与算式后再做观点检查；
        有标记但缺算式或来源 → 返回 None（硬拦）。"""
        marked = bool(arith_re.search(s))
        if not marked and not is_arith(s):
            return s
        # 宏观算术（同比/环比/差值等，或带计算标记）：标记、算式、结构化数据来源三者缺一 → 硬拦
        if not (marked and FORMULA_RE.search(s) and STRICT_ASSERT_RE.match(s)):
            return None
        # r11 BLOCKER 1：同一句里每一个“算式：”都必须恰好是一个可解析算式的起点；任一处格式不对 → 整句判失败
        starts = {fm.start() for fm in FORMULA_RE.finditer(s)}
        if any(mk.start() not in starts for mk in FORMULA_MARK_RE.finditer(s)):
            err("E-FORMULA-MISMATCH", i)
        for fm in FORMULA_RE.finditer(s):          # 算式验算：结果与写出的值不符 → 硬错误
            if not verify_formula(fm.group(0)):
                err("E-FORMULA-MISMATCH", i)
        for fm in FORMULA_RE.finditer(s):
            if formula_suffix_bad(s[fm.end():]):
                err("E-FORMULA-MISMATCH", i)       # r15：算式后紧跟未被解析消费的 ≈ / = / 舍入说明 → 不放过（必须验到最后一个值）
        rest = FORMULA_RE.sub("", arith_re.sub("", s))           # r15：算式后未被解析消费的 ≈ / = / 舍入说明 → 不放过（必须验到最后一个值）
        return rest

    def macro_block(t, quote=False):
        # r11（决定 44，中英一致）：原文直引里的宏观预测（“通胀将会上升。”“Inflation will rise.”）只标
        # R-MACRO + R-QUOTE-MODAL、交 Codex，不硬拦；直引以外的预测/判断照旧硬拦。观点词、因果词、仓位句一律硬拦。
        return (has_any(t, LEX["macro_opinion"]) or (not quote and judge(t)) or has_any(t, LEX["causal"])
                or bool(MACRO_EVAL_EN_RE.search(t)) or any(r.search(compact(t)) for r in FUND_RES) or en_alloc_position(t))
    flags["signal_card"] = card_type == "signal"
    ctx = _Ctx(repo, date)

    if internal_terms != "load":
        # r12：内部清单只认本机真实名单，调用方不得传入替代值（含非空列表）；测试改为替换 load_internal_terms
        raise ValueError('internal_terms must be "load"; substitute term lists are not accepted')
    terms = load_internal_terms()
    if not terms:
        err("E-INTERNAL-LIST-MISSING")
        terms = []

    raw_lines = text.splitlines()
    lines = [norm(l) for l in raw_lines]
    doc = "\n".join(lines)
    doc_compact = compact(doc)

    # —— counts 注释：最多一个，且必须整行严格格式、键已知、无重复
    counts_decl = None
    if len(COUNTS_ANY.findall(doc)) > 1:
        err("E-COUNT-002")

    fm_end = 0                          # 文首 front matter（--- … ---）的结束行号
    if lines and lines[0] == "---":
        fm_end = next((k for k in range(2, len(lines) + 1) if lines[k - 1] == "---"), 0)
    if fm_end:
        if not have_yaml():
            err(DEP_CODE, 1); flags["medical"] = True; fm_med = fm_bad = False   # r10：缺 PyYAML → 结构化失败，不崩溃
        else:
            fm_med, fm_bad = fm_categories(raw_lines[1:fm_end - 1], flags)   # r9：用未规范化的原始行（保留缩进）
        if fm_bad:
            err("E-SELFCHECK-FM-ALIAS", 1)   # r8：锚点/别名/合并键或解析失败 → fail-closed
        if fm_med:
            flags["medical"] = True         # r7/r8：按 yaml.safe_load 解析后的分类键兜底，按医疗类处理
    fm_parsed = _fm_parsed(raw_lines[1:fm_end - 1]) if fm_end and have_yaml() else None
    # —— 整体验收 r15（审查 bot 定的技术方案）：tongyi 长文豁免日报断言句式检查
    tongyi_fm = isinstance(fm_parsed, dict) and isinstance(fm_parsed.get("type"), str) \
        and fm_parsed["type"].strip().lower() == TONGYI_TYPE
    tongyi_path = is_tongyi_path(rel)
    long_form = False
    if tongyi_fm or tongyi_path:
        if tongyi_fm and tongyi_path:
            long_form = True
        else:
            err("E-TONGYI-MISMATCH", 1)      # type 与路径只有一方是 tongyi → fail-closed（照常跑日报检查）
    # r15 BLOCKER 修正：只在正文（列表、段落）的无来源句式检查处跳过；front matter、表头、来源核对等其他位置照常报错
    def body_err(code, line=0):
        # r16 BLOCKER：front matter 内的任何行（含 YAML 列表、块标量、flow 列表）一律不豁免
        if in_fm or not (long_form and code in LONGFORM_EXEMPT_CODES):
            err(code, line)
    # —— 宏观整篇判定
    macro_lines = [i for i, s in enumerate(lines, 1)
                   if has_any(s, LEX["macro"]) or macro_ascii.search(s)
                   or "/fred/" in s or "fred.stlouisfed.org" in s.lower()]
    # r10 MEDIUM：front matter 解析出的 macro 类别（fm_categories 先于此处置位 flags["macro"]）同样启用整篇宏观硬拦
    is_macro_doc = (bool(macro_lines) or has_any(doc, LEX["macro"]) or bool(macro_ascii.search(doc))
                    or bool(flags.get("macro")))
    if is_macro_doc:
        flags["macro"] = True

    mlines = []
    mquote = []
    for i, s in enumerate(lines, 1):
        if not s:
            continue
        in_fm = 1 < i < fm_end
        if in_fm and _correction_fm_ok(raw_lines[i - 1], fm_parsed):
            flags["structure_other"] = True; counts["other"] += 1   # 更正稿元数据（corrects / corrected_at），非断言、非低风险
            continue
        if terms and has_any(s, terms):
            flags["internal"] = True
            err("E-BLOCK-INTERNAL", i)
        if (has_any(s, LEX["invest"]) or INVEST_EN_RE.search(s)
                or any(r.search(s) for r in TICKER_RES) or any(r.search(compact(s)) for r in FUND_RES) or en_alloc_position(s)):
            err("E-BLOCK-INVEST", i)
        if MACRO_EVAL_EN_RE.search(s) and (ASSET_STRICT_EN_RE.search(s) or is_macro_doc):
            err("E-BLOCK-MACRO-OPINION", i)      # r11/r12：英文资产/宏观评价句硬拦；资产词改用无歧义集合（“The stock of knowledge is rich.”不拦）
        if not disclaimer_line(s) and (
                ((MACRO_OPP_EN_RE.search(s) or MACRO_OPP_ZH_RE.search(compact(s))) and is_macro_doc)
                or _asset_opportunity_en(s)
                or (MACRO_OPP_ZH_RE.search(compact(s)) and has_any(s, LEX["assets"]))):
            err("E-BLOCK-MACRO-OPINION", i)      # r12：评价/机会类说法（opportunity、excellent、attractive、值得、机会…）
        if has_any(s, LEX["medical"]) or med_ascii.search(norm(s)):
            flags["medical"] = True          # 可以公开，但不算低风险（含中医、佛学及常见中医疗法词）
        if has_any(s, LEX["stock"]):
            flags["stock"] = True            # 股市主题（含纯事实直引）：永不低风险
        if has_any(s, LEX["religion"]):
            flags["religion"] = True         # 佛学等宗教内容另记 R-RELIGION，同样挡住低风险
        disclaimer = s.strip() in DISCLAIMERS   # 固定免责声明：只放行中文或英文这一句精确原文（含句末标点）
        if is_macro_doc:
            mquote.append(bool(QUOTE_LINE_RE.match(s)))
        if is_macro_doc and disclaimer:
            mlines.append("")
        elif is_macro_doc:
            mt = macro_text(i, s)
            mlines.append(mt or "")
            if mt is None or macro_block(mt, quote=bool(QUOTE_LINE_RE.match(s))):
                err("E-BLOCK-MACRO-OPINION", i)
        if infer(mlines[-1] if (is_macro_doc and mlines[-1]) else s):
            flags["has_inference"] = True
            counts["inference"] += 1

        # —— 行分类
        # r17 BLOCKER：注释分支只用于正文；front matter 里的值（含 "<!-- 95 -->" 这类字符串）原样走 front matter 检查
        if COUNTS_ANY.search(s) or (not in_fm and ("<!--" in s or "-->" in s)):
            m = COUNTS_STRICT.match(s)
            if COUNTS_ANY.search(s):
                if not m or counts_decl is not None:
                    err("E-COUNT-002", i)
                else:
                    kv = {}
                    for item in m.group(1).split():
                        k, _, v = item.partition("=")
                        if k not in COUNT_KEYS or k in kv:
                            err("E-COUNT-002", i); kv = None; break
                        kv[k] = int(v)
                    counts_decl = kv if kv is not None else {}
                flags["structure_other"] = True; counts["other"] += 1   # counts 注释不在结构白名单内：不得低风险
            else:
                flags["free_text"] = True; counts["free_text"] += 1   # 其他 HTML 注释：不可见文字也不免检
                flags["structure_other"] = True; counts["other"] += 1
                _check_free_text_sources(ctx, s, i, err, counts, flags, card_type)              # r13：注释里的来源同样配对回放
            continue
        h = HEADING_RE.match(s)
        if h:
            title = re.sub(r"\d{4}-\d{2}-\d{2}", "", h.group(2))
            if compact(title) not in ALLOWED_HEADINGS or RAW_RE.search(s) or URL_RE.search(s):
                flags["free_text"] = True; counts["free_text"] += 1
                flags["structure_other"] = True; counts["other"] += 1
                _check_free_text_sources(ctx, s, i, err, counts, flags, card_type)
            continue
        if TABLE_SEP_RE.match(s) and TABLE_RE.match(s):
            flags["structure_other"] = True; counts["other"] += 1
            continue
        if re.fullmatch(r"[-*_ ]{3,}", s):          # 分隔线 / front matter 边界：不免检，非低风险
            flags["free_text"] = True; counts["free_text"] += 1
            flags["structure_other"] = True; counts["other"] += 1
            continue
        qm = QUOTE_LINE_RE.match(s)
        if qm:
            q = qm.group("q1") or qm.group("q2")
            raw_rel, url = PAIR_RE.findall(qm.group("srcs"))[0]
            e, kind, _ = ctx.check_pair(raw_rel, url)
            _x_flags([kind], counts, flags, err, i, card_type)
            if e:
                err(e, i)
            elif card_type != "daily" or not quote_in_source(ctx.last_scopes, q):
                # 逐字匹配只用于日报；不是原文连续子串（夹带原文没有的字）→ 非低风险，走 Codex
                flags["quote_unverified"] = True; counts["other"] += 1
            else:
                counts["quotes"] += 1; counts["replayable"] += 1
                for k in quote_struct_risk(q):      # r9 结构性收紧：只移出低风险（R-*），不硬拦
                    flags[k] = True
            continue
        lm = SOURCE_LINE_RE.match(s)
        if lm:
            line_err, kinds = None, []
            for raw_rel, url in PAIR_RE.findall(lm.group("srcs")):
                e, kind, _ = ctx.check_pair(raw_rel, url)
                kinds.append(kind); line_err = line_err or e
            if line_err:
                err(line_err, i)
            else:
                counts["source_links"] += 1
            _x_flags(kinds, counts, flags, err, i, card_type, assertion=False)   # 纯来源链接行不是断言
            continue
        # 以下都不在低风险结构白名单内（结构化断言、列表、表格、段落……）：照常做来源与硬拦检查，但一律非低风险
        flags["structure_other"] = True; counts["other"] += 1
        sm = STRICT_ASSERT_RE.match(s)
        if sm:
            counts["assertions"] += 1; counts["structured"] += 1
            if is_macro_doc:
                counts["macro"] += 1
            claim = sm.group("claim")
            line_err, kinds, supported, nonx_ok, loc_err = None, [], True, False, None
            for m in LOC_PAIR_RE.finditer(sm.group("srcs")):
                raw_rel, url, loc = m.group(1), m.group(2), m.group("loc")
                e, kind, sup = ctx.check_pair(raw_rel, url, claim=claim)
                kinds.append(kind)
                supported = supported and sup
                if e:
                    line_err = line_err or e
                    continue
                if kind == "x":
                    continue          # X 只作线索：带不带位置都不能支撑断言
                if loc is None:
                    if card_type == "daily":
                        loc_err = loc_err or "E-SUPPORT-LOCATOR-MISSING"
                    continue
                ok, hints = support_at(ctx.last_scopes, kind, claim, loc, fred_units=ctx.last_units)
                for h in hints:
                    flags[h] = True
                if ok:
                    nonx_ok = True
                elif card_type == "daily":
                    loc_err = loc_err or "E-SUPPORT-LOCATOR-MISMATCH"
            if line_err:
                err(line_err, i)
            else:
                counts["replayable"] += 1
                if not supported:
                    flags["unsupported"] = True
                if loc_err:
                    err(loc_err, i)
            _x_flags(kinds, counts, flags, err, i, card_type, nonx_supported=nonx_ok if not line_err else None)
            continue
        is_list = bool(LIST_RE.match(s) or QUOTE_RE.match(s) or TABLE_RE.match(s))
        is_table_header = (TABLE_RE.match(s) and i < len(lines) and TABLE_SEP_RE.match(lines[i] or "x"))
        has_src = bool(RAW_RE.search(s) or URL_RE.search(s))
        if is_list and not is_table_header:
            counts["assertions"] += 1
            if is_macro_doc:
                counts["macro"] += 1
            flags["unstructured"] = True
            if not (RAW_RE.search(s) and URL_RE.search(s)):
                flags["inference_unclear"] = True
                counts["unclear"] += 1
                body_err("E-INFER-UNCLEAR", i)        # 无来源、又无法判别是否含推断 → UNCLEAR（不发布）
                if infer(s) or CLAIM_TOKEN_RE.search(LIST_RE.sub("", s, count=1)):
                    body_err("E-REPLAY-001", i)       # 含推断/转述词或数字却无来源 → FAIL
                continue
            _check_loose_sources(ctx, s, i, err, counts, flags, count_replay=True, card_type=card_type)
            continue
        # 普通段落、表头、front matter 等：可发布文字，非低风险
        flags["free_text"] = True; counts["free_text"] += 1
        self_only = has_src and not RAW_RE.search(s) and all(SELF_LINK_RE.match(u) for u in URL_RE.findall(s))
        if has_src:
            _check_free_text_sources(ctx, s, i, err, counts, flags, card_type)
        if self_only and not (in_fm or disclaimer or is_table_header):
            # 整体验收 r3 HIGH：本组织说明链接不是来源，不能解除无来源检查——含推断或数字 → 硬错
            # （只有“详见 <链接>”这类不含断言的指引行仍放行）
            if infer(s) or CLAIM_TOKEN_RE.search(URL_RE.sub("", s)):
                flags["inference_unclear"] = True; counts["unclear"] += 1
                body_err("E-INFER-UNCLEAR", i); body_err("E-REPLAY-001", i)
        elif has_src:
            pass
        elif in_fm or disclaimer or is_table_header:
            if infer(s):                    # front matter 字段、免责声明、表头不算事实陈述，但带推断仍硬错
                err("E-REPLAY-001", i)
            elif not disclaimer and CLAIM_TOKEN_RE.search(_fm_value(s, fm_parsed, raw_lines[i - 1]) if in_fm else s):
                err("E-REPLAY-001", i)       # front matter / 表头里无来源的数字 → 硬错误（日期字段除外）
        else:
            # 无来源块规则（与列表同）：无来源的段落一律 UNCLEAR（不发布，有批准记录也不行）；
            # 含推断/转述词或数字 → 硬错误
            flags["inference_unclear"] = True; counts["unclear"] += 1
            body_err("E-INFER-UNCLEAR", i)
            if infer(s) or CLAIM_TOKEN_RE.search(s):
                body_err("E-REPLAY-001", i)

    # —— 整篇（跨行）层面
    if terms and not flags["internal"] and has_any(doc_compact, terms):
        flags["internal"] = True; err("E-BLOCK-INTERNAL", 0)
    if any(r.search(doc_compact) for r in FUND_RES) or has_any(doc_compact, LEX["invest"]) or en_alloc_position(text):
        if not any(e["code"] == "E-BLOCK-INVEST" for e in errors):
            err("E-BLOCK-INVEST", 0)
    if is_macro_doc and macro_block("\n".join(m for m, q in zip(mlines, mquote) if not q)) \
            or is_macro_doc and macro_block("\n".join(m for m, q in zip(mlines, mquote) if q), quote=True):
        if not any(e["code"] == "E-BLOCK-MACRO-OPINION" for e in errors):
            err("E-BLOCK-MACRO-OPINION", 0)
    if not flags["has_inference"] and infer("\n".join(mlines) if is_macro_doc else doc_compact):
        flags["has_inference"] = True
    if not flags["medical"] and (has_any(doc_compact, LEX["medical"]) or med_ascii.search(norm(text))):
        flags["medical"] = True
    if not flags["stock"] and has_any(doc_compact, LEX["stock"]):
        flags["stock"] = True
    if not flags["religion"] and has_any(doc_compact, LEX["religion"]):
        flags["religion"] = True
    # 双语规则（t141u，经 Grok Bot 转达）：出现“译文：”行即 R-TRANSLATION，不算低风险
    if any(TRANSLATION_RE.search(norm(ln)) for ln in text.splitlines()):
        flags["translation"] = True

    # —— 链接能否打开（只对已通过回放检查的来源 URL）
    if ctx.urls:
        if link_checker is None:
            flags["link_unchecked"] = True
        else:
            for u in ctx.urls:
                try:
                    ok = link_checker(u) is True
                except Exception:   # noqa: BLE001 —— 检查器异常按打不开处理
                    ok = False
                if not ok:
                    flags["link_unreachable"] = True
                    break

    if counts_decl:
        for k, v in counts_decl.items():
            if v != counts[k]:
                err("E-COUNT-001"); break
    return _result(errors, flags, counts, meta)


# —— 原文支持位置核对（#32 r2）
LOC_SHORT = 20        # 位置片段少于 20 个非空白字符 → R-LOCATOR-SHORT 提示（太短容易断章取义）
_UNIT_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(%|％|percentage points?|个百分点|percent|per cent|倍|×|x(?![A-Za-z])|times|-fold|fold)?", re.I)
_UNIT_CLASS = {"%": "pct", "％": "pct", "percent": "pct", "per cent": "pct",
               "个百分点": "pp", "percentage point": "pp", "percentage points": "pp",
               "倍": "mult", "×": "mult", "x": "mult", "times": "mult", "-fold": "mult", "fold": "mult"}
_POLAR_NEG_ZH = ("未能", "尚未", "未", "没有", "没", "并非", "不是", "无法", "不能", "不会", "不")
_POLAR_NEG_ZH_OK = ("不同", "不断", "不少", "不仅", "不久", "不过", "不论")   # 含“不”但不是否定
_POLAR_NEG_EN = re.compile(r"\b(?:not|no|never|cannot|without|unable|fail(?:s|ed)?\s+to|did\s+not|does\s+not|n't)\b|n't", re.I)
_CAP_NAME_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z][a-z][A-Za-z0-9\-]*(?![A-Za-z0-9])")   # Llama、Gemini 这类单大写字母专名
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _units(s):
    """数字 → 单位类别集合（pct / pp / mult / None）。"""
    out = {}
    for m in _UNIT_RE.finditer(_THOUSANDS.sub("", norm(s))):
        u = m.group(2)
        out.setdefault(m.group(1).rstrip("."), set()).add(_UNIT_CLASS.get((u or "").lower(), None) if u else None)
    return out


def _fred_unit_class(u):
    """FRED 序列元数据的 units 字段 → 单位类别。None 表示拿不到单位。"""
    if not isinstance(u, str) or not u.strip():
        return None
    l = u.lower()
    if "percentage point" in l:
        return "pp"
    if "percent" in l:
        return "pct"
    return "level"     # Index、Billions of Dollars、Thousands of Persons 等：不是百分比，也不是倍数


_OBJ_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z][A-Za-z0-9\-]*(?![A-Za-z0-9])")   # Model、B、MMLU、Llama 这类对象词


def _has_word(w, s):
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(w) + r"(?![A-Za-z0-9])", s) is not None


def _clause_spans(s):
    """按 numnorm.CLAUSE_RE 切分句，返回各分句在 s 中的 (起, 止)。"""
    spans, start = [], 0
    for m in numnorm.CLAUSE_RE.finditer(s):
        if s[start:m.start()].strip():
            spans.append((start, m.start()))
        start = m.end()
    if s[start:].strip():
        spans.append((start, len(s)))
    return spans


def _min_windows(s, ok):
    """r5：含全部关键项的最小连续分句窗口。从 1 个分句起逐步加宽，返回第一档宽度下所有符合的窗口文本。"""
    spans = _clause_spans(s)
    for k in range(1, len(spans) + 1):
        hits = [s[spans[i][0]:spans[i + k - 1][1]] for i in range(len(spans) - k + 1)
                if ok(s[spans[i][0]:spans[i + k - 1][1]])]
        if hits:
            return hits
    return []


def _neg_main(s):
    """挖掉 without/无需 短语与审慎说法后的主干，及挖掉的审慎说法个数。"""
    main, _ = numnorm.strip_scoped(s)
    main, nh = numnorm.strip_hedges(main)
    return main, nh


_PAIR_STOP = frozenset("the a an of in on to and or but for with by from that this these those is are was were be been "
                       "it its their they them we our as at than then also however while".split())


def _pair_words(s):
    """无数字、无代号分句配对用：小写普通词（3 个字母以上，去停用词）加区分大小写的对象词（Model、B、MMLU）。"""
    return ({w.lower() for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", s)} - _PAIR_STOP) | {"@" + w for w in _OBJ_RE.findall(s)}


def _neg_state(seg):
    """(否定奇偶, 是否带审慎说法)。"""
    m, h = _neg_main(seg)
    return numnorm.neg_count(m) % 2, h > 0


def _neg_parity_ok(claim, loc, kind=None):
    """#32 r4/r5：按具体说法核对否定，不整行判断。返回 (是否成立, 提示集合)。
    1. without / 无需 只否定后面的动作：先挖出这类短语（numnorm.strip_scoped）。断言里有、原文里没有 → 错配；
       原文有、断言没写同样的短语 → 提示 support_scope（R-SUPPORT-SCOPE，人工必查：断言是否写成了相反前提，
       如原文 without fine-tuning、断言“经过微调”）。
    2. 断言每个含数字、代号或对象词的分句，先按对象配对：
       - 普通文本（r5，审查 r4 HIGH）：在原文里找同时含这些数字、代号和对象词的最小连续分句窗口；
         窗口不唯一或找不到 → 错配（不再退回整段，避免把 A 的否定配给 B）；
       - FRED（kind == "fred"）：片段是“字段,数值”式，仍允许没有单句含全部关键项时按整个片段比较；多句都配得上 → 错配。
       不含数字和代号的分句合起来，与原文去掉已配对窗口后的剩余部分比（r5，dry run 发现）。
    3. 比较挖掉短语后主干的否定词个数奇偶（双重否定抵消；no longer、难以、从未、hardly、yet to 等计为否定）。
       审慎/待定说法（有待修订、尚未经同行评审、yet to be peer reviewed…）不计否定，出现就提示 support_hedge
       （R-SUPPORT-HEDGE）；但配对的原文窗口带审慎说法而整条断言没有，或断言分句带审慎说法而整个片段没有 → 错配；“难以置信”“无与伦比”“从未如此”“never before”等固定说法不算否定（r5，审查 r4 MEDIUM）。"""
    hints = set()
    loc_main, loc_scoped = numnorm.strip_scoped(loc)
    claim_scoped = numnorm.strip_scoped(claim)[1]
    if claim_scoped > loc_scoped:
        return False, hints
    if loc_scoped > claim_scoped:
        hints.add("support_scope")
    claim_hedged, loc_hedged = numnorm.strip_hedges(claim)[1] > 0, numnorm.strip_hedges(loc)[1] > 0
    if claim_hedged or loc_hedged:
        hints.add("support_hedge")
    lclauses = numnorm.clauses(loc) or [loc]
    rest_claim, rest_loc = [], loc
    for cc in numnorm.clauses(claim) or [claim]:
        keys_n = numbers(numnorm.bp_to_pp(numnorm.normalize_numbers(cc)[0]))
        keys_t = [t.lower() for t in claim_terms(cc)]
        objs = [w for w in _OBJ_RE.findall(cc) if _has_word(w, loc)]
        if not (keys_n or keys_t):
            rest_claim.append(cc)          # 不含数字和代号的分句：放到最后与原文剩余部分一起比
            continue

        def has_all(seg):
            return (keys_n <= numbers(numnorm.bp_to_pp(numnorm.normalize_numbers(seg)[0]))
                    and all(t in seg.lower() for t in keys_t) and all(_has_word(w, seg) for w in objs))
        if kind == "fred":
            cands = [lc for lc in lclauses if has_all(lc)]
            if len(cands) > 1:
                return False, hints          # 多句都配得上，分不清对象 → 错配
            target = cands[0] if cands else loc
        else:
            wins = _min_windows(loc, has_all)
            if len(wins) != 1:
                return False, hints          # 配不上或配出多个窗口，分不清对象 → 错配
            target = wins[0]
            rest_loc = rest_loc.replace(target, " ", 1)
        cc_main, cc_h = _neg_main(cc)
        tg_main, tg_h = _neg_main(target)
        if numnorm.neg_count(cc_main) % 2 != numnorm.neg_count(tg_main) % 2:
            return False, hints
        # 审慎说法不计否定，但不能凭空丢掉或加上：配对的原文窗口带审慎说法而整条断言没有（“尚待验证”写成“已经验证”），
        # 或断言分句带审慎说法而整个片段没有 → 错配
        if tg_h and not claim_hedged or cc_h and not loc_hedged:
            return False, hints
    # r5：不含数字和代号的分句逐句配对：在原文去掉已配对窗口后的剩余分句里，按普通词与对象词重合度找唯一候选；
    # 找不到唯一候选时，剩余分句否定/审慎状态全都相同才可比，否则判错配（不能只比合并奇偶，见 r5 审查 HIGH）。
    if rest_claim:
        lrest = [c for c in (numnorm.clauses(rest_loc) or []) if re.search(r"[A-Za-z0-9\u4e00-\u9fff]", c)]
        states = {_neg_state(c) for c in lrest} or {(0, False)}
        for cc in rest_claim:
            cw = _pair_words(cc)
            scored = sorted(((len(cw & _pair_words(lc)), lc) for lc in lrest), key=lambda t: -t[0])
            cstate = _neg_state(cc)
            if scored and scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                if cstate != _neg_state(scored[0][1]):        # 唯一配对：否定奇偶与审慎说法都要一致
                    return False, hints
            elif len(states) == 1:
                tstate = next(iter(states))
                if cstate[0] != tstate[0] or cstate[1] and not loc_hedged or tstate[1] and not claim_hedged:
                    return False, hints
            else:
                return False, hints                            # 配不上且剩余分句状态不一 → 分不清对象
    return True, hints


def support_at(scopes, kind, claim, loc, fred_units=None):
    """原文支持位置核对（#32）。返回 (是否成立, 提示标记集合)。
    硬性条件（不成立 → E-SUPPORT-LOCATOR-MISMATCH）：
      1. 片段是所引条目原文的连续子串；
      2. 数值先规范化（中文数字、百分之、成数、billion/亿 等量级换算），断言中的数字全部出现在片段里；
         断言里有解析不了的中文数值（如“百分之九十几”“三成多”）→ 不成立（宏观算式稿验算通过的推导值除外）；
      3. 单位与倍数一致：% 与“倍”不能互换，% 与“个百分点”不能互换；FRED 用存档的序列单位（<ID>.series.json，
         须登记在 MANIFEST）核对，拿不到单位时带单位的断言不成立；
      4. 否定按对象配对分句后核对（见 _neg_parity_ok）；基点按 100 bp = 1 个百分点换算；
      5. 断言中的指标/对象代号（两个以上大写字母或含数字，如 MMLU、GSM8K、GPT-4）全部出现在片段里。
    提示（R-*，不硬拦，交 Codex 逐条核对）：support_review（每条通过的断言都带）、locator_short、entity_unchecked、
    support_scope（原文 without/无需 短语断言没写，人工必查）、support_hedge（审慎/待定说法不计否定）。"""
    hints = set()
    if not quote_in_source(scopes, loc):
        return False, hints
    c = norm(claim)
    if kind == "fred":
        c = _CLAIM_DATE_RE.sub(" ", _VINTAGE_RE.sub(" ", c))
    fms = list(FORMULA_RE.finditer(c))
    derived = bool(_FORMULA_MARK_RE.search(c) and fms and all(verify_formula(fm.group(0)) for fm in fms))
    cn, c_unparsed = numnorm.normalize_numbers(c)
    ln, _ = numnorm.normalize_numbers(norm(loc))
    cn, ln = numnorm.bp_to_pp(cn), numnorm.bp_to_pp(ln)     # r4：100 bp = 1 个百分点
    if not derived:
        if c_unparsed or not numbers(cn) <= numbers(ln):
            return False, hints
        cu = _units(cn)
        if kind == "fred":
            fc = _fred_unit_class(fred_units)
            for n, us in cu.items():
                for u in us - {None}:
                    if fc is None or u != fc:
                        return False, hints
        else:
            lu = _units(ln)
            for n, us in cu.items():
                for u in us - {None}:
                    if u not in lu.get(n, set()):
                        return False, hints
    ok_neg, neg_hints = _neg_parity_ok(c, norm(loc), kind)
    if not ok_neg:
        return False, hints
    lt = norm(loc).lower()
    if not all(t.lower() in lt for t in claim_terms(c)):
        return False, hints
    hints.add("support_review")
    hints |= neg_hints
    if len(compact(loc)) < LOC_SHORT:
        hints.add("locator_short")
    if _CJK_RE.search(c) or any(t.lower() not in lt for t in _CAP_NAME_RE.findall(c)):
        hints.add("entity_unchecked")
    return True, hints


_FORMULA_MARK_RE = re.compile(r"由原始数据计算|按原始数据计算")


def _x_flags(kinds, counts, flags, err, line, card_type, assertion=True, nonx_supported=None):
    """唯一的 X-only 判定（r7：所有取来源的入口都必须调用本函数，err/line/card_type 为必填参数）。
    取来源的入口：原文直引行、纯来源链接行、结构化断言行、带来源的非结构化行（_check_loose_sources）、
    段落/标题/HTML 注释里的来源（_check_free_text_sources）。
    来源全部为 X → R-X-ONLY；card_type == "daily" 且该行是断言（assertion=True）→ 另判 E-X-ONLY 硬拦。
    只有纯来源链接行（“来源：…”，不含任何断言文字）传 assertion=False，仍只标 R-X-ONLY。
    #32（迁移自旧库 #51）：nonx_supported 为 False 时（有 X 来源，但没有任何非 X 来源经核对实际支撑该断言），
    日报断言同样判 E-X-ONLY；不再只看来源种类。None 表示调用方未做支撑核对（来源本身已报错）。"""
    if "x" in kinds:
        counts["x_sourced"] += 1
        x_only = all(k == "x" for k in kinds)
        if x_only:
            flags["x_only"] = True   # X 只是线索，不能单独成为低风险来源
        if assertion and card_type == "daily" and (x_only or nonx_supported is False):
            # r6（协调方 Grok Bot 定）：日报里的断言只有 X 来源支撑 → 硬拦。X 只作线索。
            err("E-X-ONLY", line)


SELF_LINK_RE = re.compile(r"^https://github\.com/markjin-lab/[A-Za-z0-9._/#-]+$")


_FM_DATE_RE = re.compile(r"^['\"]?\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?['\"]?$")


def _real_datetime(v):
    v = v.strip().strip("'\"")
    try:
        if len(v) == 10:
            _dt.date.fromisoformat(v)
        else:
            _dt.datetime.fromisoformat(v.replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return False
    return True


TONGYI_TYPE = "tongyi"
# 长文豁免的日报专用断言句式码（整体验收 r15）：无来源段落/列表的 UNCLEAR 与“含推断或数字却无来源”
LONGFORM_EXEMPT_CODES = frozenset({"E-INFER-UNCLEAR", "E-REPLAY-001"})


def is_tongyi_path(rel):
    """路径属于 tongyi 栏目：markjin-data 的 tongyi/<name>[.en].md，或站点的 content/posts/tongyi/<name>[.en].md。"""
    if not isinstance(rel, (str, Path)):
        return False
    parts = PurePosixPath(str(rel).replace("\\", "/")).parts
    if ".." in parts:
        return False
    return (len(parts) == 2 and parts[0] == "tongyi" and parts[1].endswith(".md")) or \
        (len(parts) == 4 and parts[:3] == ("content", "posts", "tongyi") and parts[3].endswith(".md"))


def _fm_parsed(fm_lines):
    """整体验收 r15：front matter 用 yaml.safe_load 解析一次，后续字段判断统一用解析后的值（带引号与不带引号等价）。
    解析失败或顶层不是映射 → None（分类判断另由 fm_categories fail-closed）。"""
    import yaml
    try:
        fm = yaml.safe_load("\n".join(fm_lines))
    except (yaml.YAMLError, TypeError, ValueError):
        return None
    return fm if isinstance(fm, dict) else None


def _fm_top_key(raw):
    """front matter 顶层键行（不缩进）的键名；其他行 → None。"""
    m = re.match(r"^([A-Za-z_][\w-]*)\s*:", raw or "")
    return m.group(1) if m else None


def _iso(v):
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.isoformat()
    return v if isinstance(v, str) else None


def _correction_fm_ok(raw, fm_parsed):
    """更正稿元数据行：按解析后的值判断（corrects 为 draft_id 格式字符串；corrected_at 为真实日期 YYYY-MM-DD），
    带不带引号都一样。"""
    k = _fm_top_key(raw)
    if not isinstance(fm_parsed, dict) or k not in ("corrects", "corrected_at") or k not in fm_parsed:
        return False
    v = _iso(fm_parsed[k])
    if k == "corrects":
        return isinstance(fm_parsed[k], str) and bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", v))
    return isinstance(v, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)) and _real_datetime(v)


def _fm_value(s, fm_parsed=None, raw=None):
    """front matter 行去掉键名；只有键名在日期字段白名单（lexicon fm_date_keys：date、publishDate…）里、
    且值是真实存在的日历日期/时间时，才不算数字断言。其他字段（score:、claim:…）即使值长得像日期也照常核对。"""
    tk = _fm_top_key(raw)
    if isinstance(fm_parsed, dict) and tk in fm_parsed and isinstance(_iso(fm_parsed[tk]), str):
        k, v = tk.lower(), _iso(fm_parsed[tk])        # r15：顶层键用 yaml.safe_load 解析后的值（引号不影响）
        if LEX and k in LEX["fm_date_keys"] and _FM_DATE_RE.match(v) and _real_datetime(v):
            return ""
        return v
    m = re.match(r"^\s*-?\s*([A-Za-z_][\w-]*)\s*:\s*(.*)$", s)
    if not m:
        return s
    k, v = m.group(1).lower(), m.group(2).strip()
    if LEX and k in LEX["fm_date_keys"] and _FM_DATE_RE.match(v) and _real_datetime(v):
        return ""
    return v


_CITE_PAIR = SRC_PAIR + r"(?: 〔原文[:：][^〔〕]+〕)?"
PURE_CITE_RE = re.compile(
    r"^(?:[-*+] )?(?:来源|出处|参见|另见|详见|见|sources?|see)\s*[:：]?\s*" + _CITE_PAIR
    + r"(?:\s*(?:；|;|、|与|和|及|，|,|and)\s*" + _CITE_PAIR + r")*"
    + r"(?:\s*[；;，,]?\s*(?:见|详见|参见|see)\s*https://github\.com/markjin-lab/[A-Za-z0-9._/#-]+)?\s*[。.]?$", re.I)


def _pure_citation(s):
    """#32 r3：纯来源说明只认固定格式——引导词（来源/出处/见/参见/source/see）+ 一个或多个来源对（用 ；、与 等连接），
    可再跟一个“见 <本组织仓库链接>”。其他写法一律按断言处理。位置检查与 X-only 检查共用这一个判定结果。"""
    return bool(PURE_CITE_RE.match(s.strip()))


def _check_free_text_sources(ctx, s, i, err, counts, flags, card_type):
    """段落/标题里的来源。
    - URL 只能是已知来源类型（arxiv/x/fred）或本组织仓库链接（github.com/markjin-lab/…），否则 E-REPLAY-005；
      所有 URL 都做“能否打开”检查。
    - raw 引用必须是同日目录下的文件（目录不算），且与已知来源类型 URL 按出现顺序一一配对，
      每对按结构化断言同样的规则回放（同类型目录、MANIFEST 哈希、ID 在存档中）；不成对 → E-REPLAY-006。
      本组织仓库链接不参与配对（它们是说明性链接，不是来源）。"""
    urls = URL_RE.findall(s)
    for url in urls:
        if not (SELF_LINK_RE.match(url) or any(rx.match(url) for rx in URL_KINDS.values())):
            err("E-REPLAY-005", i); return
        if url not in ctx.urls:
            ctx.urls.append(url)
    raws = RAW_RE.findall(s)
    for raw_rel in raws:
        parts = PurePosixPath(raw_rel).parts
        if ".." in parts or len(parts) < 2 or parts[1] != ctx.date:
            err("E-REPLAY-006", i); return
        if not ctx.repo.joinpath(*parts).is_file():
            err("E-REPLAY-002", i); return       # 必须是文件（目录不算来源）
    src_urls = [u for u in urls if not SELF_LINK_RE.match(u)]
    if not raws and not src_urls:
        return
    if len(raws) != len(src_urls):
        err("E-REPLAY-006", i); return
    kinds, nonx_ok, loc_err = [], False, None
    claim = _claim_of(s)
    # #32 r2：段落/标题/注释里的每个非 X 来源，URL 后面都必须紧跟 〔原文：…〕 并核对通过；不再“有非 X 来源就算支撑”
    locs = {m.start(1): m.group("loc") for m in re.finditer(r"(https?://[^\s)）`<>\]]+)" + LOCATOR, s)}
    url_pos = [m.start() for m in URL_RE.finditer(s) if not SELF_LINK_RE.match(m.group(0))]
    for (raw_rel, url), pos in zip(zip(raws, src_urls), url_pos):
        e, kind, sup = ctx.check_pair(raw_rel, url, claim=claim)   # r13：带上断言原文
        if e:
            err(e, i); return
        kinds.append(kind)
        if numbers(claim) and not sup:
            flags["unsupported"] = True
        if kind == "x":
            continue
        loc = locs.get(pos)
        if loc is None:
            loc_err = loc_err or "E-SUPPORT-LOCATOR-MISSING"
            continue
        ok, hints = support_at(ctx.last_scopes, kind, claim, loc, fred_units=ctx.last_units)
        for h in hints:
            flags[h] = True
        if ok:
            nonx_ok = True
        else:
            loc_err = loc_err or "E-SUPPORT-LOCATOR-MISMATCH"
    pure = _pure_citation(s)        # 同一判定：纯来源说明既不要求位置，也不按断言判 X-only
    if loc_err and card_type == "daily" and not pure:
        err(loc_err, i)
    _x_flags(kinds, counts, flags, err, i, card_type, assertion=not pure, nonx_supported=nonx_ok)   # r7 + #32


def _check_loose_sources(ctx, s, i, err, counts, flags, count_replay=False, card_type=None):
    """非结构化行中的来源：raw 与 URL 必须一一对应（按出现顺序绑定），并逐对回放。"""
    raws, urls = RAW_RE.findall(s), URL_RE.findall(s)
    if len(raws) != len(urls) or not raws:
        err("E-REPLAY-006", i)
        return
    line_err, kinds, nonx_ok = None, [], False
    claim = _claim_of(s)
    for raw_rel, url in zip(raws, urls):
        e, kind, sup = ctx.check_pair(raw_rel, url, claim=claim)   # r13：带上断言原文
        kinds.append(kind)
        line_err = line_err or e
        if not e and numbers(claim) and not sup:
            flags["unsupported"] = True
    if line_err:
        err(line_err, i)
    elif count_replay:
        counts["replayable"] += 1
        if card_type == "daily" and any(k != "x" for k in kinds):
            # #32：日报断言必须写明原文支持位置；非结构化行无法写，改用结构化断言格式
            err("E-SUPPORT-LOCATOR-MISSING", i)
    _x_flags(kinds, counts, flags, err, i, card_type, nonx_supported=None if line_err else nonx_ok)


SOFT = {
    "has_inference": "R-INFERENCE", "macro": "R-MACRO", "medical": "R-MEDICAL", "religion": "R-RELIGION", "stock": "R-STOCK",
    "quote_numeric": "R-QUOTE-NUMERIC", "quote_comparative": "R-QUOTE-COMPARATIVE",
    "quote_modal": "R-QUOTE-MODAL", "quote_entity": "R-QUOTE-ENTITY", "translation": "R-TRANSLATION", "x_only": "R-X-ONLY",
    "signal_card": "R-SIGNAL-CARD", "unstructured": "R-UNSTRUCTURED",
    "unsupported": "R-SUPPORT-UNVERIFIED", "link_unchecked": "R-LINK-UNCHECKED",
    "link_unreachable": "R-LINK-UNREACHABLE",
    "structure_other": "R-STRUCTURE", "quote_unverified": "R-QUOTE-UNVERIFIED",
    "support_review": "R-SUPPORT-REVIEW", "locator_short": "R-LOCATOR-SHORT", "entity_unchecked": "R-SUPPORT-ENTITY",
    "support_scope": "R-SUPPORT-SCOPE", "support_hedge": "R-SUPPORT-HEDGE",
}


UNCLEAR_CODES = ("E-INFER-UNCLEAR", "E-REPLAY-VERSION-UNCLEAR")


def _result(errors, flags, counts, meta):
    hard = sorted({e["code"] for e in errors})
    soft = sorted({c for k, c in SOFT.items() if flags.get(k)})
    if not hard and counts.get("replayable", 0) < 1:
        soft = sorted(set(soft) | {"R-NO-ASSERTION"})
    fail = [c for c in hard if c not in UNCLEAR_CODES]
    status = "FAIL" if fail else ("UNCLEAR" if set(hard) & set(UNCLEAR_CODES) else "PASS")
    r = {"status": status, "error_codes": hard + soft, "errors": errors, "flags": flags,
         "counts": dict(counts, errors=len(errors)), "card_type": meta["card_type"], "date": meta["date"]}
    r["low_risk"] = compute_low_risk(r)
    return r


def compute_low_risk(r) -> bool:
    """结构白名单（王总 10-11 定）：日报稿正文每个非空行都是 标题（固定栏目名）/ 原文直引（逐字核对通过）/ 来源链接，
    至少 1 条原文直引；无硬错误；不允许任何审查原因码（ANNOTATION_CODES 为空，R-INFERENCE 也不例外）；标记全为 False。
    任何字段缺失、类型不对或为 None 都返回 False。"""
    try:
        c, f = r["counts"], r["flags"]
        codes = [x for x in r["error_codes"] if x not in ANNOTATION_CODES]
        return (r["status"] == "PASS" and codes == [] and r["card_type"] == "daily"
                and valid_date(r["date"])
                and all(f[k] is False for k in FLAG_KEYS if k not in ANNOTATION_FLAGS)
                and all(type(f[k]) is bool for k in ANNOTATION_FLAGS)
                and type(c["quotes"]) is int and c["quotes"] >= 1
                and c["other"] == 0 and c["errors"] == 0)
    except (KeyError, TypeError):
        return False


_TAG = re.compile(r"<[^>]+>")
_ARXIV_ENTRY = re.compile(r"<entry\b.*?</entry>", re.S)
_ARXIV_ID_TEXT = re.compile(r"https?://arxiv\.org/abs/(\d{4}\.\d{4,5})(v\d+)?")
_ARXIV_ID = re.compile(r"<id>\s*https?://arxiv\.org/abs/(\d{4}\.\d{4,5})(v\d+)?\s*</id>")


# 更正稿 front matter（Grok Bot 定，2026-10-11）。整体验收 r15 起识别改用 yaml.safe_load 解析后的值（_correction_fm_ok），
# 本正则只保留作文档参考
CORRECTION_FM_RE = re.compile(r"(?:corrects:[ ]?[a-z0-9]+(?:-[a-z0-9]+)+|corrected_at:[ ]?\d{4}-\d{2}-\d{2})")


# r7 BLOCKER 2（医疗兜底，Grok Bot 定从严）：front matter 中这些键的取值只要含医疗标记（lexicon medical_markers：医疗、中医、
# health、medicine、TCM…），整篇按医疗类处理（R-MEDICAL → 需王总批准）。脚本只拦已知的词和标记；其余由 Codex 判，
# Codex 判为医疗类（记录 category=medical）同样需要王总批准（route.needs_wang）。
# 分类键定义在 fmkeys.FM_CATEGORY_KEYS（与 route 共用，整体验收 r10）。


def medical_ascii_re():
    """英文简称/短词（TCM、herbal、qigong…）按词边界匹配，避免 compact 后误中（如 “at CMU” → atcmu）。"""
    return re.compile(r"\b(" + "|".join(re.escape(t) for t in LEX["medical_ascii"]) + r")\b", re.I)


def fm_categories(fm_lines, flags=None):
    """r8 BLOCKER 1：front matter 先用 yaml.safe_load 解析，再按解析结果判定分类（不再逐行读原文）。
    返回 (medical, bad)：
      bad=True —— 出现 YAML 锚点（&）、别名（*）或合并键（<<），或 YAML 解析失败 / 顶层不是映射：fail-closed，
      调用方记 E-SELFCHECK-FM-ALIAS（硬错误）并同时按医疗类处理；
      medical=True —— 顶层分类键（FM_CATEGORY_KEYS，大小写不敏感）的取值（含嵌套列表/映射里的任何字符串）含医疗标记。"""
    import yaml
    src = "\n".join(fm_lines)
    try:
        for tok in yaml.scan(src):
            if isinstance(tok, (yaml.AnchorToken, yaml.AliasToken)):
                return True, True
            if isinstance(tok, yaml.ScalarToken) and tok.value == "<<":
                return True, True
        fm = yaml.safe_load(src)
    except (yaml.YAMLError, TypeError, ValueError):
        return True, True
    if fm is None:
        return False, False
    if not isinstance(fm, dict):
        return True, True
    marks = LEX["medical_markers"] + LEX["medical"]
    asc = medical_ascii_re()

    def strings(v):
        if isinstance(v, dict):
            for k, x in v.items():
                yield str(k); yield from strings(x)
        elif isinstance(v, (list, tuple, set)):
            for x in v:
                yield from strings(x)
        elif v is not None:
            yield str(v)

    med = False
    for k, v in fm.items():
        if str(k).lower() in FM_CATEGORY_KEYS:
            for t in strings(v):
                if has_any(t, marks) or asc.search(norm(t)):
                    med = True
                # r9 BLOCKER：解析出的类别全部参与类型判定——宏观、宗教类别同样置位（与正文词表取并集）
                if flags is not None:
                    if has_any(t, LEX["macro"]) or re.search(r"\bmacro", t, re.I):
                        flags["macro"] = True
                    if has_any(t, LEX["religion"]) or re.search(r"religio|宗教", t, re.I):
                        flags["religion"] = True
    return med, False


_FRED_BAD_ID = ("<invalid series id>",)   # 存在但类型无效的自报 ID：与任何 URL ID 都不相等


def _fred_ids(o):
    """FRED JSON 中自报的系列 ID：顶层/任意对象的 series_id，或 seriess[].id。
    r7 MEDIUM 2：区分“字段不存在”和“字段存在但类型无效”。series_id 不是非空字符串、seriess 不是列表、
    seriess 的元素不是带字符串 id 的对象，都记为无效 ID（→ E-REPLAY-004），不再当成“未自报”而退回按文件名绑定。"""
    out = set()
    if isinstance(o, dict):
        if "series_id" in o:
            v = o["series_id"]
            out.add(v if isinstance(v, str) and v else _FRED_BAD_ID)
        if "seriess" in o:
            ss = o["seriess"]
            if not isinstance(ss, list):
                out.add(_FRED_BAD_ID)
            else:
                for it in ss:
                    if isinstance(it, dict) and isinstance(it.get("id"), str) and it["id"]:
                        out.add(it["id"])
                    else:
                        out.add(_FRED_BAD_ID)
        for v in o.values():
            if isinstance(v, (dict, list)):
                out |= _fred_ids(v)
    elif isinstance(o, list):
        for v in o:
            out |= _fred_ids(v)
    return out


def _has_symlink(repo, parts):
    p = Path(repo)
    for x in parts:
        p = p / x
        if p.is_symlink():
            return True
    return False


def select_entries(text, kind, sid, ver=None):
    """按“自身 id 字段”精确选择条目，返回可引用正文列表；解析失败返回 None。
    arxiv：<entry> 的 <id> 基础 ID 必须等于 sid；URL 带版本时版本也必须相同（v1 存档不配 v2 链接）。
           正文域为 <title> 与 <summary>（各自独立，不跨字段拼接）。
    x：JSON 中 "id" 字段（字符串或整数）等于 sid 的对象；正文域为其 text / full_text / note_tweet.text。"""
    out = []
    if kind == "arxiv":
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return None
        local = lambda el: el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""
        entries = [root] if local(root) == "entry" else [c for c in root if local(c) == "entry"]
        vers = set()
        for e in entries:
            kids = list(e)
            ids = [c for c in kids if local(c) == "id"]            # 只认 entry 的直接子节点 <id>，嵌套的不算
            if len(ids) != 1:
                continue
            m = _ARXIV_ID_TEXT.fullmatch((ids[0].text or "").strip())
            if not m:
                continue
            base, v = m.group(1), m.group(2) or ""
            if base != sid or (ver and v != ver):
                continue
            vers.add(v)
            for c in kids:
                if local(c) in ("title", "summary"):
                    out.append(" ".join("".join(c.itertext()).split()))
        if not ver and len(vers) > 1:
            return "AMBIGUOUS"                                      # 链接无版本且存档有多个版本
        return out
    try:
        data = strictjson.loads(text)   # r11：原始 JSON 重复键 → 视为不可解析，引文无法回放（判失败）
    except ValueError:
        return None

    def walk(o):
        if isinstance(o, dict):
            if "id" in o and isinstance(o["id"], (str, int)) and not isinstance(o["id"], bool) and str(o["id"]) == sid:
                for k in ("text", "full_text"):
                    if isinstance(o.get(k), str):
                        out.append(o[k])
                nt = o.get("note_tweet")
                if isinstance(nt, dict) and isinstance(nt.get("text"), str):
                    out.append(nt["text"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    return out


# 否定词 / 限定词（中英）：直引若不是完整句子，原文中引文所在句的其余部分不得含这些词
NEG_EN = ("not", "no", "never", "n't", "nor", "none", "cannot", "without", "only", "only if", "unless",
          "except", "if", "but", "although", "though", "hardly", "barely", "rarely", "fail to", "fails to",
          "does not", "do not", "did not", "is not", "are not", "neither", "only when", "provided", "may", "might", "could")
NEG_ZH = ("不", "未", "没有", "没", "无", "非", "并非", "不是", "仅", "仅在", "只有", "只在", "除非", "除了", "若", "如果",
          "假如", "但", "但是", "可能", "或许", "尚未", "从未", "无法", "未能", "别", "勿", "否", "除外", "前提", "仅当")
_SENT_END = ".。!?！？;；"        # 否定窗口不跨这些标点
_FULL_END = ".。!?！？"           # 完整句子只认句号/问号/叹号；分号、逗号不算句末


NEG_WIN_EN, NEG_WIN_ZH = 3, 4     # 向前看：英文 3 个词、中文 4 个字（跨过中间的副词），不跨句


def _neg_in(seg):
    seg = seg.lower()
    words = re.findall(r"[a-z]+(?:'[a-z]+)?", seg)
    wtxt = " " + " ".join(words) + " "
    if any(x.endswith("n't") for x in words):
        return True
    if any(" " + w + " " in wtxt for w in NEG_EN if w != "n't"):
        return True
    zh = re.sub(r"[\sA-Za-z0-9]", "", seg)
    return any(w in zh for w in NEG_ZH)


# 分句器（r9）：中文句号/问号/叹号随处是句末；英文 . ! ? 只有后面紧跟空白或文本结束时才是句末，
# 所以小数点（2.0、66.7%）、版本号、域名中的点都不会把句子断开。
_SENT_END_RE = re.compile(r"[。！？]|[.!?](?=\s|$)")


def _last_sent_end(text):
    """text 中最后一个句末标点之后的位置（无则 0）。"""
    last = 0
    for m in _SENT_END_RE.finditer(text):
        last = m.end()
    return last


def _first_sent_end(text):
    m = _SENT_END_RE.search(text)
    return m.start() if m else len(text)


def _adjacent_neg(before, after):
    """按句判断（r8/r9）：引文不是完整句子时，引文所在句中“引文之前的部分”和“引文之后直到句末的部分”
    都不得出现否定/限定词。句子边界由 _SENT_END_RE 判定（不在数字中间断开）。"""
    head = before[_last_sent_end(before):]
    tail = after[:_first_sent_end(after)]
    return _neg_in(head) or _neg_in(tail)


def _is_full_sentence(before, q, after):
    """完整句：引文之前为空或以句末结束，引文本身以句末标点结束且该标点在原文中确是句末（后接空白或结束）。"""
    b = before.rstrip()
    starts = not b or _last_sent_end(b) == len(b)
    ends = bool(_SENT_END_RE.search(q.rstrip()[-1:] + (after[:1] or " "))) and q.rstrip()[-1:] in _FULL_END
    return starts and ends


# —— r9 结构性收紧：原文直引出现以下任一结构即移出低风险（只记 R-*，不硬拦）。不再逐个补词。
_Q_NUMERIC = re.compile(
    r"\d|[%％‰$€£¥￥]|分之|[零一二三四五六七八九十百千万亿两半几]+(?:成|倍|个百分点)|百分之|"
    r"(?:元|美元|美分|港元|日元|欧元|英镑|块钱|角|分钱)|每股|股价|价格|报价|收于|收盘|开盘|市值|"
    r"\b(?:dollars?|cents?|usd|eur|gbp|jpy|yuan|price[sd]?|pricing|valuation|per\s+share|"
    r"half|third|quarter|percent|percentage|basis\s+points?|bps|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"hundred|thousand|million|billion|trillion|dozen|twice|double|triple)\b", re.I)
_Q_COMPARATIVE = re.compile(
    r"\b(?:\w+er\s+than|than|more|less|most|least|better|best|worse|worst|superior|inferior|outperform\w*|"
    r"underperform\w*|exceed\w*|surpass\w*|beat[s]?|beating|higher|lower|greater|fewer|stronger|weaker|"
    r"faster|slower|improv\w*|advantage\w*|state[- ]of[- ]the[- ]art|sota|leading|top)\b|"
    r"比|优于|劣于|胜过|超过|超越|高于|低于|强于|弱于|不如|更|最|领先|落后|提升|改善|最佳|最好|最强", re.I)
_Q_MODAL = re.compile(
    r"\b(?:will|would|shall|should|can|could|may|might|must|ought|need(?:s|ed)?\s+to|going\s+to|"
    r"likely|unlikely|expect\w*|forecast\w*|predict\w*|project(?:s|ed|ion)?|anticipat\w*|"
    r"\w+'ll|won't|can't|cannot|shouldn't|wouldn't|couldn't)\b|"
    r"将|会|应该|应当|应会|该当|须|必须|必将|必然|需要|可能|可以|可望|能够|或将|或许|势必|拟|预计|预期|预测|有望|恐将|宜", re.I)
_Q_ENTITY = re.compile(
    r"\b[A-Z][A-Z0-9&.\-]{1,}\b|"                       # 全大写词 / 股票代号（NVIDIA、AAPL、S&P）
    r"(?<=[a-z0-9,;:)]\s)[A-Z][a-z]+(?:[A-Z][a-z]*)*\b|"   # 句中大写开头的词（专有名词：公司、机构、人名）
    r"\b[A-Z][a-z]+[A-Z]\w*\b|"                          # 驼峰（OpenAI、DeepMind）
    r"\$[A-Za-z]{1,5}\b|\b\d{4,6}\.(?:SH|SZ|HK|BJ)\b")


def quote_struct_risk(q):
    """原文直引的结构性风险：数字/百分比/分数/货币价格、比较级、情态/预测、大写实体或股票代号 → 对应 flag 集合。"""
    t = norm(q)
    out = set()
    if _Q_NUMERIC.search(t):
        out.add("quote_numeric")
    if _Q_COMPARATIVE.search(t):
        out.add("quote_comparative")
    if _Q_MODAL.search(t):
        out.add("quote_modal")
    if _Q_ENTITY.search(t):
        out.add("quote_entity")
    return out


def quote_in_source(scopes, quote):
    """引文规范化后须是所选条目某一正文域的连续子串，且（完整句子，或原文中紧邻前后都不是否定/限定词）。"""
    if not scopes or len(compact(quote)) < QUOTE_MIN:
        return False
    q = norm(quote)
    for sc in scopes:
        t = norm(sc)
        start = t.find(q)
        while start != -1:
            before, after = t[:start], t[start + len(q):]
            full = _is_full_sentence(before, q, after)
            if full or not _adjacent_neg(before, after):
                return True
            start = t.find(q, start + 1)
    return False


def http_link_checker(url, timeout=10):
    """标准库实现：HEAD（失败再 GET），HTTP 状态 < 400 视为能打开。"""
    import urllib.request
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": "markjin-selfcheck/1"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status < 400:
                    return True
        except Exception:   # noqa: BLE001
            continue
    return False


def check_file(path, repo, date, card_type, **kw):
    """读取稿件并自检。repo 与 date 必须显式传入（不退回当前目录）。读取失败 → E-SELFCHECK-READ。"""
    try:
        text = Path(path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError, TypeError):
        flags = {k: False for k in FLAG_KEYS}
        counts = {k: 0 for k in COUNT_KEYS}
        meta = {"card_type": card_type if card_type in CARD_TYPES else None,
                "date": date if valid_date(date) else None}
        return _result([{"code": "E-SELFCHECK-READ", "line": 0}], flags, counts, meta)
    if "rel" not in kw:
        try:
            kw["rel"] = Path(path).resolve().relative_to(Path(repo).resolve()).as_posix()
        except (ValueError, OSError, TypeError):
            kw["rel"] = None                         # 不在仓库内 → 无法证明是 tongyi 路径
    return check_text(text, repo, date, card_type, **kw)
