# 织境 Web：构建产物由 nginx（非 root）提供。构建上下文为仓库根目录：
#   docker build -f apps/web/Dockerfile -t contexture/web:dev .
# 此阶段保留冻结安装的 npm 包及许可，CI 单独生成前端依赖 SBOM。
# 最终 nginx 镜像只有静态文件，单扫最终镜像会漏掉 React 等已打包依赖。
FROM node:22.23.4-alpine AS frontend-dependencies
RUN apk upgrade --no-cache && corepack enable
WORKDIR /src
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages/ts-api/package.json packages/ts-api/package.json
COPY packages/ui/package.json packages/ui/package.json
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile --filter @contexture/web...
# Node 22 自带 npm 10 的 tar 7.5.11 已被安全门禁阻断；固定到已修复版本。
RUN npm install --global npm@12.2.1

# 云端开发模式（030 make cloud-dev）：Vite 开发服务器，源码由 DevSpace 同步进来；非末尾阶段，默认构建目标不变
FROM frontend-dependencies AS dev
COPY packages/ts-api packages/ts-api
COPY packages/ui packages/ui
COPY apps/web apps/web
EXPOSE 8080
CMD ["pnpm", "--filter", "@contexture/web", "exec", "vite", "--host", "0.0.0.0", "--port", "8080", "--strictPort"]

FROM frontend-dependencies AS build
COPY packages/ts-api packages/ts-api
COPY packages/ui packages/ui
COPY apps/web apps/web
RUN pnpm --filter @contexture/web build

FROM nginxinc/nginx-unprivileged:1.31.7-alpine
# 更新发行版已修复的系统库；运行阶段恢复非 root。
USER root
RUN apk upgrade --no-cache
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/apps/web/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
