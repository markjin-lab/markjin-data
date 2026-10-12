"""采集公共层（PR #3/#6 审查 REJECTED 修复，2026-10-12）。capture_sources / fetch_primary / scrapers 共用。

规则（每条对应审查意见）：
- 审批门禁：只有 enabled 且 approval_status == approved 且 approval_basis 非空的源才可采集（approval_gate）。
- 许可：默认 url+hash-only。整源、整域名一律不给全文许可；全文进公开目录只能逐条目、凭已核实的许可证据
  （license_evidence，见 public_fulltext_ok），否则一律私有。
- 原件：响应原字节不解压、不脱敏，按 sha256 独占创建写入私有档案，并追加 MANIFEST.sha256；
  解压、提取、条目 JSON 只作派生物另存（derived/，登记 DERIVED.sha256，带 derived_from）。
- 每次运行写入的公开文件都按运行戳独占创建（不覆盖），并追加到当天公开 MANIFEST.sha256。
- 访问礼仪：如实 UA（含联系方式）；每次请求（含每一跳重定向、子 sitemap、robots.txt 本身）都按主机限速；
  每一跳都先查目标主机 robots.txt 与停用状态；不自动跟随重定向；拒绝 t.co。
- 403 / 验证页：持久写入停用状态（主机 + 源），人工复核后才恢复；只有 429、5xx、网络错误按
  Retry-After 或指数退避重试，次数与等待均有上限。
- robots.txt 自身的跳转逐跳校验（scheme / t.co / 停用 / 跨主机即禁止）；robots 403 或验证页 → 持久停用。
- 一切日志（公开与私有）不写本机路径、不写凭证：URL 不带查询值（只记参数个数，不记参数名；按源 public_params 声明的才留值），hops 只存脱敏 URL；
- 地址策略强制安装（AddressPolicy，每一跳/子 sitemap 在任何请求前检查）；外部策略只能叠加更严。
- robots.txt 返回 HTTP 200 的 HTML → 一律按验证页处理并持久停用。私有根目录必须显式给出且不能与公开根目录重叠。
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
# SEC（*.sec.gov）要求 UA 带联系方式：只从环境变量读取；未设置则 SEC 请求一律不发（not_configured），不停用
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
MAX_RETRIES = 3
BACKOFF_BASE = 2.0
BACKOFF_CAP = 120.0          # Retry-After 超过此值直接放弃本次（不长时间挂起）
REFUSED_HOSTS = {"t.co"}
REDIRECT_CODES = {301, 302, 303, 307, 308}
# 验证页识别（collector 与 scrapers 共用这一份）。总原则：只有 403 和高置信的验证页（命中厂商标记）才持久停用；
# 格式不对、只命中泛用短语，只记本轮失败/可疑，不停用。
# 高置信厂商标记：用 html.parser 逐个标签解析，只看精确属性（class、src、id），不用字节正则：
#  - <script src>（只认 script 元素）：urlsplit 核对——主机 challenges.cloudflare.com；hcaptcha.com 下的 …/api.js；
#    google.com / recaptcha.net 下的 /recaptcha/…api.js；相对地址（无主机）且路径以 /cdn-cgi/challenge-platform/ 开头，
#    或路径含 _Incapsula_Resource（这两种只认 script，且不认别的主机）
#  - form#challenge-form；元素 class（按空白切分）含 cf-turnstile 或 g-recaptcha
#  - div#px-captcha，且整页可见文本很短（≤ PX_TEXT_MAX 字符）
#  - script 内容：先去掉 JS 字符串字面量和注释，只认不在引号里的 window._cf_chl_opt 赋值语句、X.src = '…' 赋值
#    （src 按 script src 规则核对）；script 里的其他文字（如 JS 字符串 '<div class="g-recaptcha">'）不解析为标签
#  - 免检：<textarea>/<xmp>/<plaintext>/<title> 内（按 HTML 规范这些是纯文本）；注释、可见文本。<pre>/<code> 照常检查
#    （其中的 script 一样执行）。data-class / data-src 等不是 class / src
#  - 响应头 cf-mitigated: challenge（见 classify_page）
_LITERAL_TAGS = frozenset({"textarea", "xmp", "plaintext", "title"})
PX_TEXT_MAX = 1000
_CF_CHL_OPT = re.compile(r"(?:^|[;{}()\s,])window\s*\.\s*_cf_chl_opt\s*=(?!=)")
_JS_SRC = re.compile(r"""\.\s*src\s*=\s*(['"])""")


def vendor_src(src, script=True):
    """<script src> 是否指向已知验证组件（urlsplit 核对主机与路径）。script=False（非 script 元素）一律不算。"""
    if not script:
        return False
    try:
        u = urlsplit((src or "").strip())
    except ValueError:
        return False
    host, path = (u.hostname or "").lower(), u.path or ""
    if not u.netloc and (path.startswith("/cdn-cgi/challenge-platform/") or "_Incapsula_Resource" in path):
        return True
    if host == "challenges.cloudflare.com":
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


def _script_hit(js):
    m = _js_mask(js)
    if _CF_CHL_OPT.search(m):
        return True
    for x in _JS_SRC.finditer(m):          # 赋值本身在代码里；值是紧随其后的字符串字面量
        q, start = x.group(1), x.end()
        end = js.find(q, start)
        if end > start and vendor_src(js[start:end]):
            return True
    return False


def _vendor_scan(text):
    from html.parser import HTMLParser

    class Scan(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.hit, self.px, self.lit, self.in_script, self.visible = False, False, 0, 0, 0
            self.sbuf = []

        def handle_starttag(self, tag, attrs):
            if tag in _LITERAL_TAGS:
                self.lit += 1
                return
            if self.lit:
                return
            if tag in ("script", "style"):
                self.in_script = tag
                self.sbuf = []
            if self.hit:
                return
            a = {}
            for k, v in attrs:                 # 精确属性名；同名重复取第一个
                a.setdefault(k, v or "")
            if tag == "script" and "src" in a and vendor_src(a["src"]):
                self.hit = True
            elif tag == "form" and a.get("id", "").strip() == "challenge-form":
                self.hit = True
            elif tag == "div" and a.get("id", "").strip() == "px-captcha":
                self.px = True                 # 还要整页可见文本很短（见末尾）
            elif {"cf-turnstile", "g-recaptcha"} & set(a.get("class", "").split()):
                self.hit = True

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)
            if tag in ("script", "style") and self.in_script == tag:
                self.in_script = 0

        def handle_endtag(self, tag):
            if tag in _LITERAL_TAGS and self.lit:
                self.lit -= 1
            elif tag in ("script", "style") and self.in_script == tag:
                if tag == "script" and not self.hit and _script_hit("".join(self.sbuf)):
                    self.hit = True
                self.in_script = 0

        def handle_data(self, data):
            if self.lit:
                return
            if self.in_script:
                self.sbuf.append(data)
            else:
                self.visible += len(" ".join(data.split()))
    sc = Scan()
    try:
        sc.feed(text)
        sc.close()
    except Exception:        # 解析异常不当作高置信证据
        pass
    if sc.in_script == "script" and not sc.hit and _script_hit("".join(sc.sbuf)):
        sc.hit = True        # 未闭合的 script 也照样检查
    return sc.hit or (sc.px and sc.visible <= PX_TEXT_MAX)


class _VendorMatcher:
    """兼容旧接口：CHALLENGE.search(body_bytes) → 是否命中真正的验证组件。"""

    def search(self, body):
        if isinstance(body, bytes):
            body = body.decode("utf-8", "replace")
        return _vendor_scan(body[:200000]) or None


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


def classify_page(ctype, body, headers=None):
    """返回 'vendor'（厂商标记，高置信 → 持久停用）、'phrase'（只命中泛用短语 → 本轮可疑，不停用）或 None。
    响应头 cf-mitigated: challenge 不论正文都算 vendor；正文只对 HTML 形态判断（JSON / XML / 普通文本交给格式校验）。"""
    for k, v in (headers or {}).items():
        if str(k).lower() == "cf-mitigated" and str(v).strip().lower() == "challenge":
            return "vendor"
    if not body or not htmlish(ctype, body):
        return None
    if CHALLENGE.search(body):
        return "vendor"
    return "phrase" if phrase_hit(body) else None


def is_challenge(body, ctype="", headers=None):
    """高置信验证页（厂商标记）——scrapers.check_body 等用；只命中短语不算。"""
    return classify_page(ctype, body, headers) == "vendor"


def plain_html(ctype, body):
    """text/plain 正文却以 HTML 标签开头（XML 文档不算）。只作辅助证据：须与短语或厂商标记同时命中才停用。"""
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
EVIDENCE_FIELDS = ("url", "sha256", "license", "license_url", "evidence_url", "attribution", "verified_by",
                   "verified_at")


def full_url_key(u):
    """许可匹配用的完整条目身份（审查 r2：不能用脱敏 URL）：只规范 scheme/主机大小写、去片段，
    路径与全部查询参数原样保留。仅在私有侧/内存中使用，不写公开记录。"""
    p = urlsplit(u.strip())
    host = (p.hostname or "").lower()
    netloc = (f"[{host}]" if ":" in host else host) + (f":{p.port}" if p.port else "")
    return urlunsplit((p.scheme.lower(), netloc, p.path or "/", p.query, ""))


def public_fulltext_ok(evidence, url, sha256):
    """逐条目判断全文可否进公开目录。默认 False（url+hash-only）。
    需要：针对该*完整* URL（含全部查询参数）且绑定该响应 sha256 的许可证据，字段齐全，许可在白名单内；
    US-Gov-PD 另需 third_party_excluded: true。原 URL 与最终 URL 须各自有证据、各自核对。"""
    if not evidence:
        return False, "no license evidence (default url+hash-only)"
    miss = [k for k in EVIDENCE_FIELDS if not str(evidence.get(k) or "").strip()]
    if miss:
        return False, "license evidence incomplete: " + ",".join(miss)
    if full_url_key(evidence["url"]) != full_url_key(url):
        return False, "license evidence is for a different URL"
    if not sha256 or str(evidence["sha256"]).strip().lower() != sha256.lower():
        return False, "license evidence sha256 does not match response"
    if evidence["license"] not in PUBLIC_LICENSES:
        return False, f"license {evidence['license']} not publishable"
    if evidence["license"] == "US-Gov-PD" and evidence.get("third_party_excluded") is not True:
        return False, "US-Gov-PD needs third_party_excluded: true"
    return True, None


def load_license_evidence(path):
    """JSON Lines，每行一条逐条目证据（字段见 EVIDENCE_FIELDS）。返回 {full_url_key: evidence}。"""
    out = {}
    if not path:
        return out
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        e = strictjson.loads(line)
        if not isinstance(e, dict) or "url" not in e:
            raise ConfigError(f"license evidence line {n}: not an object with url")
        out[full_url_key(e["url"])] = e
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

    def put_derived(self, sub, sid, src_sha, name, data, sources=None):
        """sources：参与生成的全部原件 sha256（多份 sitemap 等）；DERIVED-FROM.tsv 逐一登记（逗号分隔）。"""
        rel = f"{sub}{sid}/derived/{src_sha}.{name}"
        sha, new = self.put(rel, data, manifest="DERIVED.sha256")
        if new:
            srcs = list(dict.fromkeys(sources or [src_sha]))
            self._append("DERIVED-FROM.tsv", f"./{rel}\t{','.join(srcs)}")
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


# ---------------------------------------------------------------- 持久停用状态
class HostState:
    """{"hosts": {host: {...}}, "sources": {sid: {...}}}。只由采集器写入停用；恢复须人工（enable() 或 enable-host 命令）。
    磁盘为准：refresh() 用磁盘快照直接替换缓存（人工删掉的条目立即生效）；disable()/enable() 在 fcntl 排他锁
    （状态文件同目录 locks/<name>.lock，即私有 state/locks/）内重读磁盘，只合并/删除本次这一条，再写唯一命名的临时文件，
    最后 os.replace。旧进程不会把人工恢复的主机写回。disabled() 每次请求前都 refresh()。"""

    def __init__(self, path):
        self.path = Path(path) if path else None
        self.data = {"hosts": {}, "sources": {}}
        self.refresh()

    def _read(self):
        if self.path and self.path.exists():
            d = strictjson.loads(self.path.read_text(encoding="utf-8"))
            return dict(d.get("hosts") or {}), dict(d.get("sources") or {})
        return {}, {}

    def refresh(self):
        if self.path:
            h, src = self._read()
            self.data = {"hosts": h, "sources": src}

    def disabled(self, host, sid=None):
        self.refresh()                 # 每次请求前重读：别的进程停用、人工恢复都立即生效
        if sid and sid in self.data["sources"]:
            return f"source disabled: {self.data['sources'][sid]['reason']}"
        if host in self.data["hosts"]:
            return f"host disabled: {self.data['hosts'][host]['reason']}"
        return None

    def _locked_update(self, fn):
        import fcntl
        import tempfile
        self.path.parent.mkdir(parents=True, exist_ok=True)
        locks = self.path.parent / "locks"
        locks.mkdir(parents=True, exist_ok=True)
        with open(locks / f"{self.path.name}.lock", "a+") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            try:
                h, src = self._read()                  # 锁内以磁盘为准，只改本次这一条
                fn(h, src)
                data = {"hosts": h, "sources": src}
                fd, tmp = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
                        f.flush(); os.fsync(f.fileno())
                    os.replace(tmp, self.path)
                except BaseException:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
                    raise
                self.data = data
            finally:
                fcntl.flock(lk, fcntl.LOCK_UN)

    def disable(self, host, sid, reason):
        rec = {"reason": reason, "at": now(), "needs": "manual review before re-enable"}

        def add(h, src):
            if host:
                h[host] = rec
            if sid:
                src[sid] = dict(rec, host=host)
        if not self.path:
            add(self.data["hosts"], self.data["sources"])
            return
        self._locked_update(add)

    def enable(self, host=None, sid=None):
        """人工恢复（同一把锁）：删掉主机条目及因该主机停用的源；或按 sid 删源条目。返回删掉的条目数。"""
        n = [0]

        def rm(h, src):
            if host and h.pop(host, None) is not None:
                n[0] += 1
            for k in [k for k, v in src.items() if (sid and k == sid) or (host and v.get("host") == host)]:
                src.pop(k); n[0] += 1
        if not self.path:
            rm(self.data["hosts"], self.data["sources"])
        else:
            self._locked_update(rm)
        return n[0]


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
                 fakeip_cidr=None, lock_dir=None):
        self.state = state or HostState(None)
        # 主机组（SEC）跨进程锁目录（私有目录）：同一时间只有一个实例在请求该组，间隔按锁文件里的时间戳控制
        self.lock_dir = Path(lock_dir) if lock_dir else None
        interval = float(interval)
        if not math.isfinite(interval):
            raise ConfigError("interval must be finite")
        interval = max(interval, HOST_INTERVAL)   # 每主机间隔下限 2s，不能调低
        # 地址策略强制安装，不能关闭：fakeip_cidr 缺省取环境变量（同样受 AddressPolicy 的网段限制）。
        # addr_policy 是额外策略，只能更严：两者都放行才放行。
        self._forced_policy = AddressPolicy(fakeip_cidr if fakeip_cidr is not None else os.environ.get(FAKEIP_ENV),
                                            resolver=resolver)
        self.resolver = self._forced_policy.resolver
        self.addr_policy = addr_policy
        self.interval, self.timeout, self.max_bytes = interval, timeout, max_bytes
        self.opener = opener or urllib.request.build_opener(_NoRedirect)
        self.sleep, self.clock = sleep, clock
        self._last, self._host_interval, self._robots = {}, {}, {}
        self.robots_note = {}
        self.log = log or (lambda *_: None)
        self.requests = []     # (host, t) — 供测试/审计
        self.sec_ua = sec_user_agent()
        self._sink = None
        self._group_last = {}

    def address_check(self, url):
        """强制策略与外部策略的合取；返回拒绝原因或 None。"""
        return AllOf(self._forced_policy, self.addr_policy)(url)

    # -- 每主机限速（所有请求都走这里）
    def _wait(self, host, skip_group=False):
        gap = max(self.interval, self._host_interval.get(host, 0))
        last = self._last.get(host)
        if last is not None:
            w = gap - (self.clock() - last)
            if w > 0:
                self.sleep(w)
        for g, ggap in RATE_GROUPS.items():      # 主机组全局限速（如 SEC 全部主机合计 ≤5 次/秒）
            if in_group(host, g) and not skip_group:
                gl = self._group_last.get(g)
                if gl is not None:
                    w = ggap - (self.clock() - gl)
                    if w > 0:
                        self.sleep(w)
                self._group_last[g] = self.clock()
        self._last[host] = self.clock()
        self.requests.append((host, self._last[host]))

    def _raw(self, url, accept):
        host = host_of(url)
        if in_group(host, SEC_SUFFIX):     # 所有出站入口（get、robots、直接调用）统一门禁：缺 UA 或跨进程锁 → 不发请求
            if not self.sec_ua:
                return 0, {}, b"", "not_configured", f"{SEC_UA_ENV} not set (must include contact info)"
            if not self.lock_dir:
                return 0, {}, b"", "not_configured", "lock_dir not set (SEC requests need the cross-process rate lock)"
        g = next((x for x in RATE_GROUPS if in_group(host, x)), None)
        if g and self.lock_dir:
            import fcntl
            self.lock_dir.mkdir(parents=True, exist_ok=True)
            with open(self.lock_dir / f"rate-{g}.lock", "a+") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX)          # 跨进程互斥：持锁直到本次请求结束
                try:
                    # 锁文件记 {"group": 上次组内请求时间, "hosts": {主机: 上次请求时间}}（墙钟）；组间隔与单主机间隔
                    # （含 robots Crawl-delay 更严者）都在锁内按文件里的时间执行，跨进程有效
                    lk.seek(0)
                    try:
                        rec = strictjson.loads(lk.read() or "{}")
                        if not isinstance(rec, dict):
                            rec = {}
                    except ValueError:
                        rec = {}
                    hosts = rec.get("hosts") if isinstance(rec.get("hosts"), dict) else {}
                    hgap = max(self.interval, self._host_interval.get(host, 0))
                    now_ = time.time()
                    w = max(RATE_GROUPS[g] - (now_ - float(rec.get("group") or 0)),
                            hgap - (now_ - float(hosts.get(host) or 0)), 0)
                    if w > 0:
                        time.sleep(min(w, hgap))
                    self._group_last[g] = self._last[host] = self.clock()
                    self.requests.append((host, self._last[host]))
                    res = self._raw_inner(url, accept, host)
                    t = time.time()
                    hosts[host] = t
                    lk.seek(0); lk.truncate(); lk.write(json.dumps({"group": t, "hosts": hosts})); lk.flush()
                    return res
                finally:
                    fcntl.flock(lk, fcntl.LOCK_UN)
        self._wait(host)
        return self._raw_inner(url, accept, host)

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
        if len(buf) > self.max_bytes:
            return status, headers, b"", "too_large", f">{self.max_bytes} bytes"
        if buf and self._sink:     # 每收到一次响应（含 robots、重试中的 429/5xx）都先交给私有存档，再做任何判定
            self._sink(buf, status, (headers.get("Content-Type") if headers else "") or "")
        return status, headers, buf, None, None

    def _with_retry(self, url, accept, html_is_challenge=False):
        """html_is_challenge（robots 用）：401/429/5xx 返回 HTML 视为疑似验证页，不重试，直接交回调用方停用。"""
        for attempt in range(MAX_RETRIES + 1):
            st, h, body, ec, det = self._raw(url, accept)
            ct = ((h or {}).get("Content-Type") or "")
            challenged = st in (401, 403) or classify_page(ct, body, h) is not None
            if html_is_challenge and suspect_status(st) and body and looks_html(h, body):
                challenged = True     # robots 的 401/429/5xx HTML：不重试（本轮按禁止处理，不停用）
            retryable = (ec == "network" or st == 429 or 500 <= st < 600) and not challenged
            if not retryable or attempt == MAX_RETRIES:
                return st, h, body, ec, det
            wait = retry_after(h)
            if wait is None:
                wait = min(BACKOFF_CAP, BACKOFF_BASE * (2 ** attempt))
            elif wait > BACKOFF_CAP:
                return st, h, body, "retry_after_too_long", f"{int(wait)}s"
            self.sleep(wait)
        return st, h, body, ec, det

    # -- robots.txt（每个 scheme://host 一份；robots 自身请求同样限速）
    def robots(self, url, sid=None):
        """robots.txt 自身的每一跳也逐跳校验（审查 r2）：scheme、t.co 拒绝、停用状态；跨主机跳转一律按禁止处理
        （不拿别处的 robots 当本站许可）。robots 返回 403 或验证页（含 HTTP 200 验证页）→ 持久停用主机/源，
        禁止继续请求该站正文。"""
        p = urlsplit(url)
        host = (p.hostname or "").lower()
        base = f"{p.scheme}://{p.netloc}"
        if base in self._robots:
            return self._robots[base]
        rp = urllib.robotparser.RobotFileParser()
        cur = base + "/robots.txt"
        st, ec, body, h = 0, "too_many_redirects", b"", {}
        for hop in range(MAX_REDIRECTS + 1):
            if hop:
                q = urlsplit(cur)
                qh = (q.hostname or "").lower()
                if q.scheme not in ("http", "https") or not qh:
                    st, ec = 0, "robots_bad_redirect"; break
                if qh in REFUSED_HOSTS:
                    st, ec = 0, "robots_redirect_refused_host"; break
                if self.state.disabled(qh, sid):
                    st, ec = 0, "robots_redirect_disabled_host"; break
                if qh != host:
                    st, ec = 0, "robots_cross_host_redirect"; break
            why = self.address_check(cur)          # 每一跳 robots 请求前都过强制策略 + 外部策略
            if why:
                st, ec, body, h = 0, "robots_blocked_address", b"", {}; break
            st, h, body, ec, _ = self._with_retry(cur, "text/plain,*/*", html_is_challenge=True)
            h = h or {}
            if st in (401, 403):
                break                    # 先按状态码：403/401 → 持久停用（见下），不看正文
            kind = classify_page(h.get("Content-Type") or "", body, h)
            if kind:
                break                    # 再查验证页（含带验证内容的 3xx），不再跟随 Location
            if st in REDIRECT_CODES:
                loc = h.get("Location")
                if not loc:
                    ec = "robots_redirect_without_location"; break
                cur = urljoin(cur, loc)
                st, ec = 0, "too_many_redirects"
                continue
            break
        kind = classify_page(h.get("Content-Type") or "", body, h)
        if st in (401, 403):            # 先按状态码：403/401 持久停用（不论正文）
            self.state.disable(host, sid, f"robots.txt HTTP {st}")
            rp.disallow_all = True
        elif kind == "vendor":          # 真正的验证组件 → 持久停用
            self.state.disable(host, sid, f"robots.txt bot challenge page (HTTP {st})")
            rp.disallow_all = True
        elif kind or (body and looks_html(h, body) and st not in (404, 410)):
            self.robots_note[base] = f"robots.txt suspect/HTML (HTTP {st})"   # 格式不对：本轮按禁止，不停用
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
        else:                     # 401/5xx/网络错误/跳转被拒 → 按禁止处理
            rp.disallow_all = True
        self._robots[base] = rp
        return rp

    def allowed(self, url, sid=None):
        return self.robots(url, sid).can_fetch(UA_TOKEN, url)

    def get(self, url, sid=None, accept="*/*", raw_sink=None):
        prev, self._sink = self._sink, raw_sink
        try:
            return self._get(url, sid, accept)
        finally:
            self._sink = prev

    def _get(self, url, sid, accept):
        """抓一个 URL。不自动重定向：每一跳都重新检查拒绝主机、停用状态、robots 与限速。
        Result.hops 从一开始只持有 public_url（凭证参数不进任何日志）；final_url 为完整 URL，仅供内存内核对，
        写记录前必须经 public_url。"""
        hops, cur = [], url
        for _ in range(MAX_REDIRECTS + 1):
            p = urlsplit(cur)
            host = (p.hostname or "").lower()
            if p.scheme not in ("http", "https") or not host:
                return Result(False, final_url=cur, hops=hops, error="bad_url")
            if host in REFUSED_HOSTS:
                return Result(False, final_url=cur, hops=hops, error="refused_host")
            why = self.state.disabled(host, sid)
            if why:
                return Result(False, final_url=cur, hops=hops, error="disabled", detail=why)
            if in_group(host, SEC_SUFFIX) and not self.sec_ua:   # 未配置 SEC UA：不发请求，也不停用
                return Result(False, final_url=cur, hops=hops, error="not_configured",
                              detail=f"{SEC_UA_ENV} not set (must include contact info)")
            if in_group(host, SEC_SUFFIX) and not self.lock_dir:  # 没有跨进程限速锁：不发请求
                return Result(False, final_url=cur, hops=hops, error="not_configured",
                              detail="lock_dir not set (SEC requests need the cross-process rate lock)")
            why = self.address_check(cur)   # 每一跳、子 sitemap 都在任何请求前检查
            if why:
                return Result(False, final_url=cur, hops=hops, error="blocked_address", detail=why)
            if not self.allowed(cur, sid):
                why = self.state.disabled(host, sid)   # robots 403/验证页刚触发的停用
                if why:
                    return Result(False, final_url=cur, hops=hops, error="disabled", detail=why)
                return Result(False, final_url=cur, hops=hops, error="robots_disallow")
            st, h, body, ec, det = self._with_retry(cur, accept)
            ctype = (h.get("Content-Type") if h else "") or ""
            # 原字节已在 _raw 里交给 raw_sink；每一跳先按状态码处理（403/401 持久停用），再判正文，最后处理 Location
            if st in (401, 403):
                self.state.disable(host, sid, f"HTTP {st}")
                return Result(False, st, ctype, b"", cur, hops, f"http_{st}")
            kind = classify_page(ctype, body, h)
            if kind == "vendor":
                self.state.disable(host, sid, f"bot challenge page: vendor marker (HTTP {st})")
                return Result(False, st, ctype, b"", cur, hops, "challenge")
            if kind == "phrase":       # 只命中泛用短语：本轮可疑失败，不跟随、不停用
                return Result(False, st, ctype, b"", cur, hops, "suspected_challenge")
            if st in REDIRECT_CODES:
                loc = h.get("Location") if h else None
                if not loc:
                    return Result(False, st, final_url=cur, hops=hops, error="redirect_without_location")
                hops.append({"from": public_url(cur), "query_param_count": query_count(cur), "status": st})   # hops 只存脱敏 URL
                cur = urljoin(cur, loc)
                continue
            if ec:
                return Result(False, st, ctype, b"", cur, hops, ec, det)
            if st == 200:
                return Result(True, st, ctype, body, cur, hops)
            return Result(False, st, ctype, b"", cur, hops, f"http_{st}")
        return Result(False, final_url=cur, hops=hops, error="too_many_redirects")
