import subprocess
import sysconfig
from pathlib import Path

import pytest


def test_render_cli_reads_stdin_template_and_data_file(tmp_path: Path) -> None:
    data_path = tmp_path / "data.json"
    data_path.write_text('{"name": "Ada & Bob"}', encoding="utf-8")

    result = _run_fstache(
        ["render", "--data", str(data_path)],
        cwd=tmp_path,
        stdin=b"Hello {{name}}",
    )

    assert result.returncode == 0
    assert result.stdout == b"Hello Ada &amp; Bob"
    assert result.stderr == b""


def test_render_cli_discovers_partials_from_cwd(tmp_path: Path) -> None:
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "header.mustache").write_bytes(b"Hi {{name}}")
    data_path = tmp_path / "data.json"
    data_path.write_text('{"name": "Ada"}', encoding="utf-8")

    result = _run_fstache(
        ["render", "--data", str(data_path)],
        cwd=tmp_path,
        stdin=b"{{> shared/header.mustache}}",
    )

    assert result.returncode == 0
    assert result.stdout == b"Hi Ada"
    assert result.stderr == b""


def test_render_cli_invalid_json_exits_without_traceback(tmp_path: Path) -> None:
    data_path = tmp_path / "data.json"
    data_path.write_text("{", encoding="utf-8")

    result = _run_fstache(
        ["render", "--data", str(data_path)],
        cwd=tmp_path,
        stdin=b"Hello {{name}}",
    )

    assert result.returncode == 1
    assert result.stdout == b""
    assert b"fstache render: invalid JSON in" in result.stderr
    assert b"Traceback" not in result.stderr


def _run_fstache(
    args: list[str],
    *,
    cwd: Path,
    stdin: bytes,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [_fstache_script(), *args],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        check=False,
    )


def _fstache_script() -> str:
    script_path = Path(sysconfig.get_path("scripts")) / "fstache"
    if script_path.exists():
        return str(script_path)

    pytest.fail("fstache console script is not installed")
