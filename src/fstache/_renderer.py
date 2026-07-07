"""Render compiled Fstache templates.

The public renderer API consists of :func:`render`, :func:`html_escape`,
`TemplateLoader`, `EscapeFunction`, `RenderChunk`, `TemplateCompiler`, and
`RenderedTemplate`. The type aliases are documented here because Python type
aliases do not have per-alias runtime docstrings: a `TemplateLoader` receives a
template name and returns a `CompiledTemplate`; an `EscapeFunction` receives raw
bytes and returns escaped bytes; a `RenderChunk` is either `bytes` or
`memoryview`.
"""

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from inspect import Parameter, Signature, signature
from typing import Final, Protocol, runtime_checkable

from ._compiler import (
    DEFAULT_DELIMITERS,
    CompiledTemplate,
    Delimiters,
    DynamicPartialNode,
    InvertedSectionNode,
    Node,
    PartialNode,
    SectionNode,
    TextNode,
    VariableNode,
    _CR_BYTE,
    _CURRENT_CONTEXT_PATH,
    _LF_BYTE,
    _pad_section_raw_body,
    compile,
)
from ._missing import (
    MissingVariableResolver,
    resolve_missing_variable_as_none,
)


_ITERABLE_SECTION_TYPES: Final = (list, tuple)
_POSITIONAL_PARAMETER_KINDS: Final = (
    Parameter.POSITIONAL_ONLY,
    Parameter.POSITIONAL_OR_KEYWORD,
)
_CHUNK_TYPES: Final = (bytes, memoryview)


type TemplateLoader = Callable[[str], CompiledTemplate]
type EscapeFunction = Callable[[bytes], bytes]
type RenderChunk = bytes | memoryview


class TemplateCompiler(Protocol):
    """Compile lambda-produced template bytes during rendering."""

    def __call__(
        self,
        template: bytes,
        *,
        delimiters: Delimiters = DEFAULT_DELIMITERS,
    ) -> CompiledTemplate:
        """Compile `template` using the active render-time delimiters."""

        ...


@runtime_checkable
class RenderedTemplate(Protocol):
    """Rendered output returned by `render` and filesystem renderer factories."""

    def iter_chunks(self) -> Iterator[RenderChunk]:
        """Return a fresh iterator over the rendered bytes-like chunks."""

        ...

    def to_bytes(self) -> bytes:
        """Join all rendered chunks into a single `bytes` value."""

        ...

    def to_string(self, encoding: str = "utf-8", errors: str = "strict") -> str:
        """Decode rendered bytes with strict UTF-8 by default."""

        ...


class _Missing:
    def __bool__(self) -> bool:
        return False


_MISSING: Final = _Missing()


def html_escape(value: bytes) -> bytes:
    """Escape HTML-sensitive bytes for text interpolation.

    The default escaping replaces `&`, `<`, `>`, double quotes, and single
    quotes. The function is used for escaped variable tags and can also serve as
    the baseline for a custom `EscapeFunction`.
    """

    return (
        value.replace(b"&", b"&amp;")
        .replace(b"<", b"&lt;")
        .replace(b">", b"&gt;")
        .replace(b'"', b"&quot;")
        .replace(b"'", b"&#x27;")
    )


def render(
    name: str,
    data: object,
    load_template: TemplateLoader,
    *,
    compile_template: TemplateCompiler = compile,
    resolve_missing_variable: MissingVariableResolver = resolve_missing_variable_as_none,
    escape: EscapeFunction = html_escape,
) -> RenderedTemplate:
    """Render a named compiled template against `data`.

    Args:
        name: Root template name passed to `load_template`.
        data: Root render context. Mappings, object attributes, scalars,
            callables, lists, tuples, bytes, and memoryviews have renderer
            behavior matching Fstache's supported Mustache subset.
        load_template: Callback that receives root and partial template names
            and returns compiled templates. Exceptions from this callback
            propagate unchanged.
        compile_template: Callback used when variable and section lambdas return
            template source that must be compiled during rendering. It must
            accept keyword-only `delimiters`.
        resolve_missing_variable: Callback used when a variable lookup misses.
            Its return value is rendered normally; exceptions propagate
            unchanged.
        escape: Callback applied to escaped interpolation bytes. Unescaped tags
            bypass it.

    Returns:
        A `RenderedTemplate` whose bytes can be consumed with `iter_chunks`,
        `to_bytes`, or `to_string`.
    """

    template = load_template(name)
    renderer = _Renderer(
        _load_template=load_template,
        _compile_template=compile_template,
        _resolve_missing_variable=resolve_missing_variable,
        _escape=escape,
    )
    renderer.render_nodes((data,), None, template)

    return renderer


@dataclass(slots=True)
class _Renderer:
    """Concrete `RenderedTemplate` implementation used internally."""

    _load_template: TemplateLoader
    _compile_template: TemplateCompiler = compile
    _resolve_missing_variable: MissingVariableResolver = (
        resolve_missing_variable_as_none
    )
    _escape: EscapeFunction = html_escape
    _chunks: list[RenderChunk] = field(default_factory=list)
    _at_line_start: bool = True

    def render_nodes(
        self,
        scope_stack: tuple[object, ...],
        indentation: bytes | None,
        nodes: tuple[Node, ...],
        *,
        pad_terminal_empty_line: bool = False,
    ) -> None:
        escape_func = self._escape

        for node in nodes:
            clazz = type(node)

            if clazz is TextNode:
                self.write_template_text(
                    node.value,  # ty: ignore[unresolved-attribute]
                    node.chunks,  # ty: ignore[unresolved-attribute]
                    indentation,
                )
                continue

            if clazz is VariableNode:
                self.render_variable(
                    scope_stack,
                    indentation,
                    node.path,  # ty: ignore[unresolved-attribute]
                    escape=escape_func if node.escape else None,  # ty: ignore[unresolved-attribute]
                )
                continue

            if clazz is SectionNode:
                value = _resolve_section_path(
                    scope_stack,
                    node.path,  # ty: ignore[unresolved-attribute]
                )
                self.render_section_value(
                    scope_stack,
                    indentation,
                    value,
                    node.children,  # ty: ignore[unresolved-attribute]
                    node.raw_body,  # ty: ignore[unresolved-attribute]
                    node.delimiters,  # ty: ignore[unresolved-attribute]
                    node.indentation,  # ty: ignore[unresolved-attribute]
                )
                continue

            if clazz is InvertedSectionNode:
                value = _resolve_section_path(
                    scope_stack,
                    node.path,  # ty: ignore[unresolved-attribute]
                )

                if not value:
                    self.render_nodes(
                        scope_stack,
                        indentation,
                        node.children,  # ty: ignore[unresolved-attribute]
                    )

                continue

            if clazz is PartialNode:
                self.render_partial(
                    scope_stack,
                    indentation,
                    node,  # ty: ignore[invalid-argument-type]
                    node.name,  # ty: ignore[unresolved-attribute]
                )

            if clazz is DynamicPartialNode:
                partial_name = _resolve_partial_name(node.path, scope_stack)  # ty: ignore[unresolved-attribute]

                if partial_name is not None:
                    self.render_partial(
                        scope_stack,
                        indentation,
                        node,  # ty: ignore[invalid-argument-type]
                        partial_name,
                    )

        if (
            pad_terminal_empty_line
            and nodes
            and _allows_terminal_empty_line_padding(nodes[-1])
        ):
            self.pad_left(indentation)

    def render_variable(
        self,
        scope_stack: tuple[object, ...],
        indentation: bytes | None,
        path: tuple[str, ...],
        *,
        escape: EscapeFunction | None,
    ) -> None:
        value = _resolve_variable_path(scope_stack, path)

        if value is _MISSING:
            value = self._resolve_missing_variable(path)

        vtype = type(value)

        if vtype is str or isinstance(value, str):
            encoded = value.encode()  # ty:ignore
            escaped = escape(encoded) if escape is not None else encoded
            self.write_value(escaped, indentation)
            return

        if value is None:
            return

        if vtype is bytes or vtype is memoryview or isinstance(value, _CHUNK_TYPES):
            self.write_value_chunks(
                [value],  # ty:ignore[invalid-argument-type]
                indentation,
                escape=escape,
            )
            return

        if vtype is _Renderer:
            self.write_value_chunks(
                value._chunks,  # ty:ignore[unresolved-attribute]
                indentation,
                escape=escape,
            )
            return

        if callable(value):
            value = value()  # ty:ignore[call-top-callable]

            if value is None:
                return

            if type(value) is _Renderer:
                self.write_value_chunks(
                    value._chunks,
                    indentation,
                    escape=escape,
                )
                return

            vtype = type(value)

            if vtype is bytes or vtype is memoryview or isinstance(value, _CHUNK_TYPES):
                self.write_value_chunks(
                    [value],  # ty:ignore[invalid-argument-type]
                    indentation,
                    escape=escape,
                )
                return

            chunks = self.render_lambda_template(
                scope_stack,
                str(value),
            )
            self.write_value_chunks(
                chunks,
                indentation,
                escape=escape,
            )

            return

        rendered = str(value).encode()
        escaped = escape(rendered) if escape is not None else rendered
        self.write_value(escaped, indentation)

    def render_section_value(
        self,
        scope_stack: tuple[object, ...],
        indentation: bytes | None,
        value,
        children: tuple[Node, ...],
        raw_body: bytes,
        delimiters: Delimiters,
        node_indentation: bytes | None,
    ) -> None:
        if value is True:
            self.render_nodes(
                scope_stack,
                indentation,
                children,
            )
            return

        if not value:
            return

        if isinstance(value, _ITERABLE_SECTION_TYPES):
            for item in value:
                self.render_nodes(
                    scope_stack + (item,),
                    indentation,
                    children,
                )

            return

        if callable(value):
            if _section_callable_can_be_called_without_args(value):
                result = value()

                self.render_section_value(
                    scope_stack,
                    indentation,
                    result,
                    children,
                    raw_body,
                    delimiters,
                    node_indentation,
                )
                return

            self.render_section_lambda(
                scope_stack,
                indentation or node_indentation,
                value,
                _pad_section_raw_body(raw_body, indentation),
                delimiters,
            )
            return

        self.render_nodes(
            scope_stack + (value,),
            indentation,
            children,
        )

    def render_partial(
        self,
        scope_stack: tuple[object, ...],
        indentation: bytes | None,
        node: PartialNode | DynamicPartialNode,
        partial_name: str,
    ) -> None:
        partial = self._load_template(partial_name)
        partial_indentation = (
            indentation
            if node.indentation is None
            else (indentation or b"") + node.indentation
        )

        if node.indentation is not None and partial and partial_indentation:
            self.write_value(partial_indentation, None)

        self.render_nodes(
            scope_stack,
            partial_indentation,
            partial,
            pad_terminal_empty_line=node.indentation is None,
        )

    def render_section_lambda(
        self,
        scope_stack: tuple[object, ...],
        indentation: bytes | None,
        value,
        raw_body: bytes,
        delimiters: Delimiters,
    ) -> None:
        body = raw_body.decode()
        result = value(body)

        if result is None:
            return

        nodes = self._compile_template(str(result).encode(), delimiters=delimiters)
        self.render_nodes(
            scope_stack,
            indentation,
            nodes,
            pad_terminal_empty_line=True,
        )

    def render_lambda_template(
        self,
        scope_stack: tuple[object, ...],
        value: str,
    ) -> list[RenderChunk]:
        nodes = self._compile_template(value.encode(), delimiters=DEFAULT_DELIMITERS)
        renderer = _Renderer(
            _load_template=self._load_template,
            _compile_template=self._compile_template,
            _resolve_missing_variable=self._resolve_missing_variable,
            _escape=self._escape,
        )
        renderer.render_nodes(scope_stack, None, nodes)

        return renderer._chunks

    def write_template_text(
        self,
        value: bytes,
        chunks: tuple[bytes, ...],
        indentation: bytes | None,
    ) -> None:
        if indentation:
            for chunk in chunks:
                if self._at_line_start:
                    self._chunks.append(indentation)

                self._chunks.append(chunk)

                last_byte = chunk[-1]
                self._at_line_start = last_byte == _LF_BYTE or last_byte == _CR_BYTE

            return

        self._chunks.append(value)
        last_byte = value[-1]
        self._at_line_start = last_byte == _LF_BYTE or last_byte == _CR_BYTE

    def write_value(self, value: RenderChunk | None, indentation: bytes | None) -> None:
        if not value:
            return

        if self._at_line_start and indentation:
            self._chunks.append(indentation)

        self._chunks.append(value)
        self._at_line_start = False

    def write_value_chunks(
        self,
        chunks: list[RenderChunk],
        indentation: bytes | None,
        *,
        escape: EscapeFunction | None,
    ) -> None:
        if not chunks:
            return

        if self._at_line_start and indentation:
            self._chunks.append(indentation)

        if escape is not None:
            self._chunks.extend(escape(bytes(chunk)) for chunk in chunks)
        else:
            self._chunks.extend(chunks)

        self._at_line_start = False

    def pad_left(self, indentation: bytes | None) -> None:
        if self._at_line_start and indentation:
            self._chunks.append(indentation)
            self._at_line_start = False

    def iter_chunks(self) -> Iterator[RenderChunk]:
        """Return a fresh iterator over accumulated render chunks."""

        return iter(self._chunks)

    def to_bytes(self) -> bytes:
        """Join accumulated render chunks into bytes."""

        return b"".join(self._chunks)

    def to_string(self, encoding: str = "utf-8", errors: str = "strict") -> str:
        """Decode accumulated render bytes with the requested error policy."""

        return self.to_bytes().decode(encoding, errors)

    def __repr__(self) -> str:
        return f"_Renderer(chunks={len(self._chunks)})"


def _resolve_partial_name(
    path: tuple[str, ...], scope_stack: tuple[object, ...]
) -> str | None:
    value = _resolve_variable_path(scope_stack, path)

    if value is _MISSING or value is None:
        return None

    if callable(value):
        value = value()

    return str(value)


def _section_callable_can_be_called_without_args(
    value: Callable[..., object],
) -> bool:
    try:
        callable_signature = signature(value)
    except (TypeError, ValueError):
        return False

    required_positional_count = sum(
        1
        for parameter in callable_signature.parameters.values()
        if parameter.kind in _POSITIONAL_PARAMETER_KINDS
        and parameter.default is Signature.empty
    )

    return required_positional_count == 0


def _resolve_section_path(
    scope_stack: tuple[object, ...], path: tuple[str, ...]
) -> object:
    if path == _CURRENT_CONTEXT_PATH:
        return scope_stack[-1]

    value = _resolve_first_path_part(scope_stack, path[0])

    if len(path) == 1 or value is _MISSING:
        return value

    index = 1
    path_len = len(path)

    while index < path_len:
        part = path[index]
        if callable(value):
            value = value()  # ty:ignore
        value = _resolve_path_part(value, part)
        if value is _MISSING:
            return _MISSING

        index += 1

    return value


def _resolve_variable_path(scope_stack: tuple[object, ...], path: tuple[str, ...]):
    if path == _CURRENT_CONTEXT_PATH:
        return scope_stack[-1]

    value = _resolve_first_path_part(scope_stack, path[0])

    if len(path) == 1 or value is _MISSING:
        return value

    index = 1
    path_len = len(path)

    while index < path_len:
        part = path[index]
        if callable(value):
            value = value()  # ty:ignore
        value = _resolve_path_part(value, part)

        if value is _MISSING:
            return _MISSING

        index += 1

    return value


def _resolve_first_path_part(scope_stack: tuple[object, ...], part: str) -> object:
    index = len(scope_stack) - 1

    while index >= 0:
        value = _resolve_path_part(scope_stack[index], part)

        if value is not _MISSING:
            return value

        index -= 1

    return _MISSING


def _resolve_path_part(value, part: str):
    return (
        value.get(part, _MISSING)
        if type(value) is dict or isinstance(value, Mapping)
        else getattr(value, part, _MISSING)
    )


def _allows_terminal_empty_line_padding(node: Node) -> bool:
    clazz = type(node)
    is_partial = clazz is PartialNode or clazz is DynamicPartialNode

    return not is_partial or node.indentation  # ty: ignore[invalid-return-type,unresolved-attribute]
