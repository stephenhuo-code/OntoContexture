# 织境常用命令。标注 TODO 的目标由后续任务实现。
.PHONY: test lint up down seed e2e ports components-check patches-check offline-package mock-data

test:
	uv run pytest --cov --cov-report=term-missing

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright
	pnpm lint

# 环境：local（默认）或 lite（降低资源），如 make up ENV=lite
ENV ?= local

up:
	tools/up.sh up $(ENV)

down:
	tools/up.sh down

seed:
	set -a; . ./.env.local; set +a; SSL_CERT_FILE=$$(mktemp) && docker exec paperclip-caddy-1 cat /data/caddy/pki/authorities/local/root.crt > $$SSL_CERT_FILE && SSL_CERT_FILE=$$SSL_CERT_FILE uv run python -m tools.seed

# 模拟工厂数据（003）：按需部署模拟 MES、QMS（make up 不部署它们；可重复执行），再生成并写入三套模拟系统，最后核对 3 个案例
MONTHS ?= 12
SEED ?= 20261001
mock-data:
	KUBE_CONTEXT=kind-contexture testdata/deploy/secrets.sh
	helmfile --kube-context kind-contexture -f deploy/helmfile.yaml.gotmpl -e $(ENV) -l group=mock-sources sync --skip-deps
	for t in testdata/deploy/*/tests/smoke.sh; do $$t || exit 1; done
	uv run python -m mockfactory load --target local --months $(MONTHS) --seed $(SEED)
	uv run python -m mockfactory verify-cases --target local

# 端到端（需 make up、make seed）：集群测试（Toolbox、AI 网关、追踪与审计）+ 浏览器演示
e2e:
	uv run pytest -m cluster -o addopts="--import-mode=importlib" deploy/components tests/e2e testdata/tests/cluster
	CTX_WRONG_AUDIENCE_TOKEN=$$(PYTHONPATH=tests uv run python tests/e2e/wrong_audience_token.py) pnpm e2e:browser

# 把各组件界面转发到本机（手动验收用）
ports:
	tools/ports.sh

components-check:
	uv run python -m tools.components_check

patches-check:
	uv run python -m tools.patches_check

offline-package:
	uv run python -m tools.offline_package
