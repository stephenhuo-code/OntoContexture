#!/usr/bin/env bash
# 冒烟测试：经入口访问 bff，未登录返回 401；登录跳转到 Keycloak
set -euo pipefail
[[ $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/bff/v1/me) == 401 ]]
curl -s -o /dev/null -w "%{redirect_url}" http://localhost:8080/bff/v1/auth/login | grep -q "/protocol/openid-connect/auth"
echo "bff OK"
