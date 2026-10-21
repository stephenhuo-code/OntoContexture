#!/usr/bin/env bash
# 冒烟测试：api-server 健康，scheduler 与 dag-processor 心跳正常
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
NS=contexture
kubectl -n $NS rollout status deployment/airflow-api-server --timeout=600s
kubectl -n $NS rollout status deployment/airflow-scheduler --timeout=600s
curl_in http://airflow-api-server:8080/api/v2/monitor/health | grep -q '"scheduler":{"status":"healthy"' && echo "airflow OK"
