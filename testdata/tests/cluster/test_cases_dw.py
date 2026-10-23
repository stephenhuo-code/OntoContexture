"""本地集群：make mock-data 的两种规模下 verify-cases 全部通过（含数仓中 C3 的汇总口径）。"""

import re

import pytest

from mockfactory.__main__ import main

pytestmark = pytest.mark.cluster


@pytest.mark.parametrize("months", ["12", "1"])
def test_cases_local(months: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["load", "--target", "local", "--months", months]) == 0
    capsys.readouterr()
    assert main(["verify-cases", "--target", "local"]) == 0
    out = capsys.readouterr().out
    assert not re.search(r"步骤 \d+ 跳过", out)
    assert not re.search(r"步骤 \d+ 失败", out)
    assert re.search(r"C3 步骤 3 通过", out)  # 数仓中的汇总口径
