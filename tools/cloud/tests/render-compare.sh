#!/usr/bin/env bash
# 渲染对比测试（030 T014；SC-007、FR-021、R19）：
#   1. helmfile -e local / lite 的渲染结果与 baseline/ 逐字节一致（Secret 的值先遮掉：部分上游 Chart 每次随机生成）
#   2. -e cloud 的渲染结果中不出现本地地址与本地专用设施
#   3. 脚本与通用模板中不出现云厂商（DigitalOcean）专用值
# 用法：tools/cloud/tests/render-compare.sh [--update]（--update 重写基线，只能在确认本地渲染应当变化时使用）
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
cd "$ROOT"
failed=0
report() { printf '  ✘ %s\n' "$*"; failed=1; }

render() {  # render <环境>：排除模拟源系统，遮掉 Secret 的值
  helmfile -f deploy/helmfile.yaml.gotmpl -e "$1" -l 'group!=mock-sources' template --skip-tests 2>/dev/null |
    awk '
      /^---$/ { flush(); print; next }
      { doc[++n] = $0; if ($0 == "kind: Secret") secret = 1 }
      function flush(  i, line) {
        for (i = 1; i <= n; i++) {
          line = doc[i]
          if (secret && line ~ /^  [^ #][^:]*: .+$/ && line !~ /^  (name|namespace|labels|annotations):/)
            sub(/: .+$/, ": <masked>", line)
          print line
        }
        n = 0; secret = 0
      }
      END { flush() }'
}

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

# 云端渲染的结构断言（030 T040：FR-006～FR-009、FR-021、FR-024、FR-027、R7、R19）
cloud_assertions() {
  local file=$1 before=$failed
  failed=0
  # 逐个文档检查：Pod 模板都带弹性池 nodeSelector；PVC 都用配置的存储类；自建镜像来自配置的仓库
  awk -v label="$CTX_CLOUD_NODE_LABEL" -v pool="$CTX_CLOUD_NODE_POOL" -v sc="$CTX_CLOUD_STORAGE_CLASS" -v reg="$CTX_CLOUD_REGISTRY" '
    function check() {
      if (doc == "") return
      # 已知例外：Langfuse 的 SeaweedFS 建桶钩子（上游 Chart 无 nodeSelector 参数，短时任务，research R7 实施记录）
      if (src ~ /s3\/templates\/shared\/post-install-bucket-hook/) { } else
      if (doc ~ /\n(kind: (Deployment|StatefulSet|DaemonSet|Job|CronJob)|  kind: (Deployment|StatefulSet))\n/ && index(doc, label ": " pool) == 0 && index(doc, label ": \"" pool "\"") == 0)
        printf "  ✘ 缺少弹性池 nodeSelector：%s\n", src
      if (doc ~ /\nkind: PersistentVolumeClaim\n/ && index(doc, "storageClassName: " sc) == 0 && index(doc, "storageClassName: \"" sc "\"") == 0)
        printf "  ✘ PVC 未使用存储类 %s：%s\n", sc, src
      if (match(doc, /image: "?contexture\/[a-z-]+/))
        printf "  ✘ 自建镜像未改为仓库 %s：%s\n", reg, src
    }
    /^---$/ { check(); doc = ""; src = ""; next }
    /^# Source: / { src = substr($0, 11) }
    { doc = doc "\n" $0 }
    END { check() }' "$file" > "$tmp/struct.txt"
  if [[ -s $tmp/struct.txt ]]; then failed=1; sort -u "$tmp/struct.txt" | head -40; fi
  local expect
  for expect in "https://sso.$CTX_CLOUD_DOMAIN" "https://$CTX_CLOUD_DOMAIN" "$CTX_CLOUD_REGISTRY/bff:" \
    "$CTX_CLOUD_REGISTRY/web:" "docr-pull" "test-users.yaml" "realms/digital-workforce" \
    "00-realm.yaml"; do  # 自带 Keycloak 时启用 realm（T052 实测：新建的 realm 默认未启用，令牌端点返回 Realm not enabled）
    grep -qF -- "$expect" "$file" || report "cloud 渲染中缺少 $expect"
  done
  # Airflow 共用 RWO 卷须同节点：以必需反亲和独占一个节点，避免与其他组件争内存（T052 实测：调度器落在满载节点，其余 Pod 无法调度）
  # 只用 awk 判断：grep -q 提前退出会让 awk 收到 SIGPIPE，在 pipefail 下误报
  awk '/^# Source: airflow\/templates\/scheduler\/scheduler-deployment/{f=1} /^---$/{f=0}
    f && /podAntiAffinity/{found=1} END{exit !found}' "$file" ||
    report "Airflow 调度器缺少独占节点的 podAntiAffinity"
  [[ $failed == 0 ]] && printf '  ✔ cloud 渲染结构断言通过\n'
  [[ $before == 0 ]] || failed=1
}

# 1. 本地渲染不变
for env in local lite; do
  render "$env" > "$tmp/$env.yaml"
  if [[ ${1:-} == --update ]]; then
    cp "$tmp/$env.yaml" "$HERE/baseline/$env.yaml"; echo "  已更新基线 $env"
  elif ! diff -q "$HERE/baseline/$env.yaml" "$tmp/$env.yaml" >/dev/null; then
    report "$env 渲染与基线不一致："; diff "$HERE/baseline/$env.yaml" "$tmp/$env.yaml" | head -40
  else
    printf '  ✔ %s 渲染与基线一致\n' "$env"
  fi
done

# 2. 云端渲染：无本地地址与本地专用设施
set -a; source "$HERE/fixtures/env.cloud"; set +a
if ! render cloud > "$tmp/cloud.yaml" || [[ ! -s $tmp/cloud.yaml ]]; then
  report "cloud 环境无法渲染"
else
  # 只看实际配置：去掉 CRD（其说明文字含 localhost / NodePort 等词）与注释行
  awk '/^---$/ { if (!crd) printf "%s", doc; doc = ""; crd = 0 } /^kind: CustomResourceDefinition$/ { crd = 1 }
       !/^\s*#/ { doc = doc $0 "\n" } END { if (!crd) printf "%s", doc }' "$tmp/cloud.yaml" > "$tmp/cloud-config.yaml"
  for bad in localhost 127.0.0.1.nip.io ctx-trusted-ca NodePort; do
    if grep -q "$bad" "$tmp/cloud-config.yaml"; then report "cloud 渲染中出现 $bad"; grep -n "$bad" "$tmp/cloud-config.yaml" | head -5; fi
  done
  [[ $failed == 0 ]] && printf '  ✔ cloud 渲染无本地地址\n'
  cloud_assertions "$tmp/cloud.yaml"
fi
cp "$tmp/cloud.yaml" "${CTX_RENDER_OUT:-$tmp}/cloud.rendered.yaml" 2>/dev/null || true

# 3. 脚本与通用模板中无云厂商专用值（各组件 values/cloud.yaml、.env.cloud.example、tools.lock 除外）
leaks=$(grep -rnIE 'digitalocean|do-block-storage|doks\.' tools/cloud deploy/cloud deploy/components/*/values/base.yaml \
  deploy/components/*/config deploy/components/*/chart deploy/charts 2>/dev/null |
  grep -vE '^tools/cloud/(tools\.lock|tests/)' || true)
if [[ -n $leaks ]]; then report "通用模板或脚本中出现云厂商专用值："; echo "$leaks" | head -10; else printf '  ✔ 无云厂商专用值泄漏\n'; fi

exit $failed
