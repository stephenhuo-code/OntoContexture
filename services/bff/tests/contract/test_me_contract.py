"""v1 当前账号的显示名称兼容保证。"""

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator


@pytest.mark.parametrize(
    ("extra", "valid"),
    [
        ({}, True),
        ({"display_name": "张三"}, True),
        ({"display_name": ""}, True),
        ({"display_name": None}, False),
        ({"display_name": 12}, False),
    ],
)
def test_v1_me_display_name_schema(extra: dict[str, str | int | None], valid: bool) -> None:
    root = Path(__file__).resolve().parents[4]
    contract = yaml.safe_load((root / "contracts/openapi/bff.yaml").read_text())
    validator = Draft202012Validator(contract["components"]["schemas"]["Me"])
    assert validator.is_valid({"tenant_id": "local", "user_id": "subject", **extra}) is valid
