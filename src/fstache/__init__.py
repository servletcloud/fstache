"""Public API for compiling and rendering Fstache templates.

The common entry points are :func:`compile`, :func:`render`, and the
filesystem-backed renderer factories such as :func:`create_renderer`.
`CompiledTemplate` values are intentionally treated as opaque by the public API:
loaders, resolvers, and renderers pass them around, but callers should not rely
on the private node dataclasses unless a future release explicitly promotes
compiled-template introspection.
"""

from ._compiler import (
    DEFAULT_DELIMITERS as DEFAULT_DELIMITERS,
    EMPTY_TEMPLATE as EMPTY_TEMPLATE,
    CompiledTemplate as CompiledTemplate,
    Delimiters as Delimiters,
    InvalidDelimiterError as InvalidDelimiterError,
    InvalidNameError as InvalidNameError,
    SectionSyntaxError as SectionSyntaxError,
    TemplateSyntaxError as TemplateSyntaxError,
    UnclosedTagError as UnclosedTagError,
    UnsupportedTagError as UnsupportedTagError,
    compile as compile,
)
from ._factories import (
    TemplateRenderer as TemplateRenderer,
    create_dev_renderer as create_dev_renderer,
    create_prod_renderer as create_prod_renderer,
    create_renderer as create_renderer,
    create_test_renderer as create_test_renderer,
)
from ._inliner import inline_partials as inline_partials
from ._missing import (
    MissingTemplateError as MissingTemplateError,
    MissingTemplateResolver as MissingTemplateResolver,
    MissingVariableError as MissingVariableError,
    MissingVariableResolver as MissingVariableResolver,
    resolve_missing_template_as_empty as resolve_missing_template_as_empty,
    resolve_missing_template_as_error as resolve_missing_template_as_error,
    resolve_missing_variable_as_error as resolve_missing_variable_as_error,
    resolve_missing_variable_as_none as resolve_missing_variable_as_none,
)
from ._renderer import (
    EscapeFunction as EscapeFunction,
    TemplateLoader as TemplateLoader,
    RenderChunk as RenderChunk,
    RenderedTemplate as RenderedTemplate,
    TemplateCompiler as TemplateCompiler,
    html_escape as html_escape,
    render as render,
)


__all__ = (
    "CompiledTemplate",
    "DEFAULT_DELIMITERS",
    "EMPTY_TEMPLATE",
    "Delimiters",
    "EscapeFunction",
    "InvalidDelimiterError",
    "InvalidNameError",
    "MissingTemplateError",
    "MissingTemplateResolver",
    "MissingVariableError",
    "MissingVariableResolver",
    "RenderChunk",
    "RenderedTemplate",
    "SectionSyntaxError",
    "TemplateCompiler",
    "TemplateLoader",
    "TemplateRenderer",
    "TemplateSyntaxError",
    "UnclosedTagError",
    "UnsupportedTagError",
    "compile",
    "create_dev_renderer",
    "create_prod_renderer",
    "create_renderer",
    "create_test_renderer",
    "html_escape",
    "inline_partials",
    "render",
    "resolve_missing_template_as_empty",
    "resolve_missing_template_as_error",
    "resolve_missing_variable_as_error",
    "resolve_missing_variable_as_none",
)
