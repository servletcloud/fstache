"""Static partial inlining for precompiled Fstache templates."""

from typing import Final

from ._compiler import (
    CompiledTemplate,
    DynamicPartialNode,
    InvertedSectionNode,
    Node,
    PartialNode,
    SectionNode,
    TextNode,
)


def inline_partials(
    templates: dict[str, CompiledTemplate],
) -> dict[str, CompiledTemplate]:
    """Inline static partials in a compiled-template mapping.

    The input mapping is not mutated. Missing partials, directly recursive
    partials, indirectly recursive partials, and dynamic partials are left as
    render-time partial nodes. This helper is mainly useful for preloaded
    templates compiled with indentation handling disabled.
    """

    inlined = {}
    for name, template in templates.items():
        inlined[name] = _inline_template(template, templates, (name,))

    return inlined


def _inline_template(
    template: CompiledTemplate,
    templates: dict[str, CompiledTemplate],
    stack: tuple[str, ...],
) -> CompiledTemplate:
    nodes: list[Node] = []
    for node in template:
        _append_inlined_node(nodes, node, templates, stack)

    return tuple(nodes)


def _append_inlined_node(
    nodes: list[Node],
    node: Node,
    templates: dict[str, CompiledTemplate],
    stack: tuple[str, ...],
) -> None:
    clazz: Final = type(node)

    if clazz is PartialNode:
        name = node.name  # ty: ignore[unresolved-attribute]
        if name not in templates or name in stack:
            _append_node(nodes, node)
            return

        _append_nodes(
            nodes,
            _inline_template(templates[name], templates, stack + (name,)),
        )
        return

    if clazz is SectionNode:
        _append_node(
            nodes,
            SectionNode(
                path=node.path,  # ty: ignore[unresolved-attribute]
                children=_inline_template(
                    node.children,  # ty: ignore[unresolved-attribute]
                    templates,
                    stack,
                ),
                raw_body=node.raw_body,  # ty: ignore[unresolved-attribute]
                delimiters=node.delimiters,  # ty: ignore[unresolved-attribute]
                indentation=node.indentation,  # ty: ignore[unresolved-attribute]
            ),
        )
        return

    if clazz is InvertedSectionNode:
        _append_node(
            nodes,
            InvertedSectionNode(
                path=node.path,  # ty: ignore[unresolved-attribute]
                children=_inline_template(
                    node.children,  # ty: ignore[unresolved-attribute]
                    templates,
                    stack,
                ),
            ),
        )
        return

    if clazz is DynamicPartialNode:
        _append_node(nodes, node)
        return

    _append_node(nodes, node)


def _append_nodes(nodes: list[Node], additional_nodes: CompiledTemplate) -> None:
    for node in additional_nodes:
        _append_node(nodes, node)


def _append_node(nodes: list[Node], node: Node) -> None:
    if type(node) is TextNode and nodes and type(nodes[-1]) is TextNode:
        previous = nodes[-1]
        value = previous.value + node.value
        nodes[-1] = TextNode(chunks=(value,), value=value)
        return

    nodes.append(node)
