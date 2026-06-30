"""Missing-value policies for Fstache rendering.

`MissingVariableResolver` callbacks receive a dotted variable path as a tuple of
strings and return the fallback value to render. `MissingTemplateResolver`
callbacks receive a template name and return a `CompiledTemplate` fallback.
Resolver exceptions propagate unchanged, which lets callers install strict
application-specific error policies.
"""

from collections.abc import Callable

from ._compiler import EMPTY_TEMPLATE, CompiledTemplate


type MissingVariableResolver = Callable[[tuple[str, ...]], object]
type MissingTemplateResolver = Callable[[str], CompiledTemplate]


class MissingVariableError(LookupError):
    """Raised when a missing variable should fail rendering.

    Attributes:
        path: Dotted-name parts for the missing variable.
        name: Dot-joined variable name for messages and logs.
    """

    def __init__(self, path: tuple[str, ...]) -> None:
        self.path = path
        self.name = ".".join(path)
        super().__init__(f"missing template variable: {self.name}")


class MissingTemplateError(Exception):
    """Raised when a missing template should fail rendering.

    Attributes:
        name: Template name passed to the loader or resolver.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"missing template: {name}")


def resolve_missing_variable_as_none(path: tuple[str, ...]) -> object:
    """Resolve a missing variable as `None`, rendering it as empty output."""

    return None


def resolve_missing_variable_as_error(path: tuple[str, ...]) -> object:
    """Raise `MissingVariableError` for a missing variable path."""

    raise MissingVariableError(path)


def resolve_missing_template_as_error(name: str) -> CompiledTemplate:
    """Raise `MissingTemplateError` for a missing root template or partial."""

    raise MissingTemplateError(name)


def resolve_missing_template_as_empty(name: str) -> CompiledTemplate:
    """Resolve a missing root template or partial as `EMPTY_TEMPLATE`."""

    return EMPTY_TEMPLATE
