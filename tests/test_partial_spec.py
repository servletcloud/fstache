from collections.abc import Mapping

import fstache

from fstache import CompiledTemplate, EMPTY_TEMPLATE
from render_helpers import render_template


def _render_with_partials(
    template: bytes,
    data: object,
    partials: Mapping[str, bytes],
    *,
    missing_partials_are_empty: bool = False,
) -> bytes:
    def load_partial(name: str) -> CompiledTemplate:
        partial = partials.get(name)
        if partial is None:
            if missing_partials_are_empty:
                return EMPTY_TEMPLATE

            raise KeyError(name)

        return fstache.compile(partial)

    return render_template(fstache.compile(template), data, load_partial).to_bytes()


class TestPartialSpecRegressions:
    def test_caller_delimiters_do_not_affect_partial_parsing(self) -> None:
        assert (
            _render_with_partials(
                b"{{=<% %>=}}<%>partial%>",
                {"text": "content"},
                {"partial": b"*{{text}}*"},
            )
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
