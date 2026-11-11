#!/usr/bin/env bash
# 集群内工具箱（030 research R12）：按次创建一次性 Pod（主容器 + docker:dind 边车），上传开发机工作区（含未提交改动，
# 不含忽略文件与凭证文件），kubectl exec 运行命令并透传输出与退出码，结束或中断时删除 Pod（FR-015～FR-017、R18）。
CTX_TOOLBOX_NS=contexture-ci
CTX_TOOLBOX_POD=contexture-toolbox
CTX_DIND_IMAGE=docker:29.9.1-dind

ctx_toolbox_image() {  # 优先用 cloud-build --toolbox 记录的镜像，否则按 Dockerfile 与工具锁文件计算标签
  local recorded; recorded=$(ctx_state_get toolboxImage 2>/dev/null || true)
  if [[ -n $recorded ]]; then printf '%s' "$recorded"; return; fi
  printf '%s/toolbox:%s' "$CTX_CLOUD_REGISTRY" \
    "$(ctx_tag_lock toolbox "$CTX_REPO_ROOT/deploy/components/ci-toolbox/Dockerfile" "$CTX_REPO_ROOT/tools/cloud/tools.lock")"
}

ctx_toolbox_manifest() {
  jq -cn --arg name "$CTX_TOOLBOX_POD" --arg image "$(ctx_toolbox_image)" --arg dind "$CTX_DIND_IMAGE" \
    --arg nodekey "$CTX_CLOUD_NODE_LABEL" --arg pool "$CTX_CLOUD_NODE_POOL" '{
    apiVersion: "v1", kind: "Pod",
    metadata: {name: $name, labels: {"app.kubernetes.io/name": "contexture-toolbox"}},
    spec: {
      serviceAccountName: "toolbox", restartPolicy: "Never",
      nodeSelector: {($nodekey): $pool},
      imagePullSecrets: [{name: "docr-pull"}],
      containers: [
        {name: "toolbox", image: $image, command: ["sleep", "infinity"],
         envFrom: [{secretRef: {name: "toolbox-env"}}],
         resources: {requests: {cpu: "1", memory: "2Gi"}, limits: {memory: "6Gi"}},
         volumeMounts: [{name: "cache", mountPath: "/cache"}, {name: "workspace", mountPath: "/workspace"}]},
        {name: "dind", image: $dind, securityContext: {privileged: true},
         env: [{name: "DOCKER_TLS_CERTDIR", value: ""}],
         args: ["--host=tcp://0.0.0.0:2375"],
         resources: {requests: {cpu: "500m", memory: "1Gi"}, limits: {memory: "4Gi"}},
         # 工作区以相同路径挂入：Testcontainers 的绑定挂载由 dind 中的守护进程解析（T068 实测）
         volumeMounts: [{name: "cache", mountPath: "/var/lib/docker", subPath: "docker"}, {name: "workspace", mountPath: "/workspace"}]}
      ],
      volumes: [{name: "cache", persistentVolumeClaim: {claimName: "toolbox-cache"}}, {name: "workspace", emptyDir: {}}]
    }}'
}

ctx_toolbox_cleanup() {
  ctx_kubectl -n "$CTX_TOOLBOX_NS" delete pod "$CTX_TOOLBOX_POD" --ignore-not-found --wait=false >/dev/null 2>&1 || true
}

ctx_toolbox_upload() {  # 只上传 git 跟踪与未忽略的文件（另附 .git 供变更覆盖率计算），并再次排除 .env 类凭证文件
  { git -C "$CTX_REPO_ROOT" ls-files -z -co --exclude-standard; printf '.git\0'; } |
    grep -zvE '(^|/)\.env(\.[A-Za-z0-9_-]+)?$' |
    tar -C "$CTX_REPO_ROOT" --null -T - -czf - |
    ctx_kubectl -n "$CTX_TOOLBOX_NS" exec -i "$CTX_TOOLBOX_POD" -c toolbox -- tar xzf - -C /workspace
}

# ctx_toolbox_run <命令>：在工具箱中于 /workspace 执行；CTX_KCOV=1 时取回 bash 覆盖率到 CTX_KCOV_OUT
ctx_toolbox_run() {
  local cmd=$1 status=0
  ctx_kubectl -n "$CTX_TOOLBOX_NS" delete pod "$CTX_TOOLBOX_POD" --ignore-not-found --wait=true >/dev/null 2>&1 || true
  trap 'ctx_toolbox_cleanup; exit 130' INT TERM
  ctx_toolbox_manifest | ctx_kubectl -n "$CTX_TOOLBOX_NS" apply -f - >/dev/null
  ctx_kubectl -n "$CTX_TOOLBOX_NS" wait "pod/$CTX_TOOLBOX_POD" --for=condition=Ready --timeout=900s >/dev/null
  ctx_toolbox_upload
  ctx_kubectl -n "$CTX_TOOLBOX_NS" exec "$CTX_TOOLBOX_POD" -c toolbox -- bash -lc "cd /workspace && $cmd" || status=$?
  if [[ -n ${CTX_KCOV:-} ]]; then
    local out=${CTX_KCOV_OUT:-$CTX_REPO_ROOT/coverage/bash/cobertura.xml}
    mkdir -p "$(dirname "$out")"
    ctx_kubectl -n "$CTX_TOOLBOX_NS" exec "$CTX_TOOLBOX_POD" -c toolbox -- cat /workspace/coverage/bash/cobertura.xml > "$out" || true
  fi
  trap - INT TERM
  ctx_toolbox_cleanup
  return $status
}
