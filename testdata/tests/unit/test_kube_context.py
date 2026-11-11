"""030：模拟数据工具的 kube 上下文可配置——本地默认 kind-contexture；集群内工具箱设为空串时不传 --context。"""

import pytest

from mockfactory import viewlab
from mockfactory.load import kube_context_args


def test_default_context_is_local_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CTX_KUBE_CONTEXT", raising=False)
    assert kube_context_args() == ["--context", "kind-contexture"]


def test_empty_context_uses_in_cluster_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTX_KUBE_CONTEXT", "")
    assert kube_context_args() == []


def test_viewlab_passwords_use_configured_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class Done:
        stdout = "cHc="

    def fake_run(cmd: list[str], **_: object) -> Done:
        calls.append(cmd)
        return Done()

    monkeypatch.setenv("CTX_KUBE_CONTEXT", "")
    monkeypatch.setattr(viewlab.subprocess, "run", fake_run)
    viewlab.local_passwords()
    assert calls
    assert all("--context" not in c for c in calls)
