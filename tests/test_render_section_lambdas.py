import fstache
import pytest

from fstache import CompiledTemplate, DEFAULT_DELIMITERS, Delimiters
from render_helpers import render_template


class TestRenderSectionLambdas:
    def test_section_lambda_receives_literal_unrendered_body(self) -> None:
        bodies: list[str] = []

        def capture_body(body: str) -> None:
            bodies.append(body)

        compiled = fstache.compile(b"{{#wrap}}{{name}}{{/wrap}}")

        assert (
            render_template(compiled, {"wrap": capture_body, "name": "A&B"}).to_bytes()
            == b""
        )
        assert bodies == ["{{name}}"]

    def test_left_trim_source_section_lambda_receives_trimmed_body(self) -> None:
        bodies: list[str] = []

        def capture_body(body: str) -> None:
            bodies.append(body)

        compiled = fstache.compile(
            b"{{#wrap}}\n  {{name}}\n{{/wrap}}",
            left_trim_source=True,
        )

        assert (
            render_template(compiled, {"wrap": capture_body, "name": "A&B"}).to_bytes()
            == b""
        )
        assert bodies == ["{{name}}\n"]

    def test_dotted_final_section_lambda_receives_literal_unrendered_body(self) -> None:
        bodies: list[str] = []

        def capture_body(body: str) -> None:
            bodies.append(body)

        compiled = fstache.compile(b"{{#user.wrap}}{{name}}{{/user.wrap}}")

        assert (
            render_template(
                compiled, {"user": {"wrap": capture_body}, "name": "A&B"}
            ).to_bytes()
            == b""
        )
        assert bodies == ["{{name}}"]

    def test_section_lambda_string_result_renders_against_current_scope(self) -> None:
        compiled = fstache.compile(b"{{#wrap}}ignored{{/wrap}}")

        assert (
            render_template(
                compiled, {"wrap": lambda body: "{{name}}", "name": "world"}
            ).to_bytes()
            == b"world"
        )

    def test_section_lambda_string_result_uses_custom_compiler(self) -> None:
        calls: list[tuple[bytes, Delimiters]] = []

        def compile_template(
            template: bytes,
            *,
            delimiters: Delimiters = DEFAULT_DELIMITERS,
        ) -> CompiledTemplate:
            calls.append((template, delimiters))

            return fstache.compile(b"|override|", delimiters=delimiters)

        compiled = fstache.compile(b"{{= | | =}}|#wrap|ignored|/wrap|")

        assert (
            render_template(
                compiled,
                {
                    "wrap": lambda body: "|name|",
                    "name": "ignored",
                    "override": "custom",
                },
                compile_template=compile_template,
            ).to_bytes()
            == b"custom"
        )
        assert calls[0][0] == b"|name|"
        assert calls[0][1].start == b"|"
        assert calls[0][1].end == b"|"

    def test_section_lambda_string_result_can_render_partial_with_loader(self) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            assert name == "user"

            return fstache.compile(b"{{name}}")

        compiled = fstache.compile(b"{{#wrap}}ignored{{/wrap}}")

        assert (
            render_template(
                compiled,
                {"wrap": lambda body: "{{>user}}", "name": "A&B"},
                load_partial,
            ).to_bytes()
            == b"A&amp;B"
        )

    def test_section_lambda_string_result_can_render_empty_missing_partial(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{#wrap}}ignored{{/wrap}}")

        assert (
            render_template(
                compiled,
                {"wrap": lambda body: "{{>user}}"},
                missing_partials_are_empty=True,
            ).to_bytes()
            == b""
        )

    def test_section_lambda_result_uses_section_body_delimiters(self) -> None:
        compiled = fstache.compile(b"{{= | | =}}|#wrap|ignored|/wrap|")

        assert (
            render_template(
                compiled, {"wrap": lambda body: "|name|", "name": "A&B"}
            ).to_bytes()
            == b"A&amp;B"
        )

    def test_one_arg_section_lambda_receives_raw_body_and_uses_current_delimiters(
        self,
    ) -> None:
        bodies: list[str] = []

        def wrap(body: str) -> str:
            bodies.append(body)

            return "|name|"

        compiled = fstache.compile(b"{{= | | =}}|#wrap||name||/wrap|")

        assert (
            render_template(compiled, {"wrap": wrap, "name": "A&B"}).to_bytes()
            == b"A&amp;B"
        )
        assert bodies == ["|name|"]

    def test_section_lambda_inside_list_renders_against_current_scope(self) -> None:
        compiled = fstache.compile(b"{{#users}}{{#wrap}}x{{/wrap}};{{/users}}")
        data = {
            "site": "Docs",
            "users": [
                {"name": "A&B", "wrap": lambda body: "{{name}}@{{site}}"},
                {"name": "<C>", "wrap": lambda body: "{{name}}@{{site}}"},
            ],
        }

        assert (
            render_template(compiled, data).to_bytes()
            == b"A&amp;B@Docs;&lt;C&gt;@Docs;"
        )

    def test_section_lambda_returning_none_renders_empty_bytes(self) -> None:
        compiled = fstache.compile(b"{{#wrap}}ignored{{/wrap}}")

        assert render_template(compiled, {"wrap": lambda body: None}).to_bytes() == b""

    def test_section_lambda_returning_scalar_renders_with_str(self) -> None:
        compiled = fstache.compile(b"{{#wrap}}ignored{{/wrap}}")

        assert render_template(compiled, {"wrap": lambda body: 42}).to_bytes() == b"42"

    def test_section_lambda_invalid_utf8_body_raises_unicode_decode_error(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{#wrap}}\xff{{/wrap}}")

        with pytest.raises(UnicodeDecodeError):
            render_template(compiled, {"wrap": lambda body: body}).to_bytes()

    def test_inverted_sections_do_not_invoke_lambdas(self) -> None:
        def fail_if_called() -> bool:
            raise AssertionError("inverted section lambda should not be invoked")

        compiled = fstache.compile(b"{{^flag}}empty{{/flag}}")

        assert render_template(compiled, {"flag": fail_if_called}).to_bytes() == b""

    def test_dotted_final_inverted_section_lambdas_are_not_invoked(self) -> None:
        def fail_if_called() -> bool:
            raise AssertionError("inverted section lambda should not be invoked")

        compiled = fstache.compile(b"{{^user.flag}}empty{{/user.flag}}")

        assert (
            render_template(compiled, {"user": {"flag": fail_if_called}}).to_bytes()
            == b""
        )
