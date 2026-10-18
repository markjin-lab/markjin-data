"""路线图 v1.12（日报与产业经济打通）的自检规则：第六节“产业分段分支”、15.2 日报写法、15.3 数据、15.5 审查与治理。

本模块是公开文件，只放中性规则，不放任何内部用语。内部用语清单只在仓库外的本机文件里，
由命令行参数 --private-terms 或环境变量 MARKJIN_PRIVATE_TERMS 指向（load_private_terms）：
- 没给路径或文件不存在 → 明确跳过（结果 internal_term_check="skipped"，CLI 打印跳过说明），不报错；
- 文件在任何 git 仓库内（含被检查的仓库）、不是普通文件、读不出、不是 UTF-8 或没有任何词 → E-INTERNAL-TERM-LIST（fail-closed）；
- 命中 → E-INTERNAL-TERM。公开输出只有错误码和命中计数（行号记 0），不回显命中词与位置；定位用本机私有扫描脚本。

错误码（登记在 codes.py）：
- E-FRED-NOT-ARCHIVED：正文引用的 FRED 代码（fred.stlouisfed.org 链接或“FRED <代码>”写法）在 raw/<日期>/MANIFEST.sha256
  （日期不晚于稿件日期）里找不到逐字节一致的 fred/<代码>.json 存档。
- E-BRANCH-METHOD-MISSING：产业分段分支缺计算口径（目标观测期、公式、基期、单位、季调口径、舍入位数）、端点算法或输入版本
  （数据版本日期与 raw/ 原件 sha256），不予登记（check_branch）。
- E-BRANCH-AGGREGATE：产业分段分支的观测变量或数据来源是 15.3 所列的全国总量序列（check_branch）。
- E-CANDIDATE-DATA-CITED：正文引用了尚未转为常规的来源（15.3 所列新数据机构的网址，或 arxiv / fred / x / fulltext 以外的 raw/ 存档）。
- E-INTERNAL-LABEL：出现内部分类标签的通用写法或“若……此归类不成立”句式。具体标签词属于内部用语，只由 E-INTERNAL-TERM 按本机清单检查。
- E-INTERNAL-TERM / E-INTERNAL-TERM-LIST：见上。
- R-INDUSTRY-STRAINED：Codex 判产业链接牵强，只计数（strained_count 从 Codex 结果读出计数，供写公开台账）；自检不产生这个码。
"""
import os
import re
import stat
import unicodedata
from pathlib import Path

from .internal import _in_git_repo
from .textnorm import compact, norm, unescape

# —— 小节白名单（selfcheck.ALLOWED_HEADINGS 按 compact 后比较）
SECTION_HEADINGS = ("产业与经济数据", "Industry and economic data")

# —— 常规来源（路线图第五节；15.6 第 2 条：新数据机构一家都不转常规）
REGULAR_RAW_KINDS = frozenset({"arxiv", "fred", "x", "fulltext"})
# 15.3 所列新数据机构的公开网址（主机名完全相同或为其子域）。候选数据转常规之前只作线索，正文不得引用。
CANDIDATE_HOSTS = ("eia.gov", "bea.gov", "sec.gov", "fda.gov", "clinicaltrials.gov", "stats.gov.cn", "pbc.gov.cn",
                   "customs.gov.cn", "mof.gov.cn", "worldbank.org")
# 15.3 所列全国总量序列：只作背景和对照，不作分支的观测变量
AGGREGATE_SERIES = ("INDPRO", "TCU", "PPIACO", "Y033RC1Q027SBEA", "A053RC1Q027SBEA")

ENV_PRIVATE_TERMS = "MARKJIN_PRIVATE_TERMS"

_URL_RE = re.compile(r"https?://[^\s)）`<>\]\"'」]+", re.I)
_RAW_RE = re.compile(r"(?<![\w/.-])raw/(\d{4}-\d{2}-\d{2})/((?:round\d+/)?)([^/\s`'\")）]+)/")
_FRED_URL_RE = re.compile(r"fred\.stlouisfed\.org/(?:series/|graph/\?(?:[^\s#]*&)?id=|data/)([A-Za-z0-9_]{2,30})", re.I)
# “FRED <代码>”“FRED：<代码>”“(FRED <代码>，月度…)”。代码只认大写字母、数字、下划线；常见非代码词排除。
_FRED_TEXT_RE = re.compile(r"(?<![A-Za-z0-9])FRED[ \t]*[:：]?[ \t]*([A-Z0-9][A-Z0-9_]{1,29})(?![A-Za-z0-9_])")
_FRED_NOT_CODE = frozenset({"API", "ID", "IDS", "URL", "JSON", "CSV", "XML", "HTML", "HTTP", "HTTPS", "DATA", "SERIES"})


def heading_whitelist():
    return {compact(h) for h in SECTION_HEADINGS}


def fred_codes(text):
    """正文引用的 FRED 代码（大写），按首次出现排序。"""
    t = norm(text)
    out = []
    for m in _FRED_URL_RE.finditer(t):
        c = m.group(1).upper()
        if c not in out:
            out.append(c)
    for m in _FRED_TEXT_RE.finditer(t):
        c = m.group(1)
        if c not in _FRED_NOT_CODE and c not in out:
            out.append(c)
    return out


def _host(url):
    m = re.match(r"https?://([^/?#\s]+)", url, re.I)
    if not m:
        return ""
    h = m.group(1).rsplit("@", 1)[-1]
    h = h.split(":", 1)[0] if not h.startswith("[") else h
    return h.rstrip(".").lower()


def candidate_cited(line):
    """一行里是否引用了尚未转常规的来源：15.3 新数据机构网址，或 arxiv/fred/x/fulltext 以外的 raw/ 存档。"""
    t = norm(line)
    for u in _URL_RE.findall(t):
        h = _host(u)
        if any(h == c or h.endswith("." + c) for c in CANDIDATE_HOSTS):
            return True
    for m in _RAW_RE.finditer(t):
        if m.group(3) not in REGULAR_RAW_KINDS:
            return True
    return False


# —— 内部分类标签的通用写法（具体标签词不在此处，见模块说明）
_LABEL_ZH = re.compile(r"若[^。！？!?；;]{0,160}?(?:则)?此(?:归类|分类)(?:即|就|便)?不(?:再)?成立")
_LABEL_EN = re.compile(r"\bif\b[^.!?;]{0,240}?\bthis\s+(?:classification|categori[sz]ation|label)\s+"
                       r"(?:does\s+not|doesn't|would\s+not|wouldn't|will\s+not|won't|no\s+longer|fails\s+to)\s+(?:hold|apply|stand)", re.I)
_LABEL_MARK = re.compile(r"内部分类|分类标签[:：]|归类标签[:：]|internal\s+(?:classification|label)", re.I)


def internal_label(text):
    t = norm(text)
    return bool(_LABEL_ZH.search(t) or _LABEL_EN.search(t) or _LABEL_MARK.search(t))


# —— 仓库外的内部用语清单
class PrivateTermsError(ValueError):
    pass


def private_terms_path(path=None):
    """显式参数优先，其次环境变量；都没有 → None（跳过）。"""
    p = path if path not in (None, "") else os.environ.get(ENV_PRIVATE_TERMS) or None
    return Path(p) if p else None


def load_private_terms(path=None, repo=None):
    """返回 (状态, 词表)。状态："skipped"（没给路径或文件不存在）/"loaded"。
    不合规（在 git 仓库内、在被检查的仓库内、不是普通文件、读不出、不是 UTF-8、没有词）→ 抛 PrivateTermsError。
    清单格式：每行一个词，去掉首尾空白，空行忽略。"""
    p = private_terms_path(path)
    if p is None:
        return "skipped", []
    try:
        st = p.lstat()
    except FileNotFoundError:
        return "skipped", []
    except OSError as e:
        raise PrivateTermsError("unreadable") from e
    if stat.S_ISLNK(st.st_mode):
        try:
            rp = p.resolve(strict=True)
        except (OSError, RuntimeError) as e:
            raise PrivateTermsError("dangling link") from e
    else:
        rp = p.resolve()
    if not rp.is_file():
        raise PrivateTermsError("not a regular file")
    if _in_git_repo(rp.parent) or _in_git_repo(p.absolute().parent):
        raise PrivateTermsError("inside a git repository")
    if repo is not None:
        try:
            rr = Path(repo).resolve()
        except (OSError, RuntimeError, TypeError):
            rr = None
        if rr is not None and (rr == rp or rr in rp.parents):
            raise PrivateTermsError("inside the checked repository")
    try:
        text = rp.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise PrivateTermsError("unreadable") from e
    terms = []
    for ln in text.splitlines():
        t = ln.strip().lstrip("\ufeff").strip()
        if t and t not in terms:
            terms.append(t)
    if not terms:
        raise PrivateTermsError("empty")
    return "loaded", terms


def _light(s):
    """不做 NFKC 的规范化：实体解码、去 Cf、去空白、小写。用于 NFKC 会改变字形的词（如带圈或罗马数字字符），
    避免它们被折叠成普通数字或字母后误中。"""
    s = unescape(s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    return re.sub(r"\s+", "", s).lower()


def _term_forms(terms):
    out = []
    for t in terms:
        if unicodedata.normalize("NFKC", t) == t:
            out.append(("nfkc", compact(t)))       # 普通词：在 NFKC 规范化文本上匹配（全角、插空白等变体也算）
        else:
            out.append(("light", _light(t)))       # NFKC 会改变的词：只按原字形匹配
    return [(k, v) for k, v in out if v]


def term_hits(lines, terms):
    """命中计数：命中的行数；各行都没命中但跨行拼接后命中 → 1。不返回命中词或位置。"""
    forms = _term_forms(terms)
    if not forms:
        return 0

    def hit(s):
        c, l = compact(s), _light(s)
        return any((v in c) if k == "nfkc" else (v in l) for k, v in forms)
    n = sum(1 for s in lines if s.strip() and hit(s))
    if n == 0 and hit("\n".join(lines)):
        n = 1
    return n


# —— 产业分段分支（第六节）：登记前核对
_PERIOD = re.compile(r"\d{4}\s*年\s*(?:\d{1,2}\s*月|第?\s*[一二三四1-4]\s*季度?)|\d{4}-(?:0[1-9]|1[0-2])\b|\b\d{4}\s*Q[1-4]\b|"
                     r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}\b", re.I)
_FORMULA = re.compile(r"[(（][^()（）]*[/×*÷][^()（）]*[)）]|公式|算式|formula", re.I)
_BASE = re.compile(r"同比|环比|上年同期|上期|基期|基年|定基|读数本身|原值|level|year[-\s]over[-\s]year|month[-\s]over[-\s]month|"
                   r"quarter[-\s]over[-\s]quarter|base\s+(?:period|year)", re.I)
_SA = re.compile(r"季调|季节调整|未季调|非季调|seasonally\s+adjusted|not\s+seasonally\s+adjusted|\bN?SA\b|\bSAAR\b", re.I)
_ROUND = re.compile(r"保留\s*[零一两二三四五六0-9]\s*位小数|小数点后\s*[零一两二三四五六0-9]\s*位|取整|"
                    r"\d+\s+decimal\s+places?|(?:one|two|three|four)\s+decimal\s+places?|rounded\s+to", re.I)
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _s(row, k):
    v = row.get(k) if isinstance(row, dict) else None
    return norm(v) if isinstance(v, str) else ""


def _aggregate(s):
    return any(re.search(r"(?<![A-Za-z0-9_])" + c + r"(?![A-Za-z0-9_])", s, re.I) for c in AGGREGATE_SERIES)


def check_branch(row):
    """产业分段分支登记前核对。row 字段：observed_variable、unit、data_source（台账同名字段）；
    endpoint_method（端点算法）、input_version（输入数据版本，含 YYYY-MM-DD）、raw_sha256（raw/ 原件 sha256，字符串或字符串列表）
    ——后三项按第六节写在稿件正文与 digest 产业链接表，接入台账时按此传入。返回排序后的错误码列表（空 = 可登记）。"""
    codes = set()
    ov, unit, src = _s(row, "observed_variable"), _s(row, "unit"), _s(row, "data_source")
    method = ov + " " + unit
    if not (ov and unit and _PERIOD.search(ov) and _FORMULA.search(method) and _BASE.search(method)
            and _SA.search(method) and _ROUND.search(method)):
        codes.add("E-BRANCH-METHOD-MISSING")
    if len(compact(_s(row, "endpoint_method"))) < 4:
        codes.add("E-BRANCH-METHOD-MISSING")
    if not _DATE.search(_s(row, "input_version")):
        codes.add("E-BRANCH-METHOD-MISSING")
    shas = row.get("raw_sha256") if isinstance(row, dict) else None
    shas = [shas] if isinstance(shas, str) else shas
    if not (isinstance(shas, list) and shas and all(isinstance(x, str) and _SHA.match(x) for x in shas)):
        codes.add("E-BRANCH-METHOD-MISSING")
    if _aggregate(ov) or _aggregate(src):
        codes.add("E-BRANCH-AGGREGATE")
    return sorted(codes)


# —— R-INDUSTRY-STRAINED：从 Codex 结果读计数（日报审查提示词的输出格式含一行 “R-INDUSTRY-STRAINED: <计数>”）
_STRAINED_LINE = re.compile(r"^\s*R-INDUSTRY-STRAINED:\s*(\d{1,4})\s*$", re.M)


def strained_count(result_text):
    """返回 Codex 结果里登记的牵强计数；没有该行或出现多行且数值不一致 → None（不记台账，由人工核对）。"""
    if not isinstance(result_text, str):
        return None
    vals = {int(v) for v in _STRAINED_LINE.findall(result_text)}
    return vals.pop() if len(vals) == 1 else None
