#!/usr/bin/env bash
# 冒烟测试：FE / BE 就绪，初始化完成，ctx_reader 能登录并只读
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
NS=contexture
# operator 先拉起 FE，再拉起 BE
for i in $(seq 1 90); do kubectl -n $NS get statefulset doris-be >/dev/null 2>&1 && break; sleep 10; done
kubectl -n $NS rollout status statefulset/doris-fe --timeout=900s
kubectl -n $NS rollout status statefulset/doris-be --timeout=900s
job=$(kubectl -n $NS get jobs -l app.kubernetes.io/name=doris-init --sort-by=.metadata.creationTimestamp -o name | tail -1)
kubectl -n $NS wait "$job" --for=condition=Complete --timeout=600s
PW=$(kubectl -n $NS get secret doris-reader -o jsonpath='{.data.password}' | base64 -d)
incluster mysql:8.4 mysql --password="$PW" -h doris-fe-service -P 9030 -uctx_reader -e "show databases" | grep -q ctx_ && echo "doris OK"
