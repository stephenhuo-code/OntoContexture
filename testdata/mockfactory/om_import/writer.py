"""把 fixture 经 OM 正式接口（PUT createOrUpdate）幂等写入，并支持撤除（research R13）。

- 统计依据响应头 X-OpenMetadata-Change：entityCreated 为新建，entityNoChange 为未变化，其余为更新；
- 只管理本工具创建的资产：目标根实体已存在但没有开发态标识时拒绝写入（FR-017）；
- 撤除只删除带标识的自有服务（hardDelete + recursive）以及自有的术语表、业务域、分类。
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, NamedTuple

from mockfactory.om_import import fixture as fx

CHANGE_HEADER = "X-OpenMetadata-Change"
# 已存在时需核对归属的根实体（其下级随根实体一起归属）
ROOT_KINDS = ("classification", "domain", "glossary", "databaseService")


class Response(NamedTuple):
    status: int
    headers: Mapping[str, str]
    body: Any


Transport = Callable[[str, str, dict[str, Any] | None], Response]


class NotOwned(Exception):
    """目标实体已存在且不是本工具创建的，拒绝写入。"""


class WriteFailed(Exception):
    """OM 拒绝写入。"""


@dataclass
class Stats:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "deleted": self.deleted,
        }


def require_http(url: str) -> str:
    """只允许 http / https，避免 urllib 打开 file: 等其他协议。"""
    if urllib.parse.urlsplit(url).scheme not in {"http", "https"}:
        raise ValueError(f"只支持 http / https 地址：{url}")
    return url


def urllib_transport(om_url: str, token: str) -> Transport:
    """以 Bearer 令牌调用 OM REST（{om_url}/api/v1/...）。令牌只在内存中使用，不写盘、不打印。"""
    base = require_http(om_url).rstrip("/") + "/api"

    def send(method: str, path: str, body: dict[str, Any] | None) -> Response:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(base + path, data=data, method=method)  # noqa: S310
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310  已校验协议
                raw = resp.read()
                return Response(resp.status, dict(resp.headers), json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                payload = json.loads(raw) if raw else None
            except ValueError:
                payload = raw.decode("utf-8", "replace")
            return Response(e.code, dict(e.headers), payload)

    return send


def _quote(fqn: str) -> str:
    return urllib.parse.quote(fqn, safe="")


class OmWriter:
    def __init__(self, send: Transport) -> None:
        self.send = send

    def _get(self, kind: str, fqn: str) -> dict[str, Any] | None:
        fields = "" if kind == "classification" else "?fields=tags"
        r = self.send("GET", f"/v1/{fx.COLLECTION[kind]}/name/{_quote(fqn)}{fields}", None)
        if r.status == 404:
            return None
        if r.status >= 400:
            raise WriteFailed(f"读取 {kind} {fqn} 失败：HTTP {r.status} {r.body}")
        return dict(r.body)

    def _owners(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for team in fx.TEAM_NAMES:
            r = self.send("GET", f"/v1/teams/name/{_quote(team)}", None)
            if r.status >= 400:
                raise WriteFailed(f"OM 团队 {team} 不存在（先执行 make seed）：HTTP {r.status}")
            out[team] = {"id": r.body["id"], "type": "team"}
        return out

    def _guard(self, entities: Iterable[fx.Entity]) -> None:
        for e in entities:
            if e.kind not in ROOT_KINDS:
                continue
            existing = self._get(e.kind, e.fqn)
            if existing is not None and not fx.is_owned(e.kind, existing):
                raise NotOwned(f"{e.kind} {e.fqn} 已存在且不是开发态导入工具创建的，拒绝写入")

    def import_all(self) -> Stats:
        entities = fx.build(self._owners())
        self._guard(entities)
        stats = Stats()
        for e in entities:
            r = self.send("PUT", f"/v1/{e.collection}", e.body)
            if r.status >= 400:
                raise WriteFailed(f"写入 {e.kind} {e.fqn} 失败：HTTP {r.status} {r.body}")
            headers = {k.lower(): v for k, v in r.headers.items()}
            change = headers.get(CHANGE_HEADER.lower(), "")
            if r.status == 201 or change == "entityCreated":
                stats.created += 1
            elif change == "entityNoChange":
                stats.unchanged += 1
            else:
                stats.updated += 1
        return stats

    def _delete(self, kind: str, fqn: str) -> None:
        path = f"/v1/{fx.COLLECTION[kind]}/name/{_quote(fqn)}?hardDelete=true&recursive=true"
        r = self.send("DELETE", path, None)
        if r.status >= 400 and r.status != 404:
            raise WriteFailed(f"撤除 {kind} {fqn} 失败：HTTP {r.status} {r.body}")

    def remove(self) -> Stats:
        stats = Stats()
        targets = [
            *(("databaseService", s[0]) for s in fx.SYSTEMS.values()),
            ("glossary", fx.GLOSSARY),
            *(("domain", d) for d in fx.DOMAINS.values()),
            ("classification", fx.SAMPLE_CLASSIFICATION),
            ("classification", fx.MARKER_CLASSIFICATION),
        ]
        for kind, fqn in targets:
            existing = self._get(kind, fqn)
            if existing is None or not fx.is_owned(kind, existing):
                continue
            if kind == "classification":
                for tag in fx.tag_fqns(fqn):
                    self._delete("tag", tag)
            self._delete(kind, fqn)
            stats.deleted += 1
        return stats
