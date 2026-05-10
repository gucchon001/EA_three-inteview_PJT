from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment

from eb_app.fixtures.dashboard import admin_dashboard_context
from eb_app.fixtures.mock_screens import MOCK_INDEX
from eb_app.fixtures.stub_contexts import (
    assignment_detail_context,
    import_errors_context,
    meeting_new_context,
    me_todos_context,
    monthly_reports_list_context,
    settings_context,
    student_detail_context,
    students_list_context,
    teacher_detail_context,
    teachers_list_context,
    teacher_dashboard_context,
)

router = APIRouter()


def _templates(request: Request) -> Environment:
    return request.app.state.jinja_env


def _render(
    templates: Environment,
    request: Request,
    template_name: str,
    context: dict[str, Any],
) -> HTMLResponse:
    page = templates.get_template(template_name).render(
        request=request,
        **context,
    )
    return HTMLResponse(page)


@router.get("/", response_class=HTMLResponse)
def mock_index(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    routes = [
        {"screen_id": m.screen_id, "path": m.path, "label": m.label, "note": m.note}
        for m in MOCK_INDEX
    ]
    page = templates.get_template("mock/index.html").render(
        request=request,
        title="モック UI",
        routes=routes,
    )
    return HTMLResponse(page)


@router.get("/dashboard/admin", response_class=HTMLResponse)
def mock_dashboard_admin(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    ctx: dict[str, Any] = admin_dashboard_context()
    return _render(templates, request, "mock/dashboard_admin.html", ctx)


@router.get("/dashboard/teacher", response_class=HTMLResponse)
def mock_dashboard_teacher(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(templates, request, "mock/dashboard_teacher.html", teacher_dashboard_context())


@router.get("/teachers", response_class=HTMLResponse)
def mock_teachers_list(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(templates, request, "mock/list_page.html", teachers_list_context())


@router.get("/teachers/demo", response_class=HTMLResponse)
def mock_teacher_detail(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(templates, request, "mock/teacher_detail.html", teacher_detail_context())


@router.get("/students", response_class=HTMLResponse)
def mock_students_list(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(templates, request, "mock/list_page.html", students_list_context())


@router.get("/students/demo", response_class=HTMLResponse)
def mock_student_detail(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(templates, request, "mock/student_detail.html", student_detail_context())


@router.get("/assignments/demo", response_class=HTMLResponse)
def mock_assignment_detail(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(templates, request, "mock/assignment_detail.html", assignment_detail_context())


@router.get("/reports/monthly", response_class=HTMLResponse)
def mock_reports_monthly(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(templates, request, "mock/reports_monthly.html", monthly_reports_list_context())


@router.get("/meetings/new", response_class=HTMLResponse)
def mock_meeting_new(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(templates, request, "mock/meeting_new.html", meeting_new_context())


@router.get("/me/todos", response_class=HTMLResponse)
def mock_me_todos(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(templates, request, "mock/me_todos.html", me_todos_context())


@router.get("/settings", response_class=HTMLResponse)
def mock_settings(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(templates, request, "mock/settings.html", settings_context())


@router.get("/import-errors", response_class=HTMLResponse)
def mock_import_errors(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(templates, request, "mock/import_errors.html", import_errors_context())


@router.get("/fragments/admin-alerts", response_class=HTMLResponse)
def mock_fragment_admin_alerts(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    ctx = admin_dashboard_context()
    page = templates.get_template("mock/fragments/admin_alerts.html").render(
        request=request,
        **{"alerts": ctx["alerts"]},
    )
    return HTMLResponse(page)
