from pathlib import Path
from typing import Final

import fstache
from flask import Flask, Response

_TEMPLATES_DIR: Final = Path(__file__).parent / "templates"

render = fstache.create_dev_renderer(_TEMPLATES_DIR, remove_extension=True)

app = Flask(__name__)


def _home_data() -> dict[str, object]:
    return {
        "title": "Fstache + Flask",
        "heading": "Server-rendered Mustache",
        "lead": "A small Flask app using one filesystem Fstache renderer.",
        "notice": "<strong>This variable is escaped.</strong>",
        "safe_badge_html": '<span class="badge">trusted HTML</span>',
        "nav_items": [
            {"href": "/", "label": "Home"},
            {"href": "/stream", "label": "Stream"},
        ],
        "cards": [
            {
                "title": "One renderer",
                "body": "Create the renderer once at module load and reuse it.",
            },
            {
                "title": "HTML bytes",
                "body": "Return rendered bytes directly from Response.",
            },
            {
                "title": "Streaming",
                "body": "Pass render chunks to a streamed Response.",
            },
        ],
        "features": [
            "Escaped variables",
            "Unescaped trusted HTML",
            "Sections and partial templates",
        ],
    }


def homepage() -> Response:
    page = render("pages/home", _home_data())

    return Response(page.to_bytes(), mimetype="text/html")


def stream_homepage() -> Response:
    page = render("pages/home", _home_data())

    return Response(page.iter_chunks(), mimetype="text/html")


app.add_url_rule("/", view_func=homepage)
app.add_url_rule("/stream", view_func=stream_homepage)
