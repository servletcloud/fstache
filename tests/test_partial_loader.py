import fstache
import pytest

from fstache import CompiledTemplate, EMPTY_TEMPLATE, render


class TestPartialLoaderContract:
    def test_passes_root_template_name_to_loader_at_render_time(self) -> None:
        names: list[str] = []
        templates = {"root": fstache.compile(b"hello")}

        def load_template(name: str) -> CompiledTemplate:
            names.append(name)

            return templates[name]

        assert render("root", {}, load_template).to_bytes() == b"hello"
        assert names == ["root"]

    def test_passes_decoded_utf8_partial_name_to_loader_at_render_time(self) -> None:
        names: list[str] = []
        partial_name = "pages/landing/héro.mustache"
        templates = {
            "root": fstache.compile(f"{{{{> {partial_name} }}}}".encode()),
            partial_name: EMPTY_TEMPLATE,
        }

        def load_template(name: str) -> CompiledTemplate:
            names.append(name)

            return templates[name]

        render("root", {}, load_template).to_bytes()

        assert names == ["root", partial_name]

    def test_propagates_root_loader_exceptions(self) -> None:
        class MissingTemplateError(Exception):
            pass

        error = MissingTemplateError("root")

        def load_template(name: str) -> CompiledTemplate:
            assert name == "root"

            raise error

        with pytest.raises(MissingTemplateError) as exc_info:
            render("root", {}, load_template)

        assert exc_info.value is error

    def test_propagates_partial_loader_exceptions(self) -> None:
        class MissingTemplateError(Exception):
            pass

        error = MissingTemplateError("missing")

        def load_template(name: str) -> CompiledTemplate:
            if name == "root":
                return fstache.compile(b"{{>missing}}")

            assert name == "missing"

            raise error

        with pytest.raises(MissingTemplateError) as exc_info:
            render("root", {}, load_template).to_bytes()

        assert exc_info.value is error

    def test_public_empty_template_can_model_missing_partials(self) -> None:
        def load_template(name: str) -> CompiledTemplate:
            if name == "root":
                return fstache.compile(b"|{{>missing}}|")

            assert name == "missing"

            return EMPTY_TEMPLATE

        assert render("root", {}, load_template).to_bytes() == b"||"
