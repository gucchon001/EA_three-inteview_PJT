from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from eb_app.config import get_settings

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="EB Instruction Monitoring",
        version="0.1.0",
        description="EB塾 指導モニタリング管理（移行中）",
    )

    if settings.enable_mock_ui:
        from eb_app.routers import mock as mock_router

        app.include_router(mock_router.router, prefix="/mock", tags=["mock"])

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        if settings.enable_mock_ui:
            return RedirectResponse(url="/mock/", status_code=307)
        return RedirectResponse(url="/docs", status_code=307)

    app.state.jinja_env = Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )

    return app


app = create_app()
