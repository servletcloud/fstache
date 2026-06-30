import fstache

from fstache import CompiledTemplate, EMPTY_TEMPLATE
from fstache._compiler import (
    PartialNode,
    TextNode,
    VariableNode,
)
from render_helpers import render_template


class TestRenderPartials:
    def test_renders_basic_partial_expansion(self) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "text"

            return fstache.compile(b"{{name}}")

        compiled = fstache.compile(b"hello {{>text}}")

        assert (
            render_template(compiled, {"name": "A&B"}, load_partial).to_bytes()
            == b"hello A&amp;B"
        )

    def test_partial_inherits_current_section_scope_and_parent_fallback(self) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "user"

            return fstache.compile(b"{{site_name}}: {{name}}")

        compiled = fstache.compile(b"{{#user}}{{>user}}{{/user}}")
        data = {"site_name": "Docs", "user": {"name": "A&B"}}

        assert (
            render_template(compiled, data, load_partial).to_bytes() == b"Docs: A&amp;B"
        )

    def test_inline_partials_preserve_surrounding_whitespace(self) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "text"

            return fstache.compile(b"two")

        compiled = fstache.compile(b"one {{>text}} three")

        assert (
            render_template(compiled, {}, load_partial).to_bytes() == b"one two three"
        )

    def test_inline_indentation_partial_whitespace_is_left_untouched(self) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "partial"

            return fstache.compile(b">\n>")

        compiled = fstache.compile(b"  {{data}}  {{> partial}}\n")

        assert (
            render_template(compiled, {"data": "|"}, load_partial).to_bytes()
            == b"  |  >\n>\n"
        )

    def test_standalone_partials_strip_tag_line_and_indent_partial_lines(self) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "text"

            return fstache.compile(b"one\n{{name}}\n")

        compiled = fstache.compile(b"Begin.\n  {{>text}}\nEnd.")

        assert render_template(compiled, {"name": "A&B"}, load_partial).to_bytes() == (
            b"Begin.\n  one\n  A&amp;B\nEnd."
        )

    def test_ignore_indents_standalone_partial_does_not_indent_partial_lines(
        self,
    ) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "text"

            return fstache.compile(b"one\n{{name}}\n")

        compiled = fstache.compile(b"Begin.\n  {{>text}}\nEnd.", ignore_indents=True)

        assert render_template(compiled, {"name": "A&B"}, load_partial).to_bytes() == (
            b"Begin.\none\nA&amp;B\nEnd."
        )

    def test_left_trim_source_with_ignore_indents_removes_source_indentation(
        self,
    ) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "text"

            return fstache.compile(
                b"  one\n    {{name}}\n",
                ignore_indents=True,
                left_trim_source=True,
            )

        compiled = fstache.compile(
            b"  Begin.\n    {{>text}}\n  End.",
            ignore_indents=True,
            left_trim_source=True,
        )

        assert render_template(compiled, {"name": "A&B"}, load_partial).to_bytes() == (
            b"Begin.\none\nA&amp;B\nEnd."
        )

    def test_left_trim_source_keeps_inline_whitespace(self) -> None:
        compiled = fstache.compile(
            b"  {{first}}  {{second}}\n",
            left_trim_source=True,
        )

        assert (
            render_template(compiled, {"first": "A", "second": "B"}).to_bytes()
            == b"A  B\n"
        )

    def test_standalone_partial_lines_with_crlf_follow_standalone_behavior(
        self,
    ) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "text"

            return fstache.compile(b"one\r\n{{name}}\r\n")

        compiled = fstache.compile(b"Begin.\r\n  {{>text}}\r\nEnd.")

        assert render_template(compiled, {"name": "A&B"}, load_partial).to_bytes() == (
            b"Begin.\r\n  one\r\n  A&amp;B\r\nEnd."
        )

    def test_standalone_partial_without_previous_line(self) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "partial"

            return fstache.compile(b">\n>")

        compiled = fstache.compile(b"  {{>partial}}\n>")

        assert render_template(compiled, {}, load_partial).to_bytes() == b"  >\n  >>"

    def test_standalone_partial_without_newline(self) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "partial"

            return fstache.compile(b">\n>")

        compiled = fstache.compile(b">\n  {{>partial}}")

        assert render_template(compiled, {}, load_partial).to_bytes() == b">\n  >\n  >"

    def test_standalone_partial_indentation_preserves_multiline_content(
        self,
    ) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "partial"

            return fstache.compile(b"|\n{{{content}}}\n|\n")

        compiled = fstache.compile(b"\\\n {{>partial}}\n/\n")

        assert render_template(
            compiled, {"content": "<\n->"}, load_partial
        ).to_bytes() == (b"\\\n |\n <\n->\n |\n/\n")

    def test_empty_standalone_partial_does_not_emit_indentation(self) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "partial"

            return EMPTY_TEMPLATE

        compiled = fstache.compile(b"Begin.\n  {{>partial}}\nEnd.")

        assert render_template(compiled, {}, load_partial).to_bytes() == b"Begin.\nEnd."

    def test_partial_padding_whitespace_is_ignored(self) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "partial"

            return fstache.compile(b"[]")

        compiled = fstache.compile(b"|{{> partial }}|")

        assert render_template(compiled, {}, load_partial).to_bytes() == b"|[]|"

    def test_resolve_missing_variable_is_not_used_for_dynamic_partial_names(
        self,
    ) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            raise AssertionError(name)

        def resolve_missing_variable(path: tuple[str, ...]) -> object:
            raise AssertionError(path)

        compiled = fstache.compile(b"a{{> * name}}c")

        assert (
            render_template(
                compiled,
                {},
                load_partial,
                resolve_missing_variable=resolve_missing_variable,
            ).to_bytes()
            == b"ac"
        )

    def test_indented_partial_does_not_mutate_loader_template(self) -> None:
        partial = fstache.compile(b"one\n{{name}}")

        def load_partial(name: str) -> CompiledTemplate:
            assert name == "text"

            return partial

        compiled = fstache.compile(b"{{>text}}\n  {{>text}}\n    {{>text}}")

        assert render_template(compiled, {"name": "A&B"}, load_partial).to_bytes() == (
            b"one\nA&amp;B  one\n  A&amp;B    one\n    A&amp;B"
        )
        assert partial == fstache.compile(b"one\n{{name}}")

    def test_same_partial_name_and_indentation_can_load_distinct_templates(
        self,
    ) -> None:
        partials = (
            fstache.compile(b"first\n"),
            fstache.compile(b"second\n"),
        )
        calls = 0

        def load_partial(name: str) -> CompiledTemplate:
            nonlocal calls
            assert name == "text"

            partial = partials[calls]
            calls += 1

            return partial

        compiled = fstache.compile(b"  {{>text}}\n  {{>text}}")

        assert (
            render_template(compiled, {}, load_partial).to_bytes()
            == b"  first\n  second\n"
        )
        assert calls == 2

    def test_indented_partial_copies_section_lambda_raw_body(self) -> None:
        bodies: list[str] = []

        def capture_body(body: str) -> None:
            bodies.append(body)

        def load_partial(name: str) -> CompiledTemplate:
            assert name == "text"

            return fstache.compile(b"{{#wrap}}one\n{{name}}\n{{/wrap}}")

        compiled = fstache.compile(b"  {{>text}}")

        assert (
            render_template(compiled, {"wrap": capture_body}, load_partial).to_bytes()
            == b"  "
        )
        assert bodies == ["one\n  {{name}}\n  "]

    def test_indented_partial_applies_indentation_to_section_lambda_result(
        self,
    ) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "text"

            return fstache.compile(b"{{#wrap}}ignored{{/wrap}}")

        compiled = fstache.compile(b"  {{>text}}")
        data = {"wrap": lambda body: "one\n{{name}}\n", "name": "A&B"}

        assert (
            render_template(compiled, data, load_partial).to_bytes()
            == b"  one\n  A&amp;B\n  "
        )

    def test_indented_partial_applies_section_lambda_indentation_to_nested_partial(
        self,
    ) -> None:
        partial_templates = {
            "outer": b"{{#wrap}}ignored{{/wrap}}",
            "inner": b"one\n{{name}}\n",
        }

        def load_partial(name: str) -> CompiledTemplate:
            return fstache.compile(partial_templates[name])

        compiled = fstache.compile(b"  {{>outer}}")
        data = {"wrap": lambda body: "{{>inner}}", "name": "A&B"}

        assert (
            render_template(compiled, data, load_partial).to_bytes()
            == b"    one\n  A&amp;B\n"
        )

    def test_indented_partial_applies_inherited_indentation_to_nested_partial(
        self,
    ) -> None:
        partial_templates = {
            "outer": b"one\n{{>inner}}",
            "inner": b"two\n{{name}}",
        }

        def load_partial(name: str) -> CompiledTemplate:
            return fstache.compile(partial_templates[name])

        compiled = fstache.compile(b"  {{>outer}}")

        assert render_template(compiled, {"name": "A&B"}, load_partial).to_bytes() == (
            b"  one\n  two\n  A&amp;B"
        )

    def test_indented_partial_combines_inherited_and_local_nested_indentation(
        self,
    ) -> None:
        partial_templates = {
            "outer": b"one\n  {{>inner}}",
            "inner": b"two\n{{name}}",
        }

        def load_partial(name: str) -> CompiledTemplate:
            return fstache.compile(partial_templates[name])

        compiled = fstache.compile(b"  {{>outer}}")

        assert render_template(compiled, {"name": "A&B"}, load_partial).to_bytes() == (
            b"  one\n    two\n    A&amp;B"
        )

    def test_inline_nested_partial_inherits_indentation_after_line_breaks(
        self,
    ) -> None:
        partial_templates = {
            "outer": b"one {{>inner}}",
            "inner": b"two\n{{name}}",
        }

        def load_partial(name: str) -> CompiledTemplate:
            return fstache.compile(partial_templates[name])

        compiled = fstache.compile(b"  {{>outer}}")

        assert render_template(compiled, {"name": "A&B"}, load_partial).to_bytes() == (
            b"  one two\n  A&amp;B"
        )

    def test_render_lowers_manual_partial_node(self) -> None:
        compiled = (
            TextNode.from_bytes(b"Begin.\n"),
            PartialNode(name="text", indentation=b"  "),
        )

        def load_partial(name: str) -> CompiledTemplate:
            assert name == "text"

            return (
                TextNode.from_bytes(b"one\n"),
                VariableNode(path=("name",)),
            )

        assert (
            render_template(compiled, {"name": "A&B"}, load_partial).to_bytes()
            == b"Begin.\n  one\n  A&amp;B"
        )

    def test_nested_non_recursive_partials_work(self) -> None:
        partial_templates = {
            "outer": b"[{{>inner}}]",
            "inner": b"{{name}}",
        }

        def load_partial(name: str) -> CompiledTemplate:
            return fstache.compile(partial_templates[name])

        compiled = fstache.compile(b"{{>outer}}")

        assert (
            render_template(compiled, {"name": "A&B"}, load_partial).to_bytes()
            == b"[A&amp;B]"
        )
