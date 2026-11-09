# 织境常用命令。标注 TODO 的目标由后续任务实现。
.PHONY: test lint up down seed e2e e2e-mock-data coverage-check ports components-check patches-check offline-package mock-data dev-metadata dev-metadata-remove

test:
	uv run pytest --cov --cov-report=term-missing --cov-report=json:coverage.json

DIFF_BASE ?= HEAD
coverage-check:
	uv run python -m tools.coverage_gate --base $(DIFF_BASE) --python coverage.json --lcov apps/web/coverage/lcov.info --lcov packages/ui/coverage/lcov.info

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

# 006 开发态元数据导入：把 003 表定义作为开发态测试元数据写入本地集群的 OM（可重复执行，幂等）
# 凭证取自 .env.local 的 provisioner 客户端；临时端口转发到 18585，不占用 make ports 的 8585
DEV_OM_PORT ?= 18585
define dev_metadata
	set -a; . ./.env.local; set +a; SSL_CERT_FILE=$$(mktemp) && docker exec paperclip-caddy-1 cat /data/caddy/pki/authorities/local/root.crt > $$SSL_CERT_FILE && export SSL_CERT_FILE; \
	kubectl --context kind-contexture -n contexture port-forward svc/openmetadata $(DEV_OM_PORT):8585 >/dev/null 2>&1 & PF=$$!; trap "kill $$PF" EXIT; sleep 3; \
	uv run python -m mockfactory om-import --target local --om-url http://localhost:$(DEV_OM_PORT) $(1)
endef
dev-metadata:
	$(call dev_metadata,)

dev-metadata-remove:
	$(call dev_metadata,--remove)

# 模拟工厂数据（003）：按需部署模拟 MES、QMS（make up 不部署它们；可重复执行），再生成并写入三套模拟系统，最后核对 3 个案例
MONTHS ?= 12
SEED ?= 20261001
mock-data:
	KUBE_CONTEXT=kind-contexture testdata/deploy/secrets.sh
	helmfile --kube-context kind-contexture -f deploy/helmfile.yaml.gotmpl -e $(ENV) -l group=mock-sources sync --skip-deps
	for t in testdata/deploy/*/tests/smoke.sh; do $$t || exit 1; done
	uv run python -m mockfactory load --target local --months $(MONTHS) --seed $(SEED)
	uv run python -m mockfactory verify-cases --target local
	uv run python -m mockfactory provision-005

# 端到端（需 make up、make seed）：集群测试（Toolbox、AI 网关、追踪与审计）+ 浏览器演示
KUBE_CONTEXT ?= kind-contexture
e2e:
	@set -eu; ctx_e2e_tmp=$$(mktemp -d); trap 'rm -rf "$$ctx_e2e_tmp"' EXIT; \
	  kubectl --context "$(KUBE_CONTEXT)" config view --minify --flatten --raw > "$$ctx_e2e_tmp/config"; \
	  chmod 600 "$$ctx_e2e_tmp/config"; export KUBECONFIG="$$ctx_e2e_tmp/config"; \
	  uv run pytest -m cluster -o addopts="--import-mode=importlib" deploy/components tests/e2e; \
	  ctx_wrong_audience=$$(PYTHONPATH=tests uv run python tests/e2e/wrong_audience_token.py); \
	  CTX_WRONG_AUDIENCE_TOKEN="$$ctx_wrong_audience" pnpm e2e:browser; \
	  pnpm e2e:ui

# 003 专项回归会重建 MES / QMS / mock_dw，须明确选择；普通 e2e 不运行。
e2e-mock-data:
	uv run pytest -m cluster -o addopts="--import-mode=importlib" testdata/tests/cluster

# 把各组件界面转发到本机（手动验收用）
ports:
	tools/ports.sh

components-check:
	uv run python -m tools.components_check
	uv run python -m tools.keycloak_theme --check

patches-check:
	uv run python -m tools.patches_check

offline-package:
	uv run python -m tools.offline_package
