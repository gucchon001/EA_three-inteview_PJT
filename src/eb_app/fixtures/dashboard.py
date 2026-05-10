from __future__ import annotations

from typing import Any


def admin_dashboard_context() -> dict[str, Any]:
    """管理者ダッシュ用の固定フィクスチャ（要件 FR-6.1 の骨格イメージ）。"""
    return {
        "page_title": "ダッシュボード",
        "role_label": "管理者",
        "metrics": [
            {"label": "今月 未提出レポート", "value": "12", "tone": "warning"},
            {"label": "充足率 要確認", "value": "3", "tone": "warning"},
            {"label": "直近の面談 ToDo 超過", "value": "2", "tone": "error"},
        ],
        "alerts": [
            {
                "title": "月次レポート締切",
                "body": "3 日以内に締切の担当があります。",
                "badge": "3日以内",
            },
            {
                "title": "充足率しきい値外れ",
                "body": "選考番号 A-1024（仮）が下限を下回っています。",
                "badge": "要確認",
            },
        ],
    }
