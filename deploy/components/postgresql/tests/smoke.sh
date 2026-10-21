#!/usr/bin/env bash
# 冒烟测试：集群就绪，各 database 已创建
set -euo pipefail
kubectl -n contexture wait cluster/pg --for=condition=Ready --timeout=300s
kubectl -n contexture wait databases.postgresql.cnpg.io --all --for=jsonpath='{.status.applied}'=true --timeout=120s
for db in $(kubectl -n contexture get databases.postgresql.cnpg.io -o jsonpath='{.items[*].spec.name}'); do
  kubectl -n contexture exec pg-1 -c postgres -- psql -tAc "select 1" "$db" >/dev/null
  echo "database $db OK"
done
