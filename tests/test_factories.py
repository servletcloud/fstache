from collections.abc import Callable
from pathlib import Path

import fstache
import pytest

from fstache import Delimiters, TemplateSyntaxError


class TestCreateRenderer:
    def test_create_dev_renderer_is_live_and_fails_fast(
        self,
        tmp_path: Path,
    ) -> None:
        path = tmp_path / "page.mustache"
        _write_template(path, b"Hello {{name}}")

        render = fstache.create_dev_renderer(tmp_path)

        with pytest.raises(
            fstache.MissingVariableError,
            match="missing template variable: name",
        ):
            render("page.mustache", {})

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == b"Hello Ada"

        path.write_bytes(b"Goodbye {{name}}")

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == b"Goodbye Ada"

    def test_create_test_renderer_preloads_and_fails_fast(
        self,
        tmp_path: Path,
    ) -> None:
        path = tmp_path / "page.mustache"
        _write_template(path, b"Hello {{name}}")

        render = fstache.create_test_renderer(tmp_path)

        path.write_bytes(b"Goodbye {{name}}")

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == b"Hello Ada"

        with pytest.raises(
            fstache.MissingVariableError,
            match="missing template variable: name",
        ):
            render("page.mustache", {})

    def test_create_prod_renderer_preloads_trims_and_renders_missing_as_empty(
        self,
        tmp_path: Path,
    ) -> None:
        path = tmp_path / "page.mustache"
        _write_template(path, b"  Hello {{name}}")

        render = fstache.create_prod_renderer(tmp_path)

        path.write_bytes(b"Goodbye {{name}}")

        assert render("page.mustache", {}).to_bytes() == b"Hello "
        assert render("missing.mustache", {"name": "Ada"}).to_bytes() == b""

    def test_create_prod_renderer_applies_prod_options_to_partials(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(
            tmp_path / "page.mustache",
            b"  Begin.\n  {{>name.mustache}}\nEnd.",
        )
        _write_template(tmp_path / "name.mustache", b"  one\n{{name}}\n")

        render = fstache.create_prod_renderer(tmp_path)

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == (
            b"Begin.\none\nAda\nEnd."
        )

    @pytest.mark.parametrize(
        "create_renderer",
        [
            fstache.create_dev_renderer,
            fstache.create_test_renderer,
            fstache.create_prod_renderer,
        ],
    )
    def test_environment_renderers_accept_create_renderer_overrides(
        self,
        tmp_path: Path,
        create_renderer: Callable[..., fstache.TemplateRenderer],
    ) -> None:
        path = tmp_path / "page.mustache"
        _write_template(path, b"Hello {{name}}")

        render = create_renderer(
            tmp_path,
            preload_templates=True,
            resolve_missing_variable=fstache.resolve_missing_variable_as_none,
        )

        path.write_bytes(b"Goodbye {{name}}")

        assert render("page.mustache", {}).to_bytes() == b"Hello "

    def test_default_extension_keeps_mustache_names(self, tmp_path: Path) -> None:
        _write_template(
            tmp_path / "pages" / "hero.mustache",
            b"Hello {{>partials/name.mustache}}",
        )
        _write_template(tmp_path / "partials" / "name.mustache", b"{{name}}")

        render = fstache.create_renderer(tmp_path)

        assert render("pages/hero.mustache", {"name": "A&B"}).to_bytes() == (
            b"Hello A&amp;B"
        )

    def test_extension_without_dot_matches_mustache_files(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(tmp_path / "page.mustache", b"Hello {{name}}")

        render = fstache.create_renderer(tmp_path, extension="mustache")

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == b"Hello Ada"

    def test_remove_extension_uses_extensionless_template_names(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(tmp_path / "pages" / "hero.mustache", b"{{>partials/name}}")
        _write_template(tmp_path / "partials" / "name.mustache", b"{{name}}")

        render = fstache.create_renderer(tmp_path, remove_extension=True)

        assert render("pages/hero", {"name": "Ada"}).to_bytes() == b"Ada"

    def test_recursive_discovery_supports_slash_separated_partial_names(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(
            tmp_path / "pages" / "landing" / "home.mustache",
            b"{{>shared/cards/title.mustache}}",
        )
        _write_template(tmp_path / "shared" / "cards" / "title.mustache", b"Home")

        render = fstache.create_renderer(tmp_path)

        assert render("pages/landing/home.mustache", {}).to_bytes() == b"Home"

    def test_missing_root_template_raises_missing_template_error(
        self,
        tmp_path: Path,
    ) -> None:
        render = fstache.create_renderer(tmp_path)

        with pytest.raises(
            fstache.MissingTemplateError,
            match="missing template: missing\\.mustache",
        ) as exc_info:
            render("missing.mustache", {})

        assert exc_info.value.name == "missing.mustache"
        assert not isinstance(exc_info.value, KeyError)

    def test_missing_partial_raises_missing_template_error(
        self, tmp_path: Path
    ) -> None:
        _write_template(tmp_path / "page.mustache", b"{{>missing.mustache}}")

        render = fstache.create_renderer(tmp_path)

        with pytest.raises(
            fstache.MissingTemplateError,
            match="missing template: missing\\.mustache",
        ) as exc_info:
            render("page.mustache", {})

        assert exc_info.value.name == "missing.mustache"
        assert not isinstance(exc_info.value, KeyError)

    def test_resolve_missing_template_as_error_can_be_called_directly(self) -> None:
        with pytest.raises(
            fstache.MissingTemplateError,
            match="missing template: missing\\.mustache",
        ) as exc_info:
            fstache.resolve_missing_template_as_error("missing.mustache")

        assert exc_info.value.name == "missing.mustache"
        assert not isinstance(exc_info.value, KeyError)

    def test_resolve_missing_template_as_empty_can_be_called_directly(self) -> None:
        assert fstache.resolve_missing_template_as_empty("missing.mustache") is (
            fstache.EMPTY_TEMPLATE
        )

    def test_missing_root_template_can_render_empty_output(
        self,
        tmp_path: Path,
    ) -> None:
        render = fstache.create_renderer(
            tmp_path,
            resolve_missing_template=fstache.resolve_missing_template_as_empty,
        )

        assert render("missing.mustache", {}).to_bytes() == b""

    def test_missing_partial_can_render_empty_output(self, tmp_path: Path) -> None:
        _write_template(tmp_path / "page.mustache", b"Hello {{>missing.mustache}}")

        render = fstache.create_renderer(
            tmp_path,
            resolve_missing_template=fstache.resolve_missing_template_as_empty,
        )

        assert render("page.mustache", {}).to_bytes() == b"Hello "

    def test_custom_missing_template_resolver_can_return_fallback_template(
        self,
        tmp_path: Path,
    ) -> None:
        names: list[str] = []

        def resolve_missing_template(name: str) -> fstache.CompiledTemplate:
            names.append(name)

            return fstache.compile(b"{{name}}")

        _write_template(tmp_path / "page.mustache", b"Hello {{>missing.mustache}}")

        render = fstache.create_renderer(
            tmp_path,
            resolve_missing_template=resolve_missing_template,
        )

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == b"Hello Ada"
        assert names == ["missing.mustache"]

    def test_custom_missing_template_resolver_exception_propagates(
        self,
        tmp_path: Path,
    ) -> None:
        class CustomMissingTemplateError(Exception):
            pass

        def resolve_missing_template(name: str) -> fstache.CompiledTemplate:
            raise CustomMissingTemplateError(name)

        render = fstache.create_renderer(
            tmp_path,
            resolve_missing_template=resolve_missing_template,
        )

        with pytest.raises(CustomMissingTemplateError, match="missing\\.mustache"):
            render("missing.mustache", {})

    def test_syntax_errors_include_relative_template_name(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(tmp_path / "pages" / "broken.mustache", b"{{#open}}")

        with pytest.raises(TemplateSyntaxError) as exc_info:
            fstache.create_renderer(tmp_path)

        assert exc_info.value.template_name == "pages/broken.mustache"
        assert "pages/broken.mustache" in str(exc_info.value)

    def test_preload_templates_false_sees_root_template_edits(
        self,
        tmp_path: Path,
    ) -> None:
        path = tmp_path / "page.mustache"
        _write_template(path, b"Hello {{name}}")

        render = fstache.create_renderer(tmp_path, preload_templates=False)

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == b"Hello Ada"

        path.write_bytes(b"Goodbye {{name}}")

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == b"Goodbye Ada"

    def test_preload_templates_true_does_not_see_root_template_edits(
        self,
        tmp_path: Path,
    ) -> None:
        path = tmp_path / "page.mustache"
        _write_template(path, b"Hello {{name}}")

        render = fstache.create_renderer(tmp_path)

        path.write_bytes(b"Goodbye {{name}}")

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == b"Hello Ada"

    def test_preloaded_and_live_renderers_resolve_dot_prefixed_partials_equally(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(tmp_path / "page.mustache", b"Hello {{>./partial.mustache}}")
        _write_template(tmp_path / "partial.mustache", b"Partial")

        def create(preload_templates: bool) -> fstache.TemplateRenderer:
            return fstache.create_renderer(
                tmp_path,
                preload_templates=preload_templates,
                resolve_missing_template=fstache.resolve_missing_template_as_empty,
            )

        live = create(preload_templates=False)
        preloaded = create(preload_templates=True)
        expected = live("page.mustache", {}).to_bytes()

        assert expected == b"Hello Partial"
        assert preloaded("page.mustache", {}).to_bytes() == expected

    def test_preload_templates_false_sees_partial_template_edits(
        self,
        tmp_path: Path,
    ) -> None:
        partial_path = tmp_path / "partial.mustache"
        _write_template(tmp_path / "page.mustache", b"Hello {{>partial.mustache}}")
        _write_template(partial_path, b"{{name}}")

        render = fstache.create_renderer(tmp_path, preload_templates=False)

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == b"Hello Ada"

        partial_path.write_bytes(b"{{title}}")

        assert render("page.mustache", {"title": "Dr."}).to_bytes() == b"Hello Dr."

    def test_preload_templates_false_can_render_new_files(
        self,
        tmp_path: Path,
    ) -> None:
        render = fstache.create_renderer(tmp_path, preload_templates=False)

        _write_template(tmp_path / "page.mustache", b"Hello {{name}}")

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == b"Hello Ada"

    def test_preload_templates_false_missing_root_uses_resolver(
        self,
        tmp_path: Path,
    ) -> None:
        names: list[str] = []

        def resolve_missing_template(name: str) -> fstache.CompiledTemplate:
            names.append(name)

            return fstache.EMPTY_TEMPLATE

        render = fstache.create_renderer(
            tmp_path,
            preload_templates=False,
            resolve_missing_template=resolve_missing_template,
        )

        assert render("missing.mustache", {}).to_bytes() == b""
        assert names == ["missing.mustache"]

    def test_preload_templates_false_missing_partial_uses_resolver(
        self,
        tmp_path: Path,
    ) -> None:
        names: list[str] = []

        def resolve_missing_template(name: str) -> fstache.CompiledTemplate:
            names.append(name)

            return fstache.compile(b"fallback")

        _write_template(tmp_path / "page.mustache", b"Hello {{>missing.mustache}}")

        render = fstache.create_renderer(
            tmp_path,
            preload_templates=False,
            resolve_missing_template=resolve_missing_template,
        )

        assert render("page.mustache", {}).to_bytes() == b"Hello fallback"
        assert names == ["missing.mustache"]

    def test_preload_templates_false_custom_missing_resolver_can_return_fallback(
        self,
        tmp_path: Path,
    ) -> None:
        def resolve_missing_template(name: str) -> fstache.CompiledTemplate:
            return fstache.compile(b"Missing {{name}}")

        render = fstache.create_renderer(
            tmp_path,
            preload_templates=False,
            resolve_missing_template=resolve_missing_template,
        )

        assert render("missing.mustache", {"name": "Ada"}).to_bytes() == (
            b"Missing Ada"
        )

    def test_preload_templates_false_delays_syntax_errors_until_render(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(tmp_path / "broken.mustache", b"{{#open}}")

        render = fstache.create_renderer(tmp_path, preload_templates=False)

        with pytest.raises(TemplateSyntaxError) as exc_info:
            render("broken.mustache", {})

        assert exc_info.value.template_name == "broken.mustache"

    def test_preload_templates_false_ignore_indents_sees_partial_edits(
        self,
        tmp_path: Path,
    ) -> None:
        partial_path = tmp_path / "name.mustache"
        _write_template(
            tmp_path / "page.mustache", b"Begin.\n  {{>name.mustache}}\nEnd."
        )
        _write_template(tmp_path / "name.mustache", b"{{name}}\n")

        render = fstache.create_renderer(
            tmp_path,
            ignore_indents=True,
            preload_templates=False,
        )

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == (
            b"Begin.\nAda\nEnd."
        )

        partial_path.write_bytes(b"{{title}}\n")

        assert render("page.mustache", {"title": "Dr."}).to_bytes() == (
            b"Begin.\nDr.\nEnd."
        )

    def test_preload_templates_false_preserves_extension_mapping(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(tmp_path / "page.mustache", b"Hello {{>partial}}")
        _write_template(tmp_path / "partial.mustache", b"{{name}}")

        render = fstache.create_renderer(
            tmp_path,
            extension="mustache",
            remove_extension=True,
            preload_templates=False,
        )

        assert render("page", {"name": "Ada"}).to_bytes() == b"Hello Ada"

    @pytest.mark.parametrize(
        "name",
        [
            "page.txt",
            "missing.mustache",
            "directory.mustache",
            "../outside.mustache",
            "/outside.mustache",
        ],
    )
    def test_preload_templates_false_invalid_names_use_resolver(
        self,
        tmp_path: Path,
        name: str,
    ) -> None:
        names: list[str] = []

        def resolve_missing_template(name: str) -> fstache.CompiledTemplate:
            names.append(name)

            return fstache.EMPTY_TEMPLATE

        _write_template(tmp_path / "page.txt", b"wrong extension")
        (tmp_path / "directory.mustache").mkdir()

        render = fstache.create_renderer(
            tmp_path,
            preload_templates=False,
            resolve_missing_template=resolve_missing_template,
        )

        assert render(name, {}).to_bytes() == b""
        assert names == [name]

    @pytest.mark.parametrize(
        "name",
        [
            "page.txt",
            "missing.mustache",
            "directory.mustache",
            "../outside.mustache",
            "/outside.mustache",
        ],
    )
    def test_preload_templates_true_invalid_names_use_resolver(
        self,
        tmp_path: Path,
        name: str,
    ) -> None:
        names: list[str] = []

        def resolve_missing_template(name: str) -> fstache.CompiledTemplate:
            names.append(name)

            return fstache.EMPTY_TEMPLATE

        _write_template(tmp_path / "page.txt", b"wrong extension")
        (tmp_path / "directory.mustache").mkdir()

        render = fstache.create_renderer(
            tmp_path,
            resolve_missing_template=resolve_missing_template,
        )

        assert render(name, {}).to_bytes() == b""
        assert names == [name]

    @pytest.mark.parametrize("preload_templates", [False, True])
    def test_symlink_to_template_inside_root_renders(
        self,
        tmp_path: Path,
        preload_templates: bool,
    ) -> None:
        _write_template(tmp_path / "target.mustache", b"Hello {{name}}")
        (tmp_path / "linked.mustache").symlink_to(tmp_path / "target.mustache")

        render = fstache.create_renderer(
            tmp_path,
            preload_templates=preload_templates,
        )

        assert render("linked.mustache", {"name": "Ada"}).to_bytes() == b"Hello Ada"

    @pytest.mark.parametrize("preload_templates", [False, True])
    def test_root_template_symlink_outside_root_uses_resolver(
        self,
        tmp_path: Path,
        preload_templates: bool,
    ) -> None:
        names: list[str] = []
        outside_path = tmp_path.parent / f"{tmp_path.name}-outside" / "secret.mustache"

        def resolve_missing_template(name: str) -> fstache.CompiledTemplate:
            names.append(name)

            return fstache.compile(b"fallback {{name}}")

        _write_template(outside_path, b"secret {{name}}")
        (tmp_path / "leak.mustache").symlink_to(outside_path)

        render = fstache.create_renderer(
            tmp_path,
            preload_templates=preload_templates,
            resolve_missing_template=resolve_missing_template,
        )

        assert render("leak.mustache", {"name": "Ada"}).to_bytes() == b"fallback Ada"
        assert names == ["leak.mustache"]

    @pytest.mark.parametrize("preload_templates", [False, True])
    def test_partial_symlink_outside_root_uses_resolver(
        self,
        tmp_path: Path,
        preload_templates: bool,
    ) -> None:
        names: list[str] = []
        outside_path = tmp_path.parent / f"{tmp_path.name}-outside" / "secret.mustache"

        def resolve_missing_template(name: str) -> fstache.CompiledTemplate:
            names.append(name)

            return fstache.compile(b"fallback")

        _write_template(tmp_path / "page.mustache", b"Hello {{>leak.mustache}}")
        _write_template(outside_path, b"secret")
        (tmp_path / "leak.mustache").symlink_to(outside_path)

        render = fstache.create_renderer(
            tmp_path,
            preload_templates=preload_templates,
            resolve_missing_template=resolve_missing_template,
        )

        assert render("page.mustache", {}).to_bytes() == b"Hello fallback"
        assert names == ["leak.mustache"]

    def test_delimiters_compile_root_templates_and_partials(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(tmp_path / "page.mustache", b"Hello [[>name.mustache]]")
        _write_template(tmp_path / "name.mustache", b"[[name]]")

        render = fstache.create_renderer(
            tmp_path,
            delimiters=Delimiters(start=b"[[", end=b"]]"),
        )

        assert render("page.mustache", {"name": "A&B"}).to_bytes() == (b"Hello A&amp;B")

    def test_ignore_indents_compiles_root_templates_and_partials(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(
            tmp_path / "page.mustache", b"Begin.\n  {{>name.mustache}}\nEnd."
        )
        _write_template(tmp_path / "name.mustache", b"one\n{{name}}\n")

        render = fstache.create_renderer(tmp_path, ignore_indents=True)

        assert render("page.mustache", {"name": "A&B"}).to_bytes() == (
            b"Begin.\none\nA&amp;B\nEnd."
        )

    def test_left_trim_source_compiles_root_templates(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(tmp_path / "page.mustache", b"  Hello {{name}}")

        render = fstache.create_renderer(
            tmp_path,
            ignore_indents=True,
            left_trim_source=True,
        )

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == b"Hello Ada"

    def test_compile_options_apply_to_lambda_templates(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(tmp_path / "page.mustache", b"{{#wrap}}ignored{{/wrap}}")

        render = fstache.create_renderer(
            tmp_path,
            ignore_indents=True,
            left_trim_source=True,
        )

        assert (
            render(
                "page.mustache",
                {
                    "wrap": lambda body: "  {{name}}",
                    "name": "Ada",
                },
            ).to_bytes()
            == b"Ada"
        )

    def test_resolve_missing_variable_uses_factory_hook(self, tmp_path: Path) -> None:
        paths: list[tuple[str, ...]] = []

        def resolve_missing_variable(path: tuple[str, ...]) -> object:
            paths.append(path)

            return "fallback"

        _write_template(tmp_path / "page.mustache", b"Hello {{user.name}}")

        render = fstache.create_renderer(
            tmp_path, resolve_missing_variable=resolve_missing_variable
        )

        assert render("page.mustache", {}).to_bytes() == b"Hello fallback"
        assert paths == [("user", "name")]

    def test_escape_uses_factory_hook_for_root_and_partial_variables(
        self,
        tmp_path: Path,
    ) -> None:
        values: list[bytes] = []

        def escape(value: bytes) -> bytes:
            values.append(value)

            return b"[" + value + b"]"

        _write_template(tmp_path / "page.mustache", b"{{name}} {{>partial.mustache}}")
        _write_template(tmp_path / "partial.mustache", b"{{title}}")

        render = fstache.create_renderer(tmp_path, escape=escape)

        assert render("page.mustache", {"name": "A&B", "title": "C<D"}).to_bytes() == (
            b"[A&B] [C<D]"
        )
        assert values == [b"A&B", b"C<D"]

    def test_resolve_missing_variable_as_none_is_public_default(self) -> None:
        assert fstache.resolve_missing_variable_as_none(("name",)) is None

    def test_resolve_missing_variable_as_error_works_with_create_renderer(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(tmp_path / "page.mustache", b"Hello {{user.name}}")

        render = fstache.create_renderer(
            tmp_path,
            resolve_missing_variable=fstache.resolve_missing_variable_as_error,
        )

        with pytest.raises(
            fstache.MissingVariableError,
            match="missing template variable: user\\.name",
        ) as exc_info:
            render("page.mustache", {})

        assert exc_info.value.path == ("user", "name")
        assert exc_info.value.name == "user.name"

    def test_create_renderer_defaults_missing_variables_to_empty_output(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(tmp_path / "page.mustache", b"Hello {{name}}")

        render = fstache.create_renderer(tmp_path)

        assert render("page.mustache", {}).to_bytes() == b"Hello "

    def test_ignore_indents_removes_partial_indentation(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(
            tmp_path / "page.mustache",
            b"Begin.\n  {{>name.mustache}}\nEnd.",
        )
        _write_template(tmp_path / "name.mustache", b"one\n{{name}}\n")

        render = fstache.create_renderer(tmp_path, ignore_indents=True)

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == (
            b"Begin.\none\nAda\nEnd."
        )

    def test_default_indentation_behavior_applies_partial_indentation(
        self,
        tmp_path: Path,
    ) -> None:
        _write_template(
            tmp_path / "page.mustache",
            b"Begin.\n  {{>name.mustache}}\nEnd.",
        )
        _write_template(tmp_path / "name.mustache", b"one\n{{name}}\n")

        render = fstache.create_renderer(tmp_path)

        assert render("page.mustache", {"name": "Ada"}).to_bytes() == (
            b"Begin.\n  one\n  Ada\nEnd."
        )


def _write_template(path: Path, template: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(template)
