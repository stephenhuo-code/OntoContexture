#!/usr/bin/env bash
# make cloud-tools：按 tools/cloud/tools.lock 把开发机工具装到 ~/.local/bin（持久卷，无需 root；030 FR-031、R15、R18）。
# 已安装且版本一致的跳过；SHA256 不符时拒绝安装。
set -euo pipefail
LOCK=${CTX_TOOLS_LOCK:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tools.lock}
BIN="$HOME/.local/bin"
STATE="$HOME/.local/share/contexture/tools.installed"

missing=()
for cmd in git curl openssl tar sha256sum; do command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd"); done
if [[ ${#missing[@]} -gt 0 ]]; then
  echo "开发机缺少基础命令：${missing[*]}（devbox 镜像应自带；请先安装）" >&2
  exit 2
fi

mkdir -p "$BIN" "$(dirname "$STATE")"; touch "$STATE"
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
failed=0

while read -r name version _license _published url sha member; do
  [[ -z $name || $name == \#* ]] && continue
  if [[ -x $BIN/$name ]] && grep -qx "$name $version" "$STATE"; then
    echo "$name $version 已安装"; continue
  fi
  curl -fsSL -o "$work/$name.dl" "$url"
  if [[ $(sha256sum "$work/$name.dl" | cut -d' ' -f1) != "$sha" ]]; then
    echo "$name $version 的 SHA256 与锁文件不符，拒绝安装" >&2
    failed=1; continue
  fi
  if [[ $member == - ]]; then
    src="$work/$name.dl"
  else
    mkdir -p "$work/$name"; tar xzf "$work/$name.dl" -C "$work/$name" "$member"
    src="$work/$name/$member"
  fi
  install -m 755 "$src" "$BIN/$name"
  grep -v "^$name " "$STATE" > "$STATE.tmp" || true
  echo "$name $version" >> "$STATE.tmp"; mv "$STATE.tmp" "$STATE"
  echo "$name $version 已安装（校验通过）"
done < <(grep -vE '^\s*(#|$)' "$LOCK")

case ":$PATH:" in *":$BIN:"*) ;; *) echo "提示：把 $BIN 加入 PATH（~/.bashrc）";; esac
exit $failed
