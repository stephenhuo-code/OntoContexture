#!/usr/bin/env bash
# 构建 openmetadata-server 与 openmetadata-ingestion 镜像（版本取自 UPSTREAM.yaml 的 image_version）。
# 用法：third_party/openmetadata/build/build.sh [server|ingestion|fuseki|all]
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(awk '/^image_version:/{print $2}' UPSTREAM.yaml)
REGISTRY=${CTX_REGISTRY:-contexture}
TARGET=${1:-all}

[ -f src/pom.xml ] || { echo "子仓库未检出：git submodule update --init --depth 1 third_party/openmetadata/src"; exit 1; }

if [[ $TARGET == server || $TARGET == all ]]; then
  COMMIT=$(git -C src rev-parse HEAD)
  docker build -f build/Dockerfile.server --build-arg SOURCE_COMMIT="$COMMIT" \
    -t "$REGISTRY/openmetadata-server:$VERSION" .
fi
if [[ $TARGET == fuseki || $TARGET == all ]]; then
  # OM 的 RDF 存储：上游 docker/rdf-store（Jena Fuseki + OM 扩展），版本跟随其中的 FUSEKI_VERSION
  FUSEKI=$(awk -F= '/^ENV FUSEKI_VERSION=/{print $2}' src/docker/rdf-store/Dockerfile)
  docker build -t "$REGISTRY/openmetadata-fuseki:$FUSEKI-ctx.0" src/docker/rdf-store
fi
if [[ $TARGET == ingestion || $TARGET == all ]]; then
  # 采集镜像直接使用上游 Dockerfile（构建上下文为子仓库根目录）
  docker build -f src/ingestion/operators/docker/Dockerfile -t "$REGISTRY/openmetadata-ingestion:$VERSION" src
fi
