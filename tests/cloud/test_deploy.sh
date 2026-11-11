#!/usr/bin/env bash
# T042 云端验证：部署后冒烟测试全部通过；再次部署后自动生成的 Secret 不变，user1 仍可登录（US1 场景 1、2；FR-003；SC-006）
source "$(dirname "$0")/lib.sh"
secrets() { for s in pg-openmetadata pg-langfuse pg-airflow pg-bff pg-keycloak langfuse-init langfuse-secrets om-secrets \
  airflow-secrets doris-root keycloak-keycloak-admin keycloak-provisioner bff-oidc om-oidc; do
  printf '%s %s\n' "$s" "$(K get secret "$s" -o jsonpath='{.data}' | sha256sum | cut -c1-16)"; done; }
login() {  # 以 user1 走一次完整登录，最终回到织境首页即成功
  local jar; jar=$(mktemp)
  local form; form=$(curl -s -c "$jar" -b "$jar" -L "https://$CTX_CLOUD_DOMAIN/bff/v1/auth/login" | grep -oE 'action="[^"]+"' | head -1 | sed 's/action="//;s/"$//;s/&amp;/\&/g')
  [[ -n $form ]] || { rm -f "$jar"; return 1; }
  local final; final=$(curl -s -c "$jar" -b "$jar" -L -o /dev/null -w '%{url_effective}' --data-urlencode username=user1 --data-urlencode password=user1 "$form")
  rm -f "$jar"; [[ $final == "https://$CTX_CLOUD_DOMAIN/"* ]]
}
first=$(secrets)
( cd "$ROOT" && make cloud-deploy ) > "$CTX_LOG_DIR/test-deploy.log" 2>&1 && pass "第一次部署成功，冒烟测试全部通过" || fail "部署失败（$CTX_LOG_DIR/test-deploy.log）"
login && pass "user1 登录成功" || fail "user1 登录失败"
start=$(date +%s)
( cd "$ROOT" && make cloud-deploy ) >> "$CTX_LOG_DIR/test-deploy.log" 2>&1 && pass "重复部署成功（$(( $(date +%s)-start ))s，SC-001 ≤ 20 分钟）" || fail "重复部署失败"
second=$(secrets)
[[ $first == "$second" ]] && pass "自动生成的 Secret 未变化" || { fail "Secret 发生变化"; diff <(echo "$first") <(echo "$second"); }
login && pass "重复部署后 user1 仍可登录" || fail "重复部署后登录失败"
finish
