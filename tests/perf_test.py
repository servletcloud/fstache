import gc
import json
import os
import resource
import statistics
import sys
import time
import tracemalloc
from typing import Final, Protocol
import chevron
import chevron.tokenizer

import mstache
import pystache
from pystache.renderengine import RenderEngine
import fstache

# Resolve paths relative to this script's directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_DIR = os.path.join(BASE_DIR, "demo")
TEMPLATES_DIR = os.path.join(DEMO_DIR, "templates")
DATA_PATH = os.path.join(DEMO_DIR, "data.json")
EXPECTED_HTML_PATH = os.path.join(DEMO_DIR, "dist/index.html")
LAYOUT_NAME: Final = "layout"


class Renderer(Protocol):
    def name(self) -> str:
        """Identifier name of the renderer configuration (e.g., 'chevron')."""
        ...

    def setup(self, templates_dir: str, layout_name: str, data: dict) -> None:
        """Preloads, parses, or pre-compiles templates/data and stores them on self."""
        ...

    def render(self) -> int:
        """Executes a single render and returns the size of the output in bytes.

        Must not do any disk or console I/O.
        Should store the rendered bytes on self.last_output for verification.
        """
        ...


class ChevronRenderer:
    def name(self) -> str:
        return "chevron"

    def setup(self, templates_dir: str, layout_name: str, data: dict) -> None:
        self.data = data
        self.last_output = b""

        # Load and pre-tokenize the layout template
        layout_path = os.path.join(templates_dir, f"{layout_name}.mustache")
        with open(layout_path, "r", encoding="utf-8") as f:
            layout_str = f.read()
        self.layout_template = list(chevron.tokenizer.tokenize(layout_str))

        # Load and pre-tokenize all partial templates
        self.partials = {}
        for filename in os.listdir(templates_dir):
            if filename.endswith(".mustache"):
                name = filename[:-9]
                with open(
                    os.path.join(templates_dir, filename), "r", encoding="utf-8"
                ) as f:
                    content = f.read()
                self.partials[name] = list(chevron.tokenizer.tokenize(content))

    def render(self) -> int:
        res = chevron.render(
            template=self.layout_template,
            data=self.data,
            partials_path=None,
            partials_dict=self.partials,
            warn=False,
        )
        self.last_output = res.encode("utf-8")

        return len(self.last_output)


class MstacheRenderer:
    def name(self) -> str:
        return "mstache"

    def setup(self, templates_dir: str, layout_name: str, data: dict) -> None:
        self.data = data
        self.last_output = b""
        self._compiled_cache = {}

        # Load layout template as bytes
        layout_path = os.path.join(templates_dir, f"{layout_name}.mustache")
        with open(layout_path, "rb") as f:
            self.layout_template = f.read()

        # Load all partial templates as bytes
        self.partials = {}
        for filename in os.listdir(templates_dir):
            if filename.endswith(".mustache"):
                name = filename[:-9].encode("utf-8")
                with open(os.path.join(templates_dir, filename), "rb") as f:
                    self.partials[name] = f.read()

    def render(self) -> int:
        res_bytes = mstache.render(
            self.layout_template,
            self.data,
            resolver=self.partials.get,
            cache=self._compiled_cache,
        )
        self.last_output = res_bytes

        return len(res_bytes)


class MstacheNoIndentationRenderer:
    def name(self) -> str:
        return "mstache.no_indentation"

    def setup(self, templates_dir: str, layout_name: str, data: dict) -> None:
        self.data = data
        self.last_output = b""
        self._compiled_cache = {}

        # Load layout template as bytes
        layout_path = os.path.join(templates_dir, f"{layout_name}.mustache")
        with open(layout_path, "rb") as f:
            self.layout_template = f.read()

        # Load all partial templates as bytes
        self.partials = {}
        for filename in os.listdir(templates_dir):
            if filename.endswith(".mustache"):
                name = filename[:-9].encode("utf-8")
                with open(os.path.join(templates_dir, filename), "rb") as f:
                    self.partials[name] = f.read()

    def render(self) -> int:
        # keep_lines=True is a proxy for weakened indentation behavior, not a
        # pure no-indentation mode.
        res_bytes = mstache.render(
            self.layout_template,
            self.data,
            resolver=self.partials.get,
            cache=self._compiled_cache,
            keep_lines=True,
        )
        self.last_output = res_bytes

        return len(res_bytes)


class PystacheCachedRenderEngine(RenderEngine):
    def __init__(self, *args, **kwargs):
        self.cache = kwargs.pop("cache")
        super().__init__(*args, **kwargs)

    def render(self, template, context_stack, delimiters=None):
        key = (template, delimiters)
        if key not in self.cache:
            self.cache[key] = pystache.parse(template, delimiters)
        parsed_template = self.cache[key]
        return parsed_template.render(self, context_stack)


class PystacheCachedRenderer(pystache.Renderer):
    def __init__(self, *args, **kwargs):
        self._parse_cache = {}
        super().__init__(*args, **kwargs)

    def _make_render_engine(self):
        resolve_context = self._make_resolve_context()
        resolve_partial = self._make_resolve_partial()
        engine = PystacheCachedRenderEngine(
            literal=self._to_unicode_hard,
            escape=self._escape_to_unicode,
            resolve_context=resolve_context,
            resolve_partial=resolve_partial,
            to_str=self.str_coerce,
            cache=self._parse_cache,
        )
        return engine


class PystacheRenderer:
    def name(self) -> str:
        return "pystache"

    def setup(self, templates_dir: str, layout_name: str, data: dict) -> None:
        self.data = data
        self.last_output = b""

        # Pre-load and parse layout template
        layout_path = os.path.join(templates_dir, f"{layout_name}.mustache")
        with open(layout_path, "r", encoding="utf-8") as f:
            layout_str = f.read()
        self.parsed_layout = pystache.parse(layout_str)

        # Pre-load all partial templates as strings (the cache will parse them on first render)
        self.partials = {}
        for filename in os.listdir(templates_dir):
            if filename.endswith(".mustache"):
                name = filename[:-9]
                with open(
                    os.path.join(templates_dir, filename), "r", encoding="utf-8"
                ) as f:
                    self.partials[name] = f.read()

        self.renderer = PystacheCachedRenderer(partials=self.partials)

    def render(self) -> int:
        res = self.renderer.render(self.parsed_layout, self.data)
        self.last_output = res.encode("utf-8")

        return len(self.last_output)


class FstacheRenderer:
    data: dict
    renderer: fstache.TemplateRenderer
    last_output: bytes = b""

    def name(self) -> str:
        return "fstache"

    def setup(self, templates_dir: str, layout_name: str, data: dict) -> None:
        self.data = data
        self.renderer = fstache.create_renderer(
            templates_dir,
            remove_extension=True,
        )

    def render(self) -> int:
        res_bytes = self.renderer(
            LAYOUT_NAME,
            self.data,
        ).to_bytes()
        self.last_output = res_bytes

        return len(res_bytes)


class FstacheNoIndentationRenderer:
    data: dict
    renderer: fstache.TemplateRenderer
    last_output: bytes = b""

    def name(self) -> str:
        return "fstache.no_indentation"

    def setup(self, templates_dir: str, layout_name: str, data: dict) -> None:
        self.data = data
        self.renderer = fstache.create_renderer(
            templates_dir,
            remove_extension=True,
            ignore_indents=True,
        )

    def render(self) -> int:
        res_bytes = self.renderer(
            LAYOUT_NAME,
            self.data,
        ).to_bytes()
        self.last_output = res_bytes

        return len(res_bytes)


# Registry of preloaded renderer variants.
RENDERERS = {
    "chevron": ChevronRenderer,
    "mstache": MstacheRenderer,
    "mstache.no_indentation": MstacheNoIndentationRenderer,
    "pystache": PystacheRenderer,
    "fstache": FstacheRenderer,
    "fstache.no_indentation": FstacheNoIndentationRenderer,
}


def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_html(html_str):
    # Collapse all whitespace sequences (spaces, newlines, tabs) into a single space
    return " ".join(html_str.split())


def main():
    # 1. Resolve and validate selected renderer
    renderer_name = os.environ.get("RENDERER")
    if not renderer_name:
        sys.stderr.write("Error: RENDERER environment variable is not set.\n")
        sys.stderr.write(f"Available renderers: {list(RENDERERS.keys())}\n")
        sys.exit(1)

    if renderer_name not in RENDERERS:
        sys.stderr.write(f"Error: Unknown renderer '{renderer_name}'.\n")
        sys.stderr.write(f"Available renderers: {list(RENDERERS.keys())}\n")
        sys.exit(1)

    renderer_class = RENDERERS[renderer_name]
    renderer = renderer_class()

    # 2. Pre-load data context
    print("Loading data context (I/O phase)...")
    data = load_data()

    # 3. Setup the renderer
    print(f"Setting up renderer '{renderer.name()}'...")
    renderer.setup(TEMPLATES_DIR, LAYOUT_NAME, data)

    # 4. Verify correctness against expected output if it exists
    print("Verifying correctness...")
    # Execute a single render to populate self.last_output
    renderer.render()
    rendered_bytes = renderer.last_output
    rendered_html = rendered_bytes.decode("utf-8")

    if os.path.exists(EXPECTED_HTML_PATH):
        with open(EXPECTED_HTML_PATH, "r", encoding="utf-8") as f:
            expected_html = f.read()

        norm_rendered = normalize_html(rendered_html)
        norm_expected = normalize_html(expected_html)

        if norm_rendered == norm_expected:
            print("✓ Correctness verification PASSED (whitespace-normalized match).")
        else:
            print(
                "⚠ Warning: Rendered HTML does not match the baseline in demo/dist/index.html!"
            )
            debug_path = os.path.join(DEMO_DIR, "dist/index_perf_debug.html")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(rendered_html)
            print(f"  Debug output written to {debug_path}")
    else:
        print("⚠ Expected baseline HTML not found. Skipping validation.")

    # Benchmarking parameters
    WARMUP_ITERATIONS = 1000
    NUM_TRIALS = 10
    ITERATIONS_PER_TRIAL = 5000

    # Baseline measurements before benchmark
    gc.collect()
    gc_stats_before = gc.get_stats()
    usage_before = resource.getrusage(resource.RUSAGE_SELF)
    times_before = os.times()

    print(f"\nStarting warmup ({WARMUP_ITERATIONS} iterations)...")
    warmup_bytes = 0
    for _ in range(WARMUP_ITERATIONS):
        warmup_bytes += renderer.render()

    print(
        f"Running benchmark: {NUM_TRIALS} trials x {ITERATIONS_PER_TRIAL} iterations each..."
    )

    trial_times = []
    for t in range(NUM_TRIALS):
        trial_bytes = 0
        start_time = time.perf_counter()
        for _ in range(ITERATIONS_PER_TRIAL):
            trial_bytes += renderer.render()
        elapsed = time.perf_counter() - start_time
        avg_ms_per_render = (elapsed / ITERATIONS_PER_TRIAL) * 1000.0
        trial_times.append(avg_ms_per_render)
        print(f"  Trial {t + 1:2d}: {avg_ms_per_render:.3f} ms per render")

    # Capture times and resource usage immediately after benchmark
    times_after = os.times()
    usage_after = resource.getrusage(resource.RUSAGE_SELF)
    gc_stats_after = gc.get_stats()

    # Timing Stats
    mean_time = statistics.mean(trial_times)
    median_time = statistics.median(trial_times)
    min_time = min(trial_times)
    max_time = max(trial_times)
    stddev_time = statistics.stdev(trial_times) if len(trial_times) > 1 else 0.0
    throughput = 1000.0 / mean_time

    # CPU Time Split Calculations
    user_cpu_s = times_after.user - times_before.user
    system_cpu_s = times_after.system - times_before.system
    total_cpu_s = user_cpu_s + system_cpu_s

    # Scheduler Context Switches
    voluntary_ctx = usage_after.ru_nvcsw - usage_before.ru_nvcsw
    involuntary_ctx = usage_after.ru_nivcsw - usage_before.ru_nivcsw
    soft_page_faults = usage_after.ru_minflt - usage_before.ru_minflt
    hard_page_faults = usage_after.ru_majflt - usage_before.ru_majflt

    # GC delta calculations
    gc_deltas = []
    for gen in range(3):
        col_delta = (
            gc_stats_after[gen]["collections"] - gc_stats_before[gen]["collections"]
        )
        obj_delta = gc_stats_after[gen]["collected"] - gc_stats_before[gen]["collected"]
        gc_deltas.append((col_delta, obj_delta))

    # --- Phase 2: Memory Trace Phase ---
    # We trace heap memory allocations separately to prevent instrumentation overhead
    # from skewing the wall-clock execution times of the main benchmark.
    print("\nRunning heap memory diagnostics (with tracemalloc)...")
    tracemalloc.start()
    for _ in range(1000):
        _ = renderer.render()
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print("\n" + "=" * 60)
    print("PERFORMANCE & SYSTEM DIAGNOSTICS REPORT")
    print("=" * 60)
    print("Execution Timing:")
    print(f"  Renderer               : {renderer.name()}")
    print(f"  Mean Time per Render   : {mean_time:.3f} ms")
    print(f"  Median Time per Render : {median_time:.3f} ms")
    print(f"  Min Time per Render    : {min_time:.3f} ms")
    print(f"  Max Time per Render    : {max_time:.3f} ms")
    print(f"  Standard Deviation     : {stddev_time:.3f} ms")
    print(f"  Throughput             : {throughput:.1f} renders/sec")
    print("-" * 60)
    print("CPU Utilization Split (During Warmup + Benchmark):")
    if total_cpu_s > 0:
        print(f"  Total CPU Time         : {total_cpu_s:.3f} s")
        print(
            f"    - User CPU Time      : {user_cpu_s:.3f} s ({user_cpu_s / total_cpu_s * 100.0:.1f}%)"
        )
        print(
            f"    - System CPU Time    : {system_cpu_s:.3f} s ({system_cpu_s / total_cpu_s * 100.0:.1f}%)"
        )
    else:
        print("  Total CPU Time         : < 0.001 s")
    print("-" * 60)
    print("Memory Footprint Profile:")
    print(f"  Peak Python Heap Alloc : {peak_mem / 1024:.2f} KiB (traced separately)")
    print(
        f"  Max Resident Set (RSS) : {usage_after.ru_maxrss / 1024:.2f} MiB (Peak process RSS)"
    )
    print("-" * 60)
    print("Garbage Collector Pressure:")
    for gen in range(3):
        cols, objs = gc_deltas[gen]
        print(f"    - Gen {gen}: {cols} collections, {objs} objects collected")
    print("-" * 60)
    print("OS Scheduler Interactions:")
    print(f"  Voluntary Context Switches   : {voluntary_ctx}")
    print(f"  Involuntary Context Switches : {involuntary_ctx}")
    print(f"  Soft Page Faults (Reclaims)  : {soft_page_faults}")
    print(f"  Hard Page Faults (Disk I/O)  : {hard_page_faults}")
    print("=" * 60)


if __name__ == "__main__":
    main()
