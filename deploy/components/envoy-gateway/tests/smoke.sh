#!/usr/bin/env bash
# 冒烟测试：Gateway 已被接受并分配地址
set -euo pipefail
kubectl -n contexture wait gateway/contexture --for=condition=Programmed --timeout=180s
