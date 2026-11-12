#!/usr/bin/env bash
# 环境状态记录（030 data-model.md 第 2 节）：集群 ConfigMap contexture-cloud-state，部署元数据，非业务数据。
CTX_STATE_CM=contexture-cloud-state

ctx_state_get() {  # ctx_state_get <键>，不存在时输出空
  ctx_kubectl get configmap "$CTX_STATE_CM" -o json 2>/dev/null | jq -r --arg k "$1" '.data[$k] // ""'
}

ctx_state_set() {  # ctx_state_set 键=值 ...（合并写入；自动记录时间）
  ctx_kubectl get configmap "$CTX_STATE_CM" >/dev/null 2>&1 || ctx_kubectl create configmap "$CTX_STATE_CM" >/dev/null
  local now kv data='{}' stamp_lifecycle=0 stamp_stable=0
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  for kv in "$@"; do
    data=$(jq -c --arg k "${kv%%=*}" --arg v "${kv#*=}" '. + {($k): $v}' <<< "$data")
    case ${kv%%=*} in
      lifecycle.state) stamp_lifecycle=1 ;;
      stableVersion.deployedAt) ;;
      stableVersion.*) stamp_stable=1 ;;
    esac
  done
  [[ $stamp_lifecycle == 1 ]] && data=$(jq -c --arg t "$now" '. + {"lifecycle.updatedAt": $t}' <<< "$data")
  [[ $stamp_stable == 1 ]] && data=$(jq -c --arg t "$now" '. + {"stableVersion.deployedAt": $t}' <<< "$data")
  ctx_kubectl patch configmap "$CTX_STATE_CM" --type merge -p "$(jq -c '{data: .}' <<< "$data")" >/dev/null
}

# 运行状态判定：ctx_derive_state <lifecycle.state> <期望副本合计> <就绪副本合计> <带停止注解的工作负载数>
ctx_derive_state() {
  local lifecycle=$1 desired=$2 ready=$3 stopped=$4
  if [[ $lifecycle == stopped && $desired == 0 && $ready == 0 && $stopped -gt 0 ]]; then
    echo 已停止
  elif [[ $lifecycle == running && $stopped == 0 && $desired -gt 0 && $ready == "$desired" ]]; then
    echo 运行中
  else
    echo 部分运行
  fi
}
