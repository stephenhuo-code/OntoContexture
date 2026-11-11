#!/usr/bin/env bash
# 冒烟测试（030）：构建器已部署（平时 0 副本）且缓存卷已绑定
set -euo pipefail
kubectl -n contexture-build get deployment buildkitd >/dev/null
kubectl -n contexture-build wait pvc/buildkit-cache --for=jsonpath='{.status.phase}'=Bound --timeout=300s
