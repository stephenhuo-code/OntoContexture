"""030 云端环境内的状态检查（-m cluster，make cloud-e2e 在工具箱中运行）：证书与续期。"""

import json
import os
import subprocess
from typing import Any

import pytest

pytestmark = pytest.mark.cluster
NS = os.environ.get("CTX_CLOUD_NAMESPACE", "contexture")
SUBDOMAINS = (
    "sso",
    "om",
    "langfuse",
    "airflow",
    "jaeger",
    "prometheus",
    "dashboards",
    "gateway-admin",
)
cloud_only = pytest.mark.skipif("CTX_E2E_BASE_URL" not in os.environ, reason="仅在云端工具箱中运行")


def kubectl_json(*args: str) -> dict[str, Any]:
    cmd = ["kubectl", "-n", NS, *args, "-o", "json"]
    return json.loads(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout)


@cloud_only
def test_certificate_is_ready_and_covers_all_hosts() -> None:
    cert = kubectl_json("get", "certificate", "contexture")
    ready = {c["type"]: c["status"] for c in cert["status"]["conditions"]}
    assert ready.get("Ready") == "True"
    domain = os.environ["CTX_E2E_BASE_URL"].removeprefix("https://")
    expected = {domain} | {f"{s}.{domain}" for s in SUBDOMAINS}
    assert expected <= set(cert["spec"]["dnsNames"])


@cloud_only
def test_certificate_renews_30_days_before_expiry() -> None:
    cert = kubectl_json("get", "certificate", "contexture")
    assert cert["spec"]["renewBefore"] in {"720h", "720h0m0s"}
