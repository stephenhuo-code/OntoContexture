#!/usr/bin/env bash
# make cloud-uninstall（030 FR-030、US7）：卸载织境云端环境——先卸载全部 Helm release，再删除织境的 namespace（含持久卷）
# 与织境安装的 CRD。永不触碰 dev（开发机 devbox-0 所在）、kube-* 与 DOKS 托管的 Gateway API CRD。须显式确认。
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$HERE/common.sh"

CTX_OWNED_NAMESPACES=(mock-sources contexture-build contexture-ci envoy-gateway-system cnpg-system doris-system cert-manager)
CTX_OWNED_CRD_PATTERN='\.(postgresql\.cnpg\.io|doris\.selectdb\.com|gateway\.envoyproxy\.io|cert-manager\.io|acme\.cert-manager\.io)$'

ctx_uninstall_plan() {
  local existing ns
  existing=$(ctx_kubectl get namespace -o name 2>/dev/null | sed 's#.*/##')
  for ns in "$CTX_CLOUD_NAMESPACE" "${CTX_OWNED_NAMESPACES[@]}"; do
    [[ $ns == dev || $ns == default || $ns == kube-* ]] && continue
    grep -qx "$ns" <<< "$existing" && echo "namespace/$ns"
  done
  # 织境组件的 CRD；Gateway API 的 CRD 可能由集群托管（如 DOKS），一律保留，不按厂商标签判断（R19）
  local crd
  for crd in $(ctx_kubectl get crd -o name 2>/dev/null | sed 's#.*/##'); do
    [[ $crd =~ $CTX_OWNED_CRD_PATTERN ]] && echo "crd/$crd"
  done
  return 0
}

ctx_uninstall_main() {
  ctx_load_config
  local plan item
  plan=$(ctx_uninstall_plan)
  ctx_confirm "将卸载织境云端环境并删除以下对象（含全部持久卷与数据，不可恢复）：
$(sed 's/^/  /' <<< "$plan")
不会触碰 dev（devbox-0）、kube-* 与集群托管的 Gateway API CRD。"
  ctx_log "卸载 Helm release"
  ctx_helmfile destroy || true
  ctx_log "删除 namespace 与 CRD"
  while read -r item; do
    [[ -z $item ]] && continue
    ctx_kubectl delete "${item%%/*}" "${item#*/}" --ignore-not-found --wait=false >/dev/null
  done <<< "$plan"
  ctx_log "已提交删除；namespace 中的持久卷由集群异步回收"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  set -euo pipefail
  ctx_uninstall_main "$@"
fi
