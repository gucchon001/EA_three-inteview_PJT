from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from base_app.auth import CurrentUser, get_current_user

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> HTMLResponse:
    template = request.app.state.jinja_env.get_template("home.html")
    return HTMLResponse(
        template.render(
            request=request,
            current_user=current_user,
        )
    )


@router.get("/fragments/summary", response_class=HTMLResponse)
def summary_fragment(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> HTMLResponse:
    template = request.app.state.jinja_env.get_template("fragments/summary.html")
    return HTMLResponse(template.render(current_user=current_user))

