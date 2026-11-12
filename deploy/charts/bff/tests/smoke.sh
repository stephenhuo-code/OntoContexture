#!/usr/bin/env bash
# 冒烟测试：经入口访问 bff，未登录返回 401；登录跳转到 Keycloak
set -euo pipefail
# 入口地址：本地 kind 为 localhost:8080；云端由 cloud-deploy 传入 https://<域名>，staging 证书不受信任时允许跳过校验（030）
BASE=${CTX_SMOKE_BASE_URL:-http://localhost:8080}
curl() { command curl ${CTX_SMOKE_INSECURE:+-k} "$@"; }
[[ $(curl -s -o /dev/null -w "%{http_code}" "$BASE/bff/v1/me") == 401 ]]
curl -s -o /dev/null -w "%{redirect_url}" "$BASE/bff/v1/auth/login" | grep -q "/protocol/openid-connect/auth"
echo "bff OK"
