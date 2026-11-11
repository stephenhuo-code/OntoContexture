#!/usr/bin/env bash
# 冒烟测试共用函数：在集群内运行一次性命令并返回其输出（避免 kubectl run -i 的输出竞态）。
# 用法：source deploy/components/smoke-lib.sh；incluster <镜像> <命令...>
NS=${NS:-contexture}

incluster() {
  local image=$1; shift
  local name="smoke-$RANDOM$RANDOM"
  # 云端（030）：设置 CTX_NODE_SELECTOR=<标签键>=<值> 时把临时 Pod 固定到弹性池
  local overrides=()
  if [[ -n ${CTX_NODE_SELECTOR:-} ]]; then
    overrides=("--overrides={\"spec\":{\"nodeSelector\":{\"${CTX_NODE_SELECTOR%%=*}\":\"${CTX_NODE_SELECTOR#*=}\"}}}")
  fi
  kubectl -n "$NS" run "$name" --restart=Never --image="$image" "${overrides[@]}" --command -- "$@" >/dev/null
  kubectl -n "$NS" wait "pod/$name" --for=jsonpath='{.status.phase}'=Succeeded --timeout=180s >/dev/null 2>&1 || true
  kubectl -n "$NS" logs "$name"
  local phase
  phase=$(kubectl -n "$NS" get pod "$name" -o jsonpath='{.status.phase}')
  kubectl -n "$NS" delete pod "$name" --wait=false >/dev/null
  [[ $phase == Succeeded ]]
}

curl_in() { incluster curlimages/curl:8.17.0 curl -s "$@"; }
