from pathlib import Path
from typing import Final

import fstache
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, StreamingResponse
from starlette.routing import Route

_TEMPLATES_DIR: Final = Path(__file__).parent / "templates"

render = fstache.create_dev_renderer(_TEMPLATES_DIR, remove_extension=True)


def _home_data() -> dict[str, object]:
    return {
        "title": "Fstache + Starlette",
        "heading": "Server-rendered Mustache",
        "lead": "A small Starlette app using one filesystem Fstache renderer.",
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
                "body": "Return rendered bytes directly from HTMLResponse.",
            },
            {
                "title": "Streaming",
                "body": "Pass render chunks to StreamingResponse.",
            },
        ],
        "features": [
            "Escaped variables",
            "Unescaped trusted HTML",
            "Sections and partial templates",
        ],
    }


async def homepage(_request: Request) -> HTMLResponse:
    page = render("pages/home", _home_data())

    return HTMLResponse(page.to_bytes())


async def stream_homepage(_request: Request) -> StreamingResponse:
    page = render("pages/home", _home_data())

    return StreamingResponse(
        page.iter_chunks(),
        media_type="text/html; charset=utf-8",
    )


app = Starlette(
    debug=True,
    routes=[
        Route("/", homepage),
        Route("/stream", stream_homepage),
    ],
)
