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
- 一切日志（公开与私有）不写本机路径、不写凭证：URL 不带查询值（只记参数名；按源 public_params 声明的才留值），hops 只存脱敏 URL；
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

UA = "markjin-collector/0.1 (+https://markjin-lab.github.io; markjin@mail.grokbot.com)"
UA_TOKEN = "markjin-collector"
MAX_BYTES = 25 * 1024 * 1024
HOST_INTERVAL = 2.0          # 每主机最小请求间隔（秒）；robots Crawl-delay / Request-rate 更严时取更严者
MAX_REDIRECTS = 5
MAX_RETRIES = 3
BACKOFF_BASE = 2.0
BACKOFF_CAP = 120.0          # Retry-After 超过此值直接放弃本次（不长时间挂起）
REFUSED_HOSTS = {"t.co"}
REDIRECT_CODES = {301, 302, 303, 307, 308}
# 验证页识别（collector 与 scrapers 共用这一份）
CHALLENGE = re.compile(rb"Just a moment\.\.\.|challenges\.cloudflare\.com|/cdn-cgi/challenge-platform|cf-chl-|"
                       rb"Attention Required! \| Cloudflare|<title>\s*Access Denied|Access Denied</title>|"
                       rb"<title>[^<]*captcha|id\s*=\s*[\"']?captcha\b|class\s*=\s*[\"'][^\"']*\bcaptcha\b|"
                       rb"g-recaptcha|hcaptcha", re.I)
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
def public_url(u, public_params=()):
    """用于一切记录/日志（公开与私有）：去掉 userinfo、片段和查询串。查询参数的*值*默认一律不记
    （参数名见 query_names）；只有该源在 sources.yaml 里用 public_params 显式声明的参数才保留值。"""
    p = urlsplit(u.strip())
    host = (p.hostname or "").lower()
    netloc = (f"[{host}]" if ":" in host else host) + (f":{p.port}" if p.port else "")
    keep = set(public_params or ())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k in keep]
    return urlunsplit((p.scheme.lower(), netloc, p.path, urlencode(q), ""))


def query_names(u):
    """URL 中查询参数的名字（去重、保序），供日志记录；不含值。"""
    return list(dict.fromkeys(k for k, _ in parse_qsl(urlsplit(u.strip()).query, keep_blank_values=True)))


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


# ---------------------------------------------------------------- 持久停用状态
class HostState:
    """{"hosts": {host: {...}}, "sources": {sid: {...}}}。只由采集器写入停用；恢复须人工删除对应条目。"""

    def __init__(self, path):
        self.path = Path(path) if path else None
        self.data = {"hosts": {}, "sources": {}}
        if self.path and self.path.exists():
            d = strictjson.loads(self.path.read_text(encoding="utf-8"))
            self.data["hosts"].update(d.get("hosts") or {})
            self.data["sources"].update(d.get("sources") or {})

    def disabled(self, host, sid=None):
        if sid and sid in self.data["sources"]:
            return f"source disabled: {self.data['sources'][sid]['reason']}"
        if host in self.data["hosts"]:
            return f"host disabled: {self.data['hosts'][host]['reason']}"
        return None

    def disable(self, host, sid, reason):
        rec = {"reason": reason, "at": now(), "needs": "manual review before re-enable"}
        if host:
            self.data["hosts"][host] = rec
        if sid:
            self.data["sources"][sid] = dict(rec, host=host)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            os.replace(tmp, self.path)


# ---------------------------------------------------------------- 抓取层
def looks_html(headers, body):
    ct = ((headers or {}).get("Content-Type") or "").lower()
    head = body[:2048].lstrip(b"\xef\xbb\xbf \r\n\t").lower()
    return "html" in ct or head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<html" in head \
        or b"<body" in head or b"<script" in head
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
                 fakeip_cidr=None):
        self.state = state or HostState(None)
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
        self.log = log or (lambda *_: None)
        self.requests = []     # (host, t) — 供测试/审计

    # -- 每主机限速（所有请求都走这里）
    def _wait(self, host):
        gap = max(self.interval, self._host_interval.get(host, 0))
        last = self._last.get(host)
        if last is not None:
            w = gap - (self.clock() - last)
            if w > 0:
                self.sleep(w)
        self._last[host] = self.clock()
        self.requests.append((host, self._last[host]))

    def _raw(self, url, accept):
        host = host_of(url)
        self._wait(host)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept,
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
        return status, headers, buf, None, None

    def _with_retry(self, url, accept):
        for attempt in range(MAX_RETRIES + 1):
            st, h, body, ec, det = self._raw(url, accept)
            challenged = bool(body) and CHALLENGE.search(body[:20000])
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
            st, h, body, ec, _ = self._with_retry(cur, "text/plain,*/*")
            h = h or {}
            if st in REDIRECT_CODES:
                loc = h.get("Location")
                if not loc:
                    ec = "robots_redirect_without_location"; break
                cur = urljoin(cur, loc)
                st, ec = 0, "too_many_redirects"
                continue
            break
        challenged = bool(body) and CHALLENGE.search(body[:20000])
        if st == 200 and not ec and not challenged and looks_html(h, body):
            challenged = True     # robots.txt 返回 HTML：一律按验证页处理（不当作空规则）
        if challenged:
            self.state.disable(host, sid, f"robots.txt bot challenge page (HTTP {st})")
            rp.disallow_all = True
        elif st == 403:
            self.state.disable(host, sid, "robots.txt HTTP 403")
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

    def get(self, url, sid=None, accept="*/*"):
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
            why = AllOf(self._forced_policy, self.addr_policy)(cur)   # 每一跳、子 sitemap 都在任何请求前检查
            if why:
                return Result(False, final_url=cur, hops=hops, error="blocked_address", detail=why)
            if not self.allowed(cur, sid):
                why = self.state.disabled(host, sid)   # robots 403/验证页刚触发的停用
                if why:
                    return Result(False, final_url=cur, hops=hops, error="disabled", detail=why)
                return Result(False, final_url=cur, hops=hops, error="robots_disallow")
            st, h, body, ec, det = self._with_retry(cur, accept)
            ctype = (h.get("Content-Type") if h else "") or ""
            if st in REDIRECT_CODES:
                loc = h.get("Location") if h else None
                if not loc:
                    return Result(False, st, final_url=cur, hops=hops, error="redirect_without_location")
                hops.append({"from": public_url(cur), "query_params": query_names(cur), "status": st})   # hops 只存脱敏 URL
                cur = urljoin(cur, loc)
                continue
            if body and CHALLENGE.search(body[:20000]):
                self.state.disable(host, sid, f"bot challenge page (HTTP {st})")
                return Result(False, st, ctype, b"", cur, hops, "challenge")
            if st == 403:
                self.state.disable(host, sid, "HTTP 403")
                return Result(False, st, ctype, b"", cur, hops, "http_403")
            if ec:
                return Result(False, st, ctype, b"", cur, hops, ec, det)
            if st == 200:
                return Result(True, st, ctype, body, cur, hops)
            return Result(False, st, ctype, b"", cur, hops, f"http_{st}")
        return Result(False, final_url=cur, hops=hops, error="too_many_redirects")
