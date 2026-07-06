# Fstache

[![PyPI version](https://img.shields.io/pypi/v/fstache.svg)](https://pypi.org/project/fstache/)
[![Python versions](https://img.shields.io/pypi/pyversions/fstache.svg)](https://pypi.org/project/fstache/)
[![CI](https://github.com/servletcloud/fstache/actions/workflows/ci.yml/badge.svg)](https://github.com/servletcloud/fstache/actions/workflows/ci.yml)
[![Publish package](https://github.com/servletcloud/fstache/actions/workflows/publish.yml/badge.svg)](https://github.com/servletcloud/fstache/actions/workflows/publish.yml)
[![License](https://img.shields.io/pypi/l/fstache.svg)](https://pypi.org/project/fstache/)
[![Typed: PEP 561](https://img.shields.io/badge/typed-PEP%20561-blue.svg)](https://peps.python.org/pep-0561/)

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


## Why Fstache Exists

Fstache started from a Python web application built with server-side rendering,
[HTMX](https://htmx.org/), [Tailwind CSS](https://tailwindcss.com/), and
[Alpine.js](https://alpinejs.dev/).

That stack followed the HTML-over-the-wire style used by tools like
[HTMX](https://htmx.org/) and [Hotwire/Turbo](https://turbo.hotwired.dev/):
keep rendering on the server, send HTML pages or fragments to the browser, and
use JavaScript only for the interactions that genuinely need to happen on the
client.

For many full-stack applications, this is a lower-cost and simpler default than
building a separate client-side application. There is less state to duplicate
between backend and frontend, fewer moving parts to operate, and less
framework-specific code between the data and the HTML.

It is also friendly to backend-oriented developers. A small team can build
useful, interactive web interfaces while staying close to the backend model,
routing, validation, and deployment flow they already understand.

[Mustache](https://mustache.github.io/) fit that approach because it is
deliberately simple: templates render the data they receive. They do not become
another layer for application logic, database access, or framework-specific
behavior.

The problem showed up on a $4/month VPS. Rendering a full page with
[Chevron](https://github.com/noahmorrison/chevron) could take 5-10 ms. Smaller
fragments were faster, but full-page rendering was still common enough to
matter.

Looking for a faster drop-in renderer led to
[mstache](https://pypi.org/project/mstache/), which was much faster than Chevron
in that application. That raised the next question: how fast could a pure-Python
Mustache renderer be while staying simple, dependency-free, and compatible with
normal Mustache templates?

Fstache exists to answer that question for this style of Python web development:
simple Mustache templates, no runtime dependencies, streaming-friendly output,
and enough speed that rendering whole pages or fragments stays practical on
modest servers.


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


## CLI

Use `fstache render` when you want a small shell-friendly render step:

```bash
fstache render --data data.json < page.mustache > page.html
```

The command reads the root template from stdin, reads JSON data from `--data`,
writes rendered bytes to stdout, and writes diagnostics to stderr. If `--data`
is omitted, it renders with `{}`.

Partials resolve from the current working directory:

```mustache
{{> shared/header.mustache}}
```

Use `--remove-extension` when partial names omit the template extension:

```bash
fstache render --data data.json --remove-extension < page.mustache > page.html
```

Set `--extension` for another template file extension. The leading dot is
optional:

```bash
fstache render --data data.json --extension .html --remove-extension < page.mustache > page.html
```

If an interpolation variable or partial template is missing, `fstache render`
still writes the rendered result to stdout using an empty value for the missing
tag. It also writes a clear diagnostic to stderr and exits with status `1`.


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


## Examples

- [Flask example](examples/flask/) shows Fstache with regular and streamed
  WSGI `Response` objects in a standalone `uv` project.
- [Starlette example](examples/starlette/) shows Fstache with `HTMLResponse`
  and `StreamingResponse` in a standalone `uv` project.


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

Symlinked templates are allowed when their resolved target stays inside the
template root. If a requested root template or partial resolves outside that
root, it is treated as missing and uses `resolve_missing_template`.


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
indentation is mostly for template readability. In the workstation benchmark,
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

### Workstation throughput

| Library | Mean time | Renders per second | Indentation details |
| --- | ---: | ---: | --- |
| Fstache | 0.246 ms | 4066.5 | **Deviates**: `ignore_indents=True` skips standard standalone partial reindentation. |
| Fstache | 0.322 ms | 3102.2 | Follows standard standalone partial indentation. |
| mstache | 0.747 ms | 1339.0 | **Deviates**: `keep_lines=True` keeps tag-only lines instead of collapsing them, so partial indentation is not reapplied to every partial line. |
| mstache | 1.015 ms | 985.3 | Follows standard standalone partial indentation. |
| Chevron | 1.051 ms | 951.1 | Follows standard standalone partial indentation. |
| Pystache | 1.113 ms | 898.8 | Follows standard standalone partial indentation. |


### Workstation environment

| Field | Value |
| --- | --- |
| Python | CPython 3.14.6 |
| OS | Fedora Linux 44 (Workstation Edition), Linux 7.0.12-201.fc44.x86_64 |
| CPU | AMD Ryzen 7 8845HS w/ Radeon 780M Graphics, 8 cores / 16 threads |
| Compared versions | Fstache 0.1.1, Chevron 0.14.0, mstache 0.3.0, Pystache 0.6.8 |
| Command | `RENDERER=<renderer> uv run --python 3.14 --extra dev python tests/perf_test.py`<br>`<renderer>` values: `fstache.no_indentation`, `fstache`, `mstache.no_indentation`, `mstache`, `chevron`, `pystache` |


### $4/month VPS throughput

| Library | Mean time | Renders per second | Indentation and validation details |
| --- | ---: | ---: | --- |
| Fstache | 1.132 ms | 883.1 | **Deviates**: `ignore_indents=True` skips standard standalone partial reindentation. Baseline warning: apostrophes are escaped as `&#x27;`. |
| Fstache | 1.437 ms | 696.0 | Follows standard standalone partial indentation. Baseline warning: apostrophes are escaped as `&#x27;`. |
| mstache | 2.843 ms | 351.7 | **Deviates**: `keep_lines=True` keeps tag-only lines instead of collapsing them, so partial indentation is not reapplied to every partial line. Baseline warning: backticks are escaped as `&#x60;`. |
| mstache | 4.197 ms | 238.3 | Follows standard standalone partial indentation. Baseline warning: backticks are escaped as `&#x60;`. |
| Chevron | 4.476 ms | 223.4 | Follows standard standalone partial indentation. Baseline check passed. |
| Pystache | 5.081 ms | 196.8 | Follows standard standalone partial indentation. Baseline warning: apostrophes are escaped as `&#x27;`. |


### $4/month VPS environment

| Field | Value |
| --- | --- |
| Python | CPython 3.14.6 |
| OS | Ubuntu 24.04.4 LTS, Linux 6.8.0-71-generic |
| CPU | DO-Regular, 1 core / 1 thread |
| RAM | 458 MiB, no swap |
| Compared versions | Fstache 0.1.2 from PyPI, Chevron 0.14.0, mstache 0.3.0, Pystache 0.6.8 |
| Assets | GitHub checkout at commit `489d8d9`; only `demo/` and `tests/perf_test.py` were used from the checkout. |
| Command | `RENDERER=<renderer> uv run --no-project --python 3.14 --with fstache==0.1.2 --with chevron==0.14.0 --with mstache==0.3.0 --with pystache==0.6.8 python <checkout>/tests/perf_test.py`<br>`<renderer>` values: `fstache.no_indentation`, `fstache`, `mstache.no_indentation`, `mstache`, `chevron`, `pystache` |


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
