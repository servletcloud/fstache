from dataclasses import dataclass

import fstache
import pytest

from fstache import (
    CompiledTemplate,
    DEFAULT_DELIMITERS,
    Delimiters,
    html_escape,
)
from fstache._renderer import _Renderer
from render_helpers import render_template


def _render_into_renderer(template: bytes, data: object) -> _Renderer:
    renderer = _Renderer(_load_template=fstache.resolve_missing_template_as_empty)
    renderer.render_nodes((data,), None, fstache.compile(template))

    return renderer


class TestRenderVariables:
    def test_renders_escaped_variable_to_bytes(self) -> None:
        compiled = fstache.compile(b"hello {{name}}")

        assert render_template(compiled, {"name": "A&B"}).to_bytes() == b"hello A&amp;B"

    def test_renders_escaped_variable_lambda_result_to_bytes(self) -> None:
        compiled = fstache.compile(b"hello {{name}}")

        assert (
            render_template(compiled, {"name": lambda: "A&B"}).to_bytes()
            == b"hello A&amp;B"
        )

    def test_renders_lambda_string_result_as_template(self) -> None:
        compiled = fstache.compile(b"{{lambda}}")

        assert (
            render_template(
                compiled,
                {
                    "lambda": lambda: "{{planet}}",
                    "planet": "world",
                },
            ).to_bytes()
            == b"world"
        )

    def test_variable_lambda_string_result_uses_custom_compiler(self) -> None:
        calls: list[tuple[bytes, Delimiters]] = []

        def compile_template(
            template: bytes,
            *,
            delimiters: Delimiters = DEFAULT_DELIMITERS,
        ) -> CompiledTemplate:
            calls.append((template, delimiters))

            return fstache.compile(b"{{override}}", delimiters=delimiters)

        compiled = fstache.compile(b"{{lambda}}")

        assert (
            render_template(
                compiled,
                {"lambda": lambda: "{{name}}", "name": "ignored", "override": "custom"},
                compile_template=compile_template,
            ).to_bytes()
            == b"custom"
        )
        assert calls == [(b"{{name}}", DEFAULT_DELIMITERS)]

    def test_variable_lambda_string_result_can_render_partial_with_loader(self) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "planet"

            return fstache.compile(b"{{name}}")

        compiled = fstache.compile(b"{{lambda}}")

        assert (
            render_template(
                compiled,
                {"lambda": lambda: "{{>planet}}", "name": "A&B"},
                load_partial,
            ).to_bytes()
            == b"A&amp;amp;B"
        )

    def test_variable_lambda_string_result_can_render_empty_missing_partial(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{lambda}}")

        assert (
            render_template(
                compiled,
                {"lambda": lambda: "{{>planet}}"},
                missing_partials_are_empty=True,
            ).to_bytes()
            == b""
        )

    def test_lambda_expansion_uses_default_delimiters(self) -> None:
        compiled = fstache.compile(b"{{= | | =}}|& lambda|")

        assert (
            render_template(
                compiled,
                {
                    "lambda": lambda: "|planet| => {{planet}}",
                    "planet": "world",
                },
            ).to_bytes()
            == b"|planet| => world"
        )

    def test_lambda_expansion_output_is_not_escaped_again(self) -> None:
        compiled = fstache.compile(b"<{{lambda}}{{{lambda}}}")

        assert (
            render_template(compiled, {"lambda": lambda: ">"}).to_bytes() == b"<&gt;>"
        )

    def test_calls_lambda_every_interpolation(self) -> None:
        calls = iter(("{{first}}", "{{second}}"))
        compiled = fstache.compile(b"{{lambda}} {{lambda}}")

        assert (
            render_template(
                compiled,
                {
                    "lambda": lambda: next(calls),
                    "first": "A",
                    "second": "B",
                },
            ).to_bytes()
            == b"A B"
        )

    def test_renders_current_scope_as_escaped_variable(self) -> None:
        compiled = fstache.compile(b"{{.}}")

        assert render_template(compiled, "A&B").to_bytes() == b"A&amp;B"

    def test_escapes_html_sensitive_characters(self) -> None:
        compiled = fstache.compile(b"{{value}}")

        assert render_template(compiled, {"value": "&<>'\""}).to_bytes() == (
            b"&amp;&lt;&gt;&#x27;&quot;"
        )

    def test_html_escape_is_public_default_escape(self) -> None:
        compiled = fstache.compile(b"{{value}}")

        assert render_template(
            compiled, {"value": "&<>'\""}, escape=html_escape
        ).to_bytes() == (b"&amp;&lt;&gt;&#x27;&quot;")

    @pytest.mark.parametrize(
        "value",
        [
            "A&B",
            b"A&B",
            memoryview(b"A&B"),
        ],
    )
    def test_escaped_variables_use_custom_escape(self, value: object) -> None:
        calls: list[bytes] = []

        def escape(value: bytes) -> bytes:
            calls.append(value)

            return b"[" + value + b"]"

        compiled = fstache.compile(b"{{value}}")

        assert (
            render_template(compiled, {"value": value}, escape=escape).to_bytes()
            == b"[A&B]"
        )
        assert calls == [b"A&B"]

    def test_unescaped_variables_ignore_custom_escape(self) -> None:
        def escape(value: bytes) -> bytes:
            raise AssertionError(value)

        compiled = fstache.compile(b"{{{value}}}")

        assert (
            render_template(compiled, {"value": b"A&B"}, escape=escape).to_bytes()
            == b"A&B"
        )

    def test_variable_lambda_template_uses_custom_escape(self) -> None:
        calls: list[bytes] = []

        def escape(value: bytes) -> bytes:
            calls.append(value)

            return b"[" + value + b"]"

        compiled = fstache.compile(b"{{lambda}}")

        assert (
            render_template(
                compiled,
                {"lambda": lambda: "{{name}}", "name": "A&B"},
                escape=escape,
            ).to_bytes()
            == b"[[A&B]]"
        )
        assert calls == [b"A&B", b"[A&B]"]

    def test_renders_escaped_bytes_variable_to_bytes(self) -> None:
        compiled = fstache.compile(b"{{value}}")

        assert render_template(compiled, {"value": b"&<>'\""}).to_bytes() == (
            b"&amp;&lt;&gt;&#x27;&quot;"
        )

    def test_renders_escaped_memoryview_variable_to_bytes(self) -> None:
        compiled = fstache.compile(b"{{value}}")

        assert render_template(
            compiled, {"value": memoryview(b"&<>'\"")}
        ).to_bytes() == (b"&amp;&lt;&gt;&#x27;&quot;")

    @pytest.mark.parametrize(
        "template",
        [
            b"{{{value}}}",
            b"{{& value}}",
        ],
    )
    def test_renders_unescaped_variables_to_bytes(self, template: bytes) -> None:
        compiled = fstache.compile(template)

        assert render_template(
            compiled, {"value": "A&B <strong>x</strong>"}
        ).to_bytes() == (b"A&B <strong>x</strong>")

    @pytest.mark.parametrize(
        "template",
        [
            b"{{{value}}}",
            b"{{& value}}",
        ],
    )
    def test_renders_unescaped_bytes_variables_to_bytes(self, template: bytes) -> None:
        compiled = fstache.compile(template)

        assert render_template(
            compiled, {"value": b"A&B <strong>x</strong>"}
        ).to_bytes() == (b"A&B <strong>x</strong>")

    @pytest.mark.parametrize(
        "template",
        [
            b"{{{value}}}",
            b"{{& value}}",
        ],
    )
    def test_renders_unescaped_memoryview_variables_to_bytes(
        self, template: bytes
    ) -> None:
        compiled = fstache.compile(template)

        assert render_template(
            compiled, {"value": memoryview(b"A&B <strong>x</strong>")}
        ).to_bytes() == (b"A&B <strong>x</strong>")

    @pytest.mark.parametrize(
        "template",
        [
            b"{{{content}}}",
            b"{{& content}}",
        ],
    )
    def test_renders_unescaped_renderer_variable_to_bytes(
        self, template: bytes
    ) -> None:
        content = _render_into_renderer(
            b"<{{name}}> {{suffix}}",
            {"name": "A&B", "suffix": memoryview(b"done")},
        )
        compiled = fstache.compile(b"before " + template + b" after")

        assert render_template(compiled, {"content": content}).to_bytes() == (
            b"before <A&amp;B> done after"
        )

    def test_renders_escaped_renderer_variable_to_bytes(self) -> None:
        content = _render_into_renderer(b"<{{name}}>", {"name": "A&B"})
        compiled = fstache.compile(b"{{content}}")

        assert (
            render_template(compiled, {"content": content}).to_bytes()
            == b"&lt;A&amp;amp;B&gt;"
        )

    def test_renders_lambda_returning_renderer_variable_to_bytes(self) -> None:
        content = _render_into_renderer(b"<{{name}}>", {"name": "A&B"})
        compiled = fstache.compile(b"{{{content}}}")

        assert (
            render_template(compiled, {"content": lambda: content}).to_bytes()
            == b"<A&amp;B>"
        )

    @pytest.mark.parametrize(
        "template",
        [
            b"{{{value}}}",
            b"{{& value}}",
        ],
    )
    def test_renders_unescaped_variable_lambda_result_to_bytes(
        self, template: bytes
    ) -> None:
        compiled = fstache.compile(template)

        assert render_template(
            compiled, {"value": lambda: "A&B <strong>x</strong>"}
        ).to_bytes() == (b"A&B <strong>x</strong>")

    @pytest.mark.parametrize(
        "template",
        [
            b"{{{.}}}",
            b"{{& .}}",
        ],
    )
    def test_renders_current_scope_as_unescaped_variable(self, template: bytes) -> None:
        compiled = fstache.compile(template)

        assert render_template(compiled, "A&B").to_bytes() == b"A&B"

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            ({}, b""),
            ({"value": None}, b""),
        ],
    )
    def test_renders_missing_and_none_variables_as_empty_bytes(
        self, data: object, expected: bytes
    ) -> None:
        compiled = fstache.compile(b"{{value}}")

        assert render_template(compiled, data).to_bytes() == expected

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            ({}, b""),
            ({"value": None}, b""),
        ],
    )
    def test_renders_missing_and_none_unescaped_variables_as_empty_bytes(
        self, data: object, expected: bytes
    ) -> None:
        compiled = fstache.compile(b"{{{value}}}")

        assert render_template(compiled, data).to_bytes() == expected

    def test_resolve_missing_variable_receives_path_and_returns_fallback(self) -> None:
        paths: list[tuple[str, ...]] = []

        def resolve_missing_variable(path: tuple[str, ...]) -> object:
            paths.append(path)

            return "fallback"

        compiled = fstache.compile(b"{{name}}")

        assert render_template(
            compiled, {}, resolve_missing_variable=resolve_missing_variable
        ).to_bytes() == (b"fallback")
        assert paths == [("name",)]

    def test_resolve_missing_variable_receives_dotted_path(self) -> None:
        paths: list[tuple[str, ...]] = []

        def resolve_missing_variable(path: tuple[str, ...]) -> object:
            paths.append(path)

            return ".".join(path)

        compiled = fstache.compile(b"{{user.name}}")

        assert render_template(
            compiled, {}, resolve_missing_variable=resolve_missing_variable
        ).to_bytes() == (b"user.name")
        assert paths == [("user", "name")]

    def test_resolve_missing_variable_exception_propagates(self) -> None:
        class MissingVariableError(Exception):
            pass

        def resolve_missing_variable(path: tuple[str, ...]) -> object:
            raise MissingVariableError(".".join(path))

        compiled = fstache.compile(b"{{name}}")

        with pytest.raises(MissingVariableError, match="name"):
            render_template(
                compiled, {}, resolve_missing_variable=resolve_missing_variable
            )

    def test_resolve_missing_variable_as_error_raises_public_exception(self) -> None:
        compiled = fstache.compile(b"{{user.name}}")

        with pytest.raises(
            fstache.MissingVariableError,
            match="missing template variable: user\\.name",
        ) as exc_info:
            render_template(
                compiled,
                {},
                resolve_missing_variable=fstache.resolve_missing_variable_as_error,
            )

        assert exc_info.value.path == ("user", "name")
        assert exc_info.value.name == "user.name"

    def test_resolve_missing_variable_as_error_can_be_called_directly(self) -> None:
        with pytest.raises(
            fstache.MissingVariableError,
            match="missing template variable: name",
        ) as exc_info:
            fstache.resolve_missing_variable_as_error(("name",))

        assert exc_info.value.path == ("name",)
        assert exc_info.value.name == "name"

    @pytest.mark.parametrize(
        ("template", "expected"),
        [
            (b"{{value}}", b"&lt;strong&gt;fallback&lt;/strong&gt;"),
            (b"{{{value}}}", b"<strong>fallback</strong>"),
            (b"{{& value}}", b"<strong>fallback</strong>"),
        ],
    )
    def test_resolve_missing_variable_output_follows_interpolation_escaping(
        self, template: bytes, expected: bytes
    ) -> None:
        compiled = fstache.compile(template)

        assert (
            render_template(
                compiled,
                {},
                resolve_missing_variable=lambda path: "<strong>fallback</strong>",
            ).to_bytes()
            == expected
        )

    def test_variable_lambda_template_uses_resolve_missing_variable(self) -> None:
        paths: list[tuple[str, ...]] = []

        def resolve_missing_variable(path: tuple[str, ...]) -> object:
            paths.append(path)

            return "fallback"

        compiled = fstache.compile(b"{{lambda}}")

        assert (
            render_template(
                compiled,
                {"lambda": lambda: "{{name}}"},
                resolve_missing_variable=resolve_missing_variable,
            ).to_bytes()
            == b"fallback"
        )
        assert paths == [("name",)]

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (True, b"True"),
            (False, b"False"),
            (0, b"0"),
            (1.5, b"1.5"),
        ],
    )
    def test_renders_scalar_variables_with_str(
        self, value: object, expected: bytes
    ) -> None:
        compiled = fstache.compile(b"{{value}}")

        assert render_template(compiled, {"value": value}).to_bytes() == expected

    def test_renders_lambda_returning_none_as_empty_bytes(self) -> None:
        compiled = fstache.compile(b"{{value}}")

        assert render_template(compiled, {"value": lambda: None}).to_bytes() == b""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (False, b"False"),
            (0, b"0"),
            (0.0, b"0.0"),
            (42, b"42"),
        ],
    )
    def test_renders_lambda_returning_scalar_with_str(
        self, value: object, expected: bytes
    ) -> None:
        compiled = fstache.compile(b"{{value}}|{{{value}}}")

        assert (
            render_template(compiled, {"value": lambda value=value: value}).to_bytes()
            == expected + b"|" + expected
        )

    def test_does_not_render_ordinary_string_as_template(self) -> None:
        compiled = fstache.compile(b"{{today}}")

        assert (
            render_template(compiled, {"today": "{{year}}", "year": 1970}).to_bytes()
            == b"{{year}}"
        )

    def test_dotted_variable_paths_work_for_mappings(self) -> None:
        compiled = fstache.compile(b"{{user.name}}")

        assert (
            render_template(compiled, {"user": {"name": "A&B"}}).to_bytes()
            == b"A&amp;B"
        )

    def test_dotted_variable_paths_invoke_final_lambda(self) -> None:
        compiled = fstache.compile(b"{{user.name}}")

        assert (
            render_template(compiled, {"user": {"name": lambda: "A&B"}}).to_bytes()
            == b"A&amp;B"
        )

    def test_dotted_variable_paths_expand_final_lambda_template(self) -> None:
        compiled = fstache.compile(b"{{user.label}}")

        assert (
            render_template(
                compiled,
                {
                    "user": {"label": lambda: "{{name}}"},
                    "name": "world",
                },
            ).to_bytes()
            == b"world"
        )

    def test_dotted_variable_paths_invoke_intermediate_lambda(self) -> None:
        compiled = fstache.compile(b"{{time.hour}}")

        assert (
            render_template(compiled, {"time": lambda: {"hour": 0}}).to_bytes() == b"0"
        )

    def test_dotted_variable_paths_work_for_dataclass_attributes(self) -> None:
        @dataclass(frozen=True)
        class User:
            name: str

        compiled = fstache.compile(b"{{user.name}}")

        assert (
            render_template(compiled, {"user": User(name="A&B")}).to_bytes()
            == b"A&amp;B"
        )

    def test_dotted_variable_paths_work_for_properties(self) -> None:
        class User:
            @property
            def name(self) -> str:
                return "A&B"

        compiled = fstache.compile(b"{{user.name}}")

        assert render_template(compiled, {"user": User()}).to_bytes() == b"A&amp;B"

    def test_dotted_unescaped_variable_paths_work_for_mappings(self) -> None:
        compiled = fstache.compile(b"{{{user.name}}}")

        assert render_template(compiled, {"user": {"name": "A&B"}}).to_bytes() == b"A&B"

    def test_dotted_unescaped_variable_paths_work_for_dataclass_attributes(
        self,
    ) -> None:
        @dataclass(frozen=True)
        class User:
            name: str

        compiled = fstache.compile(b"{{& user.name}}")

        assert (
            render_template(compiled, {"user": User(name="A&B")}).to_bytes() == b"A&B"
        )
