"""Command-line interface for Fstache."""

import argparse
import errno
import json
import os
import sys
from pathlib import Path
from typing import Final, TextIO

from ._compiler import (
    DEFAULT_DELIMITERS,
    EMPTY_TEMPLATE,
    CompiledTemplate,
    Delimiters,
    TemplateSyntaxError,
    compile,
)
from ._factories import _create_template_loader
from ._renderer import render


_ROOT_TEMPLATE_NAME: Final = "<stdin>"
_PROGRAM_NAME: Final = "fstache"
_RENDER_COMMAND_NAME: Final = "render"
_STDOUT_NAME: Final = "stdout"


class _RenderDiagnostics:
    def __init__(self) -> None:
        self._missing_variables: list[str] = []
        self._missing_templates: list[str] = []
        self._seen_missing_variables: set[str] = set()
        self._seen_missing_templates: set[str] = set()

    @property
    def has_missing_values(self) -> bool:
        return bool(self._missing_variables or self._missing_templates)

    def resolve_missing_variable(self, path: tuple[str, ...]) -> object:
        name = ".".join(path)
        if name not in self._seen_missing_variables:
            self._seen_missing_variables.add(name)
            self._missing_variables.append(name)

        return None

    def resolve_missing_template(self, name: str) -> CompiledTemplate:
        if name not in self._seen_missing_templates:
            self._seen_missing_templates.add(name)
            self._missing_templates.append(name)

        return EMPTY_TEMPLATE

    def write_to(self, stderr: TextIO) -> None:
        for name in self._missing_variables:
            print(
                f"{_PROGRAM_NAME} {_RENDER_COMMAND_NAME}: "
                f"missing template variable: {name}",
                file=stderr,
            )

        for name in self._missing_templates:
            print(
                f"{_PROGRAM_NAME} {_RENDER_COMMAND_NAME}: missing template: {name}",
                file=stderr,
            )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    return args.func(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=_PROGRAM_NAME)
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser(
        _RENDER_COMMAND_NAME,
        help="render a Mustache template from stdin",
    )
    render_parser.add_argument(
        "--data",
        metavar="PATH",
        type=Path,
        help="read JSON render data from PATH",
    )
    render_parser.add_argument(
        "--extension",
        metavar="EXT",
        default=".mustache",
        help="template file extension used for partial discovery",
    )
    render_parser.add_argument(
        "--remove-extension",
        action="store_true",
        help="partial names omit the configured extension",
    )
    render_parser.set_defaults(func=_render_command)

    return parser


def _render_command(args: argparse.Namespace) -> int:
    data = _read_data(args.data)
    if isinstance(data, _CommandError):
        print(data.message, file=sys.stderr)

        return 1

    diagnostics = _RenderDiagnostics()

    try:
        template_source = _read_stdin_bytes(sys.stdin)
        rendered = _render_stdin_template(
            template_source,
            data,
            extension=args.extension,
            remove_extension=args.remove_extension,
            diagnostics=diagnostics,
        ).to_bytes()
    except TemplateSyntaxError as exc:
        print(f"{_PROGRAM_NAME} {_RENDER_COMMAND_NAME}: {exc}", file=sys.stderr)

        return 1
    except OSError as exc:
        print(_format_read_error(exc), file=sys.stderr)

        return 1

    write_exit_code = _write_stdout(sys.stdout, rendered)
    if write_exit_code != 0:
        return write_exit_code

    if diagnostics.has_missing_values:
        diagnostics.write_to(sys.stderr)

        return 1

    return 0


def _render_stdin_template(
    template_source: bytes,
    data: object,
    *,
    extension: str,
    remove_extension: bool,
    diagnostics: _RenderDiagnostics,
):
    def compile_template(
        template: bytes,
        *,
        name: str | None = None,
        delimiters: Delimiters = DEFAULT_DELIMITERS,
    ) -> CompiledTemplate:
        return compile(template, name=name, delimiters=delimiters)

    root_template = compile_template(template_source, name=_ROOT_TEMPLATE_NAME)
    partial_loader = _create_template_loader(
        Path.cwd(),
        extension=extension,
        remove_extension=remove_extension,
        delimiters=DEFAULT_DELIMITERS,
        compile_template=compile_template,
        inline_partials=False,
        preload_templates=False,
        resolve_missing_template=diagnostics.resolve_missing_template,
    )

    root_template_loaded = False

    def load_template(name: str) -> CompiledTemplate:
        nonlocal root_template_loaded
        if not root_template_loaded and name == _ROOT_TEMPLATE_NAME:
            root_template_loaded = True

            return root_template

        return partial_loader(name)

    return render(
        _ROOT_TEMPLATE_NAME,
        data,
        load_template,
        compile_template=compile_template,
        resolve_missing_variable=diagnostics.resolve_missing_variable,
    )


class _CommandError:
    def __init__(self, message: str) -> None:
        self.message = message


def _read_data(path: Path | None) -> object | _CommandError:
    if path is None:
        return {}

    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        return _CommandError(
            f"{_PROGRAM_NAME} {_RENDER_COMMAND_NAME}: invalid JSON in {path}: "
            f"{exc.msg} at line {exc.lineno}, column {exc.colno}"
        )
    except UnicodeDecodeError as exc:
        return _CommandError(
            f"{_PROGRAM_NAME} {_RENDER_COMMAND_NAME}: cannot read {path}: "
            f"invalid UTF-8 ({exc.reason})"
        )
    except OSError as exc:
        return _CommandError(_format_read_error(exc, fallback_path=path))


def _format_read_error(exc: OSError, *, fallback_path: Path | None = None) -> str:
    path = exc.filename or fallback_path
    if path is None:
        return f"{_PROGRAM_NAME} {_RENDER_COMMAND_NAME}: cannot read input: {exc}"

    return (
        f"{_PROGRAM_NAME} {_RENDER_COMMAND_NAME}: cannot read {path}: "
        f"{exc.strerror or exc}"
    )


def _write_stdout(stdout: TextIO, content: bytes) -> int:
    try:
        buffer = stdout.buffer
        buffer.write(content)
        buffer.flush()
    except BrokenPipeError:
        _silence_stdout_flush(stdout)

        return 1
    except OSError as exc:
        if exc.errno == errno.EPIPE:
            _silence_stdout_flush(stdout)

            return 1

        print(_format_write_error(exc), file=sys.stderr)

        return 1

    return 0


def _format_write_error(exc: OSError) -> str:
    return (
        f"{_PROGRAM_NAME} {_RENDER_COMMAND_NAME}: cannot write {_STDOUT_NAME}: "
        f"{exc.strerror or exc}"
    )


def _silence_stdout_flush(stdout: TextIO) -> None:
    try:
        stdout_fd = stdout.fileno()
    except (AttributeError, OSError, ValueError):
        return

    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull_fd, stdout_fd)
        finally:
            os.close(devnull_fd)
    except OSError:
        return


def _read_stdin_bytes(stdin: TextIO) -> bytes:
    buffer = getattr(stdin, "buffer", None)
    if buffer is not None:
        return buffer.read()

    content = stdin.read()
    if type(content) is bytes:
        return content

    return content.encode()


if __name__ == "__main__":
    raise SystemExit(main())
