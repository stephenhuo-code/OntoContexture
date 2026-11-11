#!/usr/bin/env bash
# 云端集群 Secret（030 FR-003、FR-010、research R14）：沿用 tools/up.sh 的名称与键，已存在的不覆盖（避免密码变化导致数据不可读）；
# 镜像仓库凭证每次按 .env.cloud 刷新。开发机无 Python，全部用 bash + openssl 生成。
# 自带 Keycloak 的管理员密码由 Keycloak Chart 自行生成并保留（keycloak-keycloak-admin，helm.sh/resource-policy: keep）。
# 用法：source common.sh; source secrets.sh; ctx_ensure_secrets

ctx_rand() { openssl rand -hex "${1:-16}"; }
# Fernet 密钥：32 字节随机数的 urlsafe base64
ctx_fernet_key() { openssl rand -base64 32 | tr '+/' '-_'; }

# 已存在则跳过：ctx_secret_ensure <namespace> <名称> <create secret 的其余参数...>
ctx_secret_ensure() {
  local ns=$1 name=$2; shift 2
  ctx_kubectl -n "$ns" get secret "$name" >/dev/null 2>&1 && return 0
  ctx_kubectl -n "$ns" create secret "$@" >/dev/null
}

# 每次按最新值覆盖：ctx_secret_apply <namespace> <create secret 的参数...>
ctx_secret_apply() {
  local ns=$1; shift
  ctx_kubectl -n "$ns" create secret "$@" --dry-run=client -o yaml | ctx_kubectl -n "$ns" apply -f - >/dev/null
}

ctx_secret_value() {  # ctx_secret_value <namespace> <名称> <键>
  ctx_kubectl -n "$1" get secret "$2" -o jsonpath="{.data.$3}" | base64 -d
}

ctx_ensure_secrets() {
  local ns=$CTX_CLOUD_NAMESPACE db registry_host
  for n in "$ns" contexture-ci contexture-build; do
    ctx_kubectl get namespace "$n" >/dev/null 2>&1 || ctx_kubectl create namespace "$n" >/dev/null
  done

  for db in openmetadata langfuse airflow bff keycloak; do
    ctx_secret_ensure "$ns" "pg-$db" generic "pg-$db" --type=kubernetes.io/basic-auth \
      --from-literal=username="$db" --from-literal=password="$(ctx_rand)"
  done
  # 自带 Keycloak：客户端密钥由部署生成并导入 Keycloak（本地由 .env.local 提供）
  ctx_secret_ensure "$ns" bff-oidc generic bff-oidc --from-literal=client-secret="$(ctx_rand)"
  ctx_secret_ensure "$ns" om-oidc generic om-oidc --from-literal=client-id=contexture-openmetadata \
    --from-literal=client-secret="$(ctx_rand)"
  # 工具与 e2e 的导入服务账号：Keycloak 导入时创建（keycloak Chart 的 import.provisionerSecret），本地由负责人手工创建
  ctx_secret_ensure "$ns" keycloak-provisioner generic keycloak-provisioner \
    --from-literal=client-id=contexture-provisioner --from-literal=client-secret="$(ctx_rand)"
  ctx_secret_ensure "$ns" om-secrets generic om-secrets --from-literal=fernet-key="$(ctx_fernet_key)" \
    --from-literal=airflow-password="$(ctx_rand 12)"
  ctx_secret_ensure "$ns" fuseki-auth generic fuseki-auth --from-literal=admin-password="$(ctx_rand 12)" \
    --from-literal=openmetadata-password="$(ctx_rand 12)"
  ctx_secret_ensure "$ns" doris-root generic doris-root --from-literal=username=root --from-literal=password="$(ctx_rand 12)"
  ctx_secret_ensure "$ns" doris-reader generic doris-reader --from-literal=username=ctx_reader \
    --from-literal=password="$(ctx_rand 12)"
  ctx_secret_ensure "$ns" langfuse-secrets generic langfuse-secrets --from-literal=salt="$(ctx_rand)" \
    --from-literal=encryption-key="$(ctx_rand 32)" --from-literal=nextauth-secret="$(ctx_rand 32)"
  ctx_secret_ensure "$ns" langfuse-init generic langfuse-init --from-literal=public-key="pk-lf-$(ctx_rand 12)" \
    --from-literal=secret-key="sk-lf-$(ctx_rand)" --from-literal=admin-password="$(ctx_rand 12)"
  ctx_secret_ensure "$ns" langfuse-clickhouse generic langfuse-clickhouse --from-literal=password="$(ctx_rand)"
  ctx_secret_ensure "$ns" airflow-secrets generic airflow-secrets --from-literal=fernet-key="$(ctx_fernet_key)" \
    --from-literal=api-secret-key="$(ctx_rand)" --from-literal=jwt-secret="$(ctx_rand 32)"

  # 由上面的 Secret 派生，每次刷新
  local lf_pk lf_sk
  lf_pk=$(ctx_secret_value "$ns" langfuse-init public-key)
  lf_sk=$(ctx_secret_value "$ns" langfuse-init secret-key)
  ctx_secret_apply "$ns" generic otel-langfuse --from-literal=auth="$(printf '%s:%s' "$lf_pk" "$lf_sk" | base64 -w0)"
  ctx_secret_apply "$ns" generic airflow-metadata \
    --from-literal=connection="postgresql://airflow:$(ctx_secret_value "$ns" pg-airflow password)@pg-rw:5432/airflow?sslmode=disable"
  ctx_secret_apply "$ns" generic ai-gateway-model --from-literal=host="${MODEL_HOST:-api.deepseek.com:443}" \
    --from-literal=model="${MODEL_NAME:-deepseek-chat}" --from-literal=api-key="${MODEL_API_KEY:-unset}"

  # bff：挂载为文件（CTX_SECRETS_DIR）；OM 机器人令牌由 cloud-seed 写入
  ctx_secret_ensure "$ns" bff-secrets generic bff-secrets --from-literal=ctx_om_token=""
  local patch
  patch=$(jq -cn --arg cs "$(ctx_secret_value "$ns" bff-oidc client-secret)" \
    --arg db "postgresql+asyncpg://bff:$(ctx_secret_value "$ns" pg-bff password)@pg-rw:5432/bff" \
    '{stringData: {ctx_client_secret: $cs, ctx_database_url: $db}}')
  ctx_kubectl -n "$ns" patch secret bff-secrets --type merge -p "$patch" >/dev/null

  # 工具箱（contexture-ci）运行 seed / e2e / mockfactory 所需的端点与凭证，以环境变量注入（不上传任何凭证文件，R12）
  ctx_secret_apply contexture-ci generic toolbox-env \
    --from-literal=KEYCLOAK_URL="https://sso.${CTX_CLOUD_DOMAIN:-}" \
    --from-literal=KEYCLOAK_REALM=digital-workforce \
    --from-literal=KEYCLOAK_PROVISIONER_CLIENT_ID=contexture-provisioner \
    --from-literal=KEYCLOAK_PROVISIONER_CLIENT_SECRET="$(ctx_secret_value "$ns" keycloak-provisioner client-secret)" \
    --from-literal=CTX_E2E_BASE_URL="https://${CTX_CLOUD_DOMAIN:-}" \
    --from-literal=CTX_CLOUD_NAMESPACE="$ns" \
    --from-literal=CTX_TENANT_ID=local

  # 镜像仓库：拉取用只读令牌（平台与工具箱），推送用读写令牌（集群内构建）；每次刷新
  registry_host=${CTX_CLOUD_REGISTRY%%/*}
  for n in "$ns" contexture-ci; do
    ctx_secret_apply "$n" docker-registry docr-pull --docker-server="$registry_host" \
      --docker-username=contexture --docker-password="$CTX_CLOUD_REGISTRY_READ_TOKEN"
  done
  if [[ -n ${CTX_CLOUD_REGISTRY_WRITE_TOKEN:-} ]]; then
    ctx_secret_apply contexture-build docker-registry docr-push --docker-server="$registry_host" \
      --docker-username=contexture --docker-password="$CTX_CLOUD_REGISTRY_WRITE_TOKEN"
  fi
}
