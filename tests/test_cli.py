import errno
import io
import sys
from pathlib import Path

import pytest

from fstache._cli import main


def test_render_reads_stdin_template_and_data_file(
    tmp_path: Path,
    monkeypatch,
    capfd,
) -> None:
    data_path = tmp_path / "data.json"
    data_path.write_text('{"user": {"name": "Ada & Bob"}}', encoding="utf-8")

    exit_code, stdout, stderr = _run_render(
        ["--data", str(data_path)],
        b"Hello {{user.name}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 0
    assert stdout == "Hello Ada &amp; Bob"
    assert stderr == ""


def test_render_without_data_uses_empty_object(monkeypatch, capfd) -> None:
    exit_code, stdout, stderr = _run_render(
        [],
        b"{{^name}}missing{{/name}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 0
    assert stdout == "missing"
    assert stderr == ""


def test_render_writes_rendered_bytes(monkeypatch, capfdbinary) -> None:
    exit_code, stdout, stderr = _run_render_binary(
        [], b"raw:\xff", monkeypatch, capfdbinary
    )

    assert exit_code == 0
    assert stdout == b"raw:\xff"
    assert stderr == b""


def test_render_default_partial_mapping_uses_mustache_extension(
    tmp_path: Path,
    monkeypatch,
    capfd,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "header.mustache").write_bytes(b"Hi {{name}}")
    data_path = tmp_path / "data.json"
    data_path.write_text('{"name": "Ada"}', encoding="utf-8")

    exit_code, stdout, stderr = _run_render(
        ["--data", str(data_path)],
        b"{{> shared/header.mustache}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 0
    assert stdout == "Hi Ada"
    assert stderr == ""


def test_render_remove_extension_maps_extensionless_partials(
    tmp_path: Path,
    monkeypatch,
    capfd,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "header.mustache").write_bytes(b"Hi {{name}}")
    data_path = tmp_path / "data.json"
    data_path.write_text('{"name": "Ada"}', encoding="utf-8")

    exit_code, stdout, stderr = _run_render(
        ["--data", str(data_path), "--remove-extension"],
        b"{{> shared/header}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 0
    assert stdout == "Hi Ada"
    assert stderr == ""


def test_render_remove_extension_allows_stdin_named_partial(
    tmp_path: Path,
    monkeypatch,
    capfd,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "<stdin>.mustache").write_bytes(b"Hi {{name}}")
    data_path = tmp_path / "data.json"
    data_path.write_text('{"name": "Ada"}', encoding="utf-8")

    exit_code, stdout, stderr = _run_render(
        ["--data", str(data_path), "--remove-extension"],
        b"{{> <stdin>}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 0
    assert stdout == "Hi Ada"
    assert stderr == ""


@pytest.mark.parametrize("extension", [".html", "html"])
def test_render_extension_matches_with_optional_dot(
    tmp_path: Path,
    monkeypatch,
    capfd,
    extension: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "header.html").write_bytes(b"Hi {{name}}")
    data_path = tmp_path / "data.json"
    data_path.write_text('{"name": "Ada"}', encoding="utf-8")

    exit_code, stdout, stderr = _run_render(
        ["--data", str(data_path), "--extension", extension, "--remove-extension"],
        b"{{> shared/header}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 0
    assert stdout == "Hi Ada"
    assert stderr == ""


def test_render_missing_variable_records_diagnostic(monkeypatch, capfd) -> None:
    exit_code, stdout, stderr = _run_render(
        [],
        b"Hello {{user.name}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 1
    assert stdout == "Hello "
    assert stderr == ("fstache render: missing template variable: user.name\n")
    assert "Traceback" not in stderr


def test_render_repeated_missing_variable_records_one_diagnostic(
    monkeypatch, capfd
) -> None:
    exit_code, stdout, stderr = _run_render(
        [],
        b"{{user.name}} {{user.name}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 1
    assert stdout == " "
    assert stderr == ("fstache render: missing template variable: user.name\n")


def test_render_missing_section_is_a_quiet_falsey_value(monkeypatch, capfd) -> None:
    exit_code, stdout, stderr = _run_render(
        [],
        b"{{#items}}item{{/items}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 0
    assert stdout == ""
    assert stderr == ""


def test_render_missing_dynamic_partial_name_is_quiet_empty_output(
    monkeypatch,
    capfd,
) -> None:
    exit_code, stdout, stderr = _run_render(
        [],
        b"Hello {{> *partial}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 0
    assert stdout == "Hello "
    assert stderr == ""


def test_render_missing_partial_records_diagnostic(monkeypatch, capfd) -> None:
    exit_code, stdout, stderr = _run_render(
        [],
        b"Hello {{> shared/header.mustache}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 1
    assert stdout == "Hello "
    assert stderr == ("fstache render: missing template: shared/header.mustache\n")
    assert "Traceback" not in stderr


def test_render_repeated_missing_partial_records_one_diagnostic(
    monkeypatch, capfd
) -> None:
    exit_code, stdout, stderr = _run_render(
        [],
        b"{{> shared/header.mustache}}{{> shared/header.mustache}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 1
    assert stdout == ""
    assert stderr == ("fstache render: missing template: shared/header.mustache\n")


def test_render_missing_stdin_named_partial_records_diagnostic(
    monkeypatch,
    capfd,
) -> None:
    exit_code, stdout, stderr = _run_render(
        [],
        b"Hello {{> <stdin>}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 1
    assert stdout == "Hello "
    assert stderr == ("fstache render: missing template: <stdin>\n")
    assert "Traceback" not in stderr


def test_render_dynamic_stdin_named_partial_records_diagnostic(
    tmp_path: Path,
    monkeypatch,
    capfd,
) -> None:
    data_path = tmp_path / "data.json"
    data_path.write_text('{"partial": "<stdin>"}', encoding="utf-8")

    exit_code, stdout, stderr = _run_render(
        ["--data", str(data_path)],
        b"Hello {{> *partial}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 1
    assert stdout == "Hello "
    assert stderr == ("fstache render: missing template: <stdin>\n")
    assert "Traceback" not in stderr


def test_render_invalid_json_exits_without_traceback(
    tmp_path: Path,
    monkeypatch,
    capfd,
) -> None:
    data_path = tmp_path / "data.json"
    data_path.write_text("{", encoding="utf-8")

    exit_code, stdout, stderr = _run_render(
        ["--data", str(data_path)],
        b"Hello {{name}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 1
    assert stdout == ""
    assert "fstache render: invalid JSON in" in stderr
    assert "Traceback" not in stderr


def test_render_undecodable_data_file_exits_without_traceback(
    tmp_path: Path,
    monkeypatch,
    capfd,
) -> None:
    data_path = tmp_path / "data.json"
    data_path.write_bytes(b"\xff")

    exit_code, stdout, stderr = _run_render(
        ["--data", str(data_path)],
        b"Hello {{name}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 1
    assert stdout == ""
    assert "fstache render: cannot read" in stderr
    assert "invalid UTF-8" in stderr
    assert "Traceback" not in stderr


def test_render_unreadable_data_file_exits_without_traceback(
    tmp_path: Path,
    monkeypatch,
    capfd,
) -> None:
    data_path = tmp_path / "missing.json"

    exit_code, stdout, stderr = _run_render(
        ["--data", str(data_path)],
        b"Hello {{name}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 1
    assert stdout == ""
    assert "fstache render: cannot read" in stderr
    assert "Traceback" not in stderr


def test_render_unreadable_partial_exits_without_traceback(
    tmp_path: Path,
    monkeypatch,
    capfd,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "shared").mkdir()
    partial_path = tmp_path / "shared" / "header.mustache"
    partial_path.write_bytes(b"Hi {{name}}")
    data_path = tmp_path / "data.json"
    data_path.write_text('{"name": "Ada"}', encoding="utf-8")
    original_read_bytes = Path.read_bytes

    def raise_for_partial(path: Path) -> bytes:
        if path == partial_path:
            raise PermissionError(errno.EACCES, "Permission denied", str(path))

        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", raise_for_partial)

    exit_code, stdout, stderr = _run_render(
        ["--data", str(data_path)],
        b"{{> shared/header.mustache}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 1
    assert stdout == ""
    assert "fstache render: cannot read" in stderr
    assert "header.mustache" in stderr
    assert "Traceback" not in stderr


def test_render_syntax_error_mentions_stdin(monkeypatch, capfd) -> None:
    exit_code, stdout, stderr = _run_render(
        [],
        b"Hello {{#user}}",
        monkeypatch,
        capfd,
    )

    assert exit_code == 1
    assert stdout == ""
    assert "<stdin>" in stderr
    assert "Traceback" not in stderr


def test_render_broken_stdout_exits_without_traceback(monkeypatch, capfd) -> None:
    monkeypatch.setattr(sys, "stdout", _BrokenStdout())

    exit_code, stdout, stderr = _run_render([], b"Hello {{name}}", monkeypatch, capfd)

    assert exit_code == 1
    assert stdout == ""
    assert stderr == ""


def test_render_broken_stdout_flush_exits_without_traceback(monkeypatch, capfd) -> None:
    monkeypatch.setattr(sys, "stdout", _FlushBrokenStdout())

    exit_code, stdout, stderr = _run_render([], b"Hello {{name}}", monkeypatch, capfd)

    assert exit_code == 1
    assert stdout == ""
    assert stderr == ""


def test_render_stdout_write_error_records_diagnostic(monkeypatch, capfd) -> None:
    monkeypatch.setattr(sys, "stdout", _WriteBrokenStdout())

    exit_code, stdout, stderr = _run_render([], b"Hello {{name}}", monkeypatch, capfd)

    assert exit_code == 1
    assert stdout == ""
    assert stderr == "fstache render: cannot write stdout: I/O error\n"
    assert "Traceback" not in stderr


def _run_render(
    args: list[str],
    stdin: bytes,
    monkeypatch,
    capfd,
) -> tuple[int, str, str]:
    stdin_buffer = io.TextIOWrapper(io.BytesIO(stdin), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    exit_code = main(["render", *args])
    stdout, stderr = capfd.readouterr()

    return exit_code, stdout, stderr


def _run_render_binary(
    args: list[str],
    stdin: bytes,
    monkeypatch,
    capfdbinary,
) -> tuple[int, bytes, bytes]:
    stdin_buffer = io.TextIOWrapper(io.BytesIO(stdin), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    exit_code = main(["render", *args])
    stdout, stderr = capfdbinary.readouterr()

    return exit_code, stdout, stderr


class _BrokenStdout:
    buffer = None

    def __init__(self) -> None:
        self.buffer = _BrokenStdoutBuffer()

    def fileno(self) -> int:
        raise OSError("stdout has no file descriptor")


class _BrokenStdoutBuffer:
    def write(self, content: bytes) -> int:
        raise BrokenPipeError(errno.EPIPE, "Broken pipe")


class _FlushBrokenStdout:
    buffer = None

    def __init__(self) -> None:
        self.buffer = _FlushBrokenStdoutBuffer()

    def fileno(self) -> int:
        raise OSError("stdout has no file descriptor")


class _FlushBrokenStdoutBuffer:
    def write(self, content: bytes) -> int:
        return len(content)

    def flush(self) -> None:
        raise BrokenPipeError(errno.EPIPE, "Broken pipe")


class _WriteBrokenStdout:
    buffer = None

    def __init__(self) -> None:
        self.buffer = _WriteBrokenStdoutBuffer()


class _WriteBrokenStdoutBuffer:
    def write(self, content: bytes) -> int:
        raise OSError(errno.EIO, "I/O error")
