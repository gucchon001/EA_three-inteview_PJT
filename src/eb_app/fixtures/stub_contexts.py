"""モック用のミニマル文脈（本番は DB から取得）。"""
from __future__ import annotations

from typing import Any


def teacher_dashboard_context() -> dict[str, Any]:
    return {
        "page_title": "ダッシュボード",
        "role_label": "教師",
        "first_view": [
            {"title": "今月の締切", "body": "月次レポート提出 — あと 5 日", "badge": "要対応"},
            {"title": "自分宛て ToDo", "body": "面談フォロー: 山田 太郎（仮）", "badge": "2件"},
        ],
        "slots_preview": [
            {"selection_no": "SEL-1001", "student": "山田 太郎", "subject": "Math AA HL"},
            {"selection_no": "SEL-1002", "student": "佐藤 花子", "subject": "Physics HL"},
        ],
    }


def list_page(
    title: str,
    role_label: str,
    columns: list[str],
    rows: list[list[str]],
) -> dict[str, Any]:
    return {
        "page_title": title,
        "role_label": role_label,
        "columns": columns,
        "rows": rows,
    }


def teachers_list_context() -> dict[str, Any]:
    return list_page(
        "教師一覧",
        "管理者",
        ["教師番号", "氏名", "状態", "稼働"],
        [
            ["T-001", "山田 太郎", "active", "稼働中"],
            ["T-002", "鈴木 次郎", "invited", "—"],
        ],
    )


def students_list_context() -> dict[str, Any]:
    return list_page(
        "生徒一覧",
        "管理者（スタブ）",
        ["生徒番号", "氏名", "学年", "ステータス"],
        [
            ["S-2001", "山田 太郎", "DP2", "在籍"],
            ["S-2002", "佐藤 花子", "DP1", "在籍"],
        ],
    )


def teacher_detail_context() -> dict[str, Any]:
    return {
        "page_title": "教師詳細",
        "role_label": "管理者",
        "teacher": {
            "no": "T-001",
            "name": "山田 太郎（デモ）",
            "email": "yamada@example.com",
            "status": "active",
        },
    }


def student_detail_context() -> dict[str, Any]:
    return {
        "page_title": "生徒詳細",
        "role_label": "管理者（スタブ）",
        "student": {
            "no": "S-2001",
            "name": "山田 太郎（デモ）",
            "grade": "DP2",
            "status": "在籍",
        },
        "assignments_link": "/mock/assignments/demo",
    }


def assignment_detail_context() -> dict[str, Any]:
    return {
        "page_title": "指導枠・月次",
        "role_label": "管理者（スタブ）",
        "assignment": {
            "selection_no": "SEL-DEMO",
            "subject": "Math AA HL",
            "monthly_hours": 8,
        },
        "monthly_rows": [
            {"ym": "2026-04", "hours": "7.5", "rate": "94%", "submitted": "✓"},
            {"ym": "2026-05", "hours": "—", "rate": "—", "submitted": "未"},
        ],
    }


def monthly_reports_list_context() -> dict[str, Any]:
    return {
        "page_title": "月次レポート一覧",
        "role_label": "管理者",
        "ym": "2026-05",
        "rows": [
            {"selection_no": "SEL-1001", "teacher": "山田", "student": "山田 太郎", "submitted": "未"},
        ],
    }


def meeting_new_context() -> dict[str, Any]:
    return {
        "page_title": "面談記録（新規）",
        "role_label": "管理者（スタブ）",
        "student_id": "demo",
        "kinds": ["三者面談", "教師MTG", "その他"],
    }


def me_todos_context() -> dict[str, Any]:
    return {
        "page_title": "自分宛 ToDo",
        "role_label": "管理者（スタブ）",
        "todos": [
            {"title": "承諾書確認", "due": "2026-05-12", "status": "open"},
        ],
    }


def settings_context() -> dict[str, Any]:
    return {
        "page_title": "システム設定",
        "role_label": "管理者",
        "keys": [
            ("monthly_report_deadline", '{"type":"month_end"}'),
            ("fulfillment_rate_warn", '{"min":80,"max":110}'),
            ("reminder_days_before", "[3,1,0]"),
            ("parallel_operation", "true"),
        ],
    }


def import_errors_context() -> dict[str, Any]:
    return {
        "page_title": "取込エラー",
        "role_label": "管理者",
        "rows": [
            {"job": "job-001", "sheet": "生徒マスタ", "row": 14, "msg": "教師名ゆれ（要マッピング）"},
        ],
    }
