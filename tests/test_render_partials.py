import fstache

from fstache import CompiledTemplate
from render_helpers import render_template


class TestRenderPartials:
    def test_partial_inherits_current_section_scope_and_parent_fallback(self) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "user"

            return fstache.compile(b"{{site_name}}: {{name}}")

        compiled = fstache.compile(b"{{#user}}{{>user}}{{/user}}")
        data = {"site_name": "Docs", "user": {"name": "A&B"}}

        assert (
            render_template(compiled, data, load_partial).to_bytes() == b"Docs: A&amp;B"
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
