from pathlib import Path
from typing import Final

import fstache
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

_TEMPLATES_DIR: Final = Path(__file__).parent / "templates"

render = fstache.create_dev_renderer(_TEMPLATES_DIR, remove_extension=True)

app = FastAPI()


def _home_data() -> dict[str, object]:
    return {
        "title": "Fstache + FastAPI",
        "heading": "Server-rendered Mustache",
        "lead": "A small FastAPI app using one filesystem Fstache renderer.",
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


@app.get("/")
async def homepage() -> HTMLResponse:
    page = render("pages/home", _home_data())

    return HTMLResponse(page.to_bytes())


@app.get("/stream")
async def stream_homepage() -> StreamingResponse:
    page = render("pages/home", _home_data())

    return StreamingResponse(
        page.iter_chunks(),
        media_type="text/html; charset=utf-8",
    )
