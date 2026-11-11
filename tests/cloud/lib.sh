#!/usr/bin/env bash
# 云端验证测试的公共部分（030）：从 .env.cloud 读取配置，所有 kubectl 固定到云端上下文；在开发机上运行。
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
source "$ROOT/tools/cloud/common.sh"
ctx_load_config
K() { ctx_kubectl "$@"; }
pass() { printf '  ✔ %s\n' "$*"; }
fail() { printf '  ✘ %s\n' "$*"; FAILED=1; }
FAILED=0
finish() { [[ $FAILED == 0 ]] && echo "通过" || { echo "失败"; exit 1; }; }
