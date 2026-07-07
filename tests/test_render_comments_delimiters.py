import fstache
import pytest

from render_helpers import render_template


class TestRenderCommentsDelimiters:
    def test_renders_plain_text_to_bytes(self) -> None:
        compiled = fstache.compile(b"hello")

        assert render_template(compiled, {}).to_bytes() == b"hello"

    @pytest.mark.parametrize(
        ("template", "expected"),
        [
            (b"a{{! hidden }}b", b"ab"),
            (b"a{{!}}b", b"ab"),
            (b"a{{!   }}b", b"ab"),
            (b"a{{! user..name }}b", b"ab"),
            (b"a{{! \xff }}b", b"ab"),
        ],
    )
    def test_renders_comments_as_empty_bytes(
        self, template: bytes, expected: bytes
    ) -> None:
        compiled = fstache.compile(template)

        assert render_template(compiled, {}).to_bytes() == expected

    def test_renders_comments_inside_truthy_section_as_empty_bytes(self) -> None:
        compiled = fstache.compile(b"{{#flag}}a{{! hidden }}b{{/flag}}")

        assert render_template(compiled, {"flag": True}).to_bytes() == b"ab"

    def test_renders_comments_inside_inverted_section_as_empty_bytes(self) -> None:
        compiled = fstache.compile(b"{{^items}}a{{! hidden }}b{{/items}}")

        assert render_template(compiled, {"items": []}).to_bytes() == b"ab"

    def test_inline_comment_keeps_following_closing_delimiter_literal(self) -> None:
        compiled = fstache.compile(b"a{{!x}}}}b")

        assert render_template(compiled, {}).to_bytes() == b"a}}b"

    def test_inline_comment_keeps_whitespace_and_following_delimiter_literal(
        self,
    ) -> None:
        compiled = fstache.compile(b"a{{!x}} }}b")

        assert render_template(compiled, {}).to_bytes() == b"a }}b"

    def test_inline_comment_allows_opening_delimiter_text_before_following_tag(
        self,
    ) -> None:
        compiled = fstache.compile(b"a{{! use {{ for tags }}{{name}}b")

        assert render_template(compiled, {"name": "X"}).to_bytes() == b"aXb"

    def test_delimiter_tags_render_empty_bytes_and_switch_interpolation(self) -> None:
        compiled = fstache.compile(b"{{=<% %>=}}(<%name%>)")

        assert render_template(compiled, {"name": "A&B"}).to_bytes() == b"(A&amp;B)"

    def test_delimiters_can_reset_to_default(self) -> None:
        compiled = fstache.compile(b"{{=<% %>=}}<%name%><%={{ }}=%>{{name}}")

        assert (
            render_template(compiled, {"name": "A&B"}).to_bytes() == b"A&amp;BA&amp;B"
        )

    @pytest.mark.parametrize(
        "template",
        [
            b"{{=[ ]=}}[name]",
            b"{{=@ @=}}@name@",
        ],
    )
    def test_delimiters_support_special_bytes_and_same_byte_pairs(
        self, template: bytes
    ) -> None:
        compiled = fstache.compile(template)

        assert render_template(compiled, {"name": "A&B"}).to_bytes() == b"A&amp;B"

    def test_delimiter_changes_persist_through_sections(self) -> None:
        compiled = fstache.compile(b"{{= | | =}}|#flag||name||/flag|")

        assert (
            render_template(compiled, {"flag": True, "name": "A&B"}).to_bytes()
            == b"A&amp;B"
        )

    def test_delimiter_changes_persist_through_inverted_sections(self) -> None:
        compiled = fstache.compile(b"{{= | | =}}|^items|empty|/items|")

        assert render_template(compiled, {"items": []}).to_bytes() == b"empty"

    def test_custom_delimiters_support_comments(self) -> None:
        compiled = fstache.compile(b"{{=<% %>=}}a<%! hidden %>b")

        assert render_template(compiled, {}).to_bytes() == b"ab"

    def test_custom_delimiter_inline_comment_keeps_following_delimiter_literal(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{=<% %>=}}a<%!x%>%>b")

        assert render_template(compiled, {}).to_bytes() == b"a%>b"

    def test_custom_delimiters_trim_standalone_comments(self) -> None:
        compiled = fstache.compile(b"{{=<% %>=}}Begin.\n<%! Comment %>\nEnd.")

        assert render_template(compiled, {}).to_bytes() == b"Begin.\nEnd."

    def test_custom_delimiters_support_ampersand_unescaped_variables(self) -> None:
        compiled = fstache.compile(b"{{=<% %>=}}<%& html %>")

        assert render_template(
            compiled, {"html": "A&B <strong>x</strong>"}
        ).to_bytes() == (b"A&B <strong>x</strong>")

    def test_default_delimiter_tags_are_literal_while_custom_delimiters_are_active(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{=<% %>=}}{{name}}<%name%>")

        assert (
            render_template(compiled, {"name": "A&B"}).to_bytes() == b"{{name}}A&amp;B"
        )

    def test_delimiter_tags_trim_standalone_lines(self) -> None:
        compiled = fstache.compile(b"a\n{{= | | =}}\n|name|")

        assert render_template(compiled, {"name": "A&B"}).to_bytes() == b"a\nA&amp;B"

    @pytest.mark.parametrize(
        ("template", "expected"),
        [
            (b"Begin.\n{{= | | =}}\n|name|", b"Begin.\nA&amp;B"),
            (b"Begin.\r\n{{= | | =}}\r\n|name|", b"Begin.\r\nA&amp;B"),
            (b"Begin.\n  \t{{= | | =}}\n|name|", b"Begin.\nA&amp;B"),
            (b"{{= | | =}}\n|name|", b"A&amp;B"),
            (b"  \t{{= | | =}}\n|name|", b"A&amp;B"),
            (b"Begin.\n{{= | | =}}", b"Begin.\n"),
            (b"{{= | | =}}", b""),
        ],
    )
    def test_trims_standalone_delimiter_lines(
        self, template: bytes, expected: bytes
    ) -> None:
        compiled = fstache.compile(template)

        assert render_template(compiled, {"name": "A&B"}).to_bytes() == expected

    def test_trims_standalone_delimiter_lines_with_custom_delimiters(self) -> None:
        compiled = fstache.compile(b"{{=<% %>=}}\n<%={{ }}=%>\n{{name}}")

        assert render_template(compiled, {"name": "A&B"}).to_bytes() == b"A&amp;B"

    def test_inline_delimiter_tags_preserve_surrounding_whitespace(self) -> None:
        compiled = fstache.compile(b"| {{=@ @=}}\n@name@")

        assert render_template(compiled, {"name": "A&B"}).to_bytes() == b"| \nA&amp;B"

    def test_trims_standalone_comment_lines(self) -> None:
        compiled = fstache.compile(b"Begin.\n{{! Comment }}\nEnd.")

        assert render_template(compiled, {}).to_bytes() == b"Begin.\nEnd."

    def test_trims_indented_standalone_comment_lines(self) -> None:
        compiled = fstache.compile(b"Begin.\n  \t{{! Comment }}\nEnd.")

        assert render_template(compiled, {}).to_bytes() == b"Begin.\nEnd."

    def test_trims_standalone_comment_lines_with_crlf(self) -> None:
        compiled = fstache.compile(b"Begin.\r\n{{! Comment }}\r\nEnd.")

        assert render_template(compiled, {}).to_bytes() == b"Begin.\r\nEnd."

    def test_trims_standalone_comment_at_eof(self) -> None:
        compiled = fstache.compile(b"{{! Comment }}")

        assert render_template(compiled, {}).to_bytes() == b""

    def test_trims_multiline_standalone_comment(self) -> None:
        compiled = fstache.compile(b"Begin.\n{{!\n  Comment\n}}\nEnd.")

        assert render_template(compiled, {}).to_bytes() == b"Begin.\nEnd."

    def test_inline_comments_preserve_surrounding_whitespace(self) -> None:
        compiled = fstache.compile(b"12 {{! 34 }}\n")

        assert render_template(compiled, {}).to_bytes() == b"12 \n"
