#!/usr/bin/env bash
# 冒烟测试（030）：工具箱的缓存卷已绑定、账号已创建
set -euo pipefail
kubectl -n contexture-ci get serviceaccount toolbox >/dev/null
kubectl -n contexture-ci wait pvc/toolbox-cache --for=jsonpath='{.status.phase}'=Bound --timeout=300s
