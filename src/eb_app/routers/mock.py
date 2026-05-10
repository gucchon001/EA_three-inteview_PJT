from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment

from eb_app.fixtures.dashboard import admin_dashboard_context

router = APIRouter()


def _templates(request: Request) -> Environment:
    return request.app.state.jinja_env


@router.get("/", response_class=HTMLResponse)
def mock_index(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    page = templates.get_template("mock/index.html").render(
        request=request,
        title="モック UI",
        routes=[
            {"path": "/mock/dashboard/admin", "label": "管理者ダッシュボード"},
            {
                "path": "/mock/fragments/admin-alerts",
                "label": "断片: 管理者アラート（HTMX 想定）",
            },
        ],
    )
    return HTMLResponse(page)


@router.get("/dashboard/admin", response_class=HTMLResponse)
def mock_dashboard_admin(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    ctx: dict[str, Any] = admin_dashboard_context()
    page = templates.get_template("mock/dashboard_admin.html").render(
        request=request,
        **ctx,
    )
    return HTMLResponse(page)


@router.get("/fragments/admin-alerts", response_class=HTMLResponse)
def mock_fragment_admin_alerts(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    ctx = admin_dashboard_context()
    page = templates.get_template("mock/fragments/admin_alerts.html").render(
        request=request,
        alerts=ctx["alerts"],
    )
    return HTMLResponse(page)
