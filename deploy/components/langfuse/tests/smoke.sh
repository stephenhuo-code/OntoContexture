#!/usr/bin/env bash
# 冒烟测试：Langfuse web 健康，初始化的项目密钥可用（OTel 写入入口可访问）
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
NS=contexture
kubectl -n $NS rollout status deployment/langfuse-web --timeout=600s
kubectl -n $NS rollout status deployment/langfuse-worker --timeout=600s
PK=$(kubectl -n $NS get secret langfuse-init -o jsonpath='{.data.public-key}' | base64 -d)
SK=$(kubectl -n $NS get secret langfuse-init -o jsonpath='{.data.secret-key}' | base64 -d)
curl_in -u "$PK:$SK" http://langfuse-web:3000/api/public/projects | grep -q '"contexture"' && echo "langfuse OK"
