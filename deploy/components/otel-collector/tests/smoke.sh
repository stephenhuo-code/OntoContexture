#!/usr/bin/env bash
# 冒烟测试：Collector 就绪，OTLP/HTTP 能接收一条 span
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
NS=contexture
kubectl -n $NS rollout status statefulset/otel-collector --timeout=300s
NOW=$(date +%s)000000000
curl_in -o /dev/null -w "%{http_code}\n" -X POST http://otel-collector:4318/v1/traces \
  -H 'Content-Type: application/json' \
  -d '{"resourceSpans":[{"resource":{"attributes":[{"key":"service.name","value":{"stringValue":"smoke"}}]},"scopeSpans":[{"spans":[{"traceId":"5b8efff798038103d269b633813fc60c","spanId":"eee19b7ec3c1b174","name":"smoke","kind":1,"startTimeUnixNano":"'"$NOW"'","endTimeUnixNano":"'"$NOW"'"}]}]}]}' | grep -q 200 && echo "otel-collector OK"
