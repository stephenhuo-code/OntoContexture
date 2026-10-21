#!/usr/bin/env bash
# 离线安装（D9）：用离线包中的镜像与 Chart 部署，不访问外网。
# 用法：deploy/offline/install.sh <离线包目录> [local|lite]（在织境仓库根目录执行，需 .env.local）
#   kind 集群：CTX_KIND_CLUSTER=<集群名>（默认 contexture）；镜像以 kind load 导入。
#   客户集群：先把 images/*.tar 推送到内网镜像仓库（见 README），再以同样的 helmfile 部署。
set -euo pipefail
DIST=$(cd "${1:?离线包目录}" && pwd)
ENV=${2:-local}
cd "$(dirname "$0")/../.."
CTX_OFFLINE_DIST="$DIST" tools/up.sh up "$ENV"
