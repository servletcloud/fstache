"""Factory helpers for filesystem-backed Fstache renderers.

The factories return `TemplateRenderer` callables that combine template
discovery, compilation, missing-template handling, missing-variable handling,
and final rendering. `create_renderer` exposes the full option set; the
dev/test/prod helpers are presets with overrideable defaults.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from ._compiler import (
    DEFAULT_DELIMITERS,
    CompiledTemplate,
    Delimiters,
    compile,
)
from ._inliner import inline_partials as _inline_partials
from ._missing import (
    MissingTemplateResolver,
    MissingVariableResolver,
    resolve_missing_template_as_empty,
    resolve_missing_template_as_error,
    resolve_missing_variable_as_error,
    resolve_missing_variable_as_none,
)
from ._renderer import (
    EscapeFunction,
    RenderedTemplate,
    TemplateLoader,
    html_escape,
    render as render_template,
)


class TemplateRenderer(Protocol):
    """Callable renderer returned by the filesystem factory helpers."""

    def __call__(self, name: str, data: object) -> RenderedTemplate:
        """Render the named template with `data` and return rendered output."""

        ...


class _TemplateCompiler(Protocol):
    def __call__(
        self,
        template: bytes,
        *,
        name: str | None = None,
        delimiters: Delimiters = DEFAULT_DELIMITERS,
    ) -> CompiledTemplate: ...


def create_dev_renderer(
    templates_path: str | os.PathLike[str],
    *,
    extension: str = ".mustache",
    remove_extension: bool = False,
    delimiters: Delimiters = DEFAULT_DELIMITERS,
    ignore_indents: bool = False,
    left_trim_source: bool = False,
    preload_templates: bool = False,
    resolve_missing_template: MissingTemplateResolver = resolve_missing_template_as_error,
    resolve_missing_variable: MissingVariableResolver = resolve_missing_variable_as_error,
    escape: EscapeFunction = html_escape,
) -> TemplateRenderer:
    """Create a development-oriented filesystem renderer.

    By default this preset reloads templates from disk on each render
    (`preload_templates=False`) and fails fast for both missing templates and
    missing variables. All `create_renderer` options remain available as
    keyword overrides.
    """

    return create_renderer(
        templates_path,
        extension=extension,
        remove_extension=remove_extension,
        delimiters=delimiters,
        ignore_indents=ignore_indents,
        left_trim_source=left_trim_source,
        preload_templates=preload_templates,
        resolve_missing_template=resolve_missing_template,
        resolve_missing_variable=resolve_missing_variable,
        escape=escape,
    )


def create_test_renderer(
    templates_path: str | os.PathLike[str],
    *,
    extension: str = ".mustache",
    remove_extension: bool = False,
    delimiters: Delimiters = DEFAULT_DELIMITERS,
    ignore_indents: bool = False,
    left_trim_source: bool = False,
    preload_templates: bool = True,
    resolve_missing_template: MissingTemplateResolver = resolve_missing_template_as_error,
    resolve_missing_variable: MissingVariableResolver = resolve_missing_variable_as_error,
    escape: EscapeFunction = html_escape,
) -> TemplateRenderer:
    """Create a test-oriented filesystem renderer.

    By default this preset preloads templates once, fails fast for missing
    templates and missing variables, and keeps normal indentation behavior. All
    `create_renderer` options remain available as keyword overrides.
    """

    return create_renderer(
        templates_path,
        extension=extension,
        remove_extension=remove_extension,
        delimiters=delimiters,
        ignore_indents=ignore_indents,
        left_trim_source=left_trim_source,
        preload_templates=preload_templates,
        resolve_missing_template=resolve_missing_template,
        resolve_missing_variable=resolve_missing_variable,
        escape=escape,
    )


def create_prod_renderer(
    templates_path: str | os.PathLike[str],
    *,
    extension: str = ".mustache",
    remove_extension: bool = False,
    delimiters: Delimiters = DEFAULT_DELIMITERS,
    ignore_indents: bool = True,
    left_trim_source: bool = True,
    preload_templates: bool = True,
    resolve_missing_template: MissingTemplateResolver = resolve_missing_template_as_empty,
    resolve_missing_variable: MissingVariableResolver = resolve_missing_variable_as_none,
    escape: EscapeFunction = html_escape,
) -> TemplateRenderer:
    """Create a production-oriented filesystem renderer.

    By default this preset preloads templates, compiles with
    `ignore_indents=True`, compiles with `left_trim_source=True`, renders
    missing templates as empty, and renders missing variables as empty. All
    `create_renderer` options remain available as keyword overrides.
    """

    return create_renderer(
        templates_path,
        extension=extension,
        remove_extension=remove_extension,
        delimiters=delimiters,
        ignore_indents=ignore_indents,
        left_trim_source=left_trim_source,
        preload_templates=preload_templates,
        resolve_missing_template=resolve_missing_template,
        resolve_missing_variable=resolve_missing_variable,
        escape=escape,
    )


def create_renderer(
    templates_path: str | os.PathLike[str],
    *,
    extension: str = ".mustache",
    remove_extension: bool = False,
    delimiters: Delimiters = DEFAULT_DELIMITERS,
    ignore_indents: bool = False,
    left_trim_source: bool = False,
    preload_templates: bool = True,
    resolve_missing_template: MissingTemplateResolver = resolve_missing_template_as_error,
    resolve_missing_variable: MissingVariableResolver = resolve_missing_variable_as_none,
    escape: EscapeFunction = html_escape,
) -> TemplateRenderer:
    """Create a filesystem-backed template renderer.

    Templates are discovered under `templates_path` with the configured
    `extension`. When `remove_extension` is true, renderer calls and partial
    tags use extensionless names; otherwise names include the extension.

    With `preload_templates=True`, templates are compiled when the renderer is
    created and later file edits are not observed. With `preload_templates=False`,
    root templates and partials are read and compiled at render time.

    Template names that are absolute, traverse through `..`, point to
    directories, resolve outside `templates_path`, or fail the extension mapping
    are treated as missing and passed to `resolve_missing_template`.
    """

    def compile_template(
        template: bytes,
        *,
        name: str | None = None,
        delimiters: Delimiters = DEFAULT_DELIMITERS,
    ) -> CompiledTemplate:
        return compile(
            template,
            name=name,
            delimiters=delimiters,
            ignore_indents=ignore_indents,
            left_trim_source=left_trim_source,
        )

    load_template = _create_template_loader(
        templates_path,
        extension=extension,
        remove_extension=remove_extension,
        delimiters=delimiters,
        compile_template=compile_template,
        inline_partials=ignore_indents,
        preload_templates=preload_templates,
        resolve_missing_template=resolve_missing_template,
    )

    def renderer(name: str, data: object) -> RenderedTemplate:
        return render_template(
            name,
            data,
            load_template,
            compile_template=compile_template,
            resolve_missing_variable=resolve_missing_variable,
            escape=escape,
        )

    return renderer


def _create_template_loader(
    templates_path: str | os.PathLike[str],
    *,
    extension: str,
    remove_extension: bool,
    delimiters: Delimiters,
    compile_template: _TemplateCompiler,
    inline_partials: bool,
    preload_templates: bool,
    resolve_missing_template: MissingTemplateResolver,
) -> TemplateLoader:
    if not preload_templates:
        return _create_live_template_loader(
            templates_path,
            extension=extension,
            remove_extension=remove_extension,
            delimiters=delimiters,
            compile_template=compile_template,
            resolve_missing_template=resolve_missing_template,
        )

    return _create_cached_template_loader(
        templates_path,
        extension=extension,
        remove_extension=remove_extension,
        delimiters=delimiters,
        compile_template=compile_template,
        inline_partials=inline_partials,
        resolve_missing_template=resolve_missing_template,
    )


def _create_cached_template_loader(
    templates_path: str | os.PathLike[str],
    *,
    extension: str,
    remove_extension: bool,
    delimiters: Delimiters,
    compile_template: _TemplateCompiler,
    inline_partials: bool,
    resolve_missing_template: MissingTemplateResolver,
) -> TemplateLoader:
    templates: dict[str, CompiledTemplate] = {}

    for content, name in _iter_template_sources(
        templates_path,
        extension=extension,
        remove_extension=remove_extension,
    ):
        templates[name] = compile_template(content, name=name, delimiters=delimiters)

    if inline_partials:
        templates = _inline_partials(templates)

    def load_template(name: str) -> CompiledTemplate:
        template = templates.get(name)
        if template is not None:
            return template

        return resolve_missing_template(name)

    return load_template


def _create_live_template_loader(
    templates_path: str | os.PathLike[str],
    *,
    extension: str,
    remove_extension: bool,
    delimiters: Delimiters,
    compile_template: _TemplateCompiler,
    resolve_missing_template: MissingTemplateResolver,
) -> TemplateLoader:
    root = Path(templates_path).resolve()
    extension = _normalize_extension(extension)

    def try_load_template(name: str) -> CompiledTemplate | None:
        path = _template_path_for_name(
            root,
            name,
            extension=extension,
            remove_extension=remove_extension,
        )

        if path is None:
            return None

        source_path = _resolve_template_file(root, path)
        if source_path is None:
            return None

        try:
            source = source_path.read_bytes()

            return compile_template(source, name=name, delimiters=delimiters)
        except FileNotFoundError:
            return None

    def load_template(name: str) -> CompiledTemplate:
        template = try_load_template(name)

        return template if template is not None else resolve_missing_template(name)

    return load_template


def _template_path_for_name(
    root: Path,
    name: str,
    *,
    extension: str,
    remove_extension: bool,
) -> Path | None:
    if remove_extension and extension != "":
        path = Path(f"{name}{extension}")
    else:
        path = Path(name)
        if extension != "" and not path.name.endswith(extension):
            return None

    if path.is_absolute() or ".." in path.parts:
        return None

    return root / path


def _iter_template_sources(
    path: str | os.PathLike[str],
    *,
    extension: str,
    remove_extension: bool,
) -> Iterator[tuple[bytes, str]]:
    root = Path(path).resolve()
    extension = _normalize_extension(extension)

    for path in sorted(root.rglob("*")):
        if not path.is_file() or not path.name.endswith(extension):
            continue

        source_path = _resolve_template_file(root, path)
        if source_path is None:
            continue

        name = path.relative_to(root).as_posix()
        if remove_extension and extension != "":
            name = name[: -len(extension)]

        yield source_path.read_bytes(), name


def _resolve_template_file(root: Path, path: Path) -> Path | None:
    try:
        resolved_path = path.resolve()
    except (OSError, RuntimeError):
        return None

    if not resolved_path.is_relative_to(root) or not resolved_path.is_file():
        return None

    return resolved_path


def _normalize_extension(extension: str) -> str:
    if extension.startswith(".") or extension == "":
        return extension

    return f".{extension}"
