#!/usr/bin/env bash
# 冒烟测试：OM 健康检查通过，搜索与 RDF 已连接；005：OM 的 pipeline service client 已启用并能连通 Airflow 3.3.2
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
NS=contexture
kubectl -n $NS rollout status deployment/openmetadata --timeout=900s
curl_in http://openmetadata:8586/healthcheck | grep -q '"healthy":true' && echo "openmetadata OK"

enabled=$(kubectl -n $NS exec deployment/openmetadata -c openmetadata -- sh -c 'echo "$PIPELINE_SERVICE_CLIENT_ENABLED"')
[[ ${enabled//\"/} == true ]] || { echo "PIPELINE_SERVICE_CLIENT_ENABLED=$enabled"; exit 1; }
# OM 的 AirflowRESTClient 使用的版本探测接口（AirflowRESTClient.java:148-172）；OM 镜像无 curl，用 JDK 自带工具不便，改用 bash /dev/tcp
kubectl -n $NS exec deployment/openmetadata -c openmetadata -- bash -c \
  'exec 3<>/dev/tcp/airflow-api-server/8080; printf "GET /pluginsv2/api/v2/openmetadata/health-auth HTTP/1.0\r\nHost: airflow-api-server\r\n\r\n" >&3; cat <&3' \
  | grep -q '"status": *"healthy", *"version": *"2.0.3' && echo "openmetadata → airflow（managed-apis 2.0.3）OK"
