import json
import os
import chevron

# Resolve paths relative to this script's directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    # Ensure dist directory exists
    dist_dir = os.path.join(BASE_DIR, "dist")
    os.makedirs(dist_dir, exist_ok=True)

    # Load context data
    with open(os.path.join(BASE_DIR, "data.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    # Read layout.mustache
    layout_path = os.path.join(BASE_DIR, "templates/layout.mustache")
    with open(layout_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Render using chevron python API
    partials_dir = os.path.join(BASE_DIR, "templates")
    html = chevron.render(
        template, data, partials_path=partials_dir, partials_ext="mustache"
    )

    # Write to dist/index.html
    output_path = os.path.join(dist_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Build successful! Generated HTML output: {output_path}")


if __name__ == "__main__":
    main()
