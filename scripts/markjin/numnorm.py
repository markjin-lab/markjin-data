"""#32 r3：支持位置核对用的数值与否定规范化。只用标准库。

- 中文数字（“百分之九十五”“九成五”“四点二”“三十亿”）先规范化成阿拉伯数字与单位，再比较；
  无法可靠解析的中文数值表述 → unparsed=True（调用方不得自动通过）。
- 量级换算：billion / million / thousand / trillion 与 亿 / 万 / 万亿 / 千万 / 百万 换算成绝对值再比较
  （“3 billion”与“30 亿”都变成 3000000000）。
- 否定按分句计“否定词个数的奇偶”（双重否定抵消）；“不变”“不同”等不是否定；“无需/无须/不必”与英文 without、
  no need 同为一个否定。
"""
import re
from decimal import Decimal, InvalidOperation

CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000}
CN_CHARS = "零〇一二两三四五六七八九十百千万亿点"
CN_NUM = "[零〇一二两三四五六七八九十][零〇一二两三四五六七八九十百千万亿点]*"   # 必须以数字或“十”开头（单独的“亿”“万”不是数）


def cn_to_decimal(s):
    """“九十五”→95，“四点二”→4.2，“三十亿”→3000000000，“一万二千”→12000。解析不了返回 None。"""
    if not s or any(ch not in CN_CHARS for ch in s):
        return None
    if "点" in s:
        a, _, b = s.partition("点")
        ip = cn_to_decimal(a) if a else Decimal(0)
        if ip is None or not b or any(ch not in CN_DIGIT for ch in b):
            return None
        return ip + Decimal("0." + "".join(str(CN_DIGIT[ch]) for ch in b))
    for big, mul in (("亿", 10 ** 8), ("万", 10 ** 4)):
        if big in s:
            a, _, b = s.rpartition(big)
            hi = cn_to_decimal(a) if a else Decimal(1)
            lo = cn_to_decimal(b) if b else Decimal(0)
            if hi is None or lo is None:
                return None
            return hi * mul + lo
    if all(ch in CN_DIGIT for ch in s):        # “二〇二六”式逐位读
        return Decimal("".join(str(CN_DIGIT[ch]) for ch in s))
    total, cur, last_unit = 0, None, 10 ** 9
    for ch in s:
        if ch in CN_DIGIT:
            if cur is not None:
                return None
            cur = CN_DIGIT[ch]
        elif ch in CN_UNIT:
            u = CN_UNIT[ch]
            if u >= last_unit:
                return None
            total += (1 if cur is None else cur) * u
            cur, last_unit = None, u
        else:
            return None
    return Decimal(total + (cur or 0))


def _fmt(d):
    d = d.normalize()
    s = format(d, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


MAG = {"trillion": 10 ** 12, "billion": 10 ** 9, "bn": 10 ** 9, "million": 10 ** 6, "mn": 10 ** 6, "thousand": 10 ** 3,
       "万亿": 10 ** 12, "亿": 10 ** 8, "千万": 10 ** 7, "百万": 10 ** 6, "万": 10 ** 4}
_MAG_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(trillion|billion|bn|million|mn|thousand|万亿|亿|千万|百万|万)(?![A-Za-z])", re.I)
_PCT_CN_RE = re.compile(r"百分之(" + CN_NUM + r"|\d+(?:\.\d+)?)")
_CHENG_RE = re.compile(r"([零〇一二两三四五六七八九十]+)成([一二三四五六七八九])?")
_VAGUE = "几余多来"   # “九十几”“三成多”这类约数：解析不了，不能自动通过
_CN_BEFORE_UNIT_RE = re.compile(r"(" + CN_NUM + r")\s*(倍|个百分点|%|％|美元|元|人|项|篇|天|年|个|名|次)")
_UNPARSED_RE = re.compile(r"百分之|[" + CN_CHARS + r"]成|[" + CN_CHARS + r"]\s*(?:倍|个百分点)")


def normalize_numbers(s):
    """返回 (规范化文本, unparsed)。"""
    t = s.replace(",", ",")
    t = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", t)
    unparsed = False

    def pct(m):
        nonlocal unparsed
        v = m.group(1)
        d = Decimal(v) if v[0].isdigit() else cn_to_decimal(v)
        if d is None or m.string[m.end():m.end() + 1] in tuple(_VAGUE):
            unparsed = True; return m.group(0)
        return _fmt(d) + "%"
    t = _PCT_CN_RE.sub(pct, t)

    def cheng(m):
        nonlocal unparsed
        d = cn_to_decimal(m.group(1))
        if d is None or d > 10 or m.string[m.end():m.end() + 1] in tuple(_VAGUE):
            unparsed = True; return m.group(0)
        v = d * 10 + (CN_DIGIT[m.group(2)] if m.group(2) else 0)
        return _fmt(v) + "%"
    t = _CHENG_RE.sub(cheng, t)

    def before_unit(m):
        nonlocal unparsed
        d = cn_to_decimal(m.group(1))
        if d is None:
            unparsed = True; return m.group(0)
        return _fmt(d) + " " + m.group(2)
    t = _CN_BEFORE_UNIT_RE.sub(before_unit, t)
    # 纯中文量级数（“三十亿”）先转阿拉伯数字再走量级换算
    t = re.sub(r"(" + CN_NUM + r")(?=万亿|亿|千万|百万|万)", lambda m: _fmt(cn_to_decimal(m.group(1))) if cn_to_decimal(m.group(1)) is not None and len(m.group(1)) >= 1 and m.group(1) not in ("万", "亿") else m.group(1), t)

    def mag(m):
        try:
            return _fmt(Decimal(m.group(1)) * MAG[m.group(2).lower()])
        except InvalidOperation:
            nonlocal unparsed
            unparsed = True; return m.group(0)
    t = _MAG_RE.sub(mag, t)
    if _UNPARSED_RE.search(t):
        unparsed = True
    return t, unparsed


# —— 否定（按分句、计奇偶）
NEG_ZH = ("难以", "尚待", "有待", "未曾", "从未", "未能", "尚未", "并非", "不是", "无法", "不能", "不会", "无需", "无须", "不必", "不用", "没有", "未", "没", "不", "非", "无")
NOT_NEG_ZH = ("不变", "不同", "不断", "不少", "不仅", "不久", "不过", "不论", "无论", "非常", "并且", "无人机", "非洲",
              "持平", "不等", "不止",
              # r5（审查 r4 MEDIUM）：含否定字但不否定谓语的固定说法——程度、评价、比较，不是“没有做到”
              "难以置信", "难以想象", "难以言喻", "难以言表", "无与伦比", "无可比拟", "从未如此", "从未这么", "从未这样",
              "前所未有", "史无前例", "毫无疑问", "无疑")
# r4：no longer 是否定（“no longer reaches”≠“仍达到”）；隐性否定 hardly/barely/scarcely/yet to/remain(s) to be 硬拦
NEG_EN = re.compile(r"\b(?:no\s+longer|not|no|never|cannot|without|unable|neither|nor|hardly|barely|scarcely|"
                    r"yet\s+to|remains?\s+to\s+be|fail(?:s|ed|ing)?\s+to)\b|n't", re.I)
NOT_NEG_EN = re.compile(r"\bno\.\s*\d|\bnot only\b|\b(?:like\s+)?never[\s\-]+before\b|\bnever\s+(?:been\s+)?seen\s+before\b", re.I)
# #79 r9（审查 HIGH）：破折号、括号与不带逗号的 while / whereas / but 也切分句，避免两个对象的相反说法留在同一分句；
# 短横线只在两侧有空格时切，不拆 1–3 这类数字范围
CLAUSE_RE = re.compile(r"[，；;。！？、—()（）]|\s[–-]\s|,(?!\d{3})|[.!?](?=\s|$)|\b(?:while|whereas|but)\b", re.I)


def neg_count(s):
    t = s.lower()
    t = NOT_NEG_EN.sub(" ", t)
    n = len(NEG_EN.findall(t))
    z = s
    for w in NOT_NEG_ZH:
        z = z.replace(w, " ")
    for w in NEG_ZH:                 # 长词优先，计数后挖掉，避免“未能”再被“未”重复计
        n += z.count(w)
        z = z.replace(w, " ")
    return n


def clauses(s):
    return [c for c in CLAUSE_RE.split(s) if c.strip()]


# —— r4：without / 无需 只否定它后面那个动作，不否定整句。先把“without X”“无需 X”整段挖出来单独配对，
#    再对剩下的主干比较否定奇偶。前置（“无需微调即达到…”“Without fine-tuning, …”）和后置写法都适用。
_SCOPED_EN = re.compile(r"\b(?:without|no\s+need\s+(?:to|for))\s+(?:any\s+|the\s+|a\s+|an\s+)?[\w\-]+", re.I)
_SCOPED_ZH = re.compile(r"(?:无需|无须|不必|不用|不需要)(?:[^\s，,；;。即就便也]{1,6}?(?=即|就|便|也|[，,；;。]|$)|[^\s，,；;。即就便也]{0,2})")


def strip_scoped(s):
    """返回 (挖掉 without/无需 短语后的文本, 挖掉的短语个数)。"""
    n = 0
    def f(m):
        nonlocal n
        n += 1
        return " "
    s = _SCOPED_EN.sub(f, s)
    s = _SCOPED_ZH.sub(f, s)
    return s, n


# —— r4：基点是独立单位，100 bp = 1 个百分点。比较前把“N 基点 / basis points / bp”换成“N/100 个百分点”。
_BP_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:个基点|基点|basis\s+points?|bps?(?![A-Za-z]))", re.I)


def bp_to_pp(s):
    return _BP_RE.sub(lambda m: _fmt(Decimal(m.group(1)) / 100) + " 个百分点", s)


# —— r5（审查 r4 MEDIUM）：审慎/待定说法（有待修订、尚未经同行评审、yet to be peer reviewed、subject to revision…）
#    说的是“结论或数据的状态”，不是“没做到某件事”。机器不按否定计，挖掉后再比主干；出现过就给人工提示
#    （R-SUPPORT-HEDGE），由 Codex 核对断言与原文的审慎程度是否一致。“难以达到”“从未达到”“yet to reach”等真否定照旧硬拦。
_HEDGE_OBJ_ZH = r"(?:同行评审|评审|审查|审核|核实|核准|证实|验证|确认|检验|修订|修正|观察|批准)"
_HEDGE_ZH = re.compile(r"(?:有待|尚待|仍待|尚需|仍需|尚未经过|尚未经|未经过|未经)(?:进一步|正式|独立)?" + _HEDGE_OBJ_ZH)
_HEDGE_EN = re.compile(r"\b(?:(?:has|have|is|are)\s+)?(?:yet\s+to\s+be|remains?\s+to\s+be|not\s+yet|subject\s+to)\s+"
                       r"(?:independently\s+|formally\s+|further\s+)?(?:peer[\s\-]+)?"
                       r"(?:review(?:ed)?|verif(?:y|ied)|confirm(?:ed)?|validat(?:e|ed)|revis(?:ed|ion)|approv(?:ed|al)|seen|determined)\b", re.I)


def strip_hedges(s):
    """返回 (挖掉审慎/待定说法后的文本, 挖掉的个数)。"""
    n = 0
    def f(m):
        nonlocal n
        n += 1
        return " "
    s = _HEDGE_EN.sub(f, s)
    s = _HEDGE_ZH.sub(f, s)
    return s, n
