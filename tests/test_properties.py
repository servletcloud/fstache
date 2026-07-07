from collections.abc import Mapping
from typing import Final

import fstache
from hypothesis import example, given, settings, strategies as st


_GENERATED_TEMPLATE_NAME: Final[str] = "generated.mustache"
_KNOWN_SYNTAX_ERROR_KINDS: Final[frozenset[str]] = frozenset(
    {
        "invalid_delimiter",
        "invalid_name",
        "section_syntax",
        "unclosed_tag",
        "unsupported_tag",
    }
)
_MAX_SYNTAX_EXCERPT_CHARS: Final[int] = 80
_CR_BYTE: Final[int] = ord("\r")
_LF_BYTE: Final[int] = ord("\n")
_OPEN_BRACE_BYTE: Final[int] = ord("{")
_LINE_BYTES: Final = st.lists(
    st.sampled_from(
        tuple(
            byte
            for byte in range(128)
            if byte not in (_CR_BYTE, _LF_BYTE, _OPEN_BRACE_BYTE)
        )
    ),
    max_size=20,
).map(bytes)


@example(b"")
@example(b"{{")
@example(b"{{{name}}")
@example(b"{{#x}}")
@example(b"{{/x}}")
@example(b"{{=<% %>=}}<%#x%>")
@example(b"line\rnext\nlast\r\nend")
@example(b"{{\xff}}")
@example(b"{{! invalid \xff comment }}")
@settings(max_examples=500, deadline=None)
@given(st.binary(min_size=0, max_size=512))
def test_arbitrary_template_bytes_compile_or_render_coherently(
    template: bytes,
) -> None:
    try:
        compiled = fstache.compile(template, name=_GENERATED_TEMPLATE_NAME)
    except fstache.TemplateSyntaxError as exc:
        assert_syntax_error_is_coherent(exc, template)

        return

    first_render = render_generated_template(compiled)
    first_bytes = first_render.to_bytes()
    first_chunks = list(first_render.iter_chunks())

    assert isinstance(first_bytes, bytes)
    assert first_render.to_bytes() == first_bytes
    assert all(isinstance(chunk, bytes | memoryview) for chunk in first_chunks)
    assert b"".join(bytes(chunk) for chunk in first_chunks) == first_bytes
    assert first_render.to_string(errors="replace") == first_bytes.decode(
        "utf-8", "replace"
    )
    assert render_generated_template(compiled).to_bytes() == first_bytes


@settings(max_examples=500, deadline=None)
@given(
    value=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(),
        st.binary(),
        st.binary().map(memoryview),
    ),
    unescaped=st.booleans(),
)
def test_variable_interpolation_matches_value_oracle(
    value: object,
    unescaped: bool,
) -> None:
    template = b"{{{value}}}" if unescaped else b"{{value}}"
    compiled = fstache.compile(template, name=_GENERATED_TEMPLATE_NAME)

    rendered = render_generated_template(compiled, {"value": value}).to_bytes()
    raw_value = expected_raw_interpolation_value(value)
    expected = raw_value if unescaped else fstache.html_escape(raw_value)

    assert rendered == expected


@settings(max_examples=500, deadline=None)
@given(
    value=st.one_of(
        st.booleans(),
        st.integers(min_value=-1_000_000, max_value=1_000_000),
        st.floats(allow_nan=False, allow_infinity=False, width=32),
    ),
    unescaped=st.booleans(),
)
def test_variable_lambda_scalar_results_match_value_oracle(
    value: object,
    unescaped: bool,
) -> None:
    template = b"{{{value}}}" if unescaped else b"{{value}}"
    compiled = fstache.compile(template, name=_GENERATED_TEMPLATE_NAME)

    rendered = render_generated_template(
        compiled, {"value": lambda value=value: value}
    ).to_bytes()
    raw_value = expected_raw_interpolation_value(value)
    expected = raw_value if unescaped else fstache.html_escape(raw_value)

    assert rendered == expected


@settings(max_examples=500, deadline=None)
@given(
    value=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.text(),
        st.dictionaries(st.text(min_size=1, max_size=5), st.integers(), max_size=3),
        st.lists(st.integers(), max_size=20),
        st.lists(st.integers(), max_size=20).map(tuple),
    )
)
def test_sections_and_inverted_sections_match_truthiness_oracle(
    value: object,
) -> None:
    compiled = fstache.compile(
        b"a{{#items}}x{{/items}}b{{^items}}y{{/items}}c",
        name=_GENERATED_TEMPLATE_NAME,
    )

    rendered = render_generated_template(compiled, {"items": value}).to_bytes()
    expected = expected_section_truthiness_render(value)

    assert rendered == expected


@settings(max_examples=500, deadline=None)
@given(
    indent=st.lists(st.sampled_from((ord(" "), ord("\t"))), max_size=8).map(bytes),
    lines=st.lists(_LINE_BYTES, min_size=1, max_size=8),
    final_newline=st.booleans(),
)
def test_standalone_partial_indents_each_partial_line(
    indent: bytes,
    lines: list[bytes],
    final_newline: bool,
) -> None:
    partial = b"\n".join(lines)
    if final_newline:
        partial += b"\n"

    compiled = fstache.compile(
        b"Begin.\n" + indent + b"{{>partial}}\nEnd.",
        name=_GENERATED_TEMPLATE_NAME,
    )

    rendered = render_generated_template(
        compiled,
        partials={"partial": fstache.compile(partial)},
    ).to_bytes()
    expected = expected_standalone_partial_render(indent, partial)

    assert rendered == expected


def assert_syntax_error_is_coherent(
    exc: fstache.TemplateSyntaxError,
    template: bytes,
) -> None:
    assert exc.reason
    assert exc.template_name == _GENERATED_TEMPLATE_NAME
    assert exc.kind is None or exc.kind in _KNOWN_SYNTAX_ERROR_KINDS

    if exc.offset is not None:
        assert 0 <= exc.offset <= len(template)

    if exc.line is not None or exc.column is not None:
        assert exc.line is not None
        assert exc.column is not None
        assert exc.line > 0
        assert exc.column > 0

    if exc.excerpt is not None:
        assert len(exc.excerpt) <= _MAX_SYNTAX_EXCERPT_CHARS
        assert "\n" not in exc.excerpt
        assert "\r" not in exc.excerpt


def expected_raw_interpolation_value(value: object) -> bytes:
    if value is None:
        return b""

    if type(value) is bytes:
        return value

    if type(value) is memoryview:
        return bytes(value)

    return str(value).encode()


def expected_section_truthiness_render(value: object) -> bytes:
    if not value:
        return b"abyc"

    if type(value) is list or type(value) is tuple:
        return b"a" + (b"x" * len(value)) + b"bc"

    return b"axbc"


def expected_standalone_partial_render(
    indent: bytes,
    partial: bytes,
) -> bytes:
    if not partial:
        return b"Begin.\nEnd."

    chunks = split_literal_line_chunks(partial)
    expected_partial = b"".join(
        chunk if index == 0 else indent + chunk for index, chunk in enumerate(chunks)
    )

    return b"Begin.\n" + indent + expected_partial + b"End."


def split_literal_line_chunks(value: bytes) -> list[bytes]:
    chunks: list[bytes] = []
    position = 0
    index = 0
    value_len = len(value)
    while index < value_len:
        byte = value[index]
        if byte == _CR_BYTE and index + 1 < value_len and value[index + 1] == _LF_BYTE:
            line_break_end = index + 2
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

    return chunks


def render_generated_template(
    compiled: fstache.CompiledTemplate,
    data: object | None = None,
    *,
    partials: Mapping[str, fstache.CompiledTemplate] | None = None,
) -> fstache.RenderedTemplate:
    def load_template(name: str) -> fstache.CompiledTemplate:
        if name == _GENERATED_TEMPLATE_NAME:
            return compiled

        if partials is not None:
            partial = partials.get(name)
            if partial is not None:
                return partial

        return fstache.resolve_missing_template_as_empty(name)

    if data is None:
        data = {}

    return fstache.render(
        _GENERATED_TEMPLATE_NAME,
        data,
        load_template,
        resolve_missing_variable=fstache.resolve_missing_variable_as_none,
    )
