# deploy/kind/

本地 kind 集群（Kubernetes in Docker）配置。`make up` 会按下面的步骤自动完成（T056），这里记录原理便于排错。

## 文件

- `cluster.yaml`：1 控制面 + 2 工作节点；织境入口映射到宿主机 8080 / 8443（80 / 443 已被 Paperclip 的 Caddy 占用）。
- `coredns-hosts.yaml`：把 `sso.127.0.0.1.nip.io` 解析到宿主机，集群内的服务才能访问负责人本机的 Keycloak。

## 接入本机 Keycloak

本机 Keycloak 位于 Paperclip 的 Caddy 之后，证书由 Caddy 本地 CA 签发。集群内服务需要信任这个 CA：

```bash
kind create cluster --config deploy/kind/cluster.yaml

# 1. 集群内解析 Keycloak 域名到宿主机
HOST_IP=$(docker run --rm --network kind alpine getent ahostsv4 host.docker.internal | awk 'NR==1{print $1}')
sed "s/HOST_GATEWAY_IP/${HOST_IP}/" deploy/kind/coredns-hosts.yaml | kubectl apply -f -
kubectl -n kube-system rollout restart deployment coredns

# 2. 导出 Caddy 根证书并以 Secret ctx-trusted-ca 注入
docker exec paperclip-caddy-1 cat /data/caddy/pki/authorities/local/root.crt > /tmp/caddy-root.crt
kubectl create namespace contexture
kubectl -n contexture create secret generic ctx-trusted-ca --from-file=ca.crt=/tmp/caddy-root.crt
```

各服务把 `ctx-trusted-ca` 挂载为受信 CA（Python 服务通过 `SSL_CERT_FILE`）。
