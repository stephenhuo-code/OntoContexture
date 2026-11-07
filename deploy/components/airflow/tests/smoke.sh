#!/usr/bin/env bash
# 冒烟测试：api-server 健康，scheduler 与 dag-processor 心跳正常；
# 005：织境采集镜像、OM managed-apis 插件可用、DAG 与生成配置位于同一共享卷、无首轮遗留 DAG
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
NS=contexture
kubectl -n $NS rollout status deployment/airflow-api-server --timeout=600s
kubectl -n $NS rollout status deployment/airflow-scheduler --timeout=600s
# api-server 仅允许 Airflow 组件与 OM 访问（网络策略），HTTP 检查从 scheduler 容器内发起
http_get() {
  kubectl -n $NS exec deployment/airflow-scheduler -c scheduler -- python -c \
    "import sys,urllib.request;print(urllib.request.urlopen(sys.argv[1],timeout=10).read().decode())" "$1"
}
http_get http://airflow-api-server:8080/api/v2/monitor/health | grep -q '"scheduler": *{"status": *"healthy"' && echo "airflow OK"

image=$(kubectl -n $NS get deployment airflow-api-server -o jsonpath='{.spec.template.spec.containers[0].image}')
[[ $image == contexture/openmetadata-ingestion-airflow:* ]] || { echo "airflow 镜像不是织境采集镜像：$image"; exit 1; }
http_get http://airflow-api-server:8080/pluginsv2/api/v2/openmetadata/health | grep -q '"status": *"healthy"' \
  && echo "managed-apis OK"
# managed-apis 在 Airflow 3 下不校验凭证（research R3），其他 Pod 必须连不上 api-server
code=$(curl_in -s -o /dev/null -w '%{http_code}' --max-time 5 http://airflow-api-server:8080/pluginsv2/api/v2/openmetadata/health || true)
[[ $code == 000 ]] || { echo "非授权 Pod 仍可访问 api-server（HTTP $code）"; exit 1; }
echo "api-server network policy OK"

dags=$(kubectl -n $NS exec deployment/airflow-api-server -c api-server -- sh -c 'airflow config get-value core dags_folder')
generated=$(kubectl -n $NS exec deployment/airflow-api-server -c api-server -- sh -c 'echo "$AIRFLOW__OPENMETADATA_AIRFLOW_APIS__DAG_GENERATED_CONFIGS"')
[[ $generated == "$dags"/* ]] || { echo "DAG_GENERATED_CONFIGS（$generated）不在 dags 卷（$dags）内"; exit 1; }
mounts=$(kubectl -n $NS get deployment airflow-dag-processor -o jsonpath='{.spec.template.spec.containers[*].volumeMounts[*].mountPath}')
[[ " $mounts " == *" $dags "* ]] || { echo "dag-processor 未挂载 dags 卷"; exit 1; }
echo "dags volume OK"

if kubectl -n $NS exec deployment/airflow-scheduler -c scheduler -- airflow dags list -o plain 2>/dev/null \
  | awk 'NR>1{print $1}' | grep -Eq '^(ctx005_|metadata_mock_|metadata_demo_)'; then
  echo "存在首轮遗留 DAG"; exit 1
fi
kubectl -n $NS exec deployment/airflow-api-server -c api-server -- test ! -e "$dags/contexture_om_dags.py" \
  || { echo "存在首轮遗留文件 contexture_om_dags.py"; exit 1; }
echo "no legacy dags OK"
