#!/usr/bin/env bash
# T060 云端验证：卸载只删除织境资源，其他 namespace 资源数量不变，devbox-0 仍运行；随后重新部署恢复（SC-009）
source "$(dirname "$0")/lib.sh"
others() { for ns in $(K get ns -o name | sed 's#.*/##' | grep -vE '^(contexture|mock-sources|contexture-build|contexture-ci|envoy-gateway-system|cnpg-system|doris-system|cert-manager)$'); do
  printf '%s %s\n' "$ns" "$(K -n "$ns" get all,pvc,secret,configmap --no-headers 2>/dev/null | wc -l)"; done; }
before=$(others)
CONFIRM=yes "$ROOT/tools/cloud/uninstall.sh"
for i in $(seq 1 60); do K get ns contexture >/dev/null 2>&1 || break; sleep 10; done
K get ns contexture >/dev/null 2>&1 && fail "namespace contexture 仍存在" || pass "namespace contexture 已删除"
after=$(others)
[[ $before == "$after" ]] && pass "其他 namespace 的资源数量不变" || { fail "其他 namespace 的资源有变化"; diff <(echo "$before") <(echo "$after"); }
[[ $(K -n dev get pod devbox-0 -o jsonpath='{.status.phase}') == Running ]] && pass "devbox-0 仍在运行" || fail "devbox-0 不在运行"
K get crd httproutes.gateway.networking.k8s.io >/dev/null && pass "集群托管的 Gateway API CRD 保留" || fail "Gateway API CRD 被删除"
echo "重新部署以恢复环境：make cloud-deploy"
finish
