#!/usr/bin/env bash
# 冒烟测试：集群健康为 green 或 yellow（单节点）
set -euo pipefail
kubectl -n contexture rollout status statefulset/opensearch-cluster-master --timeout=300s
kubectl -n contexture exec opensearch-cluster-master-0 -- \
  curl -s "http://localhost:9200/_cluster/health?wait_for_status=yellow&timeout=60s" | grep -E '"status":"(green|yellow)"'
