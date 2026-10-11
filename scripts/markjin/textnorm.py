"""文本规范化：HTML 实体解码（反复解码直至不变，最多 4 次）、NFKC、去掉零宽/格式控制字符（Unicode Cf 类）、压缩空白。

所有词表匹配都在规范化文本上进行：
  norm(s)    NFKC + 去 Cf + 空白压缩为单个空格
  compact(s) norm 后再去掉全部空白并转小写（用于中文与跨行、插空白的写法）
"""
import html
import re
import unicodedata

_WS = re.compile(r"\s+")


def unescape(s: str) -> str:
    """HTML/Markdown 字符实体解码（&#x5efa; &amp;#x5efa; &nbsp; 等），反复解码以覆盖多重编码。"""
    for _ in range(4):
        t = html.unescape(s)
        if t == s:
            break
        s = t
    return s


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", unescape(s))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    return _WS.sub(" ", s).strip()


def compact(s: str) -> str:
    return _WS.sub("", norm(s)).lower()


def has_any(text: str, terms) -> bool:
    c = compact(text)
    return any(compact(t) and compact(t) in c for t in terms)
