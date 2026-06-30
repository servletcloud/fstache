"""Compile bytes templates into Fstache's internal render tree.

The public compiler surface is intentionally small: :func:`compile`,
:class:`Delimiters`, the `TemplateSyntaxError` hierarchy, `CompiledTemplate`,
`DEFAULT_DELIMITERS`, and `EMPTY_TEMPLATE`. `CompiledTemplate` is a type alias
for the current internal node tuple, but callers should normally treat it as an
opaque value produced by :func:`compile` and consumed by renderers, loaders, and
missing-template resolvers.
"""

from dataclasses import dataclass
from typing import Final, Self


_TAG_START: Final[bytes] = b"{{"
_TAG_END: Final[bytes] = b"}}"
_TRIPLE_TAG_START: Final[bytes] = b"{{{"
_TRIPLE_TAG_END: Final[bytes] = b"}}}"
_SECTION_START_SIGIL: Final[bytes] = b"#"
_INVERTED_SECTION_START_SIGIL: Final[bytes] = b"^"
_SECTION_END_SIGIL: Final[bytes] = b"/"
_PARTIAL_SIGIL: Final[bytes] = b">"
_UNESCAPED_VARIABLE_SIGIL: Final[bytes] = b"&"
_COMMENT_SIGIL: Final[bytes] = b"!"
_SET_DELIMITER_SIGIL: Final[bytes] = b"="
_DYNAMIC_PARTIAL_SIGIL: Final[bytes] = b"*"
_UNSUPPORTED_TAG_SIGILS: Final[frozenset[bytes]] = frozenset({b"{", b"$", b"<"})
_STANDALONE_TAG_SIGILS: Final[frozenset[bytes]] = frozenset(
    {
        _SECTION_START_SIGIL,
        _INVERTED_SECTION_START_SIGIL,
        _SECTION_END_SIGIL,
        _PARTIAL_SIGIL,
        _COMMENT_SIGIL,
        _SET_DELIMITER_SIGIL,
    }
)
_TAG_SIGIL_WIDTH: Final[int] = 1  # leading tag type marker
_ROOT_STACK_DEPTH: Final[int] = 1  # parser frame depth without open sections
_LINE_SPACE_BYTES: Final[bytes] = b" \t"
_LF: Final[bytes] = b"\n"
_CR: Final[bytes] = b"\r"
_CRLF: Final[bytes] = b"\r\n"
_LF_BYTE: Final[int] = _LF[0]
_CR_BYTE: Final[int] = _CR[0]
_COMMENT_CLOSE_PADDING_BYTES: Final[bytes] = b" \t\r\n"
_DELIMITER_WHITESPACE_BYTES: Final[bytes] = b" \t\r\n\v\f"
_NAME_WHITESPACE_BYTES: Final[bytes] = b" \t\r\n\v\f"
_CURRENT_CONTEXT_PATH: Final[tuple[str, ...]] = (".",)
_SYNTAX_EXCERPT_MAX_CHARS: Final[int] = 80
_SYNTAX_EXCERPT_MAX_BYTES: Final[int] = 160


class TemplateSyntaxError(ValueError):
    """Base error raised for invalid or unsupported template syntax.

    Attributes:
        reason: Human-readable reason without source-location context.
        line: One-based line number when the compiler can locate the error.
        column: One-based column number when the compiler can locate the error.
        offset: Zero-based byte offset into the template when available.
        excerpt: Short escaped source excerpt around the offending tag.
        template_name: Optional caller-provided template name from `compile`.
        kind: Stable machine-oriented error kind for specialized subclasses.
    """

    _default_kind: str | None = None

    def __init__(
        self,
        reason: str,
        *,
        line: int | None = None,
        column: int | None = None,
        offset: int | None = None,
        excerpt: str | None = None,
        template_name: str | None = None,
        kind: str | None = None,
    ) -> None:
        self.reason = reason
        self.line = line
        self.column = column
        self.offset = offset
        self.excerpt = excerpt
        self.template_name = template_name
        self.kind = kind if kind is not None else self._default_kind
        super().__init__(reason)

    def __str__(self) -> str:
        if self.line is None or self.column is None or self.offset is None:
            if self.template_name is None:
                return self.reason

            return f"{self.reason} in {self.template_name}"

        message = (
            f"{self.reason} at line {self.line}, column {self.column} "
            f"(offset {self.offset})"
        )
        if self.template_name is not None:
            message = f"{message} in {self.template_name}"

        if self.excerpt is not None:
            message = f'{message}: near "{self.excerpt}"'

        return message


class UnclosedTagError(TemplateSyntaxError):
    """Raised when a tag is missing its closing delimiter.

    The default `kind` is `"unclosed_tag"`.
    """

    _default_kind: str | None = "unclosed_tag"


class SectionSyntaxError(TemplateSyntaxError):
    """Raised when section nesting or closing syntax is invalid.

    This covers unopened section closes, mismatched section closes, and
    unclosed sections. The default `kind` is `"section_syntax"`.
    """

    _default_kind: str | None = "section_syntax"


class UnsupportedTagError(TemplateSyntaxError):
    """Raised when Fstache sees a known unsupported Mustache tag family.

    The default `kind` is `"unsupported_tag"`.
    """

    _default_kind: str | None = "unsupported_tag"


class InvalidNameError(TemplateSyntaxError):
    """Raised when a variable, section, or partial name is invalid.

    The default `kind` is `"invalid_name"`.
    """

    _default_kind: str | None = "invalid_name"


class InvalidDelimiterError(TemplateSyntaxError):
    """Raised when a delimiter declaration is invalid.

    The default `kind` is `"invalid_delimiter"`.
    """

    _default_kind: str | None = "invalid_delimiter"


@dataclass(frozen=True, slots=True)
class Delimiters:
    """Opening and closing delimiters used while compiling a template.

    Delimiters must be non-empty `bytes`, may not contain whitespace, and may
    not contain the delimiter-change marker `b"="`. Invalid values raise
    `InvalidDelimiterError` during construction.
    """

    start: bytes
    end: bytes

    def __post_init__(self) -> None:
        for delimiter in (self.start, self.end):
            if (
                not isinstance(delimiter, bytes)
                or not delimiter
                or _SET_DELIMITER_SIGIL in delimiter
                or any(byte in _DELIMITER_WHITESPACE_BYTES for byte in delimiter)
            ):
                msg = "invalid delimiter declaration"
                raise InvalidDelimiterError(msg)


DEFAULT_DELIMITERS: Final[Delimiters] = Delimiters(start=_TAG_START, end=_TAG_END)


@dataclass(frozen=True, slots=True)
class TextNode:
    """Compiled literal template text.

    This is an internal compiled-template node. `value` stores the original text
    bytes, while `chunks` splits line endings for indentation-aware rendering.
    """

    chunks: tuple[bytes, ...]
    value: bytes

    @classmethod
    def from_bytes(cls, value: bytes) -> Self:
        """Build a text node with line-break chunks derived from `value`."""

        return cls(chunks=_split_template_text(value), value=value)


@dataclass(frozen=True, slots=True)
class VariableNode:
    """Compiled variable interpolation node.

    This is an internal compiled-template node. `path` is the dotted lookup path
    split into parts, and `escape` controls whether the renderer applies the
    configured escape function.
    """

    path: tuple[str, ...]
    escape: bool = True


@dataclass(frozen=True, slots=True)
class SectionNode:
    """Compiled truthy section node.

    This is an internal compiled-template node. `raw_body` and `delimiters` are
    preserved so section lambdas can recompile their returned template text with
    the delimiter state active at the original section.
    """

    path: tuple[str, ...]
    children: tuple["Node", ...]
    raw_body: bytes
    delimiters: Delimiters
    indentation: bytes | None = None


@dataclass(frozen=True, slots=True)
class InvertedSectionNode:
    """Compiled inverted section node rendered when its value is falsey."""

    path: tuple[str, ...]
    children: tuple["Node", ...]


@dataclass(frozen=True, slots=True)
class PartialNode:
    """Compiled static partial node.

    `name` is passed to the render-time template loader. `indentation` stores
    standalone partial indentation when indentation handling is enabled.
    """

    name: str
    indentation: bytes | None


@dataclass(frozen=True, slots=True)
class DynamicPartialNode:
    """Compiled dynamic partial node resolved from data at render time."""

    path: tuple[str, ...]
    indentation: bytes | None


type Node = (
    TextNode
    | VariableNode
    | SectionNode
    | InvertedSectionNode
    | PartialNode
    | DynamicPartialNode
)


type CompiledTemplate = tuple[Node, ...]


EMPTY_TEMPLATE: Final[CompiledTemplate] = ()


@dataclass(slots=True)
class _ParseFrame:
    path: tuple[str, ...]
    children: list[Node]
    is_inverted: bool
    raw_body_start: int
    body_delimiters: Delimiters
    opening_tag_offset: int
    opening_tag_end: int


@dataclass(frozen=True, slots=True)
class _StandaloneTag:
    text_before_tag: bytes
    position: int
    indentation: bytes


def compile(
    template: bytes,
    *,
    name: str | None = None,
    delimiters: Delimiters = DEFAULT_DELIMITERS,
    ignore_indents: bool = False,
    left_trim_source: bool = False,
) -> CompiledTemplate:
    """Compile a bytes template into a `CompiledTemplate`.

    Args:
        template: Template source as `bytes`.
        name: Optional template name included in syntax-error messages.
        delimiters: Initial tag delimiters. Delimiter-change tags in the
            template may update the active delimiters while parsing.
        ignore_indents: Disable standalone-partial indentation tracking and keep
            text nodes as single chunks.
        left_trim_source: Remove leading spaces and tabs from every source line
            before parsing. This is mainly useful for compact production output.

    Returns:
        An opaque compiled template suitable for `render`, template loaders,
        missing-template resolvers, and `inline_partials`.

    Raises:
        TypeError: If `template` is not bytes-like enough for bytes operations.
        TemplateSyntaxError: If the template uses invalid or unsupported syntax.
    """

    if left_trim_source:
        template = _left_trim_source_lines(template)

    root = _ParseFrame(
        path=(),
        children=[],
        is_inverted=False,
        raw_body_start=0,
        body_delimiters=delimiters,
        opening_tag_offset=0,
        opening_tag_end=0,
    )
    stack = [root]
    position = 0
    delimiters = delimiters

    while True:
        tag_start = template.find(delimiters.start, position)
        if tag_start < 0:
            _append_text(stack[-1], template[position:], ignore_indents=ignore_indents)
            break

        text_before_tag = template[position:tag_start]

        if delimiters == DEFAULT_DELIMITERS and template.startswith(
            _TRIPLE_TAG_START, tag_start
        ):
            _append_text(stack[-1], text_before_tag, ignore_indents=ignore_indents)
            tag_content_start = tag_start + len(_TRIPLE_TAG_START)
            tag_end = template.find(_TRIPLE_TAG_END, tag_content_start)
            if tag_end < 0:
                msg = "unclosed triple tag"
                raise _syntax_error(
                    UnclosedTagError,
                    msg,
                    template,
                    tag_start,
                    template_name=name,
                )

            tag_content = template[tag_content_start:tag_end].strip()
            tag_close_end = tag_end + len(_TRIPLE_TAG_END)
            try:
                path = _parse_dotted_name(tag_content)
            except TemplateSyntaxError as exc:
                raise _with_tag_context(
                    exc,
                    template,
                    tag_start,
                    tag_close_end,
                    template_name=name,
                ) from exc

            stack[-1].children.append(VariableNode(path=path, escape=False))
            position = tag_close_end
            continue

        tag_content_start = tag_start + len(delimiters.start)
        tag_sigil = template[tag_content_start : tag_content_start + _TAG_SIGIL_WIDTH]
        is_comment_tag = tag_sigil == _COMMENT_SIGIL
        if is_comment_tag:
            tag_end = _find_comment_tag_end(template, tag_content_start, delimiters.end)
        else:
            tag_end = template.find(delimiters.end, tag_content_start)

        if tag_end < 0:
            msg = "unclosed tag"
            raise _syntax_error(
                UnclosedTagError,
                msg,
                template,
                tag_start,
                template_name=name,
            )

        tag_content = template[tag_content_start:tag_end].strip()
        tag_close_end = tag_end + len(delimiters.end)
        if tag_sigil in _STANDALONE_TAG_SIGILS:
            standalone_tag = _parse_standalone_tag(
                template, text_before_tag, tag_start, tag_close_end
            )
            if standalone_tag is not None:
                text_before_tag = standalone_tag.text_before_tag
                partial_indentation = (
                    None if ignore_indents else standalone_tag.indentation
                )
                position = standalone_tag.position
                _append_text(stack[-1], text_before_tag, ignore_indents=ignore_indents)
            else:
                partial_indentation = None
                _append_text(stack[-1], text_before_tag, ignore_indents=ignore_indents)
                position = tag_close_end
        else:
            partial_indentation = None
            _append_text(stack[-1], text_before_tag, ignore_indents=ignore_indents)
            position = tag_end + len(delimiters.end)

        next_delimiters = _parse_tag(
            stack,
            tag_content,
            template=template,
            section_body_start=position,
            section_body_end=tag_start,
            section_delimiters=delimiters,
            partial_indentation=partial_indentation,
            tag_start=tag_start,
            tag_close_end=tag_close_end,
            template_name=name,
        )
        if next_delimiters is not None:
            delimiters = next_delimiters

    if len(stack) != _ROOT_STACK_DEPTH:
        open_section = ".".join(stack[-1].path)
        msg = f"unclosed section: {open_section}"
        raise _syntax_error(
            SectionSyntaxError,
            msg,
            template,
            stack[-1].opening_tag_offset,
            excerpt_end=stack[-1].opening_tag_end,
            template_name=name,
        )

    return tuple(root.children)


def _parse_tag(
    stack: list[_ParseFrame],
    tag_content: bytes,
    *,
    template: bytes,
    section_body_start: int,
    section_body_end: int,
    section_delimiters: Delimiters,
    partial_indentation: bytes | None,
    tag_start: int,
    tag_close_end: int,
    template_name: str | None,
) -> Delimiters | None:
    try:
        return _parse_tag_content(
            stack,
            tag_content,
            template=template,
            section_body_start=section_body_start,
            section_body_end=section_body_end,
            section_delimiters=section_delimiters,
            partial_indentation=partial_indentation,
            tag_start=tag_start,
            tag_close_end=tag_close_end,
        )
    except TemplateSyntaxError as exc:
        if exc.offset is not None:
            raise

        raise _with_tag_context(
            exc,
            template,
            tag_start,
            tag_close_end,
            template_name=template_name,
        ) from exc


def _parse_tag_content(
    stack: list[_ParseFrame],
    tag_content: bytes,
    *,
    template: bytes,
    section_body_start: int,
    section_body_end: int,
    section_delimiters: Delimiters,
    partial_indentation: bytes | None,
    tag_start: int,
    tag_close_end: int,
) -> Delimiters | None:
    sigil = tag_content[:_TAG_SIGIL_WIDTH]

    if sigil in _UNSUPPORTED_TAG_SIGILS:
        msg = "unsupported tag"
        raise UnsupportedTagError(msg)

    if sigil == _SECTION_START_SIGIL:
        path = _parse_dotted_name(tag_content[_TAG_SIGIL_WIDTH:].strip())
        stack.append(
            _ParseFrame(
                path=path,
                children=[],
                is_inverted=False,
                raw_body_start=section_body_start,
                body_delimiters=section_delimiters,
                opening_tag_offset=tag_start,
                opening_tag_end=tag_close_end,
            )
        )
        return

    if sigil == _INVERTED_SECTION_START_SIGIL:
        path = _parse_dotted_name(tag_content[_TAG_SIGIL_WIDTH:].strip())
        stack.append(
            _ParseFrame(
                path=path,
                children=[],
                is_inverted=True,
                raw_body_start=section_body_start,
                body_delimiters=section_delimiters,
                opening_tag_offset=tag_start,
                opening_tag_end=tag_close_end,
            )
        )
        return

    if sigil == _SECTION_END_SIGIL:
        if len(stack) == _ROOT_STACK_DEPTH:
            msg = "unopened section close"
            raise SectionSyntaxError(msg)

        frame = stack.pop()
        path = _parse_dotted_name(tag_content[_TAG_SIGIL_WIDTH:].strip())
        if frame.path != path:
            expected_name = ".".join(frame.path)
            actual_name = ".".join(path)
            msg = (
                f"mismatched section close: expected {expected_name}, got {actual_name}"
            )
            raise SectionSyntaxError(msg)

        if frame.is_inverted:
            node = InvertedSectionNode(path=frame.path, children=tuple(frame.children))
        else:
            node = SectionNode(
                path=frame.path,
                children=tuple(frame.children),
                raw_body=template[frame.raw_body_start : section_body_end],
                delimiters=frame.body_delimiters,
            )

        stack[-1].children.append(node)
        return

    if sigil == _UNESCAPED_VARIABLE_SIGIL:
        stack[-1].children.append(
            VariableNode(
                path=_parse_dotted_name(tag_content[_TAG_SIGIL_WIDTH:].strip()),
                escape=False,
            )
        )
        return

    if sigil == _COMMENT_SIGIL:
        return

    if sigil == _PARTIAL_SIGIL:
        raw_name = tag_content[_TAG_SIGIL_WIDTH:].strip()
        if raw_name.startswith(_DYNAMIC_PARTIAL_SIGIL):
            stack[-1].children.append(
                DynamicPartialNode(
                    path=_parse_dotted_name(raw_name[_TAG_SIGIL_WIDTH:].strip()),
                    indentation=partial_indentation,
                )
            )
        else:
            stack[-1].children.append(
                PartialNode(
                    name=_parse_partial_name(raw_name),
                    indentation=partial_indentation,
                )
            )

        return

    if sigil == _SET_DELIMITER_SIGIL:
        return _parse_set_delimiters(tag_content)

    stack[-1].children.append(VariableNode(path=_parse_dotted_name(tag_content)))


def _parse_partial_name(raw_name: bytes) -> str:
    if not raw_name:
        msg = "empty partial name"
        raise InvalidNameError(msg)

    if any(byte in _NAME_WHITESPACE_BYTES for byte in raw_name):
        msg = "invalid partial name"
        raise InvalidNameError(msg)

    try:
        return raw_name.decode()
    except UnicodeDecodeError as exc:
        msg = "partial name must be valid UTF-8"
        raise InvalidNameError(msg) from exc


def _pad_section_raw_body(value: bytes, indentation: bytes | None) -> bytes:
    if not indentation or (_LF not in value and _CR not in value):
        return value

    value_len = len(value)
    chunks: list[bytes] = []
    position = 0
    index = 0
    while index < value_len:
        byte = value[index]
        if byte == _CR_BYTE and index + 1 < value_len and value[index + 1] == _LF_BYTE:
            line_break_end = index + len(_CRLF)
        elif byte == _CR_BYTE or byte == _LF_BYTE:
            line_break_end = index + 1
        else:
            index += 1
            continue

        chunks.append(value[position:line_break_end])
        chunks.append(indentation)

        position = line_break_end
        index = line_break_end

    chunks.append(value[position:])

    return b"".join(chunks)


def _parse_set_delimiters(tag_content: bytes) -> Delimiters:
    if not tag_content.endswith(_SET_DELIMITER_SIGIL):
        msg = "invalid delimiter declaration"
        raise InvalidDelimiterError(msg)

    raw_delimiters = tag_content[
        _TAG_SIGIL_WIDTH : len(tag_content) - len(_SET_DELIMITER_SIGIL)
    ].strip()
    delimiters = raw_delimiters.split()
    if len(delimiters) != 2:
        msg = "invalid delimiter declaration"
        raise InvalidDelimiterError(msg)

    start_delimiter, end_delimiter = delimiters

    return Delimiters(start=start_delimiter, end=end_delimiter)


def _find_comment_tag_end(
    template: bytes, tag_content_start: int, tag_end_delimiter: bytes
) -> int:
    tag_end = template.find(tag_end_delimiter, tag_content_start)
    if tag_end < 0:
        return tag_end

    next_position = tag_end + len(tag_end_delimiter)
    while (
        next_position < len(template)
        and template[next_position] in _COMMENT_CLOSE_PADDING_BYTES
    ):
        next_position += 1

    if template.startswith(tag_end_delimiter, next_position):
        return next_position

    return tag_end


def _parse_standalone_tag(
    template: bytes, text_before_tag: bytes, tag_start: int, tag_close_end: int
) -> _StandaloneTag | None:
    line_start = _line_start_position(template, tag_start)
    indentation = template[line_start:tag_start]
    if any(byte not in _LINE_SPACE_BYTES for byte in indentation):
        return None

    indentation_start = len(text_before_tag) - len(indentation)
    if indentation_start < 0 or text_before_tag[indentation_start:] != indentation:
        return None

    trim_end = tag_close_end
    while trim_end < len(template) and template[trim_end] in _LINE_SPACE_BYTES:
        trim_end += 1

    if trim_end == len(template):
        return _StandaloneTag(
            text_before_tag=text_before_tag[:indentation_start],
            position=trim_end,
            indentation=indentation,
        )

    if template.startswith(_CRLF, trim_end):
        return _StandaloneTag(
            text_before_tag=text_before_tag[:indentation_start],
            position=trim_end + len(_CRLF),
            indentation=indentation,
        )

    if template.startswith(_LF, trim_end):
        return _StandaloneTag(
            text_before_tag=text_before_tag[:indentation_start],
            position=trim_end + len(_LF),
            indentation=indentation,
        )

    return None


def _line_start_position(value: bytes, position: int) -> int:
    last_line_feed = value.rfind(_LF, 0, position)
    last_carriage_return = value.rfind(_CR, 0, position)
    line_break_start = max(last_line_feed, last_carriage_return)
    if line_break_start < 0:
        return 0

    return line_break_start + 1


def _syntax_error(
    error_type: type[TemplateSyntaxError],
    reason: str,
    template: bytes,
    offset: int,
    *,
    excerpt_start: int | None = None,
    excerpt_end: int | None = None,
    template_name: str | None = None,
) -> TemplateSyntaxError:
    line, column = _line_column_for_offset(template, offset)
    excerpt = _syntax_excerpt(
        template,
        offset if excerpt_start is None else excerpt_start,
        _syntax_excerpt_end(template, offset) if excerpt_end is None else excerpt_end,
    )

    return error_type(
        reason,
        line=line,
        column=column,
        offset=offset,
        excerpt=excerpt,
        template_name=template_name,
    )


def _with_tag_context(
    error: TemplateSyntaxError,
    template: bytes,
    tag_start: int,
    tag_close_end: int,
    *,
    template_name: str | None,
) -> TemplateSyntaxError:
    line, column = _line_column_for_offset(template, tag_start)

    return type(error)(
        error.reason,
        line=line,
        column=column,
        offset=tag_start,
        excerpt=_syntax_excerpt(template, tag_start, tag_close_end),
        template_name=template_name,
        kind=error.kind,
    )


def _line_column_for_offset(template: bytes, offset: int) -> tuple[int, int]:
    line = _line_number_for_offset(template, offset)
    line_start = _line_start_position(template, offset)
    column = len(template[line_start:offset].decode(errors="replace")) + 1

    return line, column


def _line_number_for_offset(template: bytes, offset: int) -> int:
    line = 1
    index = 0
    while index < offset:
        byte = template[index]
        if byte == _CR_BYTE and index + 1 < offset and template[index + 1] == _LF_BYTE:
            line += 1
            index += len(_CRLF)
            continue

        if byte == _CR_BYTE or byte == _LF_BYTE:
            line += 1

        index += 1

    return line


def _syntax_excerpt_end(template: bytes, offset: int) -> int:
    line_feed = template.find(_LF, offset)
    carriage_return = template.find(_CR, offset)
    line_breaks = [
        position for position in (line_feed, carriage_return) if position >= 0
    ]
    if line_breaks:
        return min(line_breaks)

    return min(len(template), offset + _SYNTAX_EXCERPT_MAX_BYTES)


def _syntax_excerpt(template: bytes, start: int, end: int) -> str:
    excerpt = (
        template[start:end]
        .decode(errors="replace")
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    if len(excerpt) <= _SYNTAX_EXCERPT_MAX_CHARS:
        return excerpt

    return f"{excerpt[: _SYNTAX_EXCERPT_MAX_CHARS - 3]}..."


def _parse_dotted_name(raw_name: bytes) -> tuple[str, ...]:
    if not raw_name:
        msg = "empty name"
        raise InvalidNameError(msg)

    if raw_name == b".":
        return _CURRENT_CONTEXT_PATH

    if any(byte in _NAME_WHITESPACE_BYTES for byte in raw_name):
        msg = "invalid name"
        raise InvalidNameError(msg)

    try:
        name = raw_name.decode()
    except UnicodeDecodeError as exc:
        msg = "name must be valid UTF-8"
        raise InvalidNameError(msg) from exc

    parts = tuple(name.split("."))
    if any(part == "" or part.strip() != part for part in parts):
        msg = "invalid name"
        raise InvalidNameError(msg)

    return parts


def _append_text(
    frame: _ParseFrame,
    value: bytes,
    *,
    ignore_indents: bool,
) -> None:
    if value:
        node = (
            TextNode(chunks=(value,), value=value)
            if ignore_indents
            else TextNode.from_bytes(value)
        )
        frame.children.append(node)


def _left_trim_source_lines(value: bytes) -> bytes:
    value_len = len(value)
    if value_len == 0:
        return value

    chunks: list[bytes] = []
    line_start = 0
    changed = False

    while line_start < value_len:
        content_start = line_start
        while content_start < value_len and value[content_start] in _LINE_SPACE_BYTES:
            content_start += 1

        line_end = content_start
        while line_end < value_len:
            byte = value[line_end]
            if byte == _CR_BYTE or byte == _LF_BYTE:
                break

            line_end += 1

        if content_start != line_start:
            changed = True

        chunks.append(value[content_start:line_end])
        if line_end == value_len:
            break

        if (
            value[line_end] == _CR_BYTE
            and line_end + 1 < value_len
            and value[line_end + 1] == _LF_BYTE
        ):
            line_break_end = line_end + len(_CRLF)
        else:
            line_break_end = line_end + 1

        chunks.append(value[line_end:line_break_end])
        line_start = line_break_end

    if not changed:
        return value

    return b"".join(chunks)


def _split_template_text(value: bytes) -> tuple[bytes, ...]:
    if _LF not in value and _CR not in value:
        return (value,)

    chunks: list[bytes] = []
    value_len = len(value)
    position = 0
    index = 0

    while index < value_len:
        byte = value[index]
        if byte == _CR_BYTE and index + 1 < value_len and value[index + 1] == _LF_BYTE:
            line_break_end = index + len(_CRLF)
        elif byte == _CR_BYTE or byte == _LF_BYTE:
            line_break_end = index + 1
        else:
            index += 1
            continue

        chunks.append(value[position:line_break_end])
        position = line_break_end
        index = line_break_end

    if position < value_len:
        chunks.append(value[position:])

    return tuple(chunks)
