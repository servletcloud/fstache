# Fstache

Author: [vkorobkov](https://www.linkedin.com/in/vkorobkov/)

## Overview

- Dependency-free [Mustache](https://mustache.github.io/) renderer for
  [Python 3.12+](https://docs.python.org/3.12/).
- Supports [upstream Mustache spec fixtures](https://github.com/mustache/spec),
  including lambdas and dynamic partial names; **inheritance is unsupported**.
- Built for speed; with standard partial indentation respected,
  [benchmarked](#benchmarks) at 3.3x
  [Chevron](https://github.com/noahmorrison/chevron), 3.1x
  [mstache](https://pypi.org/project/mstache/), and 3.5x
  [Pystache](https://github.com/defunkt/pystache).
- [PEP 561](https://peps.python.org/pep-0561/) typed package.
- Supports Python mappings, objects, sequences, and callables as render data.
- Static partials are preloaded and inlined, eliminating render-time boundary overhead.


## Installation

```bash
pip install fstache
```

Package page: [fstache on PyPI](https://pypi.org/project/fstache/)


## Quick Start

Create `templates/hello.mustache`:

```mustache
Hello, {{name}}!
```

Render it:

```python
import fstache

render = fstache.create_renderer("./templates")
result = render("hello.mustache", {"name": "Ada"})
print(result.to_string())
```

Template names match file paths under the template root, including the file
extension by default.

Output:

```text
Hello, Ada!
```


## Recommended Setup

Keep templates under one root:

```text
templates/
├── pages/
│   └── home.mustache
└── partials/
    └── header.mustache
```

Create the renderer once at application startup, then reuse it:

```python
import fstache

render = fstache.create_prod_renderer("./templates")

def render_home(data: object) -> bytes:
    return render("pages/home.mustache", data).to_bytes()
```

For streaming web responses, pass the rendered chunks to your framework:

```python
from starlette.responses import StreamingResponse

async def homepage(request):
    result = render("pages/home.mustache", {"name": "Ada"})

    return StreamingResponse(
        result.iter_chunks(),
        media_type="text/html; charset=utf-8",
    )
```

For local development, use `create_dev_renderer("./templates")` so template
edits are picked up without restarting and missing data fails fast. For tests,
use `create_test_renderer("./templates")` to keep missing templates and
variables strict while still preloading templates once.


## API At A Glance

Choose one filesystem factory, keep the returned renderer around, and call it
with a template name plus render data:

```python
render = fstache.create_prod_renderer("./templates")
page = render("pages/home.mustache", data)
```

| Need | Use |
| --- | --- |
| Edit templates locally and catch missing data early. | `create_dev_renderer("./templates")` |
| Run tests that fail on missing templates or variables. | `create_test_renderer("./templates")` |
| Render in production with preloading, compact output, and empty missing values. | `create_prod_renderer("./templates")` |
| Mix defaults yourself. | `create_renderer("./templates", ...)` |

`create_renderer` is the full factory:

```python
render = fstache.create_renderer(
    "./templates",
    extension=".mustache",
    remove_extension=False,
    delimiters=fstache.DEFAULT_DELIMITERS,
    ignore_indents=False,
    left_trim_source=False,
    preload_templates=True,
    resolve_missing_template=fstache.resolve_missing_template_as_error,
    resolve_missing_variable=fstache.resolve_missing_variable_as_none,
    escape=fstache.html_escape,
)
```

Renderer calls return a `RenderedTemplate`. Use `.iter_chunks()` for streaming
bytes, `.to_bytes()` when you need one `bytes` value, and `.to_string()` for
CLI output, tests, and debugging.

Supported Mustache tags include escaped and unescaped variables, dotted names,
sections, inverted sections, variable and section lambdas, partials, dynamic
partial names such as `{{> * partial_name}}`, comments, and delimiter changes.
Inheritance is intentionally unsupported.


## Usage

### Template Preloading

`create_renderer` preloads templates by default. It reads and compiles matching
template files when the renderer is created, so later file edits are not visible
until you create a new renderer:

```python
render = fstache.create_renderer("./templates")
```

For local development, `create_dev_renderer` disables preloading by default so
template edits, partial edits, and new template files are picked up without
restarting the process. If you use `create_renderer` directly, set
`preload_templates=False`:

```python
render = fstache.create_renderer("./templates", preload_templates=False)
```

Avoid `preload_templates=False` in production. It reads and compiles templates
during rendering, repeats filesystem work on each request, and delays syntax
errors until the template is rendered.


### Partials

Partial tags load other templates from the same template root:

```text
templates/
├── pages/
│   └── home.mustache
└── partials/
    ├── footer.mustache
    └── header.mustache
```

Below is the content of the `templates/pages/home.mustache`:
```mustache
{{> partials/header.mustache}}
<main>
  <h1>{{title}}</h1>
</main>
{{> partials/footer.mustache}}
```

```python
render("pages/home.mustache", {"title": "Dashboard"})
```


### Compact Output

By default, standalone partials inherit the indentation before the partial tag.
For example, this template:

```mustache
Begin.
  {{> name.mustache}}
End.
```

with `name.mustache`:

```mustache
one
{{name}}
```

renders as:

```text
Begin.
  one
  Ada
End.
```

Set `ignore_indents=True` to skip that standalone partial indentation:

```python
render = fstache.create_renderer("./templates", ignore_indents=True)
```

```text
Begin.
one
Ada
End.
```

Set `left_trim_source=True` to remove leading spaces and tabs from every
template source line before parsing. It applies to root templates, partials,
and lambda templates:

```python
render = fstache.create_renderer(
    "./templates",
    ignore_indents=True,
    left_trim_source=True,
)
```

So this source indentation:

```mustache
  Begin.
    {{> name.mustache}}
  End.
```

renders to:

```text
Begin.
one
Ada
End.
```

Inline whitespace is preserved. For example, `{{first}}  {{second}}` still
renders with the two spaces between values.

Use compact output for whitespace-insensitive output such as HTML where source
indentation is mostly for template readability. In the current benchmark,
`ignore_indents=True` rendered `4066.5` pages/sec versus `3102.2` pages/sec
with standard standalone partial indentation.


### Template Extensions

`create_renderer` discovers `.mustache` files by default. Set `extension` when
your templates use another file extension:

```text
templates/
└── pages/
    └── home.html
```

```python
render = fstache.create_renderer("./templates", extension=".html")
render("pages/home.html", data)
```

The leading dot is optional, so `extension="html"` behaves the same way.


### Extensionless Names

With `remove_extension=True`, renderer calls and partial tags omit the file
extension. For example, `pages/home` renders `templates/pages/home.mustache`:

```python
render = fstache.create_renderer("./templates", remove_extension=True)
render("pages/home", data)
```


### Missing Variables

`create_renderer` renders missing variables as empty by default. To fail fast:

```python
render = fstache.create_renderer(
    "./templates",
    resolve_missing_variable=fstache.resolve_missing_variable_as_error,
)
```


### Missing Templates

`create_renderer` raises `MissingTemplateError` when a root template or partial
is missing. To render missing templates as empty:

```python
render = fstache.create_renderer(
    "./templates",
    resolve_missing_template=fstache.resolve_missing_template_as_empty,
)
```


### Custom Escaping and Delimiters

Pass a custom `escape` function when escaped variables need output-specific
escaping. The function receives raw `bytes` and must return escaped `bytes`:

```python
import fstache

def escape_brackets(value: bytes) -> bytes:
    return (
        fstache.html_escape(value)
        .replace(b"[", b"&#91;")
        .replace(b"]", b"&#93;")
    )

render = fstache.create_renderer("./templates", escape=escape_brackets)
```

The escape hook applies to escaped variable tags such as `{{name}}`. Unescaped
tags such as `{{{name}}}` and `{{& name}}` bypass it.

Use `Delimiters` when templates start with a non-default tag pair:

```mustache
Hello, [[name]]!
```

```python
render = fstache.create_renderer(
    "./templates",
    delimiters=fstache.Delimiters(start=b"[[", end=b"]]"),
)
```

Custom delimiters are the initial parser delimiters. Delimiter-change tags in
template source can still update the active pair while parsing.


### Low-Level Compile and Render

Use `compile` and `render` directly when your application owns template loading,
caching, or precompiled templates:

```python
import fstache

templates: dict[str, fstache.CompiledTemplate] = {
    "greeting": fstache.compile(b"Hello, {{name}}!\n", name="greeting"),
}

def load_template(name: str) -> fstache.CompiledTemplate:
    return templates[name]

result = fstache.render("greeting", {"name": "Ada"}, load_template)
print(result.to_string())
```

`compile(...)` accepts template `bytes` and returns an opaque
`CompiledTemplate`. Treat it as a value passed to loaders, renderers, missing
template resolvers, and `inline_partials`, not as a public node tree.

`render(...)` receives a root template name, render data, and a `TemplateLoader`
callback. It returns `RenderedTemplate`, so consume the result with
`.iter_chunks()`, `.to_bytes()`, or `.to_string()`.


### Render Data

Pass any Python object as render data. The most common choices are dictionaries
and application objects:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    name: str

data = {
    "site_name": "Docs",
    "user": User(name="Ada"),
}

render("profile.mustache", data)
```

Variable lookup starts in the current section scope and falls back to parent
scopes. Mapping values use key lookup, while other objects use attributes and
properties. Dotted names follow each part, so `{{user.name}}` works for both
`{"user": {"name": "Ada"}}` and `{"user": User(name="Ada")}`.

Sections use normal Python truthiness. Missing and falsey values skip
`{{#section}}` bodies and render `{{^section}}` bodies. Lists and tuples repeat
the section once per item, using each item as the current scope. Truthy mappings
and objects enter the section as a child scope; `True` renders the body without
changing scope.

Variable values are rendered as bytes:

- `str` values are UTF-8 encoded.
- `None` and missing variables render as empty by default.
- Other scalar values render with `str(value)`.
- `bytes` and `memoryview` values are rendered as byte chunks, avoiding string
  conversion and letting unescaped streaming output reuse the original bytes.
- A Fstache render result can be passed as a value to embed one rendered
  fragment in another without joining it first.

Escaped tags such as `{{value}}` apply the configured escape function, which may
copy the bytes. Unescaped tags such as `{{{value}}}` and `{{& value}}` write
`bytes`, `memoryview`, and embedded render-result chunks unchanged.


### Output

Renderer calls return a `RenderedTemplate`:

- `.to_bytes()` joins the rendered chunks into one `bytes` value.
- `.iter_chunks()` returns `bytes | memoryview` chunks for streaming. Prefer
  this for best performance when possible: it avoids buffering the whole
  response into one value, and static template fragments can be yielded from the
  compiled template without copying them into a joined response first.
- `.to_string(encoding="utf-8", errors="strict")` joins and decodes the chunks
  as text. Use it for CLI output, tests, and debugging; web responses usually
  need bytes instead.


## Benchmarks

### Renderer Throughput

| Library | Renders per second | Indentation details |
| --- | ---: | --- |
| Fstache | 4066.5 | **Deviates**: `ignore_indents=True` skips standard standalone partial reindentation. |
| Fstache | 3102.2 | Follows standard standalone partial indentation. |
| mstache | 1339.0 | **Deviates**: `keep_lines=True` keeps tag-only lines instead of collapsing them, so partial indentation is not reapplied to every partial line. |
| mstache | 985.3 | Follows standard standalone partial indentation. |
| Chevron | 951.1 | Follows standard standalone partial indentation. |
| Pystache | 898.8 | Follows standard standalone partial indentation. |


### Benchmark environment

| Field | Value |
| --- | --- |
| Python | CPython 3.14.6 |
| OS | Fedora Linux 44 (Workstation Edition), Linux 7.0.12-201.fc44.x86_64 |
| CPU | AMD Ryzen 7 8845HS w/ Radeon 780M Graphics, 8 cores / 16 threads |
| Compared versions | Fstache 0.1.1, Chevron 0.14.0, mstache 0.3.0, Pystache 0.6.8 |
| Command | `RENDERER=<renderer> uv run --python 3.14 --extra dev python tests/perf_test.py`<br>`<renderer>` values: `fstache.no_indentation`, `fstache`, `mstache.no_indentation`, `mstache`, `chevron`, `pystache` |


### Methodology

- The benchmark renders a realistic, heavy marketing/docs HTML page from the
  [source Mustache templates](demo/templates), [JSON data](demo/data.json), and
  [perf script](tests/perf_test.py):
  - About 100 KiB of [rendered HTML](https://servletcloud.github.io/fstache/)
    ([source](demo/dist/index.html)) from 15 Mustache templates, including 14
    partial files.
  - Tailwind CSS v4 utility-heavy markup with Alpine.js attributes, inline SVG
    icons, responsive navigation, cards, tables, accordions, and form controls.
  - About 15 KiB of JSON context data with nested arrays for navigation,
    feature cards, testimonials, a recursive docs tree, comparison rows, blog
    posts, changelog entries, FAQs, and pricing plans.
  - 42 section, inverted-section, and partial references, including 24 section
    tags for loops and conditionals plus recursive `node` partial rendering.
- The benchmark isolates render throughput from setup work:
  - Each engine preloads the template files and partials during setup.
  - Each engine uses the closest available precompiled, preparsed, or
    pretokenized representation for the layout and partials.
  - The timed render loop excludes disk I/O and one-time template preparation.
