"""会话库迁移（Alembic）。用法：python -m contexture_bff.migrate"""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from contexture_bff.settings import BffSettings
from contexture_core.config import load_settings

# 源码中位于 services/bff/migrations；镜像中由 CTX_BFF_MIGRATIONS 指定
MIGRATIONS = Path(
    os.environ.get("CTX_BFF_MIGRATIONS", Path(__file__).resolve().parents[2] / "migrations")
)


def upgrade(database_url: str, revision: str = "head") -> None:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, revision)


if __name__ == "__main__":
    upgrade(load_settings(BffSettings).database_url)
