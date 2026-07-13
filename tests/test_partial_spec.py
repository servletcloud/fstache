import fstache

from fstache import CompiledTemplate
from render_helpers import render_template


class TestPartialSpecRegressions:
    def test_caller_delimiters_do_not_affect_partial_parsing(self) -> None:
        compiled = fstache.compile(b"{{=<% %>=}}<%>partial%>")

        assert (
            render_template(
                compiled,
                {"text": "content"},
                partials={"partial": b"*{{text}}*"},
            ).to_bytes()
            == b"*content*"
        )


class TestDynamicPartialSpecRegressions:
    def test_dynamic_partial_name_can_come_from_zero_arg_lambda(self) -> None:
        calls: list[str] = []

        def load_partial(name: str) -> CompiledTemplate:
            calls.append(name)

            return fstache.compile(b"{{value}}")

        compiled = fstache.compile(b"{{>*dynamic}}")

        assert (
            render_template(
                compiled, {"dynamic": lambda: "content", "value": "shown"}, load_partial
            ).to_bytes()
            == b"shown"
        )
        assert calls == ["content"]

    def test_dynamic_partial_name_resolving_to_none_does_not_load_partial(
        self,
    ) -> None:
        def load_partial(name: str) -> CompiledTemplate:
            raise AssertionError(name)

        compiled = fstache.compile(b"|{{>*dynamic}}|")

        assert (
            render_template(compiled, {"dynamic": None}, load_partial).to_bytes()
            == b"||"
        )

    def test_dynamic_partial_lambda_name_result_is_not_rendered_as_template(
        self,
    ) -> None:
        calls: list[str] = []

        def load_partial(name: str) -> CompiledTemplate:
            calls.append(name)

            return fstache.compile(b"literal")

        compiled = fstache.compile(b"{{>*dynamic}}")

        assert (
            render_template(
                compiled,
                {"dynamic": lambda: "{{name}}", "name": "content"},
                load_partial,
            ).to_bytes()
            == b"literal"
        )
        assert calls == ["{{name}}"]
