from typing import cast

import fstache
import pytest

from render_helpers import render_template

from fstache import (
    Delimiters,
    InvalidDelimiterError,
    InvalidNameError,
    SectionSyntaxError,
    TemplateSyntaxError,
    UnclosedTagError,
    UnsupportedTagError,
)
from fstache._compiler import (
    DynamicPartialNode,
    InvertedSectionNode,
    PartialNode,
    SectionNode,
    TextNode,
    VariableNode,
)


class TestTextNode:
    def test_from_bytes_splits_line_break_chunks(self) -> None:
        assert TextNode.from_bytes(b"a\nb") == TextNode(
            chunks=(b"a\n", b"b"),
            value=b"a\nb",
        )


class TestCompileTemplate:
    def test_compiles_plain_text_as_text_node(self) -> None:
        assert fstache.compile(b"hello\nworld") == (
            TextNode.from_bytes(b"hello\nworld"),
        )

    def test_compiles_plain_text_line_break_chunks(self) -> None:
        assert fstache.compile(b"a\n\nb\r\nc\rd") == (
            TextNode(
                chunks=(b"a\n", b"\n", b"b\r\n", b"c\r", b"d"),
                value=b"a\n\nb\r\nc\rd",
            ),
        )

    def test_ignore_indents_compiles_plain_text_as_single_chunk(self) -> None:
        assert fstache.compile(b"a\n\nb\r\nc\rd", ignore_indents=True) == (
            TextNode(
                chunks=(b"a\n\nb\r\nc\rd",),
                value=b"a\n\nb\r\nc\rd",
            ),
        )

    def test_left_trim_source_strips_spaces_and_tabs_at_line_starts(self) -> None:
        assert fstache.compile(
            b"  a  b\n\t c \t d",
            left_trim_source=True,
        ) == (
            TextNode(
                chunks=(b"a  b\n", b"c \t d"),
                value=b"a  b\nc \t d",
            ),
        )

    def test_left_trim_source_preserves_line_endings(self) -> None:
        assert fstache.compile(
            b"  a\n\tb\r\n  c\rd",
            left_trim_source=True,
        ) == (
            TextNode(
                chunks=(b"a\n", b"b\r\n", b"c\r", b"d"),
                value=b"a\nb\r\nc\rd",
            ),
        )

    def test_compiles_section_nodes(self) -> None:
        assert fstache.compile(b"a{{#user.active}}b{{/user.active}}c") == (
            TextNode.from_bytes(b"a"),
            SectionNode(
                path=("user", "active"),
                children=(TextNode.from_bytes(b"b"),),
                raw_body=b"b",
                delimiters=Delimiters(start=b"{{", end=b"}}"),
            ),
            TextNode.from_bytes(b"c"),
        )

    def test_compiles_inverted_section_nodes(self) -> None:
        assert fstache.compile(b"a{{^items}}empty{{/items}}c") == (
            TextNode.from_bytes(b"a"),
            InvertedSectionNode(
                path=("items",),
                children=(TextNode.from_bytes(b"empty"),),
            ),
            TextNode.from_bytes(b"c"),
        )

    def test_compiles_variable_nodes(self) -> None:
        assert fstache.compile(b"a{{user.name}}c") == (
            TextNode.from_bytes(b"a"),
            VariableNode(path=("user", "name")),
            TextNode.from_bytes(b"c"),
        )

    def test_compiles_templates_without_partial_loading(self) -> None:
        assert fstache.compile(b"a{{name}}c") == (
            TextNode.from_bytes(b"a"),
            VariableNode(path=("name",)),
            TextNode.from_bytes(b"c"),
        )

    def test_compiles_partial_tags_as_unresolved_partial_nodes(self) -> None:
        assert fstache.compile(b"a{{>text}}c") == (
            TextNode.from_bytes(b"a"),
            PartialNode(name="text", indentation=None),
            TextNode.from_bytes(b"c"),
        )

    def test_ignore_indents_compiles_standalone_partial_without_indentation(
        self,
    ) -> None:
        assert fstache.compile(
            b"Begin.\n  {{>text}}\nEnd.",
            ignore_indents=True,
        ) == (
            TextNode(chunks=(b"Begin.\n",), value=b"Begin.\n"),
            PartialNode(name="text", indentation=None),
            TextNode(chunks=(b"End.",), value=b"End."),
        )

    def test_compiles_dynamic_partial_tags_as_unresolved_dynamic_partial_nodes(
        self,
    ) -> None:
        assert fstache.compile(b"a{{> * user.partial }}c") == (
            TextNode.from_bytes(b"a"),
            DynamicPartialNode(path=("user", "partial"), indentation=None),
            TextNode.from_bytes(b"c"),
        )

    def test_ignore_indents_compiles_standalone_dynamic_partial_without_indentation(
        self,
    ) -> None:
        assert fstache.compile(
            b"Begin.\n  {{> * user.partial }}\nEnd.",
            ignore_indents=True,
        ) == (
            TextNode(chunks=(b"Begin.\n",), value=b"Begin.\n"),
            DynamicPartialNode(path=("user", "partial"), indentation=None),
            TextNode(chunks=(b"End.",), value=b"End."),
        )

    def test_compiles_section_partial_and_delimiter_template_regression(self) -> None:
        assert fstache.compile(b"{{#items}}{{>row}}{{/items}}{{=<% %>=}}<%name%>") == (
            SectionNode(
                path=("items",),
                children=(PartialNode(name="row", indentation=None),),
                raw_body=b"{{>row}}",
                delimiters=Delimiters(start=b"{{", end=b"}}"),
            ),
            VariableNode(path=("name",)),
        )

    def test_left_trim_source_section_raw_body_uses_trimmed_source(self) -> None:
        assert fstache.compile(
            b"{{#wrap}}\n  {{name}}\n{{/wrap}}",
            left_trim_source=True,
        ) == (
            SectionNode(
                path=("wrap",),
                children=(VariableNode(path=("name",)), TextNode.from_bytes(b"\n")),
                raw_body=b"{{name}}\n",
                delimiters=Delimiters(start=b"{{", end=b"}}"),
            ),
        )

    def test_public_delimiters_exports(self) -> None:
        assert fstache.Delimiters is Delimiters
        assert fstache.DEFAULT_DELIMITERS == Delimiters(b"{{", b"}}")

    @pytest.mark.parametrize(
        ("start", "end"),
        [
            (b"", b"}}"),
            (b"{{", b""),
            (b"{ {", b"}}"),
            (b"{{", b"} }"),
            (b"{{=", b"}}"),
            (b"{{", b"=}}"),
        ],
    )
    def test_rejects_invalid_public_delimiters(
        self,
        start: bytes,
        end: bytes,
    ) -> None:
        with pytest.raises(InvalidDelimiterError) as exc_info:
            Delimiters(start, end)

        assert exc_info.value.reason == "invalid delimiter declaration"

    def test_compiles_with_public_initial_delimiters(self) -> None:
        compiled = fstache.compile(
            b"[[name]]",
            delimiters=fstache.Delimiters(b"[[", b"]]"),
        )

        assert render_template(compiled, {"name": "Ada"}).to_bytes() == b"Ada"

    def test_default_tags_remain_literal_with_custom_initial_delimiters(self) -> None:
        compiled = fstache.compile(
            b"{{name}} [[name]]",
            delimiters=fstache.Delimiters(b"[[", b"]]"),
        )

        assert render_template(compiled, {"name": "Ada"}).to_bytes() == b"{{name}} Ada"

    def test_delimiter_change_tag_resets_custom_initial_delimiters(self) -> None:
        compiled = fstache.compile(
            b"[[={{ }}=]]{{name}}",
            delimiters=fstache.Delimiters(b"[[", b"]]"),
        )

        assert render_template(compiled, {"name": "Ada"}).to_bytes() == b"Ada"

    @pytest.mark.parametrize(
        "template",
        [
            b"a{{{user.name}}}c",
            b"a{{& user.name}}c",
        ],
    )
    def test_compiles_unescaped_variable_nodes(self, template: bytes) -> None:
        assert fstache.compile(template) == (
            TextNode.from_bytes(b"a"),
            VariableNode(path=("user", "name"), escape=False),
            TextNode.from_bytes(b"c"),
        )

    def test_rejects_non_bytes_template_naturally(self) -> None:
        with pytest.raises(TypeError):
            fstache.compile(cast(bytes, "hello"))

    def test_template_syntax_error_constructor_still_accepts_message_only(
        self,
    ) -> None:
        error = TemplateSyntaxError("unsupported partial: text")

        assert str(error) == "unsupported partial: text"
        assert error.reason == "unsupported partial: text"
        assert error.line is None
        assert error.column is None
        assert error.offset is None
        assert error.excerpt is None
        assert error.template_name is None
        assert error.kind is None

    def test_named_template_syntax_error_includes_template_name(self) -> None:
        with pytest.raises(SectionSyntaxError) as exc_info:
            fstache.compile(b"{{#flag}}", name="pages/home.mustache")

        error = exc_info.value
        assert error.template_name == "pages/home.mustache"
        assert str(error) == (
            "unclosed section: flag at line 1, column 1 (offset 0) "
            'in pages/home.mustache: near "{{#flag}}"'
        )

    def test_raises_structured_error_for_unclosed_tags(self) -> None:
        with pytest.raises(UnclosedTagError) as exc_info:
            fstache.compile(b"hello\n{{name")

        error = exc_info.value
        assert error.reason == "unclosed tag"
        assert error.line == 2
        assert error.column == 1
        assert error.offset == 6
        assert error.excerpt == "{{name"
        assert error.kind == "unclosed_tag"
        assert str(error) == (
            'unclosed tag at line 2, column 1 (offset 6): near "{{name"'
        )

    def test_syntax_error_location_counts_carriage_return_line_breaks(self) -> None:
        with pytest.raises(UnclosedTagError) as exc_info:
            fstache.compile(b"hello\r{{name")

        error = exc_info.value
        assert error.line == 2
        assert error.column == 1
        assert error.offset == 6

    def test_raises_structured_error_for_unclosed_triple_tags(self) -> None:
        with pytest.raises(UnclosedTagError) as exc_info:
            fstache.compile(b"a\n  {{{name}}")

        error = exc_info.value
        assert error.reason == "unclosed triple tag"
        assert error.line == 2
        assert error.column == 3
        assert error.offset == 4
        assert error.excerpt == "{{{name}}"

    def test_raises_structured_error_for_unclosed_sections_at_opening_tag(
        self,
    ) -> None:
        with pytest.raises(SectionSyntaxError) as exc_info:
            fstache.compile(b"prefix\n  {{#flag}}\nbody")

        error = exc_info.value
        assert error.reason == "unclosed section: flag"
        assert error.line == 2
        assert error.column == 3
        assert error.offset == 9
        assert error.excerpt == "{{#flag}}"
        assert error.kind == "section_syntax"

    def test_raises_structured_error_for_unopened_section_close(self) -> None:
        with pytest.raises(SectionSyntaxError) as exc_info:
            fstache.compile(b"{{/flag}}")

        error = exc_info.value
        assert error.reason == "unopened section close"
        assert error.line == 1
        assert error.column == 1
        assert error.offset == 0
        assert error.excerpt == "{{/flag}}"

    def test_raises_structured_error_for_mismatched_section_close(self) -> None:
        with pytest.raises(SectionSyntaxError) as exc_info:
            fstache.compile(b"{{#flag}}x{{/other}}")

        error = exc_info.value
        assert error.reason == "mismatched section close: expected flag, got other"
        assert error.line == 1
        assert error.column == 11
        assert error.offset == 10
        assert error.excerpt == "{{/other}}"

    def test_raises_structured_error_for_unsupported_tags(self) -> None:
        with pytest.raises(UnsupportedTagError) as exc_info:
            fstache.compile(b"{{$block}}")

        error = exc_info.value
        assert error.reason == "unsupported tag"
        assert error.line == 1
        assert error.column == 1
        assert error.offset == 0
        assert error.excerpt == "{{$block}}"
        assert error.kind == "unsupported_tag"

    def test_raises_structured_error_for_invalid_partial_names(self) -> None:
        with pytest.raises(InvalidNameError) as exc_info:
            fstache.compile(b"|\n  {{> foo\tbar }}")

        error = exc_info.value
        assert error.reason == "invalid partial name"
        assert error.line == 2
        assert error.column == 3
        assert error.offset == 4
        assert error.excerpt == "{{> foo\\tbar }}"
        assert str(error) == (
            "invalid partial name at line 2, column 3 (offset 4): "
            'near "{{> foo\\tbar }}"'
        )

    def test_raises_structured_error_for_invalid_names(self) -> None:
        with pytest.raises(InvalidNameError) as exc_info:
            fstache.compile(b"{{user. name}}")

        error = exc_info.value
        assert error.reason == "invalid name"
        assert error.line == 1
        assert error.column == 1
        assert error.offset == 0
        assert error.excerpt == "{{user. name}}"
        assert error.kind == "invalid_name"

    def test_raises_structured_error_for_invalid_delimiters(self) -> None:
        with pytest.raises(InvalidDelimiterError) as exc_info:
            fstache.compile(b"{{= <%= %> =}}")

        error = exc_info.value
        assert error.reason == "invalid delimiter declaration"
        assert error.line == 1
        assert error.column == 1
        assert error.offset == 0
        assert error.excerpt == "{{= <%= %> =}}"
        assert error.kind == "invalid_delimiter"

    @pytest.mark.parametrize(
        "template",
        [
            b"{{#flag}}",
            b"{{#outer}}{{#inner}}x{{/inner}}",
            b"{{^flag}}",
            b"{{#outer}}{{^inner}}x{{/inner}}",
        ],
    )
    def test_raises_for_unclosed_sections(self, template: bytes) -> None:
        with pytest.raises(TemplateSyntaxError):
            fstache.compile(template)

    def test_raises_for_unopened_section_close(self) -> None:
        with pytest.raises(TemplateSyntaxError):
            fstache.compile(b"{{/flag}}")

    def test_raises_for_mismatched_section_close(self) -> None:
        with pytest.raises(TemplateSyntaxError):
            fstache.compile(b"{{#flag}}x{{/other}}")

    def test_raises_for_mismatched_inverted_section_close(self) -> None:
        with pytest.raises(TemplateSyntaxError):
            fstache.compile(b"{{^flag}}x{{/other}}")

    @pytest.mark.parametrize(
        "template",
        [
            b"{{$block}}default{{/block}}",
            b"{{<layout}}{{/layout}}",
            b"{{<*layout}}{{/*layout}}",
            b"{{=<% %>=}}<%$block%>default<%/block%>",
            b"{{=<% %>=}}<%<layout%><%/layout%>",
        ],
    )
    def test_raises_for_unsupported_inheritance_tags(self, template: bytes) -> None:
        with pytest.raises(TemplateSyntaxError, match="unsupported tag"):
            fstache.compile(template)

    @pytest.mark.parametrize(
        "template",
        [
            b"{{#}}x{{/}}",
            b"{{#   }}x{{/   }}",
            b"{{#user..active}}x{{/user..active}}",
            b"{{#user. active}}x{{/user. active}}",
            b"{{#.name}}x{{/.name}}",
            b"{{^}}x{{/}}",
            b"{{^   }}x{{/   }}",
            b"{{^user..active}}x{{/user..active}}",
            b"{{^user. active}}x{{/user. active}}",
            b"{{^.name}}x{{/.name}}",
            b"{{}}",
            b"{{   }}",
            b"{{.name}}",
            b"{{name.}}",
            b"{{user..name}}",
            b"{{user. name}}",
            b"{{{}}}",
            b"{{{   }}}",
            b"{{{.name}}}",
            b"{{&}}",
            b"{{& .name}}",
            b"{{& user..name}}",
            b"{{& user. name}}",
            b"{{>}}",
            b"{{>   }}",
            b"{{>foo bar}}",
            b"{{> foo\tbar }}",
            b"{{>\xff}}",
            b"{{>*}}",
            b"{{> * }}",
            b"{{>*foo bar}}",
            b"{{> * foo bar }}",
        ],
    )
    def test_raises_for_empty_or_invalid_names(self, template: bytes) -> None:
        with pytest.raises(TemplateSyntaxError):
            fstache.compile(template)

    def test_raises_for_unclosed_triple_tags(self) -> None:
        with pytest.raises(TemplateSyntaxError):
            fstache.compile(b"{{{name}}")

    @pytest.mark.parametrize(
        "template",
        [
            b"{{= =}}",
            b"{{= <% =}}",
            b"{{= <%= %> =}}",
            b"{{= <% =%> =}}",
        ],
    )
    def test_raises_for_invalid_delimiter_declarations(self, template: bytes) -> None:
        with pytest.raises(TemplateSyntaxError):
            fstache.compile(template)
