#!/usr/bin/env bash
# make ports：把各组件的界面转发到本机，供手动验收查看（Ctrl+C 结束）。
set -euo pipefail
NS=contexture
secret() { kubectl -n "$NS" get secret "$1" -o jsonpath="{.data.$2}" | base64 -d; }

forward() {  # forward <服务> <本机端口> <服务端口>
  kubectl -n "$NS" port-forward "svc/$1" "$2:$3" >/dev/null 2>&1 &
}
forward openmetadata 8585 8585
forward langfuse-web 3000 3000
forward jaeger 16686 16686
forward prometheus 9090 9090
forward opensearch-dashboards 5601 5601
forward airflow-api-server 8081 8080
trap 'kill $(jobs -p) 2>/dev/null' EXIT

cat <<INFO

织境本地环境（make up 之后）
  织境 Web               http://localhost:8080          测试用户 user1 / engineer1 / admin1（密码同用户名）
  OpenMetadata           http://localhost:8585          Keycloak 登录（admin1 为 OM 管理员）
  Langfuse（决策轨迹）   http://localhost:3000          admin@contexture.local / $(secret langfuse-init admin-password)
  Jaeger（服务追踪）     http://localhost:16686
  Prometheus（指标）     http://localhost:9090
  OpenSearch Dashboards  http://localhost:5601          日志索引 ctx-logs
  Airflow                http://localhost:8081          admin / admin（Chart 默认，仅本地）

按 Ctrl+C 结束端口转发。
INFO
wait
