"""命令行：python -m mockfactory <命令>（契约见 specs/003-mock-factory-data/contracts/cli.md）。

退出码：0 成功；1 参数错误；2 目标系统未就绪；3 写入失败（已清空）；4 案例核对不一致。
"""

import argparse
import contextlib
import sys
import time
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
    docs = sub.add_parser("docs", help="重新生成 testdata/数据说明.md")
    docs.add_argument("--out", type=Path, default=DOC_PATH)
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
