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
NEG_ZH = ("未能", "尚未", "并非", "不是", "无法", "不能", "不会", "无需", "无须", "不必", "不用", "没有", "未", "没", "不", "非", "无")
NOT_NEG_ZH = ("不变", "不同", "不断", "不少", "不仅", "不久", "不过", "不论", "无论", "非常", "并且", "无人机", "非洲",
              "持平", "不等", "不止")
NEG_EN = re.compile(r"\b(?:not|no|never|cannot|without|unable|neither|nor|fail(?:s|ed|ing)?\s+to)\b|n't", re.I)
NOT_NEG_EN = re.compile(r"\bno\.\s*\d|\bnot only\b|\bno longer\b", re.I)
CLAUSE_RE = re.compile(r"[，；;。！？、]|,(?!\d{3})|[.!?](?=\s|$)")


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
