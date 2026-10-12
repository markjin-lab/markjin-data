#!/usr/bin/env bash
# 校验 raw/ 存档：实现见 scripts/verify-raw.py（全部从 git 对象读取，逐提交检查 base..target）。
# 用法：scripts/verify-raw.sh [BASE] [--target REV]
exec python3 "$(cd "$(dirname "$0")" && pwd)/verify-raw.py" "$@"
