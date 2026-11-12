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
  jq -cn --arg owner "$(hostname)/$$" --arg name "$CTX_TOOLBOX_POD" --arg image "$(ctx_toolbox_image)" --arg dind "$CTX_DIND_IMAGE" \
    --arg nodekey "$CTX_CLOUD_NODE_LABEL" --arg pool "$CTX_CLOUD_NODE_POOL" --arg airflowns "$CTX_CLOUD_NAMESPACE" '{
    apiVersion: "v1", kind: "Pod",
    metadata: {name: $name, labels: {"app.kubernetes.io/name": "contexture-toolbox"},
      annotations: {"contexture.io/owner": $owner}},
    spec: {
      serviceAccountName: "toolbox", restartPolicy: "Never",
      nodeSelector: {($nodekey): $pool},
      # 避开 Airflow 独占的节点（T068 实测：工具箱落在该节点后采集任务 Pod 无法调度）；Airflow 的反亲和只作用于其 namespace
      affinity: {podAntiAffinity: {requiredDuringSchedulingIgnoredDuringExecution: [
        {labelSelector: {matchLabels: {release: "airflow"}}, namespaces: [$airflowns], topologyKey: "kubernetes.io/hostname"}]}},
      imagePullSecrets: [{name: "docr-pull"}],
      containers: [
        {name: "toolbox", image: $image, command: ["sleep", "infinity"],
         envFrom: [{secretRef: {name: "toolbox-env"}}],
         resources: {requests: {cpu: "1", memory: "2Gi"}, limits: {memory: "6Gi"}},
         volumeMounts: [{name: "cache", mountPath: "/cache"}, {name: "workspace", mountPath: "/workspace"}, {name: "tmp", mountPath: "/tmp"}]},
        {name: "dind", image: $dind, securityContext: {privileged: true},
         env: [{name: "DOCKER_TLS_CERTDIR", value: ""}],
         args: ["--host=tcp://0.0.0.0:2375"],
         resources: {requests: {cpu: "500m", memory: "1Gi"}, limits: {memory: "4Gi"}},
         # 工作区与 /tmp 以相同路径挂入：Testcontainers 的绑定挂载由 dind 中的守护进程解析（T068 实测）
         volumeMounts: [{name: "cache", mountPath: "/var/lib/docker", subPath: "docker"}, {name: "workspace", mountPath: "/workspace"}, {name: "tmp", mountPath: "/tmp"}]}
      ],
      volumes: [{name: "cache", persistentVolumeClaim: {claimName: "toolbox-cache"}}, {name: "workspace", emptyDir: {}}, {name: "tmp", emptyDir: {}}]
    }}'
}

ctx_toolbox_cleanup() {
  ctx_kubectl -n "$CTX_TOOLBOX_NS" delete pod "$CTX_TOOLBOX_POD" --ignore-not-found --wait=false >/dev/null 2>&1 || true
}

ctx_toolbox_upload() {  # 只上传 git 跟踪与未忽略的文件（另附 .git 供变更覆盖率计算），并再次排除 .env 类凭证文件
  # 子模块在列表中是目录，tar 会递归上传其全部内容（含 .env.example）；只保留空目录，与未初始化子模块时一致
  local excludes=() path
  while read -r _ path; do excludes+=(--exclude="$path/*"); done < <(git -C "$CTX_REPO_ROOT" config -f .gitmodules --get-regexp '\.path$' 2>/dev/null)
  { git -C "$CTX_REPO_ROOT" ls-files -z -co --exclude-standard; printf '.git\0'; } |
    grep -zvE '(^|/)\.env(\.[A-Za-z0-9_-]+)?$' |
    tar -C "$CTX_REPO_ROOT" "${excludes[@]}" --null -T - -czf - |
    ctx_kubectl -n "$CTX_TOOLBOX_NS" exec -i "$CTX_TOOLBOX_POD" -c toolbox -- tar xzf - -C /workspace
}

# ctx_toolbox_run <命令>：在工具箱中于 /workspace 执行；CTX_KCOV=1 时取回 bash 覆盖率到 CTX_KCOV_OUT
ctx_toolbox_run() {
  local cmd=$1 status=0
  # 互斥（T068 实测）：发起进程仍在运行（或来自另一台开发机）时拒绝；发起进程已退出的残留 Pod 才清理
  local owner
  owner=$(ctx_kubectl -n "$CTX_TOOLBOX_NS" get pod "$CTX_TOOLBOX_POD" --ignore-not-found \
    -o jsonpath='{.metadata.annotations.contexture\.io/owner}' 2>/dev/null) || owner=
  if [[ -n $owner ]] && { [[ ${owner%/*} != "$(hostname)" ]] || kill -0 "${owner##*/}" 2>/dev/null; }; then
    ctx_die "$CTX_EXIT_CONFIG" "另一个工具箱命令正在运行（$owner），请等它结束后再执行"
  fi
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
