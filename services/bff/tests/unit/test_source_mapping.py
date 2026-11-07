"""连接字段按连接器映射到 OM 原生字段（research R9）。"""

import pytest

from contexture_bff.adapters.om_sources import connection_view, om_connection
from contexture_core.errors import ContextureError


def conn(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {"hostPort": "h:1", "username": "ro", "password": "pw", "database": None, "tls": False}
    base.update(kw)
    return base


def test_mysql_database_optional_maps_database_schema() -> None:
    assert om_connection("Mysql", conn(database="mes")) == {
        "type": "Mysql", "hostPort": "h:1", "username": "ro", "authType": {"password": "pw"}, "databaseSchema": "mes",
    }
    assert "databaseSchema" not in om_connection("Mysql", conn(database=None))
    assert "databaseSchema" not in om_connection("Mysql", conn(database=""))


def test_doris_uses_top_level_password() -> None:
    assert om_connection("Doris", conn(database="mock_dw")) == {
        "type": "Doris", "hostPort": "h:1", "username": "ro", "password": "pw", "databaseSchema": "mock_dw",
    }


def test_postgres_and_mssql_database_required_and_single_database() -> None:
    pg = om_connection("Postgres", conn(database="qms", tls=True))
    assert pg == {
        "type": "Postgres", "hostPort": "h:1", "username": "ro", "authType": {"password": "pw"},
        "database": "qms", "ingestAllDatabases": False, "sslMode": "require",
    }
    ms = om_connection("Mssql", conn(database="erp", tls=True))
    assert ms["database"] == "erp" and ms["ingestAllDatabases"] is False and ms["encrypt"] is True
    assert ms["password"] == "pw"
    for st in ("Postgres", "Mssql", "Oracle"):
        with pytest.raises(ContextureError) as exc:
            om_connection(st, conn(database=None))
        assert exc.value.code == "source.invalid_request"


def test_oracle_service_name() -> None:
    assert om_connection("Oracle", conn(database="ERP"))["oracleConnectionType"] == {"oracleServiceName": "ERP"}


@pytest.mark.parametrize("service_type", ["Mysql", "Doris", "Oracle"])
def test_tls_not_offered_for_mysql_doris_oracle(service_type: str) -> None:
    with pytest.raises(ContextureError) as exc:
        om_connection(service_type, conn(database="x", tls=True))
    assert exc.value.code == "source.invalid_request"


def test_masked_password_is_passed_through_for_om_to_keep() -> None:
    assert om_connection("Mysql", conn(password="*********"))["authType"] == {"password": "*********"}


@pytest.mark.parametrize(
    ("service_type", "config", "expected"),
    [
        ("Mysql", {"hostPort": "h:1", "username": "ro", "authType": {"password": "*********"}, "databaseSchema": "mes"}, "mes"),
        ("Postgres", {"hostPort": "h:1", "username": "ro", "authType": {"password": "*********"}, "database": "qms", "sslMode": "require"}, "qms"),
        ("Oracle", {"hostPort": "h:1", "username": "ro", "password": "*********", "oracleConnectionType": {"oracleServiceName": "ERP"}}, "ERP"),
    ],
)
def test_connection_view_is_masked(service_type: str, config: dict[str, object], expected: str) -> None:
    view = connection_view(service_type, config)
    assert view["password"] == "*********"
    assert view["database"] == expected
    assert view["tls"] is (service_type == "Postgres")
