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
    MockScreen("MR-S00", "レポート工房: 単体MVPトップ", "/mock/monthly-report-workshop"),
    MockScreen("MR-S01", "レポート工房: ジョブ一覧", "/mock/monthly-report-workshop/jobs"),
    MockScreen("MR-S02", "レポート工房: 新規ジョブ", "/mock/monthly-report-workshop/jobs/new"),
    MockScreen("MR-S04", "レポート工房: ジョブ詳細", "/mock/monthly-report-workshop/jobs/mrj_demo_001"),
    MockScreen("MR-S05", "レポート工房: プレビュー・推敲", "/mock/monthly-report-workshop/jobs/mrj_demo_001/edit"),
    MockScreen("MR-F01", "断片: レポート工房ジョブ状態", "/mock/monthly-report-workshop/jobs/mrj_demo_001/fragments/status"),
    MockScreen("SCR-M01", "面談記録（新規）", "/mock/meetings/new"),
    MockScreen("SCR-U01", "自分宛 ToDo", "/mock/me/todos"),
    MockScreen("SCR-C01", "システム設定", "/mock/settings"),
    MockScreen("SCR-I01", "取込エラー一覧", "/mock/import-errors"),
    MockScreen("FMT-A01", "断片: 管理者アラート", "/mock/fragments/admin-alerts"),
]
