from collections.abc import Mapping
from typing import Any, Final

import fstache

from fstache import (
    CompiledTemplate,
    EMPTY_TEMPLATE,
    RenderedTemplate,
    TemplateLoader,
    render,
)


ROOT_TEMPLATE_NAME: Final = "root"

type TemplateSource = bytes | CompiledTemplate


def make_template_loader(
    template: TemplateSource,
    load_partial: TemplateLoader | None = None,
    *,
    partials: Mapping[str, TemplateSource] | None = None,
    root_name: str = ROOT_TEMPLATE_NAME,
    missing_partials_are_empty: bool = False,
) -> TemplateLoader:
    compiled_partials = {
        name: _compile_template_source(partial, name=name)
        for name, partial in (partials or {}).items()
    }
    root_template = _compile_template_source(template, name=root_name)

    def load_template(name: str) -> CompiledTemplate:
        if name == root_name:
            return root_template

        partial = compiled_partials.get(name)
        if partial is not None:
            return partial

        if load_partial is not None:
            return load_partial(name)

        if missing_partials_are_empty:
            return EMPTY_TEMPLATE

        raise KeyError(name)

    return load_template


def render_template(
    template: TemplateSource,
    data: object,
    load_partial: TemplateLoader | None = None,
    *,
    partials: Mapping[str, TemplateSource] | None = None,
    root_name: str = ROOT_TEMPLATE_NAME,
    missing_partials_are_empty: bool = False,
    **render_options: Any,
) -> RenderedTemplate:
    load_template = make_template_loader(
        template,
        load_partial,
        partials=partials,
        root_name=root_name,
        missing_partials_are_empty=missing_partials_are_empty,
    )

    return render(
        root_name,
        data,
        load_template,
        **render_options,
    )


def _compile_template_source(
    template: TemplateSource, *, name: str
) -> CompiledTemplate:
    if type(template) is bytes:
        return fstache.compile(template, name=name)

    return template
