"""本机内部目录访问。内部主题清单只在本机内部目录，不进任何仓库。

内部目录：环境变量 $MARKJIN_INTERNAL_DIR 给出的路径（推荐显式设置）；未设置时用相对路径——仓库根目录的同级目录
`../markjin-internal`（按本文件位置推出仓库根，不写任何本机绝对路径）。目录或清单不存在时调用方 fail-closed
（E-INTERNAL-LIST-MISSING），不会悄悄放行。

清单文件 topics-private.md 必须恰好含一张三列 Markdown 表格（严格解析）：
  表头必须恰好是：名称 | 识别条件 | 来源；第 2 行为分隔行；
  每个数据行恰好 3 个非空单元格，名称不得重复。
任何一项不满足（缺表、多张表、列数不对、空单元格、重复行、行首尾缺竖线、表格外出现任何非空文字）→ 返回 None，
调用方必须 fail-closed（E-INTERNAL-LIST-MISSING）。三列的内容都受保护：都参与检查，都不回显。
协调决定：表格以外**不允许出现任何文字**（含标题、说明、注释），出现即报错；需要识别的内容一律写进表格。

写入（write_internal）只靠操作系统身份与目录权限限制：内部目录必须属于当前有效用户、权限 0700、
不在任何 git 仓库内。actor 参数只是自报标签，不做授权判断，也不能作为任何批准凭证。
"""
import os
import re
import stat
from pathlib import Path

from .textnorm import compact, norm

ENV_VAR = "MARKJIN_INTERNAL_DIR"
DEFAULT_SIBLING = "markjin-internal"     # 未设环境变量时：仓库根的同级目录（相对路径）
NAME_HEADERS = {"名称"}
COND_HEADERS = {"识别条件"}
SRC_HEADERS = {"来源"}
_SEP = re.compile(r"^:?-{3,}:?$")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]          # scripts/markjin/internal.py → 仓库根


def internal_dir() -> Path:
    """$MARKJIN_INTERNAL_DIR（空串视同未设置）；否则 <仓库根>/../markjin-internal。"""
    v = os.environ.get(ENV_VAR, "").strip()
    return Path(v) if v else repo_root().parent / DEFAULT_SIBLING


def _cells(line):
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")) or len(s) < 2:
        return None
    return [norm(c) for c in s[1:-1].split("|")]


def parse_internal_list(text):
    """严格解析；返回 {"names": [...], "protected": [...]}，任何不合规返回 None。"""
    lines = text.splitlines()
    blocks, cur = [], []
    for ln in lines:
        if ln.strip() and not ln.strip().startswith("|"):
            return None                      # 表外文字（含缺行首竖线的畸形行）：一律报错
        if ln.strip().startswith("|"):
            cur.append(ln)
        elif cur:
            blocks.append(cur); cur = []
    if cur:
        blocks.append(cur)
    if len(blocks) != 1 or len(blocks[0]) < 3:
        return None
    rows = [_cells(ln) for ln in blocks[0]]
    if any(r is None or len(r) != 3 for r in rows):
        return None
    head, sep, data = rows[0], rows[1], rows[2:]
    if head[0] not in NAME_HEADERS or head[1] not in COND_HEADERS or head[2] not in SRC_HEADERS:
        return None
    if not all(_SEP.match(c.replace(" ", "")) for c in sep):
        return None
    names, protected, seen = [], [], set()
    for r in data:
        if any(not c or _SEP.match(c.replace(" ", "")) for c in r):
            return None
        key = compact(r[0])
        if key in seen:
            return None
        seen.add(key)
        names.append(r[0])
        protected.extend(r)
    return {"names": names, "protected": sorted(set(protected), key=protected.index)}


def load_internal_list():
    p = internal_dir() / "topics-private.md"
    try:
        text = p.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return parse_internal_list(text)


def load_internal_terms():
    """返回受保护词（三列全部单元格）；清单缺失/不可读/格式非法时返回 None。"""
    lst = load_internal_list()
    return lst["protected"] if lst else None


# —— 本机内部目录的写入管理（#11）
class InternalError(PermissionError):
    pass


def _is_bare_repo(d: Path) -> bool:
    return (d / "HEAD").is_file() and (d / "objects").is_dir() and (d / "refs").is_dir()


def _in_git_repo(p: Path) -> bool:
    """普通仓库（祖先有 .git）或 bare 仓库（祖先本身是 git 目录：HEAD + objects/ + refs/）都算。"""
    return any((d / ".git").exists() or _is_bare_repo(d) for d in [p, *p.parents])


def check_dir_secure(d: Path) -> None:
    """内部目录必须属于当前有效用户、权限恰为 0700（组/其他用户无任何权限）、不在 git 仓库内。"""
    st = d.lstat()
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise InternalError("内部目录不是普通目录")
    if st.st_uid != os.geteuid():
        raise InternalError("内部目录不属于当前操作系统用户")
    if stat.S_IMODE(st.st_mode) & 0o077:
        raise InternalError("内部目录权限过宽（须为 0700）")
    if _in_git_repo(d.resolve()):
        raise InternalError("内部目录位于 git 仓库内，拒绝使用")


def ensure_internal_dir() -> Path:
    d = internal_dir()
    if _in_git_repo(d.resolve()):
        raise InternalError("内部目录位于 git 仓库内，拒绝使用")
    created = not d.exists()
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    if created:
        d.chmod(0o700)
    check_dir_secure(d)
    for sub in ("review", "newsletter", "state"):
        (d / sub).mkdir(mode=0o700, exist_ok=True)
    return d


def write_internal(rel: str, content: str, actor: str = "") -> Path:
    """写入内部目录。actor 仅为自报标签：不做授权、不写入记录、不能作为批准凭证。
    授权完全依赖操作系统：只有内部目录属主（0700）能通过 check_dir_secure。"""
    d = ensure_internal_dir().resolve()
    p = (d / rel).resolve()
    if d not in p.parents:
        raise InternalError("路径越出内部目录")
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.chmod(p, 0o600)
    return p
