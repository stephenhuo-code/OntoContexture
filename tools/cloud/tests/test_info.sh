#!/usr/bin/env bash
# T056：cloud-info 输出各组件地址、登录方式与凭证位置，不输出凭证值（FR-029；US7 场景 1）
source "$REPO_ROOT/tools/cloud/info.sh"
ctx_load_config() { CTX_CLOUD_DOMAIN=ctx.example.com CTX_CLOUD_NAMESPACE=contexture CTX_CLOUD_KUBECONFIG=/k CTX_CLOUD_CONTEXT=ctx; }
ctx_kubectl() { echo "c2VjcmV0LXZhbHVl"; }   # 任何读取都返回一个“凭证值”，用于断言不被输出

test_lists_every_component_from_make_ports() {
  local out; out=$(ctx_info_main)
  local url
  for url in https://ctx.example.com https://om.ctx.example.com https://langfuse.ctx.example.com https://airflow.ctx.example.com \
    https://jaeger.ctx.example.com https://prometheus.ctx.example.com https://dashboards.ctx.example.com \
    https://gateway-admin.ctx.example.com https://sso.ctx.example.com; do
    assert_contains "$out" "$url"
  done
}

test_points_to_secret_locations_without_values() {
  local out; out=$(ctx_info_main)
  assert_contains "$out" "langfuse-init"
  assert_contains "$out" "keycloak-keycloak-admin"
  assert_contains "$out" "om-secrets"
  assert_not_contains "$out" "secret-value"
  assert_not_contains "$out" "c2VjcmV0LXZhbHVl"
}

# 负责人验收反馈（2026-11-12）：按提示用 user1 登录被拒——织境 Web 只对 admin / ai-engineer 开放，user1 是业务用户
test_web_login_hint_names_accounts_with_web_access() {
  local out; out=$(ctx_info_main)
  assert_contains "$out" "engineer1 / engineer1"
  assert_contains "$out" "user1 为业务用户"
}
