import fstache
import pytest

from fstache import CompiledTemplate, EMPTY_TEMPLATE, TemplateSyntaxError, render


class TestPartialLoaderContract:
    def test_passes_root_template_name_to_loader_at_render_time(self) -> None:
        names: list[str] = []
        templates = {"root": fstache.compile(b"hello")}

        def load_template(name: str) -> CompiledTemplate:
            names.append(name)

            return templates[name]

        assert render("root", {}, load_template).to_bytes() == b"hello"
        assert names == ["root"]

    def test_passes_raw_utf8_partial_name_to_loader_at_render_time(self) -> None:
        names: list[str] = []
        templates = {
            "root": fstache.compile(b"{{> pages/landing/hero.mustache }}"),
            "pages/landing/hero.mustache": EMPTY_TEMPLATE,
        }

        def load_template(name: str) -> CompiledTemplate:
            names.append(name)

            return templates[name]

        render("root", {}, load_template).to_bytes()

        assert names == ["root", "pages/landing/hero.mustache"]

    def test_propagates_root_loader_exceptions(self) -> None:
        class MissingTemplateError(Exception):
            pass

        def load_template(name: str) -> CompiledTemplate:
            raise MissingTemplateError(name)

        with pytest.raises(MissingTemplateError) as exc_info:
            render("root", {}, load_template)

        assert exc_info.value.args == ("root",)

    def test_propagates_partial_loader_exceptions(self) -> None:
        class MissingTemplateError(Exception):
            pass

        def load_template(name: str) -> CompiledTemplate:
            if name == "root":
                return fstache.compile(b"{{>missing}}")

            raise MissingTemplateError(name)

        with pytest.raises(MissingTemplateError) as exc_info:
            render("root", {}, load_template).to_bytes()

        assert exc_info.value.args == ("missing",)

    def test_strict_loader_can_raise_for_partial_tags_at_render_time(self) -> None:
        def load_template(name: str) -> CompiledTemplate:
            if name == "root":
                return fstache.compile(b"{{> text}}")

            msg = f"unsupported partial: {name}"
            raise TemplateSyntaxError(msg)

        with pytest.raises(TemplateSyntaxError, match="unsupported partial: text"):
            render("root", {}, load_template).to_bytes()

    def test_public_empty_template_can_model_missing_partials(self) -> None:
        def load_template(name: str) -> CompiledTemplate:
            if name == "root":
                return fstache.compile(b"|{{>missing}}|")

            assert name == "missing"

            return EMPTY_TEMPLATE

        assert render("root", {}, load_template).to_bytes() == b"||"
