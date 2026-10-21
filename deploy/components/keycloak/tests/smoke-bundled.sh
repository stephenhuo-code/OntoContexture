#!/usr/bin/env bash
# 自带 Keycloak 模式（keycloak.enabled=true）的验证：在独立命名空间中部署 Keycloak 26.8.0 与临时 PostgreSQL，
# 导入织境配置，核对客户端与角色。用法：deploy/components/keycloak/tests/smoke-bundled.sh（需 kind 集群）
set -euo pipefail
cd "$(dirname "$0")/../../../.."
NS=ctx-keycloak-bundled
trap 'kubectl delete namespace "$NS" --wait=false >/dev/null 2>&1 || true' EXIT
kubectl create namespace "$NS" >/dev/null
kubectl -n "$NS" create secret generic pg-keycloak --from-literal=username=keycloak --from-literal=password=kcpass >/dev/null
kubectl -n "$NS" create secret generic bff-oidc --from-literal=client-secret=bundled-bff >/dev/null
kubectl -n "$NS" create secret generic om-oidc --from-literal=client-secret=bundled-om >/dev/null
kubectl -n "$NS" run postgres --image=postgres:17 --env=POSTGRES_USER=keycloak --env=POSTGRES_PASSWORD=kcpass \
  --env=POSTGRES_DB=keycloak --port=5432 --expose >/dev/null
kubectl -n "$NS" wait pod/postgres --for=condition=Ready --timeout=180s >/dev/null

helm install keycloak deploy/components/keycloak/chart -n "$NS" \
  -f deploy/components/keycloak/values/bundled-example.yaml \
  --set keycloak.databaseHost=postgres --set keycloak.hostname=http://keycloak.ctx.test \
  --set import.trustedCaSecret= \
  --set-file import.files.contexture=deploy/components/keycloak/config/contexture.yaml \
  --set-file import.files.testUsers=deploy/components/keycloak/config/test-users.yaml \
  $(grep -v '^#' deploy/components/keycloak/import.env | grep = | sed 's/^/--set import.env./') \
  --wait --timeout 10m >/dev/null
kubectl -n "$NS" wait "$(kubectl -n "$NS" get jobs -o name | head -1)" --for=condition=Complete --timeout=600s >/dev/null
PW=$(kubectl -n "$NS" get secret keycloak-keycloak-admin -o jsonpath='{.data.password}' | base64 -d)
kubectl -n "$NS" run probe --restart=Never --image=curlimages/curl:8.17.0 --command -- sh -c "
  T=\$(curl -s -d grant_type=password -d client_id=admin-cli -d username=admin -d password='$PW' \
      http://keycloak-keycloak:8080/realms/master/protocol/openid-connect/token | sed 's/.*access_token\":\"\([^\"]*\).*/\1/')
  curl -s -H \"Authorization: Bearer \$T\" http://keycloak-keycloak:8080/admin/realms/digital-workforce/clients?clientId=contexture-bff
  curl -s -H \"Authorization: Bearer \$T\" http://keycloak-keycloak:8080/admin/realms/digital-workforce/roles/business-user" >/dev/null
kubectl -n "$NS" wait pod/probe --for=jsonpath='{.status.phase}'=Succeeded --timeout=120s >/dev/null
OUT=$(kubectl -n "$NS" logs probe)
grep -q '"clientId":"contexture-bff"' <<<"$OUT" && grep -q '"name":"business-user"' <<<"$OUT"
echo "keycloak（自带模式）OK"
