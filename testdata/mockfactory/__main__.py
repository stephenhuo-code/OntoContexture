"""命令行：python -m mockfactory <命令>（契约见 specs/003-mock-factory-data/contracts/cli.md）。

退出码：0 成功；1 参数错误；2 目标系统未就绪；3 写入失败（已清空）；4 案例核对不一致；
5 拒绝写入（006 om-import：目标已存在且不是本工具创建的）。
"""

import argparse
import contextlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pymysql

from mockfactory.checksum import Checksums, digest, format_checksums
from mockfactory.config import DEFAULT_MONTHS, DEFAULT_SEED, Settings
from mockfactory.dataset import Dataset
from mockfactory.docs import DOC_PATH, render_roster, write_docs
from mockfactory.generate import build
from mockfactory.load import NotReady, Targets, check_ready, dsn_targets, local_targets
from mockfactory.load import doris as doris_load
from mockfactory.load import mysql as mysql_load
from mockfactory.load import postgres as pg_load
from mockfactory.om_import import writer as om_writer
from mockfactory.schema import TABLES, Table
from mockfactory.verify import report, verify

LOCAL_PORTS = {
    "mes": "MySQL localhost:13306 database mes（make ports）",
    "qms": "PostgreSQL localhost:15432 database qms（make ports）",
    "dw": "Doris localhost:9030 database mock_dw（kubectl port-forward svc/doris-fe-service 9030）",
}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mockfactory", description="织境模拟工厂数据集")
    sub = p.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("load", "重建并写入三套模拟系统"),
        ("checksum", "逐表摘要"),
        ("verify-cases", "按标准答案核对 3 个案例"),
    ):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("--target", choices=["local", "dsn"], required=True)
        s.add_argument("--mes", help="mysql://用户:密码@主机:端口")
        s.add_argument("--qms", help="postgresql://用户:密码@主机:端口/postgres")
        s.add_argument("--dw", help="mysql://用户:密码@主机:端口（Doris FE 查询端口）")
        s.add_argument("--dw-reader-password", help="创建 mock_dw 只读账号的密码")
        s.add_argument("--months", type=int, default=DEFAULT_MONTHS)
        s.add_argument("--seed", type=int, default=DEFAULT_SEED)
    sub.add_parser("provision-005", help="005：只读元数据账号与 viewlab 视图测试库（本地集群）")
    docs = sub.add_parser("docs", help="重新生成 testdata/数据说明.md")
    docs.add_argument("--out", type=Path, default=DOC_PATH)
    om = sub.add_parser("om-import", help="006：把 003 表定义导入 OM 作为开发态测试元数据")
    om.add_argument("--target", choices=["local"], help="开发态目标环境，必须显式指定 local")
    om.add_argument("--om-url", required=True, help="OM 地址，如 http://localhost:8585")
    om.add_argument("--remove", action="store_true", help="撤除本工具导入的测试资产")
    roster = sub.add_parser("roster", help="导出人员与班组名单（CSV）")
    roster.add_argument("--out", type=Path)
    return p


@contextlib.contextmanager
def _targets(args: argparse.Namespace) -> Iterator[Targets]:
    if args.target == "local":
        with local_targets() as t:
            yield t
    else:
        if not (args.mes or args.qms or args.dw):
            raise ValueError("--target dsn 至少需要 --mes、--qms、--dw 之一")
        yield dsn_targets(args.mes, args.qms, args.dw, args.dw_reader_password)


def _systems(t: Targets) -> list[str]:
    return [s for s, v in (("mes", t.mes), ("qms", t.qms), ("dw", t.dw)) if v]


def load(args: argparse.Namespace, settings: Settings) -> int:
    started = time.monotonic()
    ds = build(settings)
    with _targets(args) as t:
        systems = _systems(t)
        check_ready(
            t, sum(ds.total(s) for s in systems), wait_seconds=60 if args.target == "local" else 0
        )
        try:
            if t.mes:
                mysql_load.load_mysql(t.mes, ds)
            if t.qms:
                pg_load.load_postgres(t.qms, ds)
            if t.dw:
                conn = pymysql.connect(**t.dw, autocommit=True, connect_timeout=5)
                try:
                    doris_load.load_doris(conn, ds, t.dw_reader_password)
                finally:
                    conn.close()
        except Exception as e:
            print(f"写入失败，已清空：{e}", file=sys.stderr)
            return 3
        described = t.describe()
    _summary(ds, systems, described if args.target == "dsn" else LOCAL_PORTS, settings, started)
    return 0


def _summary(
    ds: Dataset, systems: list[str], where: dict[str, str], settings: Settings, started: float
) -> None:
    print(f"模拟工厂：{settings.months} 个月（截至 2026-09-30），种子 {settings.seed}")
    for system in systems:
        print(f"\n[{system}] {where[system]}，共 {ds.total(system)} 行")
        for t in TABLES:
            if t.system == system:
                print(f"  {t.name:<28}{ds.count(t.name):>10}")
    print(
        f"\n合计 {sum(ds.total(s) for s in systems)} 行，用时 {time.monotonic() - started:.0f} 秒"
    )


def _fetch(t: Targets, table: Table) -> list[tuple[object, ...]]:
    if table.system == "mes" and t.mes:
        rows = mysql_load.fetch_all(t.mes, table.name, table.column_names)
    elif table.system == "qms" and t.qms:
        rows = pg_load.fetch_all(t.qms, table.name, table.column_names)
    else:
        if t.dw is None:
            raise NotReady(f"未提供 {table.system} 的连接")
        conn = pymysql.connect(**t.dw, connect_timeout=5)
        try:
            rows = doris_load.fetch_all(conn, table.name, table.column_names)
        finally:
            conn.close()
    idx = [table.column_names.index(k) for k in table.primary_key]
    return sorted(rows, key=lambda r: tuple(r[i] for i in idx))  # type: ignore[no-any-return]


def checksum(args: argparse.Namespace) -> int:
    with _targets(args) as t:
        systems = _systems(t)
        check_ready(t, 0)
        sums: Checksums = {
            (table.system, table.name): digest(_fetch(t, table))
            for table in TABLES
            if table.system in systems
        }
    print(format_checksums(sums), end="")
    return 0


def verify_cases(args: argparse.Namespace) -> int:
    with _targets(args) as t:
        check_ready(t, 0)
        results = verify(t)
    print(report(results), end="")
    return 4 if any(r.status == "失败" for r in results) else 0


def provision_005() -> int:
    """在本地集群的 mock-mes / mock-qms 实例内建只读元数据账号与 viewlab（不改动 003 数据）。"""
    from mockfactory import viewlab

    passwords = viewlab.local_passwords()
    with local_targets() as t:
        check_ready(t, 0)
        if t.mes is None or t.qms is None:
            raise SystemExit("provision-005 需要本地集群中的 mock-mes 与 mock-qms")
        viewlab.provision_mysql(t.mes, passwords)
        viewlab.provision_postgres(t.qms, passwords)
    print("provision-005: mes_meta_ro、qms_meta_ro、viewlab（MySQL / PostgreSQL）就绪")
    return 0


def _om_token() -> str:
    """凭证只读环境变量：OM_TOKEN，或 provisioner 客户端凭证（同 make seed）；不写盘、不打印。"""
    token = os.environ.get("OM_TOKEN")
    if token:
        return token
    client_id = os.environ.get("KEYCLOAK_PROVISIONER_CLIENT_ID")
    secret = os.environ.get("KEYCLOAK_PROVISIONER_CLIENT_SECRET")
    url, realm = os.environ.get("KEYCLOAK_URL"), os.environ.get("KEYCLOAK_REALM")
    if not (client_id and secret and url and realm):
        raise ValueError(
            "缺少凭证：设置 OM_TOKEN，或 KEYCLOAK_URL / KEYCLOAK_REALM / "
            "KEYCLOAK_PROVISIONER_CLIENT_ID / KEYCLOAK_PROVISIONER_CLIENT_SECRET"
        )
    form = urllib.parse.urlencode(
        {"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret}
    ).encode()
    token_url = om_writer.require_http(f"{url}/realms/{realm}/protocol/openid-connect/token")
    req = urllib.request.Request(token_url, data=form, method="POST")  # noqa: S310
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310  已校验协议
        return str(json.loads(resp.read())["access_token"])


def om_import(args: argparse.Namespace) -> int:
    if args.target != "local":
        print("未显式指定开发态目标环境（--target local），拒绝写入。", file=sys.stderr)
        return 1
    send = om_writer.urllib_transport(args.om_url, _om_token())
    w = om_writer.OmWriter(send)
    try:
        if args.remove:
            stats = w.remove()
            print(f"开发态元数据撤除（OM {args.om_url}）：删除 {stats.deleted} 个根实体")
            return 0
        stats = w.import_all()
    except om_writer.NotOwned as e:
        print(f"拒绝写入：{e}", file=sys.stderr)
        return 5
    except om_writer.WriteFailed as e:
        print(f"写入失败：{e}", file=sys.stderr)
        return 3
    print(
        f"开发态元数据导入（OM {args.om_url}）：新建 {stats.created}，"
        f"更新 {stats.updated}，未变化 {stats.unchanged}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        settings = Settings(
            months=getattr(args, "months", DEFAULT_MONTHS), seed=getattr(args, "seed", DEFAULT_SEED)
        )
        if args.command == "load":
            return load(args, settings)
        if args.command == "verify-cases":
            return verify_cases(args)
        if args.command == "provision-005":
            return provision_005()
        if args.command == "om-import":
            return om_import(args)
        if args.command == "docs":
            print(write_docs(args.out))
            return 0
        if args.command == "roster":
            if args.out:
                args.out.write_text(render_roster(), encoding="utf-8")
            else:
                print(render_roster(), end="")
            return 0
        return checksum(args)
    except SystemExit as e:
        return 1 if e.code else 0
    except ValueError as e:
        print(f"参数错误：{e}", file=sys.stderr)
        return 1
    except NotReady as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
