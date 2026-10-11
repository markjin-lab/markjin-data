#!/usr/bin/env python3
"""生产 bot 用：把状态变更写回 state/publish-state.json（门禁本身不写文件）。

  scripts/state-change.py apply --state state/publish-state.json --change '<route 输出中的 state_change JSON>'
  scripts/state-change.py heartbeat --state state/publish-state.json --mac-online true|false [--now ISO]
heartbeat 只改 updated_at 与 mac_online。写完后由生产 bot 自行 git add / commit / push。
退出码 0=已写入，1=拒绝（输出错误码，文件不变）。"""
import argparse, datetime as dt, json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import statechange as S  # noqa: E402

ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd", required=True)
a1 = sub.add_parser("apply"); a1.add_argument("--state", required=True); a1.add_argument("--change", required=True)
a2 = sub.add_parser("heartbeat"); a2.add_argument("--state", required=True)
a2.add_argument("--mac-online", required=True, choices=["true", "false"]); a2.add_argument("--now")
a = ap.parse_args()
p = Path(a.state)
try:
    state = S.loads_strict(p.read_bytes().decode("utf-8"))   # r9 MEDIUM：重复键判失败
    if a.cmd == "apply":
        change = S.loads_strict(a.change)
    else:
        now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now(dt.timezone.utc).astimezone()
        if now.tzinfo is None:
            raise S.StateChangeError("E-STATE-CHANGE-INVALID")
        change = S.heartbeat(a.mac_online == "true", now)
    new = S.apply_change(state, change)
except (OSError, UnicodeDecodeError, ValueError) as e:
    print("FAIL " + getattr(e, "code", "E-ROUTE-STATE")); sys.exit(1)
fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".publish-state.")
with os.fdopen(fd, "w", encoding="utf-8") as fh:
    fh.write(S.dumps(new))
os.replace(tmp, p)
print(json.dumps(change, ensure_ascii=False))
