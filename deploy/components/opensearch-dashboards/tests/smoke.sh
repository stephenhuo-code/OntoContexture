#!/usr/bin/env bash
# 冒烟测试：Dashboards 就绪；OpenSearch 中有服务日志索引
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
kubectl -n "$NS" rollout status deployment/opensearch-dashboards --timeout=300s
curl_in -sf http://opensearch-dashboards:5601/api/status | grep -q '"state":"green"\|"level":"available"'
curl_in -sf 'http://opensearch-cluster-master:9200/_cat/indices/ctx-logs*?h=index,docs.count' | grep -q ctx-logs \
  && echo "opensearch-dashboards OK"
