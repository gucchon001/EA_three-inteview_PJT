from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment

from eb_app.fixtures.dashboard import admin_dashboard_context
from eb_app.fixtures.mock_screens import MOCK_INDEX
from eb_app.fixtures.monthly_report_workshop import (
    workshop_home_context,
    workshop_detail_context,
    workshop_editor_context,
    workshop_jobs_context,
    workshop_new_context,
)
from eb_app.fixtures.portal_frame import PortalRole, augment_context
from eb_app.fixtures.stub_contexts import (
    assignment_detail_context,
    import_errors_context,
    meeting_new_context,
    me_todos_context,
    monthly_reports_list_context,
    settings_context,
    student_detail_context,
    students_list_context,
    teacher_dashboard_context,
    teacher_detail_context,
    teachers_list_context,
)

router = APIRouter()


def _templates(request: Request) -> Environment:
    return request.app.state.jinja_env


def _render(
    templates: Environment,
    request: Request,
    template_name: str,
    ctx: dict[str, Any],
    *,
    portal_role: PortalRole = "admin",
    active_nav: str,
    breadcrumbs: list[tuple[str, str | None]] | None = None,
    show_chrome: bool = True,
    show_parallel_sheet: bool = False,
) -> HTMLResponse:
    full_ctx = augment_context(
        ctx,
        portal_role=portal_role,
        active_nav=active_nav,
        breadcrumbs=breadcrumbs,
        show_chrome=show_chrome,
        show_parallel_sheet=show_parallel_sheet,
    )
    page = templates.get_template(template_name).render(
        request=request,
        **full_ctx,
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
    full_ctx = augment_context(
        {"title": "モック UI", "routes": routes},
        portal_role="admin",
        active_nav="index",
        show_chrome=False,
    )
    page = templates.get_template("mock/index.html").render(
        request=request,
        **full_ctx,
    )
    return HTMLResponse(page)


@router.get("/dashboard/admin", response_class=HTMLResponse)
def mock_dashboard_admin(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    ctx = admin_dashboard_context()
    return _render(
        templates,
        request,
        "mock/dashboard_admin.html",
        ctx,
        portal_role="admin",
        active_nav="dashboard",
        breadcrumbs=[("ダッシュボード", None)],
        show_parallel_sheet=True,
    )


@router.get("/dashboard/teacher", response_class=HTMLResponse)
def mock_dashboard_teacher(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/dashboard_teacher.html",
        teacher_dashboard_context(),
        portal_role="teacher",
        active_nav="dashboard",
        breadcrumbs=[("ダッシュボード", None)],
    )


@router.get("/teachers", response_class=HTMLResponse)
def mock_teachers_list(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/list_page.html",
        teachers_list_context(),
        portal_role="admin",
        active_nav="teachers",
        breadcrumbs=[("教師一覧", None)],
    )


@router.get("/teachers/demo", response_class=HTMLResponse)
def mock_teacher_detail(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/teacher_detail.html",
        teacher_detail_context(),
        portal_role="admin",
        active_nav="teachers",
        breadcrumbs=[("教師一覧", "/mock/teachers"), ("山田 太郎（デモ）", None)],
    )


@router.get("/students", response_class=HTMLResponse)
def mock_students_list(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/list_page.html",
        students_list_context(),
        portal_role="teacher",
        active_nav="students",
        breadcrumbs=[("生徒一覧", None)],
    )


@router.get("/students/demo", response_class=HTMLResponse)
def mock_student_detail(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/student_detail.html",
        student_detail_context(),
        portal_role="admin",
        active_nav="students",
        breadcrumbs=[("生徒一覧", "/mock/students"), ("山田 太郎（デモ）", None)],
    )


@router.get("/assignments/demo", response_class=HTMLResponse)
def mock_assignment_detail(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/assignment_detail.html",
        assignment_detail_context(),
        portal_role="admin",
        active_nav="students",
        breadcrumbs=[
            ("生徒一覧", "/mock/students"),
            ("山田 太郎（デモ）", "/mock/students/demo"),
            ("指導枠 SEL-DEMO", None),
        ],
    )


@router.get("/reports/monthly", response_class=HTMLResponse)
def mock_reports_monthly(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/reports_monthly.html",
        monthly_reports_list_context(),
        portal_role="admin",
        active_nav="reports",
        breadcrumbs=[("月次レポート一覧", None)],
    )


@router.get("/monthly-report-workshop", response_class=HTMLResponse)
def mock_monthly_report_workshop_home(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/monthly_report_workshop/home.html",
        workshop_home_context(),
        portal_role="admin",
        active_nav="report_workshop",
        show_chrome=False,
    )


@router.get("/monthly-report-workshop/jobs", response_class=HTMLResponse)
def mock_monthly_report_workshop_jobs(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/monthly_report_workshop/jobs.html",
        workshop_jobs_context(),
        portal_role="admin",
        active_nav="report_workshop",
        show_chrome=False,
        breadcrumbs=[("レポート工房", None)],
    )


@router.get("/monthly-report-workshop/jobs/new", response_class=HTMLResponse)
def mock_monthly_report_workshop_new(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/monthly_report_workshop/new.html",
        workshop_new_context(),
        portal_role="admin",
        active_nav="report_workshop",
        show_chrome=False,
        breadcrumbs=[("レポート工房", "/mock/monthly-report-workshop/jobs"), ("新規ジョブ", None)],
    )


@router.get("/monthly-report-workshop/jobs/{job_id}", response_class=HTMLResponse)
def mock_monthly_report_workshop_detail(
    job_id: str,
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    ctx = workshop_detail_context()
    ctx["job"]["public_id"] = job_id
    return _render(
        templates,
        request,
        "mock/monthly_report_workshop/detail.html",
        ctx,
        portal_role="admin",
        active_nav="report_workshop",
        show_chrome=False,
        breadcrumbs=[("レポート工房", "/mock/monthly-report-workshop/jobs"), (job_id, None)],
    )


@router.get("/monthly-report-workshop/jobs/{job_id}/edit", response_class=HTMLResponse)
def mock_monthly_report_workshop_edit(
    job_id: str,
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    ctx = workshop_editor_context()
    ctx["job"]["public_id"] = job_id
    return _render(
        templates,
        request,
        "mock/monthly_report_workshop/edit.html",
        ctx,
        portal_role="admin",
        active_nav="report_workshop",
        show_chrome=False,
        breadcrumbs=[
            ("レポート工房", "/mock/monthly-report-workshop/jobs"),
            (job_id, f"/mock/monthly-report-workshop/jobs/{job_id}"),
            ("推敲", None),
        ],
    )


@router.get("/monthly-report-workshop/jobs/{job_id}/fragments/status", response_class=HTMLResponse)
def mock_monthly_report_workshop_status_fragment(
    job_id: str,
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    ctx = workshop_detail_context()
    ctx["job"]["public_id"] = job_id
    page = templates.get_template("mock/monthly_report_workshop/fragments/status.html").render(
        request=request,
        job=ctx["job"],
    )
    return HTMLResponse(page)


@router.get("/meetings/new", response_class=HTMLResponse)
def mock_meeting_new(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/meeting_new.html",
        meeting_new_context(),
        portal_role="admin",
        active_nav="meetings",
        breadcrumbs=[("面談・記録（新規）", None)],
    )


@router.get("/me/todos", response_class=HTMLResponse)
def mock_me_todos(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/me_todos.html",
        me_todos_context(),
        portal_role="teacher",
        active_nav="todos",
        breadcrumbs=[("自分宛 ToDo", None)],
    )


@router.get("/settings", response_class=HTMLResponse)
def mock_settings(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/settings.html",
        settings_context(),
        portal_role="admin",
        active_nav="settings",
        breadcrumbs=[("設定", None)],
    )


@router.get("/import-errors", response_class=HTMLResponse)
def mock_import_errors(
    request: Request,
    templates: Environment = Depends(_templates),
) -> HTMLResponse:
    return _render(
        templates,
        request,
        "mock/import_errors.html",
        import_errors_context(),
        portal_role="admin",
        active_nav="import_errors",
        breadcrumbs=[("取込エラー", None)],
    )


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
