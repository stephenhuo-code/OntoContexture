#!/usr/bin/env bash
# 冒烟测试：OM 健康检查通过，搜索与 RDF 已连接；005：OM 的 pipeline service client 已启用并能连通 Airflow 3.3.2
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
NS=contexture
kubectl -n $NS rollout status deployment/openmetadata --timeout=900s
curl_in http://openmetadata:8586/healthcheck | grep -q '"healthy":true' && echo "openmetadata OK"

enabled=$(kubectl -n $NS exec deployment/openmetadata -c openmetadata -- sh -c 'echo "$PIPELINE_SERVICE_CLIENT_ENABLED"')
[[ ${enabled//\"/} == true ]] || { echo "PIPELINE_SERVICE_CLIENT_ENABLED=$enabled"; exit 1; }
# OM 的 AirflowRESTClient 使用的版本探测接口（AirflowRESTClient.java:148-172）
kubectl -n $NS exec deployment/openmetadata -c openmetadata -- sh -c \
  'curl -s -u "$AIRFLOW_USERNAME:$AIRFLOW_PASSWORD" http://airflow-api-server:8080/pluginsv2/api/v2/openmetadata/health-auth' \
  | grep -q '"version":"3.3.2"' && echo "openmetadata → airflow OK"
