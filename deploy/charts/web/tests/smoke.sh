#!/usr/bin/env bash
# 冒烟测试：入口返回页面，前端路由回落到 index.html，/bff 仍由 bff 处理
set -euo pipefail
curl -sf http://localhost:8080/ | grep -q '<div id="root">'
curl -sf http://localhost:8080/objects/equipment | grep -q '<div id="root">'
[[ $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/bff/v1/me) == 401 ]]
echo "web OK"
