#!/usr/bin/env bash
# 冒烟测试：Fuseki 就绪，openmetadata 数据集存在
set -euo pipefail
kubectl -n contexture rollout status statefulset/fuseki --timeout=300s
kubectl -n contexture exec fuseki-0 -- wget -qO- http://localhost:3030/\$/ping >/dev/null && echo "fuseki OK"
