"""testdata 测试的公共夹具：Testcontainers 启动的 MySQL 8.4 与 PostgreSQL 17
（与 plan 中的版本一致）。

连接串指向服务器（管理员账号），`load` 自行重建 `mes`、`qms` 两个 database。
"""

from collections.abc import Iterator

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

MYSQL_IMAGE = "mysql:8.4.13"
POSTGRES_IMAGE = "postgres:17"
PASSWORD = "mock-test"


@pytest.fixture(scope="session")
def mysql_dsn() -> Iterator[str]:
    container = (
        DockerContainer(MYSQL_IMAGE)
        .with_env("MYSQL_ROOT_PASSWORD", PASSWORD)
        .with_exposed_ports(3306)
        .waiting_for(
            LogMessageWaitStrategy("port: 3306  MySQL Community Server").with_startup_timeout(120)
        )
    )
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(3306)
        yield f"mysql://root:{PASSWORD}@{host}:{port}"


@pytest.fixture(scope="session")
def postgres_dsn() -> Iterator[str]:
    container = (
        DockerContainer(POSTGRES_IMAGE)
        .with_env("POSTGRES_PASSWORD", PASSWORD)
        .with_exposed_ports(5432)
        .waiting_for(
            LogMessageWaitStrategy(
                "database system is ready to accept connections", times=2
            ).with_startup_timeout(60)
        )
    )
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        yield f"postgresql://postgres:{PASSWORD}@{host}:{port}/postgres"
