#!/usr/bin/env bash
# T023 实测（research R13）：catchup=False 的 DAG 在调度器停止、跨过两个调度点后恢复，Airflow 是否为最近一个区间补建运行。
# 只读结论，不作断言：输出恢复后新建的运行，由负责人决定接受补跑还是启动时跳过（T086）。用时约 30 分钟。
# 探针 DAG 只含 EmptyOperator（不启动任务 Pod），结束时删除 DAG 与文件。
source "$(dirname "$0")/lib.sh"
DAG=ctx030_catchup_probe
NS=$CTX_CLOUD_NAMESPACE
STOP_MINUTES=${STOP_MINUTES:-22}   # 每 10 分钟一次的调度，22 分钟可跨过两个调度点

ax() { K -n "$NS" exec deployment/airflow-scheduler -c scheduler -- "$@"; }
runs() { ax airflow dags list-runs "$DAG" -o json 2>/dev/null || echo '[]'; }
dags=$(K -n "$NS" exec deployment/airflow-api-server -c api-server -- airflow config get-value core dags_folder)

cleanup() {
  K -n "$NS" scale deployment/airflow-scheduler --replicas=1 >/dev/null 2>&1 || true
  ax airflow dags delete -y "$DAG" >/dev/null 2>&1 || true
  K -n "$NS" exec deployment/airflow-api-server -c api-server -- rm -f "$dags/$DAG.py" || true
}
trap cleanup EXIT

K -n "$NS" exec -i deployment/airflow-api-server -c api-server -- sh -c "cat > '$dags/$DAG.py'" <<'PY'
from datetime import datetime

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import DAG

with DAG("ctx030_catchup_probe", schedule="*/10 * * * *", start_date=datetime(2026, 1, 1),
         catchup=False, is_paused_upon_creation=False, tags=["ctx030-probe"]):
    EmptyOperator(task_id="noop")
PY

echo "等待 DAG 登记并产生首个运行"
for _ in $(seq 1 90); do
  [[ $(runs | jq 'length') -gt 0 ]] && break
  sleep 10
done
before=$(runs)
echo "停止前的运行：$(jq -c '[.[]|{logical_date,run_type}]' <<<"$before")"

stop_at=$(date -u +%FT%TZ)
K -n "$NS" scale deployment/airflow-scheduler --replicas=0 >/dev/null
echo "调度器已停止（$stop_at），等待 $STOP_MINUTES 分钟"
sleep $((STOP_MINUTES * 60))
K -n "$NS" scale deployment/airflow-scheduler --replicas=1 >/dev/null
K -n "$NS" rollout status deployment/airflow-scheduler --timeout=600s >/dev/null
resume_at=$(date -u +%FT%TZ)
echo "调度器已恢复（$resume_at），观察 3 分钟"
sleep 180

after=$(runs)
new=$(jq -c --argjson b "$before" '[.[] | select(.run_id as $r | ($b | map(.run_id) | index($r)) | not)
  | {run_id, run_type, logical_date, data_interval_start, data_interval_end, start_date}]' <<<"$after")
echo "恢复后新建的运行：$new"
# Airflow 3 的 list-runs 输出中 run_type 为空，以 run_id 前缀与逻辑时间判断补跑
catch=$(jq --arg s "$stop_at" --arg r "$resume_at" '[.[] | select((.run_id | startswith("scheduled__")) and .logical_date >= $s and .logical_date < $r)] | length' <<<"$new")
echo "结论：停止区间 $stop_at ～ $resume_at；为停止期间的调度点补建运行 $catch 个"
