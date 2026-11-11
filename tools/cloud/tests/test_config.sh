#!/usr/bin/env bash
# T008：.env.cloud 校验（contracts/cloud-config.md；FR-004、FR-005）
source "$REPO_ROOT/tools/cloud/common.sh"

kubectl() {  # 桩：已知上下文 ctx-ok，且 API 可达
  case "$*" in
    *"config get-contexts -o name"*) echo ctx-ok ;;
    *"get --raw /version"*) echo '{}' ;;
    *) return 0 ;;
  esac
}

write_env() {  # write_env <目录> [覆盖的 键=值 ...]
  local dir=$1; shift
  : > "$dir/kubeconfig"; chmod 600 "$dir/kubeconfig"
  {
    echo "CTX_CLOUD_KUBECONFIG=$dir/kubeconfig"
    echo "CTX_CLOUD_CONTEXT=ctx-ok"
    echo "CTX_CLOUD_NODE_LABEL=example.com/node-pool"
    echo "CTX_CLOUD_NODE_POOL=elastic"
    echo "CTX_CLOUD_STORAGE_CLASS=standard-rwo"
    echo "CTX_CLOUD_DOMAIN=ctx.example.com"
    echo "CTX_CLOUD_ACME_EMAIL=ops@example.com"
    echo "CTX_CLOUD_REGISTRY=registry.example.com/ctx"
    echo "CTX_CLOUD_REGISTRY_READ_TOKEN=secret-read-token-value"
    echo "CTX_CLOUD_REGISTRY_WRITE_TOKEN=secret-write-token-value"
  } > "$dir/env"
  local kv
  for kv in "$@"; do
    sed -i "/^${kv%%=*}=/d" "$dir/env"
    [[ $kv == *= ]] || echo "$kv" >> "$dir/env"
  done
  printf '%s' "$dir/env"
}

test_valid_config_loads_with_defaults() {
  local d; d=$(tmpdir)
  ctx_load_config "$(write_env "$d")"
  assert_eq contexture "$CTX_CLOUD_NAMESPACE" "namespace 默认值"
  assert_eq production "$CTX_CLOUD_ACME_SERVER" "签发器默认值"
}

test_missing_required_key_exits_2() {
  local d; d=$(tmpdir)
  assert_status 2 ctx_load_config "$(write_env "$d" CTX_CLOUD_DOMAIN=)"
  assert_contains "$OUTPUT" CTX_CLOUD_DOMAIN
}

test_kubeconfig_must_be_mode_600() {
  local d; d=$(tmpdir); local env; env=$(write_env "$d"); chmod 644 "$d/kubeconfig"
  assert_status 2 ctx_load_config "$env"
  assert_contains "$OUTPUT" 600
}

test_unknown_context_exits_2() {
  local d; d=$(tmpdir)
  assert_status 2 ctx_load_config "$(write_env "$d" CTX_CLOUD_CONTEXT=ctx-missing)"
  assert_contains "$OUTPUT" ctx-missing
}

test_local_domains_are_rejected() {
  local d; d=$(tmpdir)
  assert_status 2 ctx_load_config "$(write_env "$d" CTX_CLOUD_DOMAIN=localhost)"
  assert_status 2 ctx_load_config "$(write_env "$d" CTX_CLOUD_DOMAIN=sso.127.0.0.1.nip.io)"
  assert_status 2 ctx_load_config "$(write_env "$d" CTX_CLOUD_DOMAIN=not_a_domain)"
}

test_acme_server_must_be_staging_or_production() {
  local d; d=$(tmpdir)
  assert_status 2 ctx_load_config "$(write_env "$d" CTX_CLOUD_ACME_SERVER=prod)"
  ctx_load_config "$(write_env "$d" CTX_CLOUD_ACME_SERVER=staging)"
}

test_errors_never_echo_token_values() {
  local d; d=$(tmpdir)
  assert_status 2 ctx_load_config "$(write_env "$d" CTX_CLOUD_DOMAIN=localhost)"
  assert_not_contains "$OUTPUT" secret-read-token-value
  assert_not_contains "$OUTPUT" secret-write-token-value
}

test_missing_env_file_exits_2_with_hint() {
  assert_status 2 ctx_load_config /nonexistent/.env.cloud
  assert_contains "$OUTPUT" ".env.cloud.example"
}

test_confirm_requires_yes() {
  CONFIRM=yes ctx_confirm "删除" </dev/null
  CONFIRM= assert_status 3 ctx_confirm "删除"
}
