import fstache
import pytest

from render_helpers import render_template


class TestRenderCommentsDelimiters:
    @pytest.mark.parametrize("comment_body", [b"user..name", b"\xff"])
    def test_comment_bodies_are_opaque(self, comment_body: bytes) -> None:
        compiled = fstache.compile(b"a{{! " + comment_body + b" }}b")

        assert render_template(compiled, {}).to_bytes() == b"ab"

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

    def test_delimiters_can_reset_to_default(self) -> None:
        compiled = fstache.compile(b"{{=<% %>=}}<%name%><%={{ }}=%>{{name}}")

        assert (
            render_template(compiled, {"name": "A&B"}).to_bytes() == b"A&amp;BA&amp;B"
        )

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

    def test_trims_standalone_delimiter_lines_with_custom_delimiters(self) -> None:
        compiled = fstache.compile(b"{{=<% %>=}}\n<%={{ }}=%>\n{{name}}")

        assert render_template(compiled, {"name": "A&B"}).to_bytes() == b"A&amp;B"
