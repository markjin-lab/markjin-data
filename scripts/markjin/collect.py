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
- 公开日志不写本机路径、不写凭证型 URL 参数；私有根目录必须显式给出且不能与公开根目录重叠。
"""
import datetime as dt
import email.utils
import hashlib
import json
import os
import re
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
CHALLENGE = re.compile(rb"Just a moment\.\.\.|challenges\.cloudflare\.com|/cdn-cgi/challenge-platform|cf-chl-|"
                       rb"Attention Required! \| Cloudflare|<title>\s*Access Denied|<title>[^<]*captcha", re.I)
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
SECRET_PARAM = re.compile(r"(?i)^(.*[_-])?(api[_-]?key|apikey|key|token|access[_-]?token|auth|authorization|sig|"
                          r"signature|secret|password|passwd|pwd|session|sessionid|sid|code|credential|jwt)$")
TRACKING_PARAM = re.compile(r"(?i)^(utm_.*|linkid|s|ref_src|ref|fbclid|gclid|mc_eid|mc_cid)$")


def public_url(u):
    """用于公开记录/日志：去掉 userinfo、片段、跟踪参数和凭证型参数。原 URL 只留私有记录。"""
    p = urlsplit(u.strip())
    host = (p.hostname or "").lower()
    netloc = host + (f":{p.port}" if p.port else "")
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if not SECRET_PARAM.match(k) and not TRACKING_PARAM.match(k)]
    return urlunsplit((p.scheme.lower(), netloc, p.path, urlencode(q), ""))


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
                 clock=time.monotonic, max_bytes=MAX_BYTES, log=None):
        self.state = state or HostState(None)
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
    def robots(self, url):
        p = urlsplit(url)
        base = f"{p.scheme}://{p.netloc}"
        if base in self._robots:
            return self._robots[base]
        rp = urllib.robotparser.RobotFileParser()
        cur = base + "/robots.txt"
        for _ in range(MAX_REDIRECTS + 1):
            st, h, body, ec, _ = self._with_retry(cur, "text/plain,*/*")
            if st in REDIRECT_CODES and h.get("Location"):
                cur = urljoin(cur, h["Location"])
                continue
            break
        if st == 200 and not ec:
            rp.parse(body.decode("utf-8", "replace").splitlines())
            cd = rp.crawl_delay(UA_TOKEN)
            rr = rp.request_rate(UA_TOKEN)
            stricter = max(float(cd or 0), (rr.seconds / rr.requests) if rr and rr.requests else 0)
            if stricter:
                self._host_interval[p.hostname.lower()] = stricter
        elif st in (404, 410):
            rp.allow_all = True
        else:                     # 401/403/5xx/网络错误 → 按禁止处理
            rp.disallow_all = True
        self._robots[base] = rp
        return rp

    def allowed(self, url):
        return self.robots(url).can_fetch(UA_TOKEN, url)

    def get(self, url, sid=None, accept="*/*"):
        """抓一个 URL。不自动重定向：每一跳都重新检查拒绝主机、停用状态、robots 与限速。"""
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
            if not self.allowed(cur):
                return Result(False, final_url=cur, hops=hops, error="robots_disallow")
            st, h, body, ec, det = self._with_retry(cur, accept)
            ctype = (h.get("Content-Type") if h else "") or ""
            if st in REDIRECT_CODES:
                loc = h.get("Location") if h else None
                if not loc:
                    return Result(False, st, final_url=cur, hops=hops, error="redirect_without_location")
                hops.append({"from": cur, "status": st})
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
