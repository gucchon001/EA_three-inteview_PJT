from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from jinja2 import Environment, FileSystemLoader, select_autoescape

from base_app.config import get_settings
from base_app.routers import health, pages

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
    )
    app.state.jinja_env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    app.include_router(health.router)
    app.include_router(pages.router)
    return app


app = create_app()

