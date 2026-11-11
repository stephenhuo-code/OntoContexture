# 织境 CI 工具箱（030 research R12）：在集群内对开发机工作区运行 lint / 测试 / e2e / seed；不进入任何交付物。
# 构建：make cloud-build TARGET=toolbox（集群内 BuildKit，上下文为仓库根目录）。
# 版本与仓库锁定一致：Node 22.23.4 + pnpm（package.json packageManager）、uv 0.12.0 + Python 3.12、Playwright 1.64.1；
# kcov（GPL-2.0，许可白名单例外，仅统计 bash 覆盖率）来自 Debian trixie。
FROM node:22.23.4-trixie-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /uvx /usr/local/bin/
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates curl git jq kcov make openssl tar \
    && rm -rf /var/lib/apt/lists/*
# kubectl / helm / helmfile：与开发机相同的锁文件与校验
COPY tools/cloud/tools.lock tools/cloud/install-tools.sh /opt/ctx-tools/
RUN HOME=/opt/ctx-tools-home /opt/ctx-tools/install-tools.sh \
    && mv /opt/ctx-tools-home/.local/bin/* /usr/local/bin/ && rm -rf /opt/ctx-tools-home
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python UV_LINK_MODE=copy UV_CACHE_DIR=/cache/uv \
    PNPM_HOME=/cache/pnpm-home npm_config_store_dir=/cache/pnpm-store \
    PLAYWRIGHT_BROWSERS_PATH=/cache/ms-playwright \
    DOCKER_HOST=tcp://localhost:2375 TESTCONTAINERS_HOST_OVERRIDE=localhost TESTCONTAINERS_RYUK_DISABLED=true
RUN uv python install 3.12 && corepack enable && corepack prepare pnpm@11.20.0 --activate \
    && npx --yes playwright@1.64.1 install-deps chromium && rm -rf /var/lib/apt/lists/* /root/.npm
WORKDIR /workspace
CMD ["sleep", "infinity"]
