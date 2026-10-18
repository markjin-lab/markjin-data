"""采集公共层（PR #3/#6 审查 REJECTED 修复，2026-10-12）。capture_sources / fetch_primary / scrapers 共用。

规则（每条对应审查意见）：
- 审批门禁：只有 enabled 且 approval_status == approved 且 approval_basis 非空的源才可采集（approval_gate）。
- 许可：默认 url+hash-only。整源、整域名一律不给全文许可；全文进公开目录只能逐条目、凭已核实的许可证据
  （license_evidence，见 public_fulltext_ok），否则一律私有。
- 原件：响应原字节不解压、不脱敏，按 sha256 独占创建写入私有档案，并追加 MANIFEST.sha256；
  解压、提取、条目 JSON 只作派生物另存（derived/，登记 DERIVED.sha256，带 derived_from）。
- 每次运行写入的公开文件都按运行戳独占创建（不覆盖），并追加到当天公开 MANIFEST.sha256。
- 访问礼仪：如实 UA（含联系方式）；每次请求（含每一跳重定向、子 sitemap、robots.txt 本身）都按站点限速：未公布限速的站点
  每站每分钟最多 1 次（跨进程共享），只有 sources.yaml site_rate_limits 写明公布限额和依据的站点按其限额，SEC 5 次/秒；
  每一跳都先查目标主机 robots.txt、源状态、本轮主机停止与 URL 冷却；不自动跟随重定向；拒绝 t.co。
- 封锁规则（出处与细则见「封锁规则与来源健康状态」一节）：单次可疑（401/403、429、验证页、登录墙）→ 该主机本轮全部停止、
  被拒 URL 冷却 ≥24 小时；最近 5 轮 3 轮可疑 → pending-disable（下一轮起不抓，等人工确认）。收到任何 HTTP 状态都不重发，
  只有没收到响应的网络错误有限重试。
- robots.txt 自身的跳转逐跳校验（scheme / t.co / 跨主机即禁止）；robots 401/403/429、验证页或登录墙 → 与正文相同处理。
- 一切日志（公开与私有）不写本机路径、不写凭证：URL 不带查询值（只记参数个数，不记参数名；按源 public_params 声明的才留值），hops 只存脱敏 URL；
- 地址策略强制安装（AddressPolicy，每一跳/子 sitemap 在任何请求前检查）；外部策略只能叠加更严。
- robots.txt 返回 HTML 但不是验证页 → 本轮按禁止，不算可疑。私有根目录必须显式给出且不能与公开根目录重叠。
"""
import datetime as dt
import email.utils
import hashlib
import ipaddress
import json
import math
import os
import re
import socket
import time
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from . import strictjson

UA = "markjin-collector/0.1 (+https://markjin-lab.github.io)"     # 不写死任何邮箱
# SEC（*.sec.gov）要求 UA 带联系方式：只从环境变量读取；未设置则 SEC 请求一律不发（not_configured），不算可疑
SEC_UA_ENV = "MARKJIN_SEC_USER_AGENT"
SEC_SUFFIX = "sec.gov"
# 主机组全局限速（跨该组所有主机共用一个桶）：SEC 公示上限 10 次/秒，这里取 5 次/秒留余量
RATE_GROUPS = {SEC_SUFFIX: 0.2}


def in_group(host, suffix):
    host = (host or "").lower()
    return host == suffix or host.endswith("." + suffix)


def sec_user_agent(env=None):
    """从环境变量读取 SEC UA；必须含联系方式（邮箱或 http(s) 网址），否则视为未配置，返回 None。"""
    v = ((env if env is not None else os.environ).get(SEC_UA_ENV) or "").strip()
    if v and re.search(r"[^\s@]+@[^\s@]+\.[^\s@]+|https?://\S+", v) and "\n" not in v and "\r" not in v:
        return v
    return None
UA_TOKEN = "markjin-collector"
MAX_BYTES = 25 * 1024 * 1024
HOST_INTERVAL = 2.0          # 每主机最小请求间隔（秒）；robots Crawl-delay / Request-rate 更严时取更严者
MAX_REDIRECTS = 5
NET_RETRIES = 2              # 只对没收到 HTTP 响应的网络错误重试；任何 HTTP 状态（含 429、5xx）都不重发
LOCAL_ROUND = "0000-00-00/r1"  # 无持久状态（测试、单次调用）时的进程内轮次
BACKOFF_BASE = 2.0
BACKOFF_CAP = 120.0          # Retry-After 超过此值直接放弃本次（不长时间挂起）
_LOGIN_PATH = re.compile(r"/(?:log-?in|sign-?in|signon|sso|servicelogin|auth(?:orize)?|account/login|users/sign_in|session/new)(?:[/?.;#]|$)", re.I)


def is_login_url(u):
    """跳转目标是登录页（登录墙）：路径命中常见登录路径，或主机以 login. / signin. / sso. / accounts. 开头。"""
    p = urlsplit(u)
    h = (p.hostname or "").lower()
    return bool(_LOGIN_PATH.search(p.path or "/")) or h.split(".")[0] in ("login", "signin", "sso", "auth", "accounts")
REFUSED_HOSTS = {"t.co"}
REDIRECT_CODES = {301, 302, 303, 307, 308}
# 验证页识别（collector 与 scrapers 共用这一份）。厂商标记（vendor）与泛用短语（phrase）都算可疑：该主机本轮停止、
# URL 冷却，给源记一次可疑（见「封锁规则与来源健康状态」）；区分两者只为报告里写清原因。误判代价是该主机本轮丢失，
# 并可能累积成源的 pending-disable，所以两类仍尽量收紧。
# 高置信厂商标记：用 html.parser 逐个标签解析，只看精确属性（class、src、id、meta），不用字节正则。
# 地址一律用 urljoin(响应 URL, src) 补全后比对：同源（scheme + 主机 + 端口与响应一致）的才算本站资源。
#  - Cloudflare：<script src> 或脚本里 X.src = '…' 指向 challenges.cloudflare.com，或本站
#    /cdn-cgi/challenge-platform/h/<字母>/orchestrate/（验证页专属；/cdn-cgi/challenge-platform/scripts/jsd/ 是往正常页面
#    注入的检测脚本，不算）；不在引号里的 window._cf_chl_opt 赋值语句；元素 class 含 cf-turnstile
#  - reCAPTCHA / hCaptcha：class 含 g-recaptcha；script src 指向 google.com/recaptcha.net 的 /recaptcha/…api.js、hcaptcha 的 api.js
#  - Incapsula：<script src> 指向本站 /_Incapsula_Resource；或 <iframe src> 指向本站 /_Incapsula_Resource?…
#    且正文含 "Incapsula incident ID"（组合证据）
#  - PerimeterX：script src（含 X.src 赋值）指向 captcha.px-cdn.net / captcha.px-cloud.net（r13：单独的 window._pxAppId
#    赋值是正常页面的 Sensor，不算）；
#    meta description 为 px-captcha 且标题为 "Access to this page has been denied"；div#px-captcha 且整页可见文本很短
#  - form#challenge-form
#  - 没闭合的 <script>（一直到文末）：永不算高置信；内容混入 HTML 标签时不判定，纯脚本命中标记 → 只算疑似（phrase）
#  - 免检：<textarea>/<xmp>/<plaintext>/<title> 内（HTML 规范里的纯文本元素）、注释、可见文本；<pre>/<code> 照常检查。
#    script 内容先去掉 JS 字符串字面量和注释，其余文字不解析为标签。data-class / data-src 等不是 class / src
#  - 响应头 cf-mitigated: challenge（见 classify_page）
_LITERAL_TAGS = frozenset({"textarea", "xmp", "plaintext", "title"})
PX_TEXT_MAX = 1000
_CF_CHL_OPT = re.compile(r"(?:^|[;{}()\s,])window\s*\.\s*_cf_chl_opt\s*=(?!=)")
_JS_SRC = re.compile(r"""\.\s*src\s*=\s*(['"])""")
_CF_ORCH = re.compile(r"^/cdn-cgi/challenge-platform/h/[a-z]/orchestrate/", re.I)
_PX_CAPTCHA_HOSTS = frozenset({"captcha.px-cdn.net", "captcha.px-cloud.net"})
PX_DENIED_TITLE = "access to this page has been denied"
_HTML_IN_SCRIPT = re.compile(r"<(?:/?[a-z][a-z0-9-]*(?:\s|>|/>)|!--)", re.I)


def _origin(u):
    p = urlsplit(u)
    port = p.port or {"http": 80, "https": 443}.get((p.scheme or "").lower())
    return (p.scheme or "").lower(), (p.hostname or "").lower(), port


def vendor_src(src, script=True, base=None, iframe=False):
    """src 是否指向已知验证组件。base = 响应 URL：用 urljoin 补成完整地址，同源的本站资源才认（没有 base 时只认相对地址）。
    返回 'incapsula-iframe'（iframe 指向本站 /_Incapsula_Resource?…，须再配合 incident ID）、True 或 False。"""
    raw = (src or "").strip()
    try:
        full = urljoin(base, raw) if base else raw
        u = urlsplit(full)
        same = (_origin(full) == _origin(base)) if base else not urlsplit(raw).netloc
    except ValueError:
        return False
    host, path = (u.hostname or "").lower(), u.path or ""
    if iframe:
        return "incapsula-iframe" if same and path.startswith("/_Incapsula_Resource") and u.query else False
    if not script:
        return False
    if same and (_CF_ORCH.match(path) or path.startswith("/_Incapsula_Resource")):
        return True
    if host == "challenges.cloudflare.com" or host in _PX_CAPTCHA_HOSTS:
        return True
    if (host == "hcaptcha.com" or host.endswith(".hcaptcha.com")) and path.endswith("/api.js"):
        return True
    if host in ("google.com", "www.google.com", "recaptcha.net", "www.recaptcha.net") and \
            path.startswith("/recaptcha/") and path.endswith("api.js"):
        return True
    return False


def _js_mask(js):
    """把 JS 字符串字面量（'…' "…" `…`）内容和注释替换成空格（保留引号字符与长度），用于只在代码里找赋值语句。"""
    out, i, n = list(js), 0, len(js)
    while i < n:
        c = js[i]
        if c in "'\"`":
            j = i + 1
            while j < n and js[j] != c:
                j += 2 if js[j] == "\\" else 1
            for k in range(i + 1, min(j, n)):
                out[k] = " "
            i = j + 1
        elif js.startswith("//", i):
            j = js.find("\n", i); j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif js.startswith("/*", i):
            j = js.find("*/", i + 2); j = n if j < 0 else j + 2
            for k in range(i, j):
                out[k] = " "
            i = j
        else:
            i += 1
    return "".join(out)


def _script_markers(js, base=None):
    """脚本内容里的独立标记集合：cf_chl_opt / src（X.src = '…' 指向验证组件）。
    r13：window._pxAppId 赋值是 HUMAN/PerimeterX 正常页面传感器（Sensor）的标准写法，不拦截流量，不算标记。"""
    m, found = _js_mask(js), set()
    if _CF_CHL_OPT.search(m):
        found.add("cf_chl_opt")
    for x in _JS_SRC.finditer(m):          # 赋值本身在代码里；值是紧随其后的字符串字面量
        q, start = x.group(1), x.end()
        end = js.find(q, start)
        if end > start and vendor_src(js[start:end].replace("\\/", "/"), base=base) is True:
            found.add("src")
    return found


def _vendor_scan(text, base=None):
    """返回 'vendor'（高置信）、'suspect'（没闭合的 script 里只有单一标记）或 None。"""
    from html.parser import HTMLParser

    class Scan(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.hit, self.px, self.lit, self.in_script, self.visible = False, False, [], 0, 0
            self.sbuf, self.title, self.meta_px, self.incap_iframe, self.text = [], [], False, False, []

        def handle_starttag(self, tag, attrs):
            if tag in _LITERAL_TAGS:
                self.lit.append(tag)
                return
            if self.lit:
                return
            if tag in ("script", "style"):
                self.in_script = tag
                self.sbuf = []
            a = {}
            for k, v in attrs:                 # 精确属性名；同名重复取第一个
                a.setdefault(k, v or "")
            if tag == "script" and "src" in a and vendor_src(a["src"], base=base) is True:
                self.hit = True
            elif tag == "iframe" and "src" in a and vendor_src(a["src"], base=base, iframe=True):
                self.incap_iframe = True
            elif tag == "form" and a.get("id", "").strip() == "challenge-form":
                self.hit = True
            elif tag == "div" and a.get("id", "").strip() == "px-captcha":
                self.px = True                 # 还要整页可见文本很短（见末尾）
            elif tag == "meta" and a.get("name", "").strip().lower() == "description" and \
                    a.get("content", "").strip() == "px-captcha":
                self.meta_px = True
            elif {"cf-turnstile", "g-recaptcha"} & set(a.get("class", "").split()):
                self.hit = True

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)
            if tag in ("script", "style") and self.in_script == tag:
                self.in_script = 0

        def handle_endtag(self, tag):
            if self.lit and tag == self.lit[-1]:
                self.lit.pop()
            elif tag in ("script", "style") and self.in_script == tag:
                if tag == "script" and _script_markers("".join(self.sbuf), base):
                    self.hit = True
                self.in_script = 0

        def handle_data(self, data):
            if self.lit:
                if self.lit[-1] == "title":
                    self.title.append(data)
                return
            if self.in_script:
                self.sbuf.append(data)
            else:
                self.visible += len(" ".join(data.split()))
                self.text.append(data)
    sc = Scan()
    try:
        sc.feed(text)
        sc.close()
    except Exception:        # 解析异常不当作高置信证据
        pass
    title = " ".join("".join(sc.title).split()).lower()
    if sc.hit or (sc.px and sc.visible <= PX_TEXT_MAX) or (sc.meta_px and title == PX_DENIED_TITLE) or \
            (sc.incap_iframe and "incapsula incident id" in " ".join("".join(sc.text).split()).lower()):
        return "vendor"
    if sc.in_script == "script":                       # r13：没闭合的 script 永不算高置信
        js = "".join(sc.sbuf)
        if _HTML_IN_SCRIPT.search(js):                 # 混入 HTML 标签（如 <pre>）：不是可执行的挑战脚本，不凭内部赋值判定
            return None
        if _script_markers(js, base):
            return "suspect"
    return None


class _VendorMatcher:
    """兼容旧接口：CHALLENGE.search(body_bytes, url=None) → 是否命中高置信验证组件。"""

    def search(self, body, url=None):
        if isinstance(body, bytes):
            body = body.decode("utf-8", "replace")
        return (_vendor_scan(body[:200000], url) == "vendor") or None


CHALLENGE = _VendorMatcher()
# 泛用短语（低置信）：只在 HTML 里匹配，且只看 title，或页面很短、短语占了主要内容
CHALLENGE_PHRASES = re.compile(
    r"check(?:ing)? (?:your|the) browser|checking if the site connection is secure|just a moment|"
    r"verify(?:ing)? (?:that )?you are (?:a )?human|are you a robot|robot check|"
    r"(?:please )?enable javascript and cookies(?: to continue)?|(?:please )?enable cookies and javascript|"
    r"ddos protection by \w+|access to this page has been denied|access denied|"
    r"unusual traffic from your (?:computer )?network", re.I)
SHORT_VISIBLE = 512          # 可见文本不超过这么多字符才算“很短”的页面
PHRASE_SHARE = 0.5           # 短语至少占 title / 可见文本的一半，才算“主要内容”
_TITLE = re.compile(rb"<title[^>]*>(.*?)</title\s*>", re.I | re.S)
_INVISIBLE = re.compile(rb"<(script|style|noscript|template|title)\b.*?</\1\s*>|<!--.*?-->", re.I | re.S)
_TAGS = re.compile(rb"<[^>]*>")


def visible_text(body):
    """(title 文本, 去掉 title/脚本/样式/noscript/注释/标签后的可见文本)，均合并空白。"""
    head = body[:200000]
    t = _TITLE.search(head)
    norm = lambda x: re.sub(r"\s+", " ", x.decode("utf-8", "replace")).strip()
    vis = _TAGS.sub(b" ", _INVISIBLE.sub(b" ", head))
    return norm(t.group(1) if t else b""), norm(vis)


def _dominant(text):
    m = CHALLENGE_PHRASES.search(text or "")
    return bool(m) and len(m.group(0)) > PHRASE_SHARE * len(text.strip(" .!?:-|"))


def htmlish(ctype, body):
    """HTML 形态：Content-Type 含 html，或正文第一个元素是 HTML 标签 / <!doctype html>（XML 文档不算）。"""
    return "html" in (ctype or "").lower() or (bool(body) and looks_html({}, body, xml_ok=True))


def phrase_hit(body):
    """泛用短语：title 以短语为主，或可见文本很短且以短语为主。"""
    title, vis = visible_text(body)
    return _dominant(title) or (len(vis) <= SHORT_VISIBLE and _dominant(vis))


def classify_page(ctype, body, headers=None, url=None):
    """返回 'vendor'（厂商标记，高置信）、'phrase'（只命中泛用短语或单一弱标记，疑似）或 None。两者后果相同（该主机本轮停止、URL 冷却）。
    url = 响应 URL，用来把相对 / 协议相对 / 同主机绝对地址补全并核对同源。响应头 cf-mitigated: challenge 不论正文都算 vendor；
    正文只对 HTML 形态判断（JSON / XML / 普通文本交给格式校验）。"""
    for k, v in (headers or {}).items():
        if str(k).lower() == "cf-mitigated" and str(v).strip().lower() == "challenge":
            return "vendor"
    if not body or not htmlish(ctype, body):
        return None
    t = body[:200000].decode("utf-8", "replace") if isinstance(body, bytes) else body[:200000]
    v = _vendor_scan(t, url)
    if v == "vendor":
        return "vendor"
    return "phrase" if (v == "suspect" or phrase_hit(body)) else None


# 不跳转的登录墙（任何非 3xx 状态，含 200）：只看结构特征，不对全文做单词匹配（FRED 等正常页面有 id="signin-wrap"
# 之类的属性或页眉「Sign in」链接，不能误伤）。特征：
#   T  <title> 含 sign in / log in / login / password（或 登录 / 登入）
#   P  <form> 里有密码输入框 <input type=password>
#   A  某个 <form> 的 action 指向登录路径（is_login_url：/login、/signin、/auth、/sso… 或 login./accounts. 主机）
#   F  <form> 内可见文字（含 label、button、submit 的 value）含上述登录词
# 判定：P 且 T；或 T 且 A；或 P 且 A 且 F 且表单外可见文字很短（≤ LOGIN_OUTSIDE_MAX，整页基本就是登录表单）。
# 侧栏 / 页眉里带登录框的普通文章（标题不是登录、正文很长）不算。
_LOGIN_WORDS = re.compile(r"(?<![a-z])(?:sign[\s-]?in|log[\s-]?in|login|sign[\s-]?on|password)(?![a-z])|登录|登入|ログイン", re.I)
LOGIN_OUTSIDE_MAX = 600


def _login_features(text, base=None):
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.title, self.in_title, self.skip, self.form = [], False, 0, 0
            self.pw = self.action = self.has_form = False
            self.form_text, self.outside = [], 0

        def handle_starttag(self, tag, attrs):
            a = {}
            for k, v in attrs:
                a.setdefault(k, v or "")
            if tag == "title":
                self.in_title = True
            elif tag in ("script", "style", "noscript", "template"):
                self.skip += 1
            elif tag == "form":
                self.form += 1; self.has_form = True
                act = a.get("action", "").strip()
                if act:
                    try:
                        full = urljoin(base, act) if base else act
                        self.action = self.action or is_login_url(full if urlsplit(full).scheme else "https://x" + (
                            full if full.startswith("/") else "/" + full))
                    except ValueError:
                        pass
            elif tag == "input" and self.form:
                typ = a.get("type", "").strip().lower()
                if typ == "password":
                    self.pw = True
                if typ in ("submit", "button") and a.get("value"):
                    self.form_text.append(a["value"])

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)

        def handle_endtag(self, tag):
            if tag == "title":
                self.in_title = False
            elif tag in ("script", "style", "noscript", "template") and self.skip:
                self.skip -= 1
            elif tag == "form" and self.form:
                self.form -= 1

        def handle_data(self, d):
            if self.in_title:
                self.title.append(d)
            elif self.skip:
                return
            elif self.form:
                self.form_text.append(d)
            else:
                self.outside += len(" ".join(d.split()))
    p = P()
    try:
        p.feed(text); p.close()
    except Exception:
        pass
    title = " ".join("".join(p.title).split())
    return {"T": bool(title) and len(title) <= 160 and bool(_LOGIN_WORDS.search(title)), "P": p.pw, "A": p.action,
            "F": bool(_LOGIN_WORDS.search(" ".join(p.form_text))), "form": p.has_form, "outside": p.outside}


def login_page(ctype, body, url=None):
    """不跳转的登录页（结构特征，见上）。只判 HTML 形态。"""
    if not body or not htmlish(ctype, body):
        return False
    t = body[:200000].decode("utf-8", "replace") if isinstance(body, bytes) else body[:200000]
    f = _login_features(t, url)
    if not f["form"]:
        return False
    return (f["P"] and f["T"]) or (f["T"] and f["A"]) or \
        (f["P"] and f["A"] and f["F"] and f["outside"] <= LOGIN_OUTSIDE_MAX)


def is_challenge(body, ctype="", headers=None, url=None):
    """高置信验证页（厂商标记）——scrapers.check_body 等用；只命中短语不算。"""
    return classify_page(ctype, body, headers, url) == "vendor"


def plain_html(ctype, body):
    """text/plain 正文却以 HTML 标签开头（XML 文档不算）。只作辅助证据，单独命中不算可疑。"""
    return "text/plain" in (ctype or "").lower() and bool(body) and looks_html({}, body, xml_ok=True)


# XML 根元素按完整 QName（ElementTree 的 {namespace}local 写法）比对
RSS_ROOTS = frozenset({"rss", "{http://www.w3.org/2005/Atom}feed",
                       "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF"})
def xml_root(b):
    """返回 XML 根元素完整 QName。用 xml.parsers.expat 按 XML 编码与语法检查（含 UTF-16、DOCTYPE 引号里的 >）：
    DOCTYPE 有内部子集（has_internal_subset）→ 拒收；出现任何实体声明（EntityDeclHandler）→ 拒收（ValueError）。
    外部 DOCTYPE 放行但不加载（不解析参数实体/外部 DTD；未声明的实体引用 SkippedEntityHandler 拒收）。解析失败抛 ET.ParseError。"""
    import xml.etree.ElementTree as ET
    from xml.parsers import expat

    def doctype(name, sysid, pubid, has_internal_subset):
        if has_internal_subset:
            raise ValueError("xml_internal_subset_or_entity")

    def entity(*_):
        raise ValueError("xml_internal_subset_or_entity")
    root = []
    p = expat.ParserCreate(namespace_separator="}")
    p.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    p.StartDoctypeDeclHandler = doctype
    p.EntityDeclHandler = entity
    p.UnparsedEntityDeclHandler = entity
    p.SkippedEntityHandler = entity          # 外部 DTD 不加载 → 未声明的实体引用一律拒收
    p.StartElementHandler = lambda name, attrs: root.append(name) if not root else None
    try:
        p.Parse(b, True)
    except expat.ExpatError as e:
        raise ET.ParseError(str(e))
    if not root:
        raise ET.ParseError("no root element")
    n = root[0]
    return ("{" + n) if "}" in n else n


def json_ok(b):
    """严格 JSON（重复键判失败），且顶层必须是对象或数组。"""
    from . import strictjson
    try:
        v = strictjson.loads(b.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return False
    return isinstance(v, (dict, list))


def content_suspect(method, headers, body, fmt=None, xml_roots=None):
    """按采集方式校验内容（不再逐个加厂商特征）。返回疑似验证页的原因，正常返回 None。
    任一方式：looks_html 即可疑。rss：XML 根元素的完整 QName 必须是 rss / Atom feed / RDF；api：默认应是
    顶层为对象或数组的 JSON；api 源在 sources.yaml 声明 format: xml 时，根元素完整 QName 必须在它的 xml_roots 中。
    含 DOCTYPE / ENTITY 的 XML 一律拒收。"""
    import gzip, xml.etree.ElementTree as ET
    b = body or b""
    if b[:2] == b"\x1f\x8b":
        try:
            b = gzip.decompress(b)
        except OSError:
            return "gzip_undecodable"
    b = b.lstrip(b"\xef\xbb\xbf \r\n\t")
    if looks_html(headers, b, xml_ok=True):
        return "html"
    if method == "rss" or fmt == "xml":
        roots = RSS_ROOTS if method == "rss" else frozenset(xml_roots or ())
        try:
            root = xml_root(b)
        except ValueError:
            return "xml_internal_subset_or_entity"
        except ET.ParseError:
            return "xml_unparseable"
        return None if root in roots else f"xml_root:{root[:80]}"
    return None if json_ok(b) else "json_unparseable"


FAKEIP_ENV = "MARKJIN_PROXY_FAKEIP_CIDR"
APPROVED = "approved"


class ConfigError(Exception):
    pass


class ArchiveError(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def stamp():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


# ---------------------------------------------------------------- 审批门禁
def approval_gate(s):
    """(ok, reason)。缺任一条件都拒绝采集。"""
    if not s.get("enabled"):
        return False, "not enabled"
    if s.get("approval_status") != APPROVED:
        return False, f"approval_status={s.get('approval_status') or 'missing'}"
    if not str(s.get("approval_basis") or "").strip():
        return False, "approval_basis missing"
    return True, None


# ---------------------------------------------------------------- 路径
def _overlap(a, b):
    return a == b or a in b.parents or b in a.parents


def resolve_private_root(arg, out_root, env="MARKJIN_PRIVATE_DIR"):
    """私有根目录必须由参数或环境变量显式给出（代码里没有默认本机路径），且与公开根目录互不包含。"""
    v = arg or os.environ.get(env)
    if not v:
        raise ConfigError(f"private root required (--private-root or ${env})")
    p, o = Path(v).resolve(), Path(out_root).resolve()
    if _overlap(p, o):
        raise ConfigError("private root and public out-root overlap")
    return p


def resolve_internal_root(arg, out_root, env="MARKJIN_INTERNAL_DIR"):
    v = arg or os.environ.get(env)
    if not v:
        return None
    p = Path(v).resolve()
    if _overlap(p, Path(out_root).resolve()):
        raise ConfigError("internal root and public out-root overlap")
    return p


# ---------------------------------------------------------------- URL 脱敏
def url_sha256(u):
    return hashlib.sha256(u.strip().encode("utf-8")).hexdigest()


def public_url(u, public_params=(), public_path=False):
    """用于一切记录/日志（公开与私有）。默认只写 scheme://主机/ 加完整 URL 的 sha256（作为片段
    #sha256=…），路径、查询串一律不写——路径里也可能有凭证。只有逐条确认路径不含凭证（public_path=True：
    sources.yaml 里该源声明 public_path: true，或逐条许可证据已核实）才写出路径；查询值仍只保留该源
    public_params 声明的参数（日志只记参数个数，见 query_count）。"""
    p = urlsplit(u.strip())
    host = (p.hostname or "").lower()
    netloc = (f"[{host}]" if ":" in host else host) + (f":{p.port}" if p.port else "")
    if not public_path:
        return f"{p.scheme.lower()}://{netloc}/#sha256={url_sha256(u)}"
    keep = set(public_params or ())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k in keep]
    return urlunsplit((p.scheme.lower(), netloc, p.path, urlencode(q), ""))


def query_count(u):
    """URL 中查询参数的个数。日志默认只记个数，不记参数名（参数名本身也可能是秘密）。"""
    return len(parse_qsl(urlsplit(u.strip()).query, keep_blank_values=True))


def host_of(u):
    return (urlsplit(u).hostname or "").lower()


# ---------------------------------------------------------------- 逐条目许可
PUBLIC_LICENSES = {"CC-BY-4.0", "CC0-1.0", "US-Gov-PD"}
EVIDENCE_FIELDS = ("url", "license", "license_url", "evidence_url", "attribution", "verified_by", "verified_at")


def public_fulltext_ok(evidence, url):
    """逐条目判断全文可否进公开目录。默认 False（url+hash-only）。
    需要：针对该 URL 的许可证据记录，字段齐全，许可在白名单内；US-Gov-PD 另需 third_party_excluded: true。"""
    if not evidence:
        return False, "no license evidence (default url+hash-only)"
    miss = [k for k in EVIDENCE_FIELDS if not str(evidence.get(k) or "").strip()]
    if miss:
        return False, "license evidence incomplete: " + ",".join(miss)
    if public_url(evidence["url"]) != public_url(url):
        return False, "license evidence is for a different URL"
    if evidence["license"] not in PUBLIC_LICENSES:
        return False, f"license {evidence['license']} not publishable"
    if evidence["license"] == "US-Gov-PD" and evidence.get("third_party_excluded") is not True:
        return False, "US-Gov-PD needs third_party_excluded: true"
    return True, None


def load_license_evidence(path):
    """JSON Lines，每行一条逐条目证据（字段见 EVIDENCE_FIELDS）。返回 {public_url: evidence}。"""
    out = {}
    if not path:
        return out
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        e = strictjson.loads(line)
        if not isinstance(e, dict) or "url" not in e:
            raise ConfigError(f"license evidence line {n}: not an object with url")
        out[public_url(e["url"])] = e
    return out


# ---------------------------------------------------------------- 目标地址策略（防 SSRF）
BENCHMARK_NET = ipaddress.ip_network("198.18.0.0/15")


def _blocked_ip(ip):
    if ip.version == 6 and (ip.ipv4_mapped or ip.sixtofour):
        inner = ip.ipv4_mapped or ip.sixtofour
        if _blocked_ip(inner) or inner in BENCHMARK_NET:
            return True
    return (not ip.is_global) or ip.is_multicast or ip.is_loopback or ip.is_link_local or ip.is_private \
        or ip.is_reserved or ip.is_unspecified


class AddressPolicy:
    """拒绝本机、内网、链路本地、保留、组播地址：初始 URL、DNS 解析结果、每一跳都查（Fetcher 每跳调用）。

    唯一例外（窄）：fakeip_cidr —— 本机出站经透明代理、DNS 返回代理“假 IP”（RFC 2544 基准网段内的地址）时，
    *主机名*解析到该网段视为“交给已配置的出站代理”。约束：
      - 只能是 198.18.0.0/15（RFC 2544 基准网段）的子网，其他网段一律拒绝配置；
      - 只对 DNS 解析结果生效；URL 中直接写 IP 字面量（含 198.18.x.x）一律拒绝；
      - 同一主机名若还解析出任何其他非公网地址，仍拒绝。
    该模式下真实目标 IP 由代理在远端解析，本地无法核对，这一层残余风险由代理负责（见 scripts/README.md）。"""

    def __init__(self, fakeip_cidr=None, resolver=None):
        self.fakeip = None
        if fakeip_cidr:
            net = ipaddress.ip_network(fakeip_cidr, strict=False)
            if net.version != 4 or not net.subnet_of(BENCHMARK_NET):
                raise ConfigError("fakeip cidr must be inside 198.18.0.0/15")
            self.fakeip = net
        self.resolver = resolver or (lambda h: {a[4][0] for a in socket.getaddrinfo(h, None)})

    def __call__(self, url):
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
        if not host:
            return "no host"
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
        if ip is not None:
            return f"IP literal not public ({ip})" if _blocked_ip(ip) or ip in BENCHMARK_NET else None
        if host == "localhost" or host.endswith(".localhost"):
            return "localhost"
        try:
            addrs = {ipaddress.ip_address(a.split("%")[0]) for a in self.resolver(host)}
        except (OSError, ValueError, UnicodeError) as e:
            return f"dns error ({type(e).__name__})"
        if not addrs:
            return "dns returned no address"
        for a in addrs:
            if self.fakeip is not None and a.version == 4 and a in self.fakeip:
                continue
            if _blocked_ip(a):
                return f"resolves to non-public address ({a})"
        return None




class AllOf:
    """多个地址策略的合取：任一拒绝即拒绝。"""

    def __init__(self, *policies):
        self.policies = [p for p in policies if p is not None]

    def __call__(self, url):
        for p in self.policies:
            why = p(url)
            if why:
                return why
        return None


def check_interval(v):
    """--interval / Fetcher 间隔：必须是有限数且不小于 HOST_INTERVAL。"""
    v = float(v)
    if not math.isfinite(v) or v < HOST_INTERVAL:
        raise ConfigError(f"interval must be a finite number >= {HOST_INTERVAL}")
    return v


# ---------------------------------------------------------------- 只追加档案
def _excl_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


class Archive:
    """一个日期目录（raw/DATE）。文件只独占创建；MANIFEST / DERIVED 清单只追加。路径一律相对本目录。"""

    def __init__(self, day_dir):
        self.day = Path(day_dir)

    def _append(self, name, line):
        self.day.mkdir(parents=True, exist_ok=True)
        with open(self.day / name, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def put(self, rel, data, manifest="MANIFEST.sha256"):
        """独占写入 rel；已存在且字节相同 → 去重返回 False；字节不同 → ArchiveError（拒绝改写）。"""
        p = self.day / rel
        sha = hashlib.sha256(data).hexdigest()
        try:
            _excl_write(p, data)
        except FileExistsError:
            if hashlib.sha256(p.read_bytes()).hexdigest() != sha:
                raise ArchiveError(f"refusing to overwrite {rel}")
            return sha, False
        self._append(manifest, f"{sha}  ./{rel}")
        return sha, True

    def put_raw(self, sub, sid, body, ext):
        sha = hashlib.sha256(body).hexdigest()
        rel = f"{sub}{sid}/{sha}.{ext}"
        self.put(rel, body)
        return rel, sha

    def put_derived(self, sub, sid, src_sha, name, data):
        rel = f"{sub}{sid}/derived/{src_sha}.{name}"
        sha, new = self.put(rel, data, manifest="DERIVED.sha256")
        if new:
            self._append("DERIVED-FROM.tsv", f"./{rel}\t{src_sha}")
        return rel, sha

    def put_json(self, rel, obj):
        return self.put(rel, (json.dumps(obj, ensure_ascii=False, indent=1) + "\n").encode())


def ext_for(ctype, body):
    b = body.lstrip(b"\xef\xbb\xbf \r\n\t")[:1]
    if body[:2] == b"\x1f\x8b":
        return "gz"
    if body[:5] == b"%PDF-" or "pdf" in ctype:
        return "pdf"
    if b in (b"{", b"[") or "json" in ctype:
        return "json"
    if "html" in ctype:
        return "html"
    if b == b"<" or "xml" in ctype:
        return "xml"
    return "bin"


# ---------------------------------------------------------------- 封锁规则与来源健康状态
# 出处：王总 10-18 13:50 决定切回正常模式、恢复 #3/#6（14:15 改为立即生效）；封锁细则由 Grok Bot 定，10-18 13:51 初版，
# 15:22 按审查意见收紧为现行版，底线是王总 10-11 确认的『遇到拦截即停』。现行细则：
#  1. 单次可疑（401/403、429、验证页、登录墙；robots.txt 同样）→ 该主机本轮全部停止（跨进程、跨源生效），429 不重试。
#  2. 被拒的 URL（含跳转起点）至少冷却 COOLDOWN_SECONDS（24 小时）；失败记录按轮次分别保存，补跑旧轮不清新轮的记录。
#     来源级扩展（补充口径，待审查确认）：来源只要还有未到期的 URL 冷却，从下一轮起整个来源都不请求（source cooldown）。
#     本轮停止的只是返回可疑响应的那一跳的主机；跳转起点只冷却该 URL，起点主机不停（r15 ⑤）。
#  3. 一个源最近 WINDOW_ROUNDS（5）轮里有 PENDING_AFTER（3）轮可疑（不要求连续）→ pending-disable：
#     触发那一轮照常跑完，从下一轮起不抓；当轮写报告与 GROK-BOT-REVIEW 汇报，等人工 confirm-disable / enable。
#  4. 没有公布限速的站点，每站（site_of）每分钟最多 1 次（跨进程共享；限速锁文件损坏 → 拒绝请求并报 rate_lock_invalid）；只有 sources.yaml site_rate_limits 写明
#     公布限额和依据的站点按其限额；SEC 维持 5 次/秒。robots Crawl-delay 更严时从严。
#  5. 旧 collector-hosts.json 的主机全部保持停用：未迁移时拒绝运行，迁移（source_health.py migrate）后不再请求；
#     因验证页或登录墙停的（unrecoverable）永不恢复，没有放行开关，只能改 sources.yaml 并重新审批。
#  永不绕过付费墙、登录或验证：不重试、不换 UA、不跑 JS、不带 cookie。
WINDOW_ROUNDS = 5
PENDING_AFTER = 3
KEEP_ROUNDS = 10
COOLDOWN_SECONDS = 24 * 3600
SITE_INTERVAL = 60.0          # 未公布限速的站点：每站每分钟最多 1 次
SOURCE_STATUSES = ("ok", "pending-disable", "disabled")
STATE_VERSION = 2
LEGACY_HOSTS_FILE = "collector-hosts.json"   # 旧 HostState 文件（#3 的持久停用表），只读迁移，不再写
HOST_CATEGORIES = ("bot_check", "login", "http_403", "other")
UNRECOVERABLE_CATEGORIES = frozenset({"bot_check", "login"})
_ROUND_ID = re.compile(r"\d{4}-\d{2}-\d{2}/r[12]")
_SHA = re.compile(r"[0-9a-f]{64}")
SUSPICIOUS_ERRORS = frozenset({"http_401", "http_403", "http_429", "challenge", "suspected_challenge", "login_wall",
                               "robots_http_401", "robots_http_403", "robots_http_429", "robots_challenge",
                               "robots_suspected_challenge", "robots_login_wall"})
_TOP_KEYS = frozenset({"version", "sources", "urls", "host_stops", "hosts", "legacy_imports"})
_SRC_KEYS = frozenset({"status", "rounds", "status_at", "status_reason", "pending_round", "unrecoverable"})
_URL_KEYS = frozenset({"reason", "sid", "host", "at", "until"})
_STOP_KEYS = frozenset({"reason", "sid", "at"})
_HOST_REQ = frozenset({"status", "reason", "category", "unrecoverable"})
_HOST_KEYS = _HOST_REQ | {"review", "since", "origin", "imported_at"}


# r15 ⑦：公开输出（skipped detail、source-health 报告、GROK-BOT-REVIEW）只写固定代码；旧表停用原因、人工 --reason
# 等自由文本只留在私有状态文件（source_health.py report 只打到终端时可看）。
CONTENT_SUSPECT_CODES = frozenset({"html", "gzip_undecodable", "xml_internal_subset_or_entity", "xml_unparseable",
                                   "json_unparseable", "xml_root"})
_PUBLIC_CODES = SUSPICIOUS_ERRORS | frozenset({"network", "too_large", "rate_lock_invalid"})


def public_code(reason):
    """把内部记录的原因收成固定代码（未知一律 other）：suspected_challenge:xml_root:<根元素> → suspected_challenge:xml_root。"""
    r = str(reason or "")
    if r in _PUBLIC_CODES:
        return r
    if r.startswith("suspected_challenge:"):
        sub = r.split(":", 2)[1]
        return f"suspected_challenge:{sub if sub in CONTENT_SUSPECT_CODES else 'other'}"
    return "other"


def status_code(rec):
    """源状态的固定代码（不含 status_reason 原文）。"""
    if rec["status"] == "pending-disable":
        return "pending-disable:suspicious-threshold"
    if rec["status"] == "disabled":
        legacy = str(rec.get("status_reason") or "").startswith(f"legacy {LEGACY_HOSTS_FILE}")
        code = "disabled:legacy-import" if legacy else "disabled:manual-confirm"
        return code + (":unrecoverable" if rec.get("unrecoverable") else "")
    return "ok"


def is_suspicious(error):
    """是否算「可疑结果」（计入源的可疑轮数，并让该主机本轮停止）。网络错误、404、5xx、robots 禁止、
    因冷却 / 本轮主机已停 / 旧表停用而没发请求等都不算。"""
    e = error or ""
    return e in SUSPICIOUS_ERRORS or e.startswith("suspected_challenge:")


def round_id(date, rnd):
    rid = f"{date}/r{int(rnd)}"
    if not _ROUND_ID.fullmatch(rid):
        raise ConfigError(f"bad round id {rid!r}")
    return rid


def normalize_url(u):
    """失败记录用的规范化请求身份：scheme、主机转小写，去默认端口（http:80 / https:443），空路径补 /，去片段；
    路径大小写、尾斜杠、查询串原样保留（它们可能指向不同资源）。"""
    p = urlsplit((u or "").strip())
    scheme = p.scheme.lower()
    host = (p.hostname or "").lower()
    try:
        port = p.port
    except ValueError:
        port = None
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    if p.username or p.password:
        ui = p.netloc.rsplit("@", 1)[0]
        host = f"{ui}@{host}"
    return urlunsplit((scheme, host, p.path or "/", p.query, ""))


def url_key(u):
    """失败 URL 的持久键：规范化后的 sha256（不写 URL 本身）。"""
    return hashlib.sha256(normalize_url(u).encode("utf-8")).hexdigest()


_TWO_LEVEL = frozenset({"co.uk", "ac.uk", "gov.uk", "org.uk", "com.cn", "gov.cn", "edu.cn", "ac.cn", "org.cn", "net.cn",
                        "com.au", "gov.au", "edu.au", "co.jp", "ac.jp", "go.jp", "or.jp", "com.hk", "gov.hk",
                        "com.sg", "gov.sg", "edu.sg", "com.tw", "gov.tw", "co.kr", "go.kr", "co.in", "gov.in"})


def site_of(host):
    """限速用的「站点」：注册域名的近似（最后两段；常见二级后缀取最后三段）。IP 字面量按自身。
    同一站点的所有主机（如 rss.arxiv.org 与 export.arxiv.org）共用一个限速桶。"""
    h = (host or "").lower().strip(".")
    try:
        ipaddress.ip_address(h.strip("[]"))
        return h
    except ValueError:
        pass
    parts = h.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _TWO_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def load_site_limits(cfg):
    """sources.yaml 顶层 site_rate_limits：{站点: {min_interval_s: 正数, basis: 公布限额的出处}}。缺依据或数值不对 → ConfigError。
    只有写明公布限额和依据的站点才按其限额；其余一律 SITE_INTERVAL。SEC 内置 5 次/秒（RATE_GROUPS）。"""
    out = {}
    for site, rec in (cfg or {}).items():
        if not isinstance(rec, dict) or not str(rec.get("basis") or "").strip():
            raise ConfigError(f"site_rate_limits.{site}: basis (published limit source) required")
        v = rec.get("min_interval_s")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ConfigError(f"site_rate_limits.{site}: min_interval_s must be a positive number")
        out[site_of(site)] = float(v)
    return out


class StateError(ValueError):
    """状态文件损坏或结构不对。"""


def legacy_category(reason):
    """旧停用原因（按记录原文）归类：验证页 → bot_check；401 / 登录 → login；403 → http_403；其他 → other。
    bot_check 与 login 属于「不可恢复」：enable 默认拒绝。"""
    r = (reason or "").lower()
    if "challenge" in r or "captcha" in r or "验证" in r:
        return "bot_check"
    if re.search(r"\b401\b", r) or "login" in r or "登录" in r or "auth" in r:
        return "login"
    if re.search(r"\b403\b", r):
        return "http_403"
    return "other"


def read_legacy_hosts(path):
    """严格读取旧 collector-hosts.json（{"hosts": {主机: {reason, at, ...}}, "sources": {sid: {reason, at, host, ...}}}）。
    结构不对 → StateError（不当作空表，避免把停用的主机悄悄放开）。返回 (hosts, sources, 文件 sha256)。"""
    raw = Path(path).read_bytes()
    try:
        d = strictjson.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise StateError(f"legacy host state unreadable: {type(e).__name__}")
    if not isinstance(d, dict):
        raise StateError("legacy host state top level must be an object")
    out = []
    for k in ("hosts", "sources"):
        m = d.get(k, {})
        if not isinstance(m, dict):
            raise StateError(f"legacy host state '{k}' must be an object")
        for name, rec in m.items():
            if not isinstance(rec, dict) or not isinstance(rec.get("reason"), str) or not rec["reason"].strip():
                raise StateError(f"legacy host state '{k}' entry without reason")
        out.append(m)
    return out[0], out[1], hashlib.sha256(raw).hexdigest()


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _nonempty(v):
    return isinstance(v, str) and bool(v.strip())


class SourceHealth:
    """私有状态文件（PRIVATE/state/source-health.json），顶层键恰好是：
    {"version": 2（整数）,
     "sources": {sid: {"status": ok|pending-disable|disabled, "rounds": {"YYYY-MM-DD/rN": {"suspicious": bool, "reasons": [..]}},
                       ["status_at", "status_reason", "pending_round": 触发 pending 的轮次, "unrecoverable": bool]}},
     "urls": {轮次: {url_key(规范化 URL): {"reason", "sid": 字符串或 null（必填）, "host", "at": 秒, "until": 秒}}},
     "host_stops": {轮次: {主机: {"reason", "sid", "at"}}},
     "hosts": {主机: 旧表迁移来的停用条目（status=disabled、review=pending-manual-review、reason 原文、category、unrecoverable…）},
     "legacy_imports": {旧文件 sha256: 迁移时间}}
    urls 与 host_stops 按轮次分别保存：写一轮不会动别的轮。URL 冷却按 until（≥24 小时）判定，过期才清理；
    host_stops 只保留最近 KEEP_ROUNDS 个轮次。只存 URL 的 sha256，不写 URL 本身。
    严格读取：顶层键、各条目的键与类型都必须精确匹配（多键、少键、2.0、true 都算损坏）；文件不存在 = 首次运行。
    损坏时 blocked() 对一切请求返回拒绝，report() 抛 StateError，写操作一律拒绝改写。
    写入：fcntl 排他锁（同目录 locks/<name>.lock）内重读磁盘、只改本次条目，mkstemp + fsync + os.replace。"""

    def __init__(self, path, clock=None):
        self.path = Path(path) if path else None
        self.clock = clock or (lambda: time.time())     # 冷却按墙钟；调用时取 time.time（测试可替换）
        self.data = self._empty()
        self.error = None
        try:
            self.refresh()
        except StateError as e:
            self.error = str(e)

    @staticmethod
    def _empty():
        return {"version": STATE_VERSION, "sources": {}, "urls": {}, "host_stops": {}, "hosts": {}, "legacy_imports": {}}

    # -- 读取与校验
    def _read(self):
        if not (self.path and self.path.exists()):
            return self._empty()
        try:
            d = strictjson.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise StateError(f"source health unreadable: {type(e).__name__}")
        self.validate(d)
        return d

    @staticmethod
    def validate(d):
        def bad(msg):
            raise StateError(msg)
        if not isinstance(d, dict):
            bad("source health top level must be an object")
        if set(d) != _TOP_KEYS:
            bad(f"source health top-level keys must be exactly {sorted(_TOP_KEYS)}")
        if type(d["version"]) is not int or d["version"] != STATE_VERSION:
            bad(f"source health version must be the integer {STATE_VERSION}")
        if not all(isinstance(d[k], dict) for k in _TOP_KEYS - {"version"}):
            bad("source health sections must be objects")
        for sid, rec in d["sources"].items():
            if not sid or not isinstance(rec, dict) or not {"status", "rounds"} <= set(rec) <= _SRC_KEYS or \
                    rec["status"] not in SOURCE_STATUSES or not isinstance(rec["rounds"], dict):
                bad("source health entry malformed")
            for rid, rr in rec["rounds"].items():
                if not _ROUND_ID.fullmatch(rid) or not isinstance(rr, dict) or set(rr) != {"suspicious", "reasons"} or \
                        not isinstance(rr["suspicious"], bool) or not isinstance(rr["reasons"], list) or \
                        not all(isinstance(x, str) for x in rr["reasons"]):
                    bad("source health round entry malformed")
            if rec["status"] != "ok" and not _nonempty(rec.get("status_reason")):
                bad("non-ok source without status_reason")
            if rec["status"] == "pending-disable" and not _ROUND_ID.fullmatch(str(rec.get("pending_round"))):
                bad("pending-disable source without pending_round")
            if "unrecoverable" in rec and not isinstance(rec["unrecoverable"], bool):
                bad("source health entry malformed")
            for k in ("status_at", "status_reason", "pending_round"):
                if k in rec and rec[k] is not None and not isinstance(rec[k], str):
                    bad("source health entry malformed")
        for rid, m in d["urls"].items():
            if not _ROUND_ID.fullmatch(rid) or not isinstance(m, dict):
                bad("source health urls round malformed")
            for k, rec in m.items():
                if not _SHA.fullmatch(k) or not isinstance(rec, dict) or set(rec) != _URL_KEYS or \
                        not _nonempty(rec["reason"]) or not (rec["sid"] is None or _nonempty(rec["sid"])) or \
                        not isinstance(rec["host"], str) or not _num(rec["at"]) or not _num(rec["until"]) or \
                        rec["until"] < rec["at"] + COOLDOWN_SECONDS:
                    bad("source health url entry malformed")
        for rid, m in d["host_stops"].items():
            if not _ROUND_ID.fullmatch(rid) or not isinstance(m, dict):
                bad("source health host_stops round malformed")
            for h, rec in m.items():
                if not h or not isinstance(rec, dict) or set(rec) != _STOP_KEYS or not _nonempty(rec["reason"]) or \
                        not (rec["sid"] is None or _nonempty(rec["sid"])) or not _num(rec["at"]):
                    bad("source health host_stop entry malformed")
        for h, rec in d["hosts"].items():
            if not h or not isinstance(rec, dict) or not _HOST_REQ <= set(rec) <= _HOST_KEYS or \
                    rec["status"] != "disabled" or not _nonempty(rec["reason"]) or \
                    rec["category"] not in HOST_CATEGORIES or not isinstance(rec["unrecoverable"], bool):
                bad("source health host entry malformed")
        for k, v in d["legacy_imports"].items():
            if not _SHA.fullmatch(k) or not isinstance(v, str):
                bad("source health legacy_imports entry malformed")

    def refresh(self):
        if self.path:
            self.data = self._read()
            self.error = None

    def _fresh(self):
        """每次判定前以磁盘为准；损坏返回原因字符串。"""
        try:
            self.refresh()
        except StateError as e:
            self.error = str(e)
        return self.error

    # -- 查询
    def blocked(self, sid=None, rid=None):
        """拒绝原因或 None：状态文件损坏 → 一律拒绝；disabled → 立即拒绝；pending-disable → 从触发轮的下一轮起拒绝
        （rid 为空时保守拒绝）。"""
        bad = self._fresh()
        if bad:
            return f"source health invalid ({bad}); refusing requests"
        rec = self.data["sources"].get(sid) if sid else None
        if rec and rec["status"] != "ok" and not (rec["status"] == "pending-disable" and rid and rid <= rec["pending_round"]):
            return f"source {status_code(rec)}"          # r15 ⑦：只写固定代码，不写 status_reason 原文
        return self.source_cooling(sid, rid)             # 触发 pending 的那一轮照常跑完（但仍受来源冷却约束）

    def source_cooling(self, sid, rid, now=None):
        """来源级冷却（补充口径，待审查确认）：该来源在别的轮次被拒、且仍有未到期（≥24 小时）的 URL 冷却记录 →
        下一轮起整个来源都不请求（不只那个 URL），直到最晚的那条记录到期。触发的那一轮不受此限（同主机已按规则 1 停止）；
        没有轮次上下文时保守拒绝。只看持久状态（跨运行生效）。返回固定代码或 None。"""
        if not sid:
            return None
        t = self.clock() if now is None else now
        for r in sorted(self.data["urls"], reverse=True):
            if r == rid:
                continue
            for u in self.data["urls"][r].values():
                if u["sid"] == sid and u["until"] > t:
                    return f"source cooldown:{public_code(u['reason'])}"
        return None

    def host_blocked(self, host):
        """旧表迁移来的停用主机（或状态文件损坏）→ 拒绝原因；否则 None。对这些主机不发任何请求（含 robots.txt）。"""
        bad = self._fresh()
        if bad:
            return f"source health invalid ({bad}); refusing requests"
        rec = self.data["hosts"].get((host or "").lower())
        if rec:                                            # r15 ⑦：只写固定代码（类别），不写旧表原因原文
            return f"host disabled:legacy-import:{rec['category']}{':unrecoverable' if rec['unrecoverable'] else ''}"
        return None

    def host_stopped(self, host, rid):
        """本轮该主机已因可疑响应停止 → 原因；否则 None。损坏 → 拒绝原因。"""
        bad = self._fresh()
        if bad:
            return f"source health invalid ({bad}); refusing requests"
        rec = self.data["host_stops"].get(rid or "", {}).get((host or "").lower())
        return public_code(rec["reason"]) if rec else None

    def url_cooling(self, url, now=None):
        """该 URL（规范化后）在任一轮被拒且仍在冷却期 → 原因；否则 None。损坏 → 拒绝原因。"""
        bad = self._fresh()
        if bad:
            return f"source health invalid ({bad}); refusing requests"
        t = self.clock() if now is None else now
        k = url_key(url)
        for rid in sorted(self.data["urls"], reverse=True):
            rec = self.data["urls"][rid].get(k)
            if rec and rec["until"] > t:
                return public_code(rec["reason"])
        return None

    @staticmethod
    def window(rec):
        """最近 WINDOW_ROUNDS 个记录过的轮次（新→旧）。"""
        return sorted(rec.get("rounds", {}), reverse=True)[:WINDOW_ROUNDS]

    @classmethod
    def suspicious_in_window(cls, rec):
        return sum(1 for r in cls.window(rec) if rec["rounds"][r]["suspicious"])

    # -- 写入（锁内重读）
    def _locked_update(self, fn):
        if not self.path:
            return fn(self.data)
        import fcntl
        import tempfile
        self.path.parent.mkdir(parents=True, exist_ok=True)
        locks = self.path.parent / "locks"
        locks.mkdir(parents=True, exist_ok=True)
        with open(locks / f"{self.path.name}.lock", "a+") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            try:
                d = self._read()                       # 损坏 → StateError，不改写
                out = fn(d)
                self.validate(d)                       # 写出前同样严格校验
                fd, tmp = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
                        f.flush(); os.fsync(f.fileno())
                    os.replace(tmp, self.path)
                except BaseException:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
                    raise
                self.data, self.error = d, None
                return out
            finally:
                fcntl.flock(lk, fcntl.LOCK_UN)

    def stop(self, urls, rid, sid, reason):
        """单次可疑：urls[0] = 返回可疑响应的那一跳，其余为跳转起点等。每个 URL 各记一条冷却 ≥24 小时的失败记录（记在本轮
        名下）；只有 urls[0] 的主机记为本轮停止（r15 ⑤：起点主机不停，如 doi.org 跳到出版商 403，同轮其他 DOI 照常）。
        只动本轮的条目；别的轮只清理冷却已过期的 URL 记录。"""
        if not _ROUND_ID.fullmatch(rid or ""):
            raise ConfigError(f"bad round id {rid!r}")
        t = float(self.clock())

        def upd(d):
            for r in list(d["urls"]):
                d["urls"][r] = {k: v for k, v in d["urls"][r].items() if v["until"] > t}
                if not d["urls"][r] and r != rid:
                    del d["urls"][r]
            cur = d["urls"].setdefault(rid, {})
            stops = d["host_stops"].setdefault(rid, {})
            for u in urls:
                cur.setdefault(url_key(u), {"reason": reason, "sid": sid, "host": host_of(u), "at": t,
                                            "until": t + COOLDOWN_SECONDS})
            if urls:
                stops.setdefault(host_of(urls[0]), {"reason": reason, "sid": sid, "at": t})
            for old in sorted(d["host_stops"])[:-KEEP_ROUNDS]:
                del d["host_stops"][old]
        self._locked_update(upd)

    def record_round(self, rid, results):
        """results: {sid: [可疑原因, ...]}（空列表 = 该源本轮实际请求过且无可疑）。同一轮重复记录按「任一次可疑即可疑」合并。
        最近 WINDOW_ROUNDS 轮里可疑轮数达到 PENDING_AFTER 且状态为 ok → pending-disable（记 pending_round = 本轮）。
        返回 {sid: 本轮新转入 pending-disable 与否}。"""
        if not _ROUND_ID.fullmatch(rid or ""):
            raise ConfigError(f"bad round id {rid!r}")
        changed = {}

        def upd(d):
            for sid, reasons in results.items():
                rec = d["sources"].setdefault(sid, {"status": "ok", "rounds": {}})
                rr = rec["rounds"].setdefault(rid, {"suspicious": False, "reasons": []})
                rr["suspicious"] = rr["suspicious"] or bool(reasons)
                rr["reasons"] = sorted(set(rr["reasons"]) | set(reasons))
                for old in sorted(rec["rounds"])[:-KEEP_ROUNDS]:
                    del rec["rounds"][old]
                n = self.suspicious_in_window(rec)
                changed[sid] = False
                if rec["status"] == "ok" and n >= PENDING_AFTER:
                    rec.update(status="pending-disable", status_at=now(), pending_round=rid,
                               status_reason=f"{n} of the last {WINDOW_ROUNDS} rounds had suspicious results; "
                                             f"awaiting Grok Bot review")
                    changed[sid] = True
        self._locked_update(upd)
        return changed

    def set_status(self, sid, status, reason):
        """人工操作：confirm-disable（status=disabled，须写明确认依据，立即生效）或 enable（status=ok，清空轮次）。
        r15 ②：旧表迁移且标 unrecoverable（验证页 / 登录墙）的源一律不恢复（ConfigError），没有任何放行开关；
        只能改 sources.yaml（换源）并重新审批。"""
        if status not in ("ok", "disabled"):
            raise ConfigError(f"bad status {status!r}")
        if status != "ok" and not (reason or "").strip():
            raise ConfigError("reason required")

        def upd(d):
            rec = d["sources"].setdefault(sid, {"status": "ok", "rounds": {}})
            if status == "ok" and rec.get("unrecoverable"):
                raise ConfigError(f"source {sid} is marked unrecoverable (bot check / login); not re-enabled — "
                                  f"change sources.yaml and get it re-approved instead")
            if status == "ok":
                d["sources"][sid] = {"status": "ok", "rounds": {}, "status_at": now(),
                                     "status_reason": reason or "manually re-enabled"}
            else:
                rec.pop("pending_round", None)
                rec.update(status="disabled", status_at=now(), status_reason=reason.strip())
        self._locked_update(upd)

    def legacy_pending(self, legacy_path):
        """旧 collector-hosts.json 存在且尚未迁移（按文件 sha256）→ True。旧文件损坏 → StateError。"""
        _, _, sha = read_legacy_hosts(legacy_path)
        bad = self._fresh()
        if bad:
            raise StateError(bad)
        return sha not in self.data["legacy_imports"]

    def migrate_legacy(self, legacy_path):
        """把旧 collector-hosts.json 的每个主机 / 源迁移为「已停用、等人工复核」（不自动恢复，不参与可疑计数）。
        幂等：同一份旧文件（按 sha256）只迁移一次；已存在的主机条目不覆盖。旧文件不改不删。
        返回 {"hosts": 新迁移主机数, "sources": 新迁移源数, "skipped": 旧文件是否已迁移过}。"""
        hosts, sources, sha = read_legacy_hosts(legacy_path)
        res = {"hosts": 0, "sources": 0, "skipped": False}

        def upd(d):
            if sha in d["legacy_imports"]:
                res["skipped"] = True
                return
            for h, rec in sorted(hosts.items()):
                h = h.lower()
                if h in d["hosts"]:
                    continue
                cat = legacy_category(rec["reason"])
                d["hosts"][h] = {"status": "disabled", "review": "pending-manual-review", "reason": rec["reason"].strip(),
                                 "since": rec.get("at") if isinstance(rec.get("at"), str) else None, "category": cat,
                                 "unrecoverable": cat in UNRECOVERABLE_CATEGORIES,
                                 "origin": f"legacy {LEGACY_HOSTS_FILE}", "imported_at": now()}
                res["hosts"] += 1
            for sid, rec in sorted(sources.items()):
                cur = d["sources"].get(sid)
                if cur and cur["status"] == "disabled":
                    continue
                cat = legacy_category(rec["reason"])
                d["sources"][sid] = {"status": "disabled", "rounds": (cur or {}).get("rounds", {}),
                                     "status_at": rec.get("at") if isinstance(rec.get("at"), str) else now(),
                                     "status_reason": f"legacy {LEGACY_HOSTS_FILE}: {rec['reason'].strip()}; "
                                                      f"awaiting manual review",
                                     "unrecoverable": cat in UNRECOVERABLE_CATEGORIES}
                res["sources"] += 1
            d["legacy_imports"][sha] = now()
        self._locked_update(upd)
        return res

    def enable_host(self, host, reason):
        """人工恢复旧表迁移来的停用主机（须写明依据）。r15 ②：unrecoverable（bot_check / login）一律不恢复，没有放行开关。"""
        host = (host or "").lower()

        def upd(d):
            rec = d["hosts"].get(host)
            if rec is None:
                raise ConfigError(f"host {host} not disabled")
            if not (reason or "").strip():
                raise ConfigError("reason required")
            if rec["unrecoverable"]:
                raise ConfigError(f"host {host} is marked unrecoverable ({rec['category']}); not re-enabled — "
                                  f"change sources.yaml and get it re-approved instead")
            del d["hosts"][host]
        self._locked_update(upd)

    def _strict(self):
        bad = self._fresh()
        if bad:
            raise StateError(bad)

    def host_report(self):
        """旧表迁移来的停用主机（私有：只给 source_health.py report，不写进公开目录）。读取失败 → StateError。"""
        self._strict()
        return [dict(rec, host=h) for h, rec in sorted(self.data["hosts"].items())]

    def report(self, sids=None, include_text=False):
        """报告条目：所有非 ok 的源，以及最近 WINDOW_ROUNDS 轮内有可疑轮的源（watch）。pending-disable 标明交 Grok Bot 复核。
        r15 ⑦：只写固定代码（reason_code、各轮 reasons 经 public_code），可写进公开目录；include_text=True 时另附
        status_reason 原文（只给 source_health.py report 打到终端，不得写进公开目录）。读取失败 → StateError（不输出旧缓存）。"""
        self._strict()
        out = []
        for sid, rec in sorted(self.data["sources"].items()):
            if sids is not None and sid not in sids:
                continue
            n = self.suspicious_in_window(rec)
            if rec["status"] == "ok" and n == 0:
                continue
            recent = [{"round": r, "suspicious": rec["rounds"][r]["suspicious"],
                       "reasons": sorted({public_code(x) for x in rec["rounds"][r]["reasons"]})} for r in self.window(rec)]
            e = {"id": sid, "status": rec["status"] if rec["status"] != "ok" else "watch",
                 "suspicious_rounds_in_window": n, "window": WINDOW_ROUNDS, "threshold": PENDING_AFTER, "recent": recent}
            if rec["status"] == "pending-disable":
                e.update(flag="grok-bot-review", since=rec.get("status_at"), pending_round=rec.get("pending_round"),
                         effective="from the round after pending_round",
                         action="confirm-disable or enable (scripts/source_health.py)")
            elif rec["status"] == "disabled":
                e.update(since=rec.get("status_at"))
            if rec["status"] != "ok":
                e["reason_code"] = status_code(rec)
            if include_text and rec.get("status_reason"):
                e["status_reason_private"] = rec["status_reason"]
            out.append(e)
        return out


def open_source_health(priv_root, clock=None):
    """打开 PRIVATE/state/source-health.json。同目录有旧 collector-hosts.json 且尚未迁移 → StateError（拒绝运行，
    须先 scripts/source_health.py migrate）；旧文件损坏同样 StateError。不会把旧表停用的主机悄悄放开。"""
    st = Path(priv_root) / "state"
    h = SourceHealth(st / "source-health.json", clock=clock)
    legacy = st / LEGACY_HOSTS_FILE
    if h.error:
        raise StateError(h.error)
    if legacy.exists() and h.legacy_pending(legacy):
        raise StateError(f"legacy {LEGACY_HOSTS_FILE} not migrated; run scripts/source_health.py migrate first")
    return h


def review_md(date, rnd, entries, newly):
    """pending-disable 源的当天汇报片段（只含源 id、轮次与原因，不含 URL）。capture_sources 与 fetch_primary 共用。"""
    out = [f"# {date} round-{rnd}：待 Grok Bot 复核（pending-disable）", "",
           f"以下源最近 {WINDOW_ROUNDS} 轮里有 {PENDING_AFTER} 轮及以上可疑，已转为 pending-disable：触发轮照常跑完，"
           "下一轮起不再请求，等人工 `scripts/source_health.py confirm-disable` 或 `enable`。"
           "请把本节写进当天 capture-failures.md 并报给 Grok Bot。", "",
           "| 源 | 本轮新转入 | 最近 5 轮可疑轮数 | 触发轮 | 最近原因 |", "|---|---|---|---|---|"]
    for e in entries:
        why = "; ".join(f"{x['round']}: {', '.join(x['reasons']) or '-'}" for x in e.get("recent", []) if x["suspicious"])
        out.append(f"| {e['id']} | {'是' if newly.get(e['id']) else '否（此前已转入）'} | "
                   f"{e['suspicious_rounds_in_window']} | {e.get('pending_round') or '-'} | {why} |")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- 抓取层
def suspect_status(st):
    return st in (401, 429) or 500 <= st < 600


_TAG_START = re.compile(rb"<(?:!|\?|/?[a-z][a-z0-9-]*(?:\s|>|/>))", re.I)   # 标签名后必须是空白、> 或 />


_HTML_TAGS = frozenset(b"html head body div p span script title meta link form iframe noscript style br a img table "
                       b"center main section header footer h1 h2 h3 h4 h5 h6 ul li button input".split())
_PROLOG = re.compile(rb"(?:\s*(?:<\?[^>]*\?>|<!--.*?-->|<!doctype(?!\s+html)[^>]*>))*\s*", re.I | re.S)
_FIRST_EL = re.compile(rb"<([a-z][a-z0-9:-]*)(?=\s|>|/>)", re.I)


def looks_html(headers, body, xml_ok=False):
    """是否 HTML：Content-Type 含 html，或正文（去 BOM/空白后）以 < 开头的标签片段（含 text/plain 下的
    <div>…、<!doctype …>、<?xml …>）。robots.txt 正文合法情况下不会以标签开头，所以默认任何标签开头都算。
    xml_ok=True（rss/api 内容校验用）：XML 文档不算 HTML，除非跳过 XML 声明/注释后第一个元素是 HTML 标签
    或 <!doctype html>；根元素对不对由 content_suspect 另行校验。"""
    ct = ((headers or {}).get("Content-Type") or "").lower()
    head = body[:2048].lstrip(b"\xef\xbb\xbf \r\n\t").lower()
    if "html" in ct or head.startswith(b"<!doctype html"):
        return True
    if xml_ok:
        m = _FIRST_EL.match(head, _PROLOG.match(head).end())
        return bool(m) and m.group(1) in _HTML_TAGS
    return bool(_TAG_START.match(head)) or b"<html" in head or b"<body" in head or b"<script" in head


_NO_SID = object()      # _raw 未给源（直接调用）：不重查源状态
# 没发请求的结果（不算本轮联系过该源，也不算可疑）
NO_CONTACT = frozenset({"host_disabled", "not_configured", "source_blocked", "host_stopped_this_round", "url_cooldown",
                        "rate_lock_invalid"})


def _read_rate_lock(text):
    """严格读取站点限速锁文件：空文件 = 首次使用；否则必须是 {"site": 数, "hosts": {主机: 数}}（site 可缺）。
    损坏返回 None（r15 ⑥：调用方拒绝请求并报错，不当空桶放行）。"""
    if not (text or "").strip():
        return {"hosts": {}}
    try:
        rec = strictjson.loads(text)
    except ValueError:
        return None
    if not isinstance(rec, dict) or not set(rec) <= {"site", "hosts"} or not isinstance(rec.get("hosts", {}), dict):
        return None
    if "site" in rec and not _num(rec["site"]):
        return None
    hosts = dict(rec.get("hosts", {}))
    if not all(isinstance(k, str) and _num(v) for k, v in hosts.items()):
        return None
    return {**({"site": rec["site"]} if "site" in rec else {}), "hosts": hosts}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Result:
    def __init__(self, ok, status=0, ctype="", body=b"", final_url=None, hops=(), error=None, detail=None):
        self.ok, self.status, self.ctype, self.body = ok, status, ctype, body
        self.final_url, self.hops, self.error, self.detail = final_url, list(hops), error, detail

    @property
    def sha256(self):
        return hashlib.sha256(self.body).hexdigest() if self.body else None


def retry_after(headers):
    v = (headers or {}).get("Retry-After")
    if not v:
        return None
    v = v.strip()
    if v.isdigit():
        return float(v)
    try:
        t = email.utils.parsedate_to_datetime(v)
        return max(0.0, (t - dt.datetime.now(dt.timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


class Fetcher:
    def __init__(self, state=None, interval=HOST_INTERVAL, timeout=30, opener=None, sleep=time.sleep,
                 clock=time.monotonic, max_bytes=MAX_BYTES, log=None, addr_policy=None, resolver=None,
                 fakeip_cidr=None, lock_dir=None, round_id=None, wall=None, site_limits=None):
        # state = SourceHealth（逐源可疑计数、按轮次的失败 URL 与主机停止）；round_id = "YYYY-MM-DD/rN"
        self.state = state if state is not None else SourceHealth(None)
        if self.state.path and not round_id:
            raise ConfigError("round_id required with a persistent source health state")
        self.round_id = round_id or LOCAL_ROUND
        self.suspicious = {}       # sid（无源时为 None）→ [{"reason", "host"}]：本轮该源的可疑结果，交 record_round
        self.contacted = set()     # 本轮实际发出过请求的 sid（只有这些源记一轮；没发请求的不算正常也不算可疑）
        self._robots_bad = {}      # scheme://host → 本轮 robots.txt 的可疑原因
        self._robots_err = {}      # scheme://host → robots.txt 没能请求的错误（如 rate_lock_invalid），交 _get 原样报出
        # 跨进程锁目录（私有 state/locks）：每站限速桶 rate-site-<站点>.lock、每个 URL 的请求锁 urls/<key>.lock
        self.lock_dir = Path(lock_dir) if lock_dir else None
        interval = float(interval)
        if not math.isfinite(interval):
            raise ConfigError("interval must be finite")
        interval = max(interval, HOST_INTERVAL)   # 每主机间隔下限 2s，不能调低
        # 地址策略强制安装，不能关闭：fakeip_cidr 缺省取环境变量（同样受 AddressPolicy 的网段限制）。
        # addr_policy 是额外策略，只能更严：两者都放行才放行。
        self.resolver = resolver
        self._forced_policy = AddressPolicy(fakeip_cidr if fakeip_cidr is not None else os.environ.get(FAKEIP_ENV),
                                            resolver=resolver)
        self.addr_policy = addr_policy
        self.interval, self.timeout, self.max_bytes = interval, timeout, max_bytes
        self.opener = opener or urllib.request.build_opener(_NoRedirect)
        self.sleep, self.clock = sleep, clock
        self.wall = wall or ((lambda: time.time()) if clock is time.monotonic else clock)   # 跨进程限速用墙钟
        self.site_limits = dict(site_limits or {})
        self._last, self._site_last, self._host_interval, self._robots = {}, {}, {}, {}
        self.robots_note = {}
        self.log = log or (lambda *_: None)
        self.requests = []     # (host, t) — 供测试/审计
        self.sec_ua = sec_user_agent()
        self._sink = None

    def address_check(self, url):
        """强制策略与外部策略的合取；返回拒绝原因或 None。"""
        return AllOf(self._forced_policy, self.addr_policy)(url)

    # -- 可疑记录：URL 冷却 + 主机本轮停止 + 源事件
    def _event(self, sid, reason, url):
        self.suspicious.setdefault(sid, []).append({"reason": reason, "host": host_of(url)})

    def mark_failed(self, url, sid, reason, also=()):
        """单次可疑：url（返回可疑响应的那一跳）与 also（跳转起点等）冷却 ≥24 小时；只有 url 的主机本轮全部停止
        （持久，跨进程；起点主机不停），给 sid 记一次可疑。"""
        self._event(sid, reason, url)
        urls = [url] + [u for u in also if u and u != url]
        self.state.stop(urls, self.round_id, sid, reason)

    def precheck(self, url):
        """不发请求的拦截：旧表停用主机、本轮主机已停、URL 冷却中。返回 (错误码, 原因) 或 None。都不算可疑。"""
        host = host_of(url)
        why = self.state.host_blocked(host)
        if why:
            return "host_disabled", why
        why = self.state.host_stopped(host, self.round_id)
        if why:
            return "host_stopped_this_round", why
        why = self.state.url_cooling(url)
        if why:
            return "url_cooldown", why
        return None

    def _lock(self, name):
        """跨进程排他锁（无 lock_dir 时为空操作，仅进程内）。"""
        import contextlib
        if not self.lock_dir:
            return contextlib.nullcontext(None)

        @contextlib.contextmanager
        def held():
            import fcntl
            p = self.lock_dir / name
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a+") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX)
                try:
                    yield lk
                finally:
                    fcntl.flock(lk, fcntl.LOCK_UN)
        return held()

    def url_lock(self, url):
        """每个规范化 URL 一把跨进程锁：持锁后重查失败状态，请求、分类、写失败记录都在锁内完成。"""
        return self._lock(f"urls/{url_key(url)[:40]}.lock")

    # -- 每站限速（所有请求都走这里）
    def site_gap(self, host):
        site = site_of(host)
        if site in self.site_limits:
            return self.site_limits[site]
        for g, ggap in RATE_GROUPS.items():      # SEC：公布上限 10 次/秒，这里 5 次/秒
            if in_group(host, g):
                return ggap
        return SITE_INTERVAL

    def _raw(self, url, accept, sid=_NO_SID, judge=None):
        """所有出站请求的唯一入口。持站点限速锁（跨进程）完成：等待 → 等待后重跑完整预检（旧表停用、源状态、本轮主机停止、
        URL 冷却；r15 ①）→ 发请求 → judge（可疑分类与停止写入）。所以「写停止」与同站「发请求」互斥：别的进程在等待期间
        停掉的主机不会再被请求，本进程判定可疑并写下停止之前，同站其他请求也发不出去。
        judge(st, headers, body, ec, det) 在锁内调用，返回值原样交给调用方（第 6 个返回值）。"""
        host = host_of(url)
        why = self.state.host_blocked(host)
        if why:                                # 所有出站入口的最后一道门：旧表停用主机一律不发请求
            return 0, {}, b"", "host_disabled", why, None
        if in_group(host, SEC_SUFFIX):     # 所有出站入口（get、robots、直接调用）统一门禁：缺 UA 或跨进程锁 → 不发请求
            if not self.sec_ua:
                return 0, {}, b"", "not_configured", f"{SEC_UA_ENV} not set (must include contact info)", None
            if not self.lock_dir:
                return 0, {}, b"", "not_configured", "lock_dir not set (SEC requests need the cross-process rate lock)", None
        site = site_of(host)
        sgap = self.site_gap(host)
        hgap = max(self.interval, self._host_interval.get(host, 0))   # 每主机下限与 robots Crawl-delay（更严者）
        with self._lock(f"rate-site-{site}.lock") as lk:
            # 锁文件记 {"site": 上次站内请求时间, "hosts": {主机: 上次请求时间}}（墙钟），持锁直到本次请求与判定结束
            rec = {"hosts": {}}
            if lk is not None:
                lk.seek(0)
                rec = _read_rate_lock(lk.read())
                if rec is None:                # r15 ⑥：锁文件损坏不当空桶放行，拒绝本次请求并报错
                    return 0, {}, b"", "rate_lock_invalid", f"site rate lock for {site} unreadable; refusing request", None
            hosts = rec["hosts"]
            ls = [x for x in (rec.get("site"), self._site_last.get(site)) if _num(x)]
            lh = [x for x in (hosts.get(host), self._last.get(host)) if _num(x)]
            t0 = self.wall()
            w = max(sgap - (t0 - max(ls)) if ls else 0, hgap - (t0 - max(lh)) if lh else 0, 0)
            if w > 0:
                self.sleep(w)
            # r15 ①：等待期间别的进程可能已停掉该主机、记下该 URL 或停用该源 → 同一把锁里重跑完整预检
            why = self.state.host_blocked(host)
            if why:
                return 0, {}, b"", "host_disabled", why, None
            if sid is not _NO_SID:
                why = self.state.blocked(sid, self.round_id)
                if why:
                    return 0, {}, b"", "source_blocked", why, None
            pre = self.precheck(url)
            if pre:
                return 0, {}, b"", pre[0], pre[1], None
            t = self.wall()
            self._site_last[site] = self._last[host] = t
            self.requests.append((host, t))
            if lk is not None:
                hosts[host] = t
                lk.seek(0); lk.truncate(); lk.write(json.dumps({"site": t, "hosts": hosts})); lk.flush()
            st, h, body, ec, det = self._raw_inner(url, accept, host)
            verdict = judge(st, h or {}, body, ec, det) if judge else None
            return st, h, body, ec, det, verdict

    def _raw_inner(self, url, accept, host):
        ua = self.sec_ua if in_group(host, SEC_SUFFIX) and self.sec_ua else UA
        req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": accept,
                                                   "Accept-Encoding": "identity"})
        try:
            r = self.opener.open(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            r = e
        except Exception as e:   # 网络 / TLS / 超时
            return 0, {}, b"", "network", type(e).__name__
        try:
            status = getattr(r, "status", None) or r.getcode()
            headers = r.headers or {}
            buf = r.read(self.max_bytes + 1) or b""
        except Exception as e:
            return 0, {}, b"", "network", type(e).__name__
        finally:
            try:
                r.close()
            except Exception:
                pass
        if len(buf) > self.max_bytes:          # 正文丢弃；调用方仍先按状态码判可疑（401/403/429 → 停主机），再报 too_large
            return status, headers, b"", "too_large", f">{self.max_bytes} bytes"
        if buf and self._sink:     # 每收到一次响应（含 robots、3xx）都先交给私有存档，再做任何判定
            self._sink(buf, status, (headers.get("Content-Type") if headers else "") or "")
        return status, headers, buf, None, None

    def _fetch_once(self, url, accept, sid=_NO_SID, judge=None):
        """只有「没收到任何 HTTP 响应」的网络错误才重试（最多 NET_RETRIES 次、指数退避）。
        收到任何 HTTP 状态（含 429、5xx）都不重发：429 计可疑并停止该主机本轮。每次尝试都走 _raw（锁内重跑预检）。"""
        for attempt in range(NET_RETRIES + 1):
            st, h, body, ec, det, v = self._raw(url, accept, sid=sid, judge=judge)
            if ec != "network" or attempt == NET_RETRIES:
                return st, h or {}, body, ec, det, v
            self.sleep(min(BACKOFF_CAP, BACKOFF_BASE * (2 ** attempt)))
        return st, h or {}, body, ec, det, v

    @staticmethod
    def _classify(st, h, body, url, robots=False):
        """可疑分类：401/403/429 先按状态码；再看验证页（vendor / phrase，任何状态含 200）；跳转到登录页，或不跳转的
        登录页（结构特征，见 login_page，含 200）→ login_wall。"""
        pre = "robots_" if robots else ""
        if st in (401, 403, 429):
            return f"{pre}http_{st}"
        kind = classify_page((h or {}).get("Content-Type") or "", body, h, url)
        if kind == "vendor":
            return f"{pre}challenge"
        if kind == "phrase":
            return f"{pre}suspected_challenge"
        if st in REDIRECT_CODES and (h or {}).get("Location") and is_login_url(urljoin(url, h["Location"])):
            return f"{pre}login_wall"
        if st not in REDIRECT_CODES and login_page((h or {}).get("Content-Type") or "", body, url):
            return f"{pre}login_wall"          # 不跳转的登录页（含 200）：结构特征命中同样是登录墙
        return None

    # -- robots.txt（每个 scheme://host 一份；robots 自身请求同样限速、同样受主机停止与 URL 冷却约束）
    def _disallow_all(self):
        rp = urllib.robotparser.RobotFileParser()
        rp.disallow_all = True
        return rp

    def robots(self, url, sid=None):
        """robots.txt 自身的每一跳也逐跳校验：scheme、t.co 拒绝、跨主机跳转一律按禁止处理。
        robots 返回 401/403/429、验证页或跳登录页 → 与正文相同：该主机本轮全部停止、robots.txt 冷却，给 sid 记一次可疑。"""
        p = urlsplit(url)
        host = (p.hostname or "").lower()
        base = f"{p.scheme}://{p.netloc}"
        if self.state.blocked(sid, self.round_id) or self.precheck(base + "/robots.txt"):
            return self._disallow_all()               # 状态损坏 / 源停用 / 旧表停用 / 本轮主机已停 / 冷却中：不发请求
        if base in self._robots:
            return self._robots[base]
        rp = urllib.robotparser.RobotFileParser()
        start = cur = base + "/robots.txt"
        st, ec, body, h, bad = 0, "too_many_redirects", b"", {}, None
        for hop in range(MAX_REDIRECTS + 1):
            if hop:
                q = urlsplit(cur)
                qh = (q.hostname or "").lower()
                if q.scheme not in ("http", "https") or not qh:
                    st, ec = 0, "robots_bad_redirect"; break
                if qh in REFUSED_HOSTS:
                    st, ec = 0, "robots_redirect_refused_host"; break
                if qh != host:
                    st, ec = 0, "robots_cross_host_redirect"; break
                if self.precheck(cur):
                    st, ec = 0, "robots_redirect_blocked"; break
            why = self.address_check(cur)          # 每一跳 robots 请求前都过强制策略 + 外部策略
            if why:
                st, ec, body, h = 0, "robots_blocked_address", b"", {}; break
            with self.url_lock(cur):
                if self.precheck(cur):              # 持锁后重查（别的进程可能刚停了该主机）
                    st, ec = 0, "robots_redirect_blocked"; break
                def judge(st, h, body, ec, det, _cur=cur):   # 站点限速锁内：分类并写停止（与同站发请求互斥）
                    b = self._classify(st, h, body, _cur, robots=True)
                    if b:                           # robots.txt（及起点）冷却、主机本轮停止
                        self.mark_failed(_cur, sid, b, also=(start,))
                    return b
                st, h, body, ec, rdet, bad = self._fetch_once(cur, "text/plain,*/*", sid=sid, judge=judge)
                if ec not in NO_CONTACT:
                    self.contacted.add(sid)
                if bad:
                    break
            if st in REDIRECT_CODES:
                loc = h.get("Location")
                if not loc:
                    ec = "robots_redirect_without_location"; break
                cur = urljoin(cur, loc)
                st, ec = 0, "too_many_redirects"
                continue
            break
        if bad:
            self._robots_bad[base] = bad
            self.robots_note[base] = f"{bad} (HTTP {st})"
            rp.disallow_all = True
        elif body and looks_html(h, body) and st not in (404, 410):
            self.robots_note[base] = f"robots.txt suspect/HTML (HTTP {st})"   # 格式不对：本轮按禁止，不算可疑
            rp.disallow_all = True
        elif st == 200 and not ec:
            rp.parse(body.decode("utf-8", "replace").splitlines())
            cd = rp.crawl_delay(UA_TOKEN)
            rr = rp.request_rate(UA_TOKEN)
            stricter = max(float(cd or 0), (rr.seconds / rr.requests) if rr and rr.requests else 0)
            if stricter:
                self._host_interval[host] = stricter
        elif st in (404, 410) and not ec:
            rp.allow_all = True
        elif ec == "rate_lock_invalid":    # r15 ⑥：限速锁损坏 → 不请求、不缓存，交 _get 报错
            self._robots_err[base] = (ec, rdet)
            return self._disallow_all()
        else:                     # 5xx/网络错误/跳转被拒 → 本轮按禁止处理
            rp.disallow_all = True
        self._robots[base] = rp
        return rp

    def allowed(self, url, sid=None):
        return self.robots(url, sid).can_fetch(UA_TOKEN, url)

    def get(self, url, sid=None, accept="*/*", raw_sink=None, validate=None):
        """validate(ctype, body) → 格式可疑原因或 None：对最终 200 响应做内容校验（如 rss/api 格式），在 URL 锁与站点限速锁内
        完成，命中即按 suspected_challenge:<原因> 处理（该主机本轮停止、URL 冷却），与状态码 / 验证页判定同一处写停止。"""
        prev, self._sink = self._sink, raw_sink
        try:
            return self._get(url, sid, accept, validate)
        finally:
            self._sink = prev

    def _get(self, url, sid, accept, validate=None):
        """抓一个 URL。不自动重定向：每一跳都重新检查拒绝主机、旧表停用、源状态、本轮主机停止、URL 冷却、robots 与限速。
        sid 可以是函数（按每一跳的主机给出伪源 id，如 fetch_primary 的 primary:<主机>）。
        可疑响应（401/403/429、验证页、跳登录页）：该跳与起点 URL 冷却 ≥24 小时、该跳主机本轮全部停止（起点主机不停），
        给该跳的 sid 记一次可疑；
        不重试、不跟随 Location。「查失败记录—发请求—写记录」在同一把按 URL 的跨进程锁里完成。
        Result.hops 只持有 public_url；final_url 为完整 URL，仅供内存内核对。"""
        sid_of = sid if callable(sid) else (lambda _h, _s=sid: _s)
        hops, cur = [], url
        for _ in range(MAX_REDIRECTS + 1):
            p = urlsplit(cur)
            host = (p.hostname or "").lower()
            if p.scheme not in ("http", "https") or not host:
                return Result(False, final_url=cur, hops=hops, error="bad_url")
            if host in REFUSED_HOSTS:
                return Result(False, final_url=cur, hops=hops, error="refused_host")
            esid = sid_of(host)
            why = self.state.blocked(esid, self.round_id)
            if why:
                return Result(False, final_url=cur, hops=hops, error="source_blocked", detail=why)
            pre = self.precheck(cur)
            if pre:                       # 旧表停用 / 本轮主机已停 / URL 冷却：不发请求，不算可疑
                return Result(False, final_url=cur, hops=hops, error=pre[0], detail=pre[1])
            if in_group(host, SEC_SUFFIX) and not self.sec_ua:   # 未配置 SEC UA：不发请求，不算可疑
                return Result(False, final_url=cur, hops=hops, error="not_configured",
                              detail=f"{SEC_UA_ENV} not set (must include contact info)")
            if in_group(host, SEC_SUFFIX) and not self.lock_dir:  # 没有跨进程限速锁：不发请求
                return Result(False, final_url=cur, hops=hops, error="not_configured",
                              detail="lock_dir not set (SEC requests need the cross-process rate lock)")
            why = self.address_check(cur)   # 每一跳、子 sitemap 都在任何请求前检查
            if why:
                return Result(False, final_url=cur, hops=hops, error="blocked_address", detail=why)
            if not self.allowed(cur, esid):
                err = self._robots_err.pop(f"{p.scheme}://{p.netloc}", None)
                if err:                   # robots.txt 没能请求（限速锁损坏等）：原样报错
                    return Result(False, final_url=cur, hops=hops, error=err[0], detail=err[1])
                bad = self._robots_bad.get(f"{p.scheme}://{p.netloc}")
                if bad:                   # robots.txt 可疑：该主机本轮已停
                    return Result(False, final_url=cur, hops=hops, error=bad, detail=self.robots_note.get(
                        f"{p.scheme}://{p.netloc}"))
                pre = self.precheck(cur) or (("source_blocked", why) if (why := self.state.blocked(esid, self.round_id))
                                             else None)
                if pre:
                    return Result(False, final_url=cur, hops=hops, error=pre[0], detail=pre[1])
                return Result(False, final_url=cur, hops=hops, error="robots_disallow")
            with self.url_lock(cur):
                pre = self.precheck(cur)  # 持锁后重查：别的进程可能刚记下该 URL 或停了该主机
                if pre:
                    return Result(False, final_url=cur, hops=hops, error=pre[0], detail=pre[1])
                def judge(st, h, body, ec, det, _cur=cur, _esid=esid):
                    # 站点限速锁内（与同站发请求互斥）：每一跳先按状态码，再判正文与登录跳转；命中即写停止
                    # r15 ③：超过大小上限（too_large，正文已丢弃）也先按状态码 / 响应头判可疑，再报 too_large
                    b = self._classify(st, h, body, _cur) if ec in (None, "too_large") else None
                    if not b and not ec and st == 200 and validate:   # r15 ④：格式校验也在锁内，命中即写停止
                        v = validate(h.get("Content-Type") or "", body)
                        if v:
                            b = f"suspected_challenge:{v}"
                    if b:                 # 该跳与起点冷却、该跳主机本轮停止
                        self.mark_failed(_cur, _esid, b, also=(url,))
                    return b
                st, h, body, ec, det, bad = self._fetch_once(cur, accept, sid=esid, judge=judge)
                if ec not in NO_CONTACT:
                    self.contacted.add(esid)
                ctype = h.get("Content-Type") or ""
                # 原字节已在 _raw 里交给 raw_sink；分类与停止写入已在锁内完成，最后处理 Location
                if bad:
                    return Result(False, st, ctype, b"", cur, hops, bad)
            if ec:
                return Result(False, st, ctype, b"", cur, hops, ec, det)
            if st in REDIRECT_CODES:
                loc = h.get("Location")
                if not loc:
                    return Result(False, st, final_url=cur, hops=hops, error="redirect_without_location")
                hops.append({"from": public_url(cur), "query_param_count": query_count(cur), "status": st})   # hops 只存脱敏 URL
                cur = urljoin(cur, loc)
                continue
            if st == 200:
                return Result(True, st, ctype, body, cur, hops)
            return Result(False, st, ctype, b"", cur, hops, f"http_{st}")
        return Result(False, final_url=cur, hops=hops, error="too_many_redirects")
