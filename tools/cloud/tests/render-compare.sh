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
  for bad in localhost 127.0.0.1.nip.io ctx-trusted-ca NodePort; do
    if grep -q "$bad" "$tmp/cloud.yaml"; then report "cloud 渲染中出现 $bad"; grep -n "$bad" "$tmp/cloud.yaml" | head -5; fi
  done
  [[ $failed == 0 ]] && printf '  ✔ cloud 渲染无本地地址\n'
fi
cp "$tmp/cloud.yaml" "${CTX_RENDER_OUT:-$tmp}/cloud.rendered.yaml" 2>/dev/null || true

# 3. 脚本与通用模板中无云厂商专用值（各组件 values/cloud.yaml、.env.cloud.example、tools.lock 除外）
leaks=$(grep -rnIE 'digitalocean|do-block-storage|doks\.' tools/cloud deploy/cloud deploy/components/*/values/base.yaml \
  deploy/components/*/config deploy/components/*/chart deploy/charts 2>/dev/null |
  grep -vE '^tools/cloud/(tools\.lock|tests/)' || true)
if [[ -n $leaks ]]; then report "通用模板或脚本中出现云厂商专用值："; echo "$leaks" | head -10; else printf '  ✔ 无云厂商专用值泄漏\n'; fi

exit $failed
