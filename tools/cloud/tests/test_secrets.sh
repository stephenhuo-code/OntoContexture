#!/usr/bin/env bash
# T025：集群 Secret 生成（FR-003、FR-010、R14）——已存在不覆盖；docr-pull 按配置更新；不创建 ctx-trusted-ca
source "$REPO_ROOT/tools/cloud/common.sh"
source "$REPO_ROOT/tools/cloud/secrets.sh"
stub_log_init
CTX_CLOUD_NAMESPACE=contexture CTX_CLOUD_REGISTRY=registry.example.com/ctx
CTX_CLOUD_REGISTRY_READ_TOKEN=read-token CTX_CLOUD_REGISTRY_WRITE_TOKEN=write-token
EXISTING=" "
ctx_kubectl() {  # 桩：记录调用；get secret 按 EXISTING 判断；jsonpath 读取返回固定口令
  stub_record "kubectl $*"
  case "$*" in
    *"get secret"*"jsonpath"*) printf '%s' "$(printf 'pw' | base64)" ;;
    *"get secret "*) local name; name=$(sed -E 's/.*get secret ([^ ]+).*/\1/' <<< "$*"); [[ $EXISTING == *" $name "* ]] ;;
    *"apply -f -"*) cat >> "$STUB_LOG" ;;
    *) return 0 ;;
  esac
}

created() { stub_calls | grep -E "create secret [a-z-]+ $1( |$)" ; }

test_creates_all_platform_secrets_when_missing() {
  ctx_ensure_secrets
  local name
  for name in pg-openmetadata pg-langfuse pg-airflow pg-bff pg-keycloak bff-oidc om-oidc om-secrets fuseki-auth \
    doris-root doris-reader langfuse-secrets langfuse-init langfuse-clickhouse airflow-secrets; do
    [[ -n $(created "$name") ]] || fail "未创建 $name"
  done
}

test_existing_secrets_are_not_recreated() {
  EXISTING=" pg-bff om-secrets langfuse-init "
  ctx_ensure_secrets
  [[ -z $(created pg-bff) ]] || fail "已存在的 pg-bff 被重建"
  [[ -z $(created om-secrets) ]] || fail "已存在的 om-secrets 被重建"
  [[ -z $(created langfuse-init) ]] || fail "已存在的 langfuse-init 被重建"
}

test_registry_pull_secret_is_refreshed_each_time_in_pulling_namespaces() {
  EXISTING=" docr-pull "
  ctx_ensure_secrets
  local calls; calls=$(stub_calls)
  assert_contains "$calls" "-n contexture create secret docker-registry docr-pull"
  assert_contains "$calls" "-n contexture-ci create secret docker-registry docr-pull"
  assert_contains "$calls" "-n contexture-build create secret docker-registry docr-push"
  assert_contains "$calls" "--docker-server=registry.example.com"
}

test_trusted_ca_secret_is_never_created() {
  ctx_ensure_secrets
  assert_not_contains "$(stub_calls)" ctx-trusted-ca
}

test_tokens_are_not_printed() {
  local out; out=$(ctx_ensure_secrets 2>&1)
  assert_not_contains "$out" read-token
  assert_not_contains "$out" write-token
}

test_fernet_key_is_32_bytes_urlsafe_base64() {
  local key; key=$(ctx_fernet_key)
  [[ $key =~ ^[A-Za-z0-9_-]{43}=$ ]] || fail "格式不对：$key"
  assert_eq 32 "$(printf '%s' "$key" | tr '_-' '/+' | base64 -d | wc -c)"
}

test_bff_secrets_get_generated_client_secret_and_database_url() {
  ctx_ensure_secrets
  local calls; calls=$(stub_calls)
  assert_contains "$calls" "patch secret bff-secrets"
  assert_contains "$calls" "postgresql+asyncpg://bff:pw@pg-rw:5432/bff"
}
