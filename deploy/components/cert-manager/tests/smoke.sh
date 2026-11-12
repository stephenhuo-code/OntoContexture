#!/usr/bin/env bash
# 冒烟测试（030）：证书已签发（DNS 未就绪时会超时，按 cloud-deploy 输出的 DNS 记录配置后重试）
set -euo pipefail
[[ ${CTX_ENV:-} == cloud ]] || { echo "跳过：该组件只在云端环境部署（030）"; exit 0; }
kubectl -n "${NS:-contexture}" wait certificate/contexture --for=condition=Ready --timeout="${CTX_CERT_TIMEOUT:-600s}"
