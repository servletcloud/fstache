import fstache

from fstache._compiler import (
    Delimiters,
    DynamicPartialNode,
    InvertedSectionNode,
    PartialNode,
    SectionNode,
    TextNode,
    VariableNode,
)


class TestInlinePartials:
    def test_inlines_static_partials_and_merges_adjacent_text(self) -> None:
        templates = {
            "main": (
                TextNode(chunks=(b"Hello ",), value=b"Hello "),
                PartialNode(name="name", indentation=None),
                TextNode(chunks=(b"!",), value=b"!"),
            ),
            "name": (TextNode(chunks=(b"world",), value=b"world"),),
        }

        assert fstache.inline_partials(templates)["main"] == (
            TextNode(chunks=(b"Hello world!",), value=b"Hello world!"),
        )

    def test_returns_new_dict_without_mutating_input_templates(self) -> None:
        main = (
            PartialNode(name="name", indentation=None),
            TextNode(chunks=(b"!",), value=b"!"),
        )
        partial = (TextNode(chunks=(b"Ada",), value=b"Ada"),)
        templates = {"main": main, "name": partial}

        inlined = fstache.inline_partials(templates)

        assert inlined is not templates
        assert templates == {"main": main, "name": partial}

    def test_inlines_nested_static_partials(self) -> None:
        templates = {
            "main": (PartialNode(name="outer", indentation=None),),
            "outer": (
                TextNode(chunks=(b"[",), value=b"["),
                PartialNode(name="inner", indentation=None),
                TextNode(chunks=(b"]",), value=b"]"),
            ),
            "inner": (VariableNode(path=("name",)),),
        }

        assert fstache.inline_partials(templates)["main"] == (
            TextNode(chunks=(b"[",), value=b"["),
            VariableNode(path=("name",)),
            TextNode(chunks=(b"]",), value=b"]"),
        )

    def test_leaves_missing_partials_unresolved(self) -> None:
        templates = {
            "main": (
                TextNode(chunks=(b"a",), value=b"a"),
                PartialNode(name="missing", indentation=None),
                TextNode(chunks=(b"c",), value=b"c"),
            ),
        }

        assert fstache.inline_partials(templates)["main"] == templates["main"]

    def test_stops_direct_recursive_inlining(self) -> None:
        templates = {
            "main": (
                TextNode(chunks=(b"a",), value=b"a"),
                PartialNode(name="main", indentation=None),
                TextNode(chunks=(b"c",), value=b"c"),
            ),
        }

        assert fstache.inline_partials(templates)["main"] == templates["main"]

    def test_stops_indirect_recursive_inlining(self) -> None:
        templates = {
            "main": (PartialNode(name="outer", indentation=None),),
            "outer": (
                TextNode(chunks=(b"b",), value=b"b"),
                PartialNode(name="main", indentation=None),
            ),
        }

        assert fstache.inline_partials(templates)["main"] == (
            TextNode(chunks=(b"b",), value=b"b"),
            PartialNode(name="main", indentation=None),
        )

    def test_leaves_dynamic_partials_unresolved(self) -> None:
        dynamic_partial = DynamicPartialNode(path=("partial_name",), indentation=None)
        templates = {
            "main": (
                TextNode(chunks=(b"a",), value=b"a"),
                dynamic_partial,
                TextNode(chunks=(b"c",), value=b"c"),
            ),
            "dynamic": (TextNode(chunks=(b"b",), value=b"b"),),
        }

        assert fstache.inline_partials(templates)["main"] == templates["main"]

    def test_inlines_section_children_without_changing_raw_body(self) -> None:
        templates = {
            "main": (
                SectionNode(
                    path=("items",),
                    children=(PartialNode(name="row", indentation=None),),
                    raw_body=b"{{>row}}",
                    delimiters=Delimiters(start=b"{{", end=b"}}"),
                ),
            ),
            "row": (TextNode(chunks=(b"{{name}}",), value=b"{{name}}"),),
        }

        assert fstache.inline_partials(templates)["main"] == (
            SectionNode(
                path=("items",),
                children=(TextNode(chunks=(b"{{name}}",), value=b"{{name}}"),),
                raw_body=b"{{>row}}",
                delimiters=Delimiters(start=b"{{", end=b"}}"),
            ),
        )

    def test_inlines_inverted_section_children(self) -> None:
        templates = {
            "main": (
                InvertedSectionNode(
                    path=("items",),
                    children=(PartialNode(name="empty", indentation=None),),
                ),
            ),
            "empty": (TextNode(chunks=(b"empty",), value=b"empty"),),
        }

        assert fstache.inline_partials(templates)["main"] == (
            InvertedSectionNode(
                path=("items",),
                children=(TextNode(chunks=(b"empty",), value=b"empty"),),
            ),
        )
