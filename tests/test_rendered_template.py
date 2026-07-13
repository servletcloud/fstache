import fstache
import pytest

from fstache import RenderChunk, RenderedTemplate
from render_helpers import render_template


def test_render_returns_rendered_template() -> None:
    result = render_template(fstache.compile(b"hello {{name}}"), {"name": "A&B"})

    assert isinstance(result, RenderedTemplate)


def test_iter_chunks_returns_render_chunks_and_fresh_iterators() -> None:
    result = render_template(
        fstache.compile(b"{{{value}}}"), {"value": memoryview(b"ok")}
    )

    first_iterator = result.iter_chunks()
    second_iterator = result.iter_chunks()
    first_chunks: list[RenderChunk] = list(first_iterator)
    second_chunks: list[RenderChunk] = list(second_iterator)

    assert first_iterator is not second_iterator
    assert first_chunks == [memoryview(b"ok")]
    assert second_chunks == first_chunks


def test_to_string_uses_strict_utf8_by_default() -> None:
    result = render_template(fstache.compile(b"{{{value}}}"), {"value": b"\xff"})

    with pytest.raises(UnicodeDecodeError):
        result.to_string()


def test_to_string_honors_explicit_decode_options() -> None:
    result = render_template(fstache.compile(b"{{{value}}}"), {"value": b"\xff"})

    assert result.to_string(encoding="latin-1") == "\xff"
    assert result.to_string(errors="replace") == "\ufffd"
