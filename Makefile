# 织境常用命令。标注 TODO 的目标由后续任务实现。
.PHONY: test lint up down seed e2e components-check patches-check offline-package

test:
	uv run pytest --cov --cov-report=term-missing

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright
	pnpm lint

up:
	@echo "TODO(T056): 创建 kind 集群并以伞形 Chart 部署整个环境" && exit 1

down:
	@echo "TODO(T056): 删除本地环境" && exit 1

seed:
	@echo "TODO(T068): 写入端到端骨架的示例数据" && exit 1

e2e:
	@echo "TODO(T072): 运行端到端测试" && exit 1

components-check:
	uv run python -m tools.components_check

patches-check:
	@echo "TODO(T060): 检查 third_party 补丁登记" && exit 1

offline-package:
	@echo "TODO(T058): 构建离线安装包" && exit 1
