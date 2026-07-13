from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any, Final

import fstache
import pytest

from fstache import CompiledTemplate, EMPTY_TEMPLATE, render


type JsonObject = dict[str, Any]


_SPEC_DIR: Final = Path(__file__).parent / "fixtures" / "mustache-specs"
_JSON_SUFFIX: Final = ".json"
_ROOT_TEMPLATE_NAME: Final = "root"
_UTF_8: Final = "utf-8"

_EXCLUDED_SPEC_FILES: Final[Mapping[str, str]] = {
    "~inheritance.json": (
        "Fstache intentionally does not support parent/block inheritance tags."
    ),
}
_EXCLUDED_SPEC_CASES: Final[Mapping[tuple[str, str], str]] = {}


def _load_spec_file(file_name: str) -> JsonObject:
    with (_SPEC_DIR / file_name).open(encoding=_UTF_8) as spec_file:
        spec = json.load(spec_file)

    if not isinstance(spec, dict):
        raise TypeError(f"{file_name} must contain a JSON object")

    return spec


def _spec_cases() -> list[Any]:
    params: list[Any] = []
    for path in sorted(_SPEC_DIR.glob(f"*{_JSON_SUFFIX}")):
        if path.name in _EXCLUDED_SPEC_FILES:
            continue

        spec = _load_spec_file(path.name)
        cases = spec["tests"]
        for case in cases:
            case_name = case["name"]
            if (path.name, case_name) in _EXCLUDED_SPEC_CASES:
                continue

            spec_name = path.name.removesuffix(_JSON_SUFFIX)
            params.append(pytest.param(path.name, case, id=f"{spec_name}::{case_name}"))

    return params


@pytest.mark.parametrize(("file_name", "case"), _spec_cases())
def test_upstream_mustache_spec_case(file_name: str, case: JsonObject) -> None:
    namespace: dict[str, object] = {}
    data = _hydrate_fixture_value(case.get("data", {}), namespace)
    partials = case.get("partials", {})
    root_template = fstache.compile(
        _fixture_text_to_bytes(case["template"]),
        name=f"{file_name}::{case['name']}",
    )

    def load_template(name: str) -> CompiledTemplate:
        if name == _ROOT_TEMPLATE_NAME:
            return root_template

        partial_template = partials.get(name)
        if partial_template is None:
            return EMPTY_TEMPLATE

        return fstache.compile(
            _fixture_text_to_bytes(partial_template),
            name=f"{file_name}::{case['name']}::{name}",
        )

    actual = render(_ROOT_TEMPLATE_NAME, data, load_template).to_bytes().decode(_UTF_8)

    assert actual == case["expected"]


def test_exclusions_are_documented_and_reference_vendored_fixtures() -> None:
    file_names = {path.name for path in _SPEC_DIR.glob(f"*{_JSON_SUFFIX}")}
    missing_files = set(_EXCLUDED_SPEC_FILES) - file_names

    assert missing_files == set()
    assert all(reason.strip() for reason in _EXCLUDED_SPEC_FILES.values())

    for (file_name, case_name), reason in _EXCLUDED_SPEC_CASES.items():
        assert reason.strip()
        assert file_name in file_names
        assert file_name not in _EXCLUDED_SPEC_FILES

        case_names = {case["name"] for case in _load_spec_file(file_name)["tests"]}

        assert case_name in case_names


def _hydrate_fixture_value(value: object, namespace: dict[str, object]) -> object:
    if _is_code_fixture(value):
        return eval(value["python"], namespace, namespace)

    if isinstance(value, dict):
        return {
            key: _hydrate_fixture_value(child, namespace)
            for key, child in value.items()
        }

    if isinstance(value, list):
        return [_hydrate_fixture_value(item, namespace) for item in value]

    return value


def _is_code_fixture(value: object) -> bool:
    return (
        isinstance(value, dict)
        and value.get("__tag__") == "code"
        and isinstance(value.get("python"), str)
    )


def _fixture_text_to_bytes(value: object) -> bytes:
    if not isinstance(value, str):
        raise TypeError(f"expected fixture string, got {type(value).__name__}")

    return value.encode(_UTF_8)
