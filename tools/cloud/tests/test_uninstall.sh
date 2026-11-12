#!/usr/bin/env bash
# T058：cloud-uninstall 只删除织境的资源（FR-030）
source "$REPO_ROOT/tools/cloud/uninstall.sh"
stub_log_init
ctx_load_config() { CTX_CLOUD_NAMESPACE=contexture; }
ctx_helmfile() { stub_record "helmfile $*"; }
ctx_kubectl() {
  case "$*" in
    *"get crd -o name"*)
      printf '%s\n' "clusters.postgresql.cnpg.io " "dorisclusters.doris.selectdb.com " "envoyproxies.gateway.envoyproxy.io " \
        "certificates.cert-manager.io " "listenersets.gateway.networking.k8s.io " \
        "httproutes.gateway.networking.k8s.io true" "gateways.gateway.networking.k8s.io true" "ciliumnodes.cilium.io " ;;
    *"get namespace"*) printf '%s\n' contexture mock-sources contexture-build contexture-ci envoy-gateway-system cnpg-system doris-system cert-manager dev kube-system default ;;
    *) stub_record "kubectl $*" ;;
  esac
}

test_plan_contains_only_contexture_namespaces_and_crds() {
  ctx_load_config
  local plan; plan=$(ctx_uninstall_plan)
  local ns
  for ns in contexture mock-sources contexture-build contexture-ci envoy-gateway-system cnpg-system doris-system cert-manager; do
    assert_contains "$plan" "namespace/$ns"
  done
  assert_contains "$plan" "crd/clusters.postgresql.cnpg.io"
  assert_contains "$plan" "crd/certificates.cert-manager.io"
  # Gateway API CRD 可能由集群托管，一律不删除（厂商无关，R19）
  assert_not_contains "$plan" "listenersets.gateway.networking.k8s.io"
  assert_not_contains "$plan" "namespace/dev"
  assert_not_contains "$plan" "namespace/kube-system"
  assert_not_contains "$plan" "namespace/default"
  assert_not_contains "$plan" "httproutes.gateway.networking.k8s.io"
  assert_not_contains "$plan" "gateways.gateway.networking.k8s.io"
  assert_not_contains "$plan" "cilium"
}

test_unconfirmed_uninstall_deletes_nothing() {
  CONFIRM= assert_status 3 ctx_uninstall_main
  [[ -z $(stub_calls | grep -E 'delete|destroy') ]] || fail "未确认时不应删除：$(stub_calls)"
}

test_confirmed_uninstall_destroys_releases_then_namespaces_then_crds() {
  CONFIRM=yes ctx_uninstall_main >/dev/null
  local calls; calls=$(stub_calls)
  assert_contains "$calls" "helmfile destroy"
  assert_contains "$calls" "delete namespace contexture"
  assert_contains "$calls" "delete crd clusters.postgresql.cnpg.io"
  assert_not_contains "$calls" "delete namespace dev"
  assert_not_contains "$calls" "delete crd httproutes.gateway.networking.k8s.io"
  [[ $(grep -n 'helmfile destroy' <<< "$calls" | cut -d: -f1) -lt $(grep -n 'delete namespace' <<< "$calls" | head -1 | cut -d: -f1) ]] ||
    fail "须先卸载 release 再删除 namespace"
}

test_plan_succeeds_under_errexit_when_last_crd_is_not_owned() {
  ctx_load_config
  ( set -e; ctx_uninstall_plan >/dev/null ) || fail "set -e 下 plan 不应失败"
}
