from dataclasses import dataclass

import fstache
import pytest

from render_helpers import render_template


class TestRenderSections:
    def test_renders_truthy_section_body(self) -> None:
        compiled = fstache.compile(b"a{{#flag}}b{{/flag}}c")

        assert render_template(compiled, {"flag": True}).to_bytes() == b"abc"

    @pytest.mark.parametrize(
        "data",
        [
            {},
            {"flag": None},
            {"flag": False},
            {"flag": 0},
            {"flag": ""},
            {"flag": {}},
            {"flag": []},
            {"flag": ()},
        ],
    )
    def test_skips_falsey_section_body(self, data: object) -> None:
        compiled = fstache.compile(b"a{{#flag}}b{{/flag}}c")

        assert render_template(compiled, data).to_bytes() == b"ac"

    @pytest.mark.parametrize(
        "data",
        [
            {},
            {"items": None},
            {"items": False},
            {"items": 0},
            {"items": ""},
            {"items": {}},
            {"items": []},
            {"items": ()},
        ],
    )
    def test_renders_inverted_section_body_for_falsey_or_missing_values(
        self, data: object
    ) -> None:
        compiled = fstache.compile(b"a{{^items}}empty{{/items}}c")

        assert render_template(compiled, data).to_bytes() == b"aemptyc"

    def test_resolve_missing_variable_is_not_used_for_section_truthiness(self) -> None:
        def resolve_missing_variable(path: tuple[str, ...]) -> object:
            raise AssertionError(path)

        compiled = fstache.compile(b"a{{#flag}}yes{{/flag}}{{^flag}}no{{/flag}}c")

        assert render_template(
            compiled, {}, resolve_missing_variable=resolve_missing_variable
        ).to_bytes() == (b"anoc")

    @pytest.mark.parametrize(
        "value",
        [
            True,
            "yes",
            {"name": "A&B"},
            ["one"],
            ("one",),
        ],
    )
    def test_skips_inverted_section_body_for_truthy_values(self, value: object) -> None:
        compiled = fstache.compile(b"a{{^items}}empty{{/items}}c")

        assert render_template(compiled, {"items": value}).to_bytes() == b"ac"

    def test_skips_inverted_section_body_for_truthy_objects(self) -> None:
        @dataclass(frozen=True)
        class User:
            name: str

        compiled = fstache.compile(b"a{{^user}}empty{{/user}}c")

        assert render_template(compiled, {"user": User(name="A&B")}).to_bytes() == b"ac"

    def test_nested_sections_resolve_from_current_scope(self) -> None:
        compiled = fstache.compile(
            b"{{#user}}{{#active}}{{#flag}}yes{{/flag}}{{/active}}{{/user}}"
        )
        data = {"user": {"active": {"flag": True}}}

        assert render_template(compiled, data).to_bytes() == b"yes"

    def test_dotted_section_paths_work_for_mappings(self) -> None:
        compiled = fstache.compile(b"{{#user.active}}yes{{/user.active}}")

        assert (
            render_template(compiled, {"user": {"active": True}}).to_bytes() == b"yes"
        )

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

    def test_dotted_inverted_section_paths_work_for_mappings(self) -> None:
        compiled = fstache.compile(b"{{^user.active}}no{{/user.active}}")

        assert (
            render_template(compiled, {"user": {"active": False}}).to_bytes() == b"no"
        )

    def test_dotted_inverted_section_paths_invoke_intermediate_lambda(self) -> None:
        compiled = fstache.compile(b"{{^time.active}}no{{/time.active}}")

        assert (
            render_template(compiled, {"time": lambda: {"active": False}}).to_bytes()
            == b"no"
        )

    def test_dotted_inverted_section_paths_work_for_dataclass_attributes(self) -> None:
        @dataclass(frozen=True)
        class User:
            active: bool

        compiled = fstache.compile(b"{{^user.active}}no{{/user.active}}")

        assert (
            render_template(compiled, {"user": User(active=False)}).to_bytes() == b"no"
        )

    def test_dotted_section_paths_work_for_properties(self) -> None:
        class User:
            @property
            def active(self) -> bool:
                return True

        compiled = fstache.compile(b"{{#user.active}}yes{{/user.active}}")

        assert render_template(compiled, {"user": User()}).to_bytes() == b"yes"

    def test_lists_repeat_section_body_once_per_item(self) -> None:
        compiled = fstache.compile(b"{{#items}}{{#active}}x{{/active}}{{/items}}")

        assert render_template(
            compiled, {"items": [{"active": True}, {"active": True}]}
        ).to_bytes() == (b"xx")

    def test_tuples_repeat_section_body_once_per_item(self) -> None:
        compiled = fstache.compile(b"{{#items}}{{#active}}x{{/active}}{{/items}}")

        assert render_template(
            compiled, {"items": ({"active": True}, {"active": True})}
        ).to_bytes() == (b"xx")

    def test_truthy_mapping_enters_child_scope(self) -> None:
        compiled = fstache.compile(b"{{#user}}{{#active}}yes{{/active}}{{/user}}")

        assert (
            render_template(compiled, {"user": {"active": True}}).to_bytes() == b"yes"
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

    def test_truthy_current_scope_section_renders_body(self) -> None:
        compiled = fstache.compile(b"{{#.}}yes{{/.}}")

        assert render_template(compiled, True).to_bytes() == b"yes"

    def test_current_scope_section_keeps_scope_for_true(self) -> None:
        compiled = fstache.compile(b"{{#.}}{{name}}{{/.}}")

        assert render_template(compiled, {"name": "A&B"}).to_bytes() == b"A&amp;B"

    @pytest.mark.parametrize(
        "data",
        [
            False,
            [],
        ],
    )
    def test_inverted_current_scope_section_renders_for_falsey_scope(
        self, data: object
    ) -> None:
        compiled = fstache.compile(b"{{^.}}empty{{/.}}")

        assert render_template(compiled, data).to_bytes() == b"empty"

    def test_variables_inside_sections_resolve_from_current_scope(self) -> None:
        compiled = fstache.compile(b"{{#user}}{{name}}{{/user}}")

        assert (
            render_template(compiled, {"user": {"name": "A&B"}}).to_bytes()
            == b"A&amp;B"
        )

    def test_variables_inside_sections_fall_back_to_parent_scope(self) -> None:
        compiled = fstache.compile(b"{{#user}}{{site_name}}: {{name}}{{/user}}")
        data = {"site_name": "Docs", "user": {"name": "A&B"}}

        assert render_template(compiled, data).to_bytes() == b"Docs: A&amp;B"

    def test_dotted_variables_fall_back_to_parent_scope_for_first_part(self) -> None:
        compiled = fstache.compile(b"{{#user}}{{site.name}}: {{name}}{{/user}}")
        data = {"site": {"name": "Docs"}, "user": {"name": "A&B"}}

        assert render_template(compiled, data).to_bytes() == b"Docs: A&amp;B"

    def test_list_item_rendering_falls_back_to_parent_scope(self) -> None:
        compiled = fstache.compile(b"{{#users}}{{site_name}}: {{name}};{{/users}}")
        data = {
            "site_name": "Docs",
            "users": [{"name": "A&B"}, {"name": "<C>"}],
        }

        assert (
            render_template(compiled, data).to_bytes()
            == b"Docs: A&amp;B;Docs: &lt;C&gt;;"
        )

    def test_current_scope_shadows_parent_scope(self) -> None:
        compiled = fstache.compile(b"{{#user}}{{site_name}}{{/user}}")
        data = {"site_name": "Parent", "user": {"site_name": "Child"}}

        assert render_template(compiled, data).to_bytes() == b"Child"

    @pytest.mark.parametrize("value", [None, ""])
    def test_falsey_current_scope_values_do_not_fall_back_to_parent_scope(
        self, value: object
    ) -> None:
        compiled = fstache.compile(b"{{#user}}{{site_name}}{{/user}}")
        data = {"site_name": "Parent", "user": {"site_name": value}}

        assert render_template(compiled, data).to_bytes() == b""

    def test_sections_inside_sections_fall_back_to_parent_scope(self) -> None:
        compiled = fstache.compile(b"{{#user}}{{#site}}{{name}}{{/site}}{{/user}}")
        data = {"site": {"name": "Docs"}, "user": {"name": "A&B"}}

        assert render_template(compiled, data).to_bytes() == b"Docs"

    def test_unescaped_variables_inside_sections_resolve_from_current_scope(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{#user}}{{{name}}}{{/user}}")

        assert render_template(compiled, {"user": {"name": "A&B"}}).to_bytes() == b"A&B"

    def test_variables_inside_inverted_sections_resolve_from_current_scope(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{^items}}{{name}}{{/items}}")

        assert (
            render_template(compiled, {"items": [], "name": "A&B"}).to_bytes()
            == b"A&amp;B"
        )

    def test_unescaped_variables_inside_inverted_sections_resolve_from_current_scope(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{^items}}{{& name}}{{/items}}")

        assert (
            render_template(compiled, {"items": [], "name": "A&B"}).to_bytes() == b"A&B"
        )

    def test_nested_normal_and_inverted_sections_render_correctly(self) -> None:
        compiled = fstache.compile(
            b"{{#user}}{{^items}}{{name}} has no items{{/items}}{{/user}}"
        )
        data = {"user": {"name": "A&B", "items": []}}

        assert render_template(compiled, data).to_bytes() == b"A&amp;B has no items"

    def test_variables_inside_list_sections_render_once_per_item(self) -> None:
        compiled = fstache.compile(b"{{#items}}{{name}};{{/items}}")

        assert render_template(
            compiled, {"items": [{"name": "A&B"}, {"name": "<C>"}]}
        ).to_bytes() == (b"A&amp;B;&lt;C&gt;;")

    def test_current_scope_variables_inside_list_sections_render_each_item(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{#items}}{{.}};{{/items}}")

        assert render_template(compiled, {"items": ["A&B", "<C>"]}).to_bytes() == (
            b"A&amp;B;&lt;C&gt;;"
        )

    def test_current_scope_variables_inside_list_sections_do_not_search_parents(
        self,
    ) -> None:
        compiled = fstache.compile(b"{{#items}}{{.}};{{/items}}")

        assert render_template(
            compiled, {"items": ["A&B", "<C>"], ".": "parent"}
        ).to_bytes() == (b"A&amp;B;&lt;C&gt;;")

    def test_non_list_tuple_iterables_render_once_without_iteration(self) -> None:
        class TruthyIterable:
            def __iter__(self) -> object:
                raise AssertionError("should not iterate")

        compiled = fstache.compile(b"{{#items}}x{{/items}}")

        assert render_template(compiled, {"items": TruthyIterable()}).to_bytes() == b"x"

    @pytest.mark.parametrize(
        ("template", "expected"),
        [
            (
                b"Begin.\n{{#flag}}\nShown.\n{{/flag}}\nEnd.",
                b"Begin.\nShown.\nEnd.",
            ),
            (
                b"Begin.\r\n{{#flag}}\r\nShown.\r\n{{/flag}}\r\nEnd.",
                b"Begin.\r\nShown.\r\nEnd.",
            ),
            (
                b"Begin.\n  \t{{#flag}}\nShown.\n  \t{{/flag}}\nEnd.",
                b"Begin.\nShown.\nEnd.",
            ),
            (
                b"{{#flag}}\nShown.\n{{/flag}}\nEnd.",
                b"Shown.\nEnd.",
            ),
            (
                b"Begin.\n{{#flag}}\nShown.\n{{/flag}}",
                b"Begin.\nShown.\n",
            ),
        ],
    )
    def test_trims_standalone_section_lines(
        self, template: bytes, expected: bytes
    ) -> None:
        compiled = fstache.compile(template)

        assert render_template(compiled, {"flag": True}).to_bytes() == expected

    def test_trims_standalone_section_lines_when_section_is_falsey(self) -> None:
        compiled = fstache.compile(b"Begin.\n{{#flag}}\nHidden.\n{{/flag}}\nEnd.")

        assert render_template(compiled, {"flag": False}).to_bytes() == b"Begin.\nEnd."

    @pytest.mark.parametrize(
        ("template", "expected"),
        [
            (
                b"Begin.\n{{^items}}\nEmpty.\n{{/items}}\nEnd.",
                b"Begin.\nEmpty.\nEnd.",
            ),
            (
                b"Begin.\r\n{{^items}}\r\nEmpty.\r\n{{/items}}\r\nEnd.",
                b"Begin.\r\nEmpty.\r\nEnd.",
            ),
            (
                b"Begin.\n  \t{{^items}}\nEmpty.\n  \t{{/items}}\nEnd.",
                b"Begin.\nEmpty.\nEnd.",
            ),
            (
                b"{{^items}}\nEmpty.\n{{/items}}\nEnd.",
                b"Empty.\nEnd.",
            ),
            (
                b"Begin.\n{{^items}}\nEmpty.\n{{/items}}",
                b"Begin.\nEmpty.\n",
            ),
        ],
    )
    def test_trims_standalone_inverted_section_lines(
        self, template: bytes, expected: bytes
    ) -> None:
        compiled = fstache.compile(template)

        assert render_template(compiled, {"items": []}).to_bytes() == expected

    def test_trims_standalone_inverted_section_lines_when_section_is_truthy(
        self,
    ) -> None:
        compiled = fstache.compile(b"Begin.\n{{^items}}\nEmpty.\n{{/items}}\nEnd.")

        assert (
            render_template(compiled, {"items": ["one"]}).to_bytes() == b"Begin.\nEnd."
        )

    def test_inline_sections_preserve_surrounding_whitespace(self) -> None:
        compiled = fstache.compile(b"| {{#flag}}x{{/flag}} |")

        assert render_template(compiled, {"flag": True}).to_bytes() == b"| x |"

    def test_inline_inverted_sections_preserve_surrounding_whitespace(self) -> None:
        compiled = fstache.compile(b"| {{^items}}empty{{/items}} |")

        assert render_template(compiled, {"items": []}).to_bytes() == b"| empty |"
