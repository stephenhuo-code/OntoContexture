"""标准答案文件：符合契约 Schema；仓库内的 Schema 副本与 spec 中的契约一致。"""

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "testdata" / "cases"
CONTRACT = ROOT / "specs" / "003-mock-factory-data" / "contracts" / "case-answer.schema.json"


def test_schema_copy_matches_contract() -> None:
    assert json.loads(
        (CASES / "case-answer.schema.json").read_text(encoding="utf-8")
    ) == json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_answers_valid() -> None:
    validator = Draft202012Validator(json.loads(CONTRACT.read_text(encoding="utf-8")))
    files = sorted(CASES.glob("C*.yaml"))
    assert [f.stem for f in files] == ["C1", "C2", "C3"]
    for f in files:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        errors = [e.message for e in validator.iter_errors(data)]
        assert not errors, (f.name, errors)
        assert data["id"] == f.stem
        for step in data["steps"]:
            assert step["sql"].lstrip().upper().startswith(("SELECT", "WITH")), step["description"]
            width = len(step["expected"]["columns"])
            assert all(len(row) == width for row in step["expected"]["rows"])
