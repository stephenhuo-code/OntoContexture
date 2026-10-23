"""写入目标：`dsn`（指定地址，集成测试用）与 `local`（本地 kind 集群，经端口转发）。

local 目标：模拟 MES、QMS 在命名空间 mock-sources，数仓在 contexture 命名空间的 Doris；
凭证取自集群 Secret。
"""

import contextlib
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse

import pymysql

from mockfactory.load import mysql, postgres

KUBE_CONTEXT = "kind-contexture"
MOCK_NS = "mock-sources"
PLATFORM_NS = "contexture"
BYTES_PER_ROW = 150  # 估算磁盘占用（含索引）


class NotReady(Exception):
    """目标系统不可连接或空间不足。"""


@dataclass
class Targets:
    mes: dict[str, Any] | None = None  # PyMySQL 连接参数
    qms: str | None = None  # PostgreSQL 管理库连接串
    dw: dict[str, Any] | None = None  # Doris（MySQL 协议）连接参数
    dw_reader_password: str | None = None
    free_bytes: int | None = None  # 已知时用于磁盘估算

    def describe(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.mes:
            out["mes"] = f"MySQL {self.mes['host']}:{self.mes['port']} database mes"
        if self.qms:
            p = urlparse(self.qms)
            out["qms"] = f"PostgreSQL {p.hostname}:{p.port} database qms"
        if self.dw:
            out["dw"] = f"Doris {self.dw['host']}:{self.dw['port']} database mock_dw"
        return out


def parse_mysql_dsn(dsn: str) -> dict[str, Any]:
    p = urlparse(dsn)
    return {
        "host": p.hostname or "127.0.0.1",
        "port": p.port or 3306,
        "user": unquote(p.username or "root"),
        "password": unquote(p.password or ""),
    }


def dsn_targets(
    mes: str | None, qms: str | None, dw: str | None, dw_reader_password: str | None
) -> Targets:
    return Targets(
        mes=parse_mysql_dsn(mes) if mes else None,
        qms=qms,
        dw=parse_mysql_dsn(dw) if dw else None,
        dw_reader_password=dw_reader_password,
    )


def _kubectl(*args: str) -> str:
    return subprocess.run(  # noqa: S603
        ["kubectl", "--context", KUBE_CONTEXT, *args],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _secret(ns: str, name: str, key: str) -> str:
    import base64

    return base64.b64decode(
        _kubectl("-n", ns, "get", "secret", name, "-o", f"jsonpath={{.data.{key}}}")
    ).decode()


@contextlib.contextmanager
def _port_forward(ns: str, target: str, remote_port: int) -> Iterator[int]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        local = int(s.getsockname()[1])
    proc = subprocess.Popen(  # noqa: S603
        [  # noqa: S607
            "kubectl",
            "--context",
            KUBE_CONTEXT,
            "-n",
            ns,
            "port-forward",
            target,
            f"{local}:{remote_port}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        # 以 kubectl 输出的 “Forwarding from” 判断就绪：不能先建一个空连接试探，
        # PostgreSQL 会重置该连接，kubectl port-forward 随之退出
        stdout = proc.stdout
        line = stdout.readline() if stdout else ""
        if "Forwarding from" not in line:
            raise NotReady(f"无法转发 {ns}/{target}")
        # 继续读掉后续输出（每个连接一行），避免管道写满后 kubectl 阻塞
        threading.Thread(target=stdout.read, daemon=True).start()  # type: ignore[union-attr]
        yield local
    finally:
        proc.terminate()


def _node_free_bytes() -> int | None:
    """kind 工作节点上的可用空间（持久卷落在节点的 local-path）。"""
    if shutil.which("docker") is None:
        return None
    out = subprocess.run(
        ["docker", "exec", "contexture-worker", "df", "-Pk", "/var"],  # noqa: S607
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        return None
    return int(out.stdout.splitlines()[-1].split()[3]) * 1024


@contextlib.contextmanager
def local_targets() -> Iterator[Targets]:
    try:
        mes_pw = _secret(MOCK_NS, "mock-mes", "root-password")
        qms_user = _secret(MOCK_NS, "mock-qms-superuser", "username")
        qms_pw = _secret(MOCK_NS, "mock-qms-superuser", "password")
        dw_pw = _secret(PLATFORM_NS, "doris-root", "password")
        reader_pw = _secret(MOCK_NS, "mock-dw-reader", "password")
    except subprocess.CalledProcessError as e:
        raise NotReady(f"读取凭证失败（模拟源系统是否已部署？）：{e.stderr.strip()}") from e
    with (
        _port_forward(MOCK_NS, "svc/mock-mes", 3306) as mes_port,
        _port_forward(MOCK_NS, "svc/mock-qms-rw", 5432) as qms_port,
        _port_forward(PLATFORM_NS, "svc/doris-fe-service", 9030) as dw_port,
    ):
        yield Targets(
            mes={"host": "127.0.0.1", "port": mes_port, "user": "root", "password": mes_pw},
            qms=f"postgresql://{qms_user}:{qms_pw}@127.0.0.1:{qms_port}/postgres",
            dw={"host": "127.0.0.1", "port": dw_port, "user": "root", "password": dw_pw},
            dw_reader_password=reader_pw,
            free_bytes=_node_free_bytes(),
        )


def check_ready(targets: Targets, estimated_rows: int, wait_seconds: int = 0) -> None:
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            if targets.mes:
                mysql.connect(targets.mes).close()
            if targets.qms:
                postgres.ping(targets.qms)
            if targets.dw:
                pymysql.connect(**targets.dw, connect_timeout=5).close()
            break
        except Exception as e:
            if time.monotonic() >= deadline:
                raise NotReady(f"目标系统未就绪：{e}") from e
            time.sleep(3)
    need = estimated_rows * BYTES_PER_ROW
    if targets.free_bytes is not None and targets.free_bytes < need * 2:
        raise NotReady(
            f"磁盘空间不足：预计需要约 {need // 2**20} MB，"
            f"节点可用 {targets.free_bytes // 2**20} MB"
        )
