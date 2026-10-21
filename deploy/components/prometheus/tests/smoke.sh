#!/usr/bin/env bash
# 冒烟测试：Prometheus 就绪，抓取目标均为 up
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
kubectl -n "$NS" rollout status statefulset/prometheus --timeout=180s
out=$(curl_in -sf 'http://prometheus:9090/api/v1/query?query=up')
grep -q '"status":"success"' <<<"$out"
! grep -q '"value":\[[0-9.]*,"0"\]' <<<"$out" && echo "prometheus OK"
