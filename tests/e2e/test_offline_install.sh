#!/usr/bin/env bash
# 离线安装验收（T042，SC-005）：新建 kind 集群并禁止节点访问外网，只用离线包安装全部组件，冒烟测试全部通过。
# 前置：make offline-package 已生成 deploy/offline/dist/；本机 kind 集群 contexture 需先停止以释放端口与内存
#   （docker stop contexture-control-plane contexture-worker contexture-worker2），验收后再 docker start。
set -euo pipefail
cd "$(dirname "$0")/../.."
DIST=deploy/offline/dist
CLUSTER=contexture-offline
compgen -G "$DIST/images/*.tar" >/dev/null || { echo "缺少离线包，先执行 make offline-package"; exit 1; }

kind create cluster --name "$CLUSTER" --config deploy/kind/cluster.yaml
trap 'kind delete cluster --name "$CLUSTER"' EXIT
# 断开集群节点的外网：只允许集群内部、宿主机（Keycloak 经宿主机网关）与 Docker 网段
for node in $(kind get nodes --name "$CLUSTER"); do
  docker exec "$node" sh -c '
    iptables -I OUTPUT 1 -d 10.0.0.0/8 -j ACCEPT
    iptables -I OUTPUT 1 -d 172.16.0.0/12 -j ACCEPT
    iptables -I OUTPUT 1 -d 192.168.0.0/16 -j ACCEPT
    iptables -I OUTPUT 1 -d 127.0.0.0/8 -j ACCEPT
    iptables -A OUTPUT -o eth0 -j REJECT
    iptables -I FORWARD 1 -d 10.0.0.0/8 -j ACCEPT
    iptables -I FORWARD 1 -d 172.16.0.0/12 -j ACCEPT
    iptables -I FORWARD 1 -d 192.168.0.0/16 -j ACCEPT
    iptables -A FORWARD -o eth0 -j REJECT
    # kind 节点有 IPv6 出口：只放行集群内部的 fc00::/7
    ip6tables -A OUTPUT -o eth0 ! -d fc00::/7 -j REJECT
    ip6tables -A FORWARD -o eth0 ! -d fc00::/7 -j REJECT'
done
# 确认已断网：节点无法访问 Docker Hub
if docker exec "$CLUSTER-control-plane" curl -s -m 5 -o /dev/null https://registry-1.docker.io/v2/; then
  echo "断网未生效"; exit 1
fi
echo "==> 集群已断网"

CTX_KIND_CLUSTER=$CLUSTER deploy/offline/install.sh "$DIST"
echo "离线安装验收通过"
