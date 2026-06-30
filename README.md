# Fstache

## Overview

- Dependency-free [Mustache](https://mustache.github.io/) renderer for
  [Python 3.12+](https://docs.python.org/3.12/).
- Supports [upstream Mustache spec fixtures](https://github.com/mustache/spec),
  including lambdas and dynamic partial names; **inheritance is unsupported**.
- Built for speed; [benchmarked](#benchmarks) at 3.3x
  [Chevron](https://github.com/noahmorrison/chevron), 3.1x
  [mstache](https://pypi.org/project/mstache/), and 3.5x
  [Pystache](https://github.com/defunkt/pystache).
- [PEP 561](https://peps.python.org/pep-0561/) typed package.
- Supports Python mappings, objects, sequences, and callables as render data.


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
| Compared versions | Fstache 0.1.0, Chevron 0.14.0, mstache 0.3.0, Pystache 0.6.8 |
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

---

## Utility Commands

### Generate Reference HTML
Builds and renders the templates from `./demo` into `./demo/dist/index.html` (performing file I/O):
```bash
make build-html
```

### Format and Lint
Runs ruff checks and auto-formats the project:
```bash
make post-ai-change
```
