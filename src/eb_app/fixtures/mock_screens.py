"""画面 ID・モック索引（docs/web-app/screen-design.md と同期）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MockScreen:
    screen_id: str
    label: str
    path: str
    note: str = ""


# モック索引に載せるエントリ（本番実装時は同 SCR_ID で差し替え）
MOCK_INDEX: list[MockScreen] = [
    MockScreen("SCR-D01", "ダッシュボード（管理者）", "/mock/dashboard/admin"),
    MockScreen("SCR-D02", "ダッシュボード（教師）", "/mock/dashboard/teacher"),
    MockScreen("SCR-T01", "教師一覧", "/mock/teachers"),
    MockScreen("SCR-T02", "教師詳細（デモ）", "/mock/teachers/demo"),
    MockScreen("SCR-S01", "生徒一覧", "/mock/students"),
    MockScreen("SCR-S02", "生徒詳細（デモ）", "/mock/students/demo"),
    MockScreen("SCR-A01", "指導枠・月次（デモ）", "/mock/assignments/demo"),
    MockScreen("SCR-R01", "月次レポート一覧（管理者）", "/mock/reports/monthly"),
    MockScreen("SCR-M01", "面談記録（新規）", "/mock/meetings/new"),
    MockScreen("SCR-U01", "自分宛 ToDo", "/mock/me/todos"),
    MockScreen("SCR-C01", "システム設定", "/mock/settings"),
    MockScreen("SCR-I01", "取込エラー一覧", "/mock/import-errors"),
    MockScreen("FMT-A01", "断片: 管理者アラート", "/mock/fragments/admin-alerts"),
]
