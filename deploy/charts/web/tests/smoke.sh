#!/usr/bin/env bash
# 冒烟测试：入口返回页面，前端路由回落到 index.html，/bff 仍由 bff 处理
set -euo pipefail
# 入口地址：本地 kind 为 localhost:8080；云端由 cloud-deploy 传入 https://<域名>，staging 证书不受信任时允许跳过校验（030）
BASE=${CTX_SMOKE_BASE_URL:-http://localhost:8080}
curl() { command curl ${CTX_SMOKE_INSECURE:+-k} "$@"; }
curl -sf "$BASE/" | grep -q '<div id="root">'
curl -sf "$BASE/objects/equipment" | grep -q '<div id="root">'
[[ $(curl -s -o /dev/null -w "%{http_code}" "$BASE/bff/v1/me") == 401 ]]
echo "web OK"
