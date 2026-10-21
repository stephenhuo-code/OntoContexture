# 织境 bff 镜像：多阶段构建，运行时非 root、只读根文件系统（写入只发生在 /tmp）。
# 构建上下文为仓库根目录：docker build -f services/bff/Dockerfile .
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/py-core packages/py-core
COPY services/bff services/bff
COPY tools/pyproject.toml tools/pyproject.toml
RUN uv sync --frozen --no-dev --package contexture-bff --no-editable

FROM python:3.12-slim-bookworm
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY services/bff/migrations /app/migrations
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    CTX_BFF_MIGRATIONS=/app/migrations
USER 10001:10001
EXPOSE 8080
CMD ["python", "-c", "from contexture_bff.main import run; run()"]
