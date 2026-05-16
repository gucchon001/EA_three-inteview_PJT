"""モック用ポータル枠（screen-design §2）。本番ではロールに応じて同構造を組み立てる。"""
from __future__ import annotations

from typing import Any, Literal

PortalRole = Literal["admin", "teacher", "accounting"]

ROLE_LABEL_JA: dict[PortalRole, str] = {
    "admin": "管理者",
    "teacher": "教師",
    "accounting": "経理",
}


def _nav_groups(role: PortalRole) -> list[dict[str, Any]]:
    """本番 URL ではなくモックプレフィクス付き（画面設計書のグループに準拠）。"""
    p = "/mock"

    home = [
        {
            "id": "dashboard",
            "label": "ダッシュボード",
            "href": f"{p}/dashboard/admin"
            if role == "admin"
            else f"{p}/dashboard/teacher",
        },
    ]
    master: list[dict[str, Any]] = []
    if role in ("admin", "accounting"):
        master.append({"id": "teachers", "label": "教師一覧", "href": f"{p}/teachers"})
    master.append({"id": "students", "label": "生徒一覧", "href": f"{p}/students"})

    ops = [
        {"id": "reports", "label": "月次レポート一覧", "href": f"{p}/reports/monthly"},
        {"id": "report_workshop", "label": "レポート工房", "href": f"{p}/monthly-report-workshop/jobs"},
        {"id": "meetings", "label": "面談・記録（新規）", "href": f"{p}/meetings/new"},
        {"id": "todos", "label": "自分宛 ToDo", "href": f"{p}/me/todos"},
    ]
    if role == "teacher":
        ops = [o for o in ops if o["id"] != "reports"]

    groups: list[dict[str, Any]] = [
        {"label": "ホーム", "items": home},
        {"label": "マスタ", "items": master},
        {"label": "運用", "items": ops},
    ]

    if role == "admin":
        groups.append(
            {
                "label": "システム",
                "items": [
                    {"id": "settings", "label": "設定", "href": f"{p}/settings"},
                    {"id": "import_errors", "label": "取込エラー", "href": f"{p}/import-errors"},
                ],
            }
        )

    return groups


def augment_context(
    ctx: dict[str, Any],
    *,
    portal_role: PortalRole = "admin",
    active_nav: str,
    breadcrumbs: list[tuple[str, str | None]] | None = None,
    show_chrome: bool = True,
    show_parallel_sheet: bool = False,
    parallel_sheet_url: str = "https://docs.google.com/spreadsheets/d/example",
) -> dict[str, Any]:
    """
    :param active_nav: nav item id（dashboard, teachers, students, reports, meetings, todos, settings, import_errors, index）
    :param breadcrumbs: (表示名, href or None が現在地)
    """
    crumbs: list[dict[str, Any]] = []
    if breadcrumbs:
        for label, href in breadcrumbs:
            crumbs.append({"label": label, "href": href})

    merged = dict(ctx)
    merged["portal"] = {
        "show_chrome": show_chrome,
        "role": portal_role,
        "role_label_ja": ROLE_LABEL_JA[portal_role],
        "active_nav": active_nav,
        "nav_groups": _nav_groups(portal_role),
        "home_href": "/mock/dashboard/admin"
        if portal_role == "admin"
        else "/mock/dashboard/teacher",
        "mock_index_href": "/mock/",
        "breadcrumbs": crumbs,
        "show_parallel_sheet": show_parallel_sheet,
        "parallel_sheet_url": parallel_sheet_url,
        "todo_badge": None,
    }
    return merged
