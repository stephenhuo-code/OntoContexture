#!/usr/bin/env bash
# make cloud-uninstall（030 FR-030、US7）：卸载织境云端环境——先卸载全部 Helm release，再删除织境的 namespace（含持久卷）
# 与织境安装的 CRD。永不触碰 dev（开发机 devbox-0 所在）、kube-* 与 DOKS 托管的 Gateway API CRD。须显式确认。
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$HERE/common.sh"

CTX_OWNED_NAMESPACES=(mock-sources contexture-build contexture-ci envoy-gateway-system cnpg-system doris-system cert-manager)
CTX_OWNED_CRD_PATTERN='\.(postgresql\.cnpg\.io|doris\.selectdb\.com|gateway\.envoyproxy\.io|cert-manager\.io|acme\.cert-manager\.io|gateway\.networking\.x-k8s\.io)$'

ctx_uninstall_plan() {
  local existing ns crd managed
  existing=$(ctx_kubectl get namespace -o name 2>/dev/null | sed 's#.*/##')
  for ns in "$CTX_CLOUD_NAMESPACE" "${CTX_OWNED_NAMESPACES[@]}"; do
    [[ $ns == dev || $ns == default || $ns == kube-* ]] && continue
    grep -qx "$ns" <<< "$existing" && echo "namespace/$ns"
  done
  # 织境组件的 CRD；Gateway API 中只删 DOKS 未托管、由 Envoy Gateway 新增的（如 listenersets、tcproutes）
  while read -r crd managed; do
    [[ -z $crd ]] && continue
    if [[ $crd =~ $CTX_OWNED_CRD_PATTERN ]] ||
      [[ $crd == *.gateway.networking.k8s.io && $managed != true ]]; then
      echo "crd/$crd"
    fi
  done < <(ctx_kubectl get crd -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.metadata.labels.doks\.digitalocean\.com/managed}{"\n"}{end}')
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
