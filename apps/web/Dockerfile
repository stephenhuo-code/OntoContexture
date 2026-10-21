# 织境 Web：构建产物由 nginx（非 root）提供。构建上下文为仓库根目录：
#   docker build -f apps/web/Dockerfile -t contexture/web:dev .
FROM node:22-alpine AS build
RUN corepack enable
WORKDIR /src
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages/ts-api packages/ts-api
COPY apps/web apps/web
RUN pnpm install --frozen-lockfile --filter @contexture/web... \
 && pnpm --filter @contexture/web build

FROM nginxinc/nginx-unprivileged:1.31.7-alpine
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/apps/web/dist /usr/share/nginx/html
EXPOSE 8080
