from dataclasses import dataclass

import fstache

from render_helpers import render_template


class TestRenderSections:
    def test_resolve_missing_variable_is_not_used_for_section_truthiness(self) -> None:
        def resolve_missing_variable(path: tuple[str, ...]) -> object:
            raise AssertionError(path)

        compiled = fstache.compile(b"a{{#flag}}yes{{/flag}}{{^flag}}no{{/flag}}c")

        assert render_template(
            compiled, {}, resolve_missing_variable=resolve_missing_variable
        ).to_bytes() == (b"anoc")

    def test_dotted_section_paths_invoke_intermediate_lambda(self) -> None:
        compiled = fstache.compile(b"{{#time.active}}yes{{/time.active}}")

        assert (
            render_template(compiled, {"time": lambda: {"active": True}}).to_bytes()
            == b"yes"
        )

    def test_dotted_section_paths_skip_missing_after_intermediate_lambda(self) -> None:
        compiled = fstache.compile(b"{{#time.active}}yes{{/time.active}}")

        assert render_template(compiled, {"time": lambda: {}}).to_bytes() == b""

    def test_dotted_section_paths_skip_falsey_after_intermediate_lambda(self) -> None:
        compiled = fstache.compile(b"{{#time.active}}yes{{/time.active}}")

        assert (
            render_template(compiled, {"time": lambda: {"active": False}}).to_bytes()
            == b""
        )

    def test_zero_arg_final_section_callable_returning_true_renders_body(self) -> None:
        compiled = fstache.compile(b"{{#flag}}yes{{/flag}}")

        assert render_template(compiled, {"flag": lambda: True}).to_bytes() == b"yes"

    def test_zero_arg_final_section_callable_returning_false_renders_empty(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{#flag}}yes{{/flag}}")

        assert render_template(compiled, {"flag": lambda: False}).to_bytes() == b""

    def test_zero_arg_final_section_callable_returning_mapping_enters_child_scope(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{#user}}{{name}}{{/user}}")

        assert (
            render_template(compiled, {"user": lambda: {"name": "A&B"}}).to_bytes()
            == b"A&amp;B"
        )

    def test_zero_arg_dotted_final_section_callable_renders_normally(self) -> None:
        compiled = fstache.compile(b"{{#user.active}}yes{{/user.active}}")

        assert (
            render_template(compiled, {"user": {"active": lambda: True}}).to_bytes()
            == b"yes"
        )

    def test_dotted_section_paths_work_for_dataclass_attributes(self) -> None:
        @dataclass(frozen=True)
        class User:
            active: bool

        compiled = fstache.compile(b"{{#user.active}}yes{{/user.active}}")

        assert (
            render_template(compiled, {"user": User(active=True)}).to_bytes() == b"yes"
        )

    def test_dotted_inverted_section_paths_invoke_intermediate_lambda(self) -> None:
        compiled = fstache.compile(b"{{^time.active}}no{{/time.active}}")

        assert (
            render_template(compiled, {"time": lambda: {"active": False}}).to_bytes()
            == b"no"
        )

    def test_truthy_object_enters_child_scope(self) -> None:
        @dataclass(frozen=True)
        class User:
            active: bool

        compiled = fstache.compile(b"{{#user}}{{#active}}yes{{/active}}{{/user}}")

        assert (
            render_template(compiled, {"user": User(active=True)}).to_bytes() == b"yes"
        )

    def test_true_renders_body_without_changing_scope(self) -> None:
        compiled = fstache.compile(b"{{#flag}}{{#nested}}yes{{/nested}}{{/flag}}")

        assert (
            render_template(compiled, {"flag": True, "nested": True}).to_bytes()
            == b"yes"
        )

    def test_inverted_current_scope_section_renders_for_falsey_scope(self) -> None:
        compiled = fstache.compile(b"{{^.}}empty{{/.}}")

        assert render_template(compiled, False).to_bytes() == b"empty"

    def test_falsey_current_scope_value_does_not_fall_back_to_parent_scope(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{#user}}{{site_name}}{{/user}}")
        data = {"site_name": "Parent", "user": {"site_name": None}}

        assert render_template(compiled, data).to_bytes() == b""

    def test_variables_inside_inverted_sections_resolve_from_current_scope(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{^items}}{{name}}{{/items}}")

        assert (
            render_template(compiled, {"items": [], "name": "A&B"}).to_bytes()
            == b"A&amp;B"
        )

    def test_current_scope_variables_inside_list_sections_do_not_search_parents(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{#items}}{{.}};{{/items}}")

        assert render_template(
            compiled, {"items": ["A&B", "<C>"], ".": "parent"}
        ).to_bytes() == (b"A&amp;B;&lt;C&gt;;")

    def test_non_list_or_tuple_iterables_render_once_without_iteration(self) -> None:
        class TruthyIterable:
            def __iter__(self) -> object:
                raise AssertionError("should not iterate")

        compiled = fstache.compile(b"{{#items}}x{{/items}}")

        assert render_template(compiled, {"items": TruthyIterable()}).to_bytes() == b"x"
