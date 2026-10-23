"""供其他特性的集成测试复用：把 1 个月规模（含 3 个案例）的模拟工厂数据载入临时数据库。

用法（其他特性的 conftest 中，数据库由 Testcontainers 启动）：

    from mockfactory.testing import load_small
    ds = load_small("mysql://root:密码@主机:端口", "postgresql://postgres:密码@主机:端口/postgres")

载入后 MES 在 database `mes`，QMS 在 database `qms`；返回的数据集可用于断言。
"""

from mockfactory.config import DEFAULT_SEED, Settings
from mockfactory.dataset import Dataset
from mockfactory.generate import build
from mockfactory.load import parse_mysql_dsn
from mockfactory.load.mysql import load_mysql
from mockfactory.load.postgres import load_postgres


def load_small(mes_dsn: str, qms_dsn: str, seed: int = DEFAULT_SEED) -> Dataset:
    ds = build(Settings(months=1, seed=seed))
    load_mysql(parse_mysql_dsn(mes_dsn), ds)
    load_postgres(qms_dsn, ds)
    return ds
