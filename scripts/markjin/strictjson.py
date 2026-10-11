"""严格 JSON 解析（整体验收 r11 BLOCKER 2，王总定）：同一对象出现重复键一律判失败（object_pairs_hook）。

DuplicateKeyError 是 ValueError 子类，调用方原有的 `except ValueError` 分支即按“无法解析”处理，不会静默取后值。
全部 json.load/json.loads 入口的清单见 scripts/README.md「严格 JSON 入口清单」，tests 逐个断言。"""
import json


class DuplicateKeyError(ValueError):
    pass


def _hook(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise DuplicateKeyError(f"duplicate JSON key {k!r}")
        out[k] = v
    return out


def loads(text):
    return json.loads(text, object_pairs_hook=_hook)
