"""レポート工房モック用フィクスチャ。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_SAMPLE_DIR = Path(__file__).resolve().parents[3] / "docs" / "samples" / "monthly-reports"
_BODY_RE = re.compile(r"<body[^>]*>(?P<body>.*)</body>", re.IGNORECASE | re.DOTALL)


def _sample_report_body(filename: str, fallback: str) -> str:
    path = _SAMPLE_DIR / filename
    try:
        html = path.read_text(encoding="utf-8")
    except OSError:
        return fallback

    match = _BODY_RE.search(html)
    return match.group("body").strip() if match else html.strip()


def _base_stages(current_stage: str, status: str) -> list[dict[str, str]]:
    stage_states = {
        "fetch_sources": "done",
        "bundle": "done",
        "build_messages": "done",
        "call_llm": "done" if status == "succeeded" else "running",
        "validate": "done" if status == "succeeded" else "pending",
        "persist": "done" if status == "succeeded" else "pending",
    }
    if status == "needs_review":
        stage_states["call_llm"] = "done"
        stage_states["validate"] = "running"
        stage_states["persist"] = "pending"

    durations = {
        "fetch_sources": "12s",
        "bundle": "2s",
        "build_messages": "1s",
        "call_llm": "1m 18s" if status == "succeeded" else "48s",
        "validate": "9s" if status == "succeeded" else "-",
        "persist": "4s" if status == "succeeded" else "-",
    }
    return [
        {"id": "fetch_sources", "label": "ソース取得", "state": stage_states["fetch_sources"], "duration": durations["fetch_sources"]},
        {"id": "bundle", "label": "バンドル", "state": stage_states["bundle"], "duration": durations["bundle"]},
        {"id": "build_messages", "label": "プロンプト構築", "state": stage_states["build_messages"], "duration": durations["build_messages"]},
        {"id": "call_llm", "label": "LLM本文生成", "state": stage_states["call_llm"], "duration": durations["call_llm"]},
        {"id": "validate", "label": "規約検証", "state": stage_states["validate"], "duration": durations["validate"]},
        {"id": "persist", "label": "成果物保存", "state": stage_states["persist"], "duration": durations["persist"]},
    ]


_DEMO_JOB_DATA: dict[str, dict[str, Any]] = {
    "mrj_demo_takafuji": {
        "public_id": "mrj_demo_001",
        "target_month": "2026-04",
        "household": "高藤 泰次郎さま（匿名デモ）",
        "status": "running",
        "current_stage": "call_llm",
        "created_by": "mock-admin@tomonokai-corp.com",
        "prompt_version": "monthly-report-v20260513.1",
        "template_hash": "sha256:pattern-b-v3.5.7",
        "requested_model": "anthropic/claude-sonnet-4.6",
        "resolved_model": "anthropic/claude-sonnet-4.6",
        "app_version": "mock-build-20260514",
        "source_bundle_hash": "sha256:takafuji-source-bundle",
        "validation_summary": {"errors": 1, "warnings": 2},
        "stages": _base_stages("call_llm", "running"),
        "sources": [
            {
                "name": "monthly_2026-04_takafuji_report.html",
                "kind": "sample report asset",
                "status": "取得済み",
                "size": "HTML",
                "hash": "sha256:takafuji-report-demo",
                "truncated": "なし",
            },
            {
                "name": "高藤 学習計画表",
                "kind": "Google Sheets",
                "status": "取得済み",
                "size": "184 KB",
                "hash": "sha256:takafuji-sheet-demo",
                "truncated": "なし",
            },
            {
                "name": "高藤 教師MTG議事録",
                "kind": "Google Docs",
                "status": "取得済み",
                "size": "42 KB",
                "hash": "sha256:takafuji-doc-demo",
                "truncated": "なし",
            },
        ],
        "validations": [
            {"severity": "error", "rule": "star_lines_exact", "message": "05 学習の進捗の星5行が原文と一致していません。"},
            {"severity": "warning", "rule": "tone", "message": "保護者向け表現として少し硬い可能性があります。"},
            {"severity": "warning", "rule": "required_headings", "message": "補足説明の見出し位置を確認してください。"},
        ],
        "artifacts": [
            {"type": "draft_markdown", "label": "生成Markdown", "hash": "sha256:takafuji-draft-md", "status": "保存済み"},
            {"type": "draft_html", "label": "プレビューHTML", "hash": "sha256:takafuji-draft-html", "status": "保存済み"},
        ],
        "editor_html": _sample_report_body(
            "monthly_2026-04_takafuji_report.html",
            "<article><h1>高藤 泰次郎さま 月次学習レポート</h1><p>サンプルレポートを読み込めませんでした。</p></article>",
        ),
    },
    "mrj_demo_001": {},
    "mrj_demo_suzuki": {
        "public_id": "mrj_demo_suzuki",
        "target_month": "2026-04",
        "household": "鈴木 謙吾さま（匿名デモ）",
        "status": "succeeded",
        "current_stage": "persist",
        "created_by": "mock-admin@tomonokai-corp.com",
        "prompt_version": "monthly-report-v20260513.1",
        "template_hash": "sha256:pattern-b-v3.6.1",
        "requested_model": "openrouter/auto",
        "resolved_model": "anthropic/claude-sonnet-4.6",
        "app_version": "mock-build-20260514",
        "source_bundle_hash": "sha256:suzuki-source-bundle",
        "validation_summary": {"errors": 0, "warnings": 0},
        "stages": _base_stages("persist", "succeeded"),
        "sources": [
            {"name": "monthly_2026-04_suzuki_report.html", "kind": "sample report asset", "status": "取得済み", "size": "HTML", "hash": "sha256:suzuki-report-demo", "truncated": "なし"},
            {"name": "鈴木 学習計画表", "kind": "Google Sheets", "status": "取得済み", "size": "201 KB", "hash": "sha256:suzuki-sheet-demo", "truncated": "なし"},
            {"name": "鈴木 ソース運用メモ", "kind": "Markdown", "status": "取得済み", "size": "18 KB", "hash": "sha256:suzuki-source-notes", "truncated": "なし"},
        ],
        "validations": [
            {"severity": "info", "rule": "required_headings", "message": "Pattern B の必須見出しを確認済みです。"},
            {"severity": "info", "rule": "forbidden_terms", "message": "家庭向け本文に内部用語は検出されていません。"},
        ],
        "artifacts": [
            {"type": "draft_markdown", "label": "生成Markdown", "hash": "sha256:suzuki-draft-md", "status": "保存済み"},
            {"type": "final_html", "label": "最終HTML", "hash": "sha256:suzuki-final-html", "status": "保存済み"},
        ],
        "editor_html": _sample_report_body(
            "monthly_2026-04_suzuki_report.html",
            "<article><h1>鈴木 謙吾さま 月次学習レポート</h1><p>サンプルレポートを読み込めませんでした。</p></article>",
        ),
    },
    "mrj_demo_tokura": {
        "public_id": "mrj_demo_tokura",
        "target_month": "2026-04",
        "household": "十倉 未希さま（匿名デモ）",
        "status": "needs_review",
        "current_stage": "validate",
        "created_by": "mock-admin@tomonokai-corp.com",
        "prompt_version": "monthly-report-v20260513.2",
        "template_hash": "sha256:pattern-b-tokura-v3",
        "requested_model": "anthropic/claude-sonnet-4.6",
        "resolved_model": "anthropic/claude-sonnet-4.6",
        "app_version": "mock-build-20260514",
        "source_bundle_hash": "sha256:tokura-source-bundle",
        "validation_summary": {"errors": 0, "warnings": 2},
        "stages": _base_stages("validate", "needs_review"),
        "sources": [
            {"name": "monthly_2026-04_tokura_v3_report.html", "kind": "sample report asset", "status": "取得済み", "size": "HTML", "hash": "sha256:tokura-v3-report-demo", "truncated": "なし"},
            {"name": "十倉 学習計画表", "kind": "Google Sheets", "status": "取得済み", "size": "236 KB", "hash": "sha256:tokura-sheet-demo", "truncated": "なし"},
            {"name": "十倉 MTGメモ", "kind": "Google Docs", "status": "取得済み", "size": "57 KB", "hash": "sha256:tokura-doc-demo", "truncated": "なし"},
        ],
        "validations": [
            {"severity": "warning", "rule": "source_readability", "message": "MTGメモ由来の表記ゆれは配布前に確認してください。"},
            {"severity": "warning", "rule": "teacher_name", "message": "教師名の漢字表記は原記録照合が必要です。"},
        ],
        "artifacts": [
            {"type": "draft_markdown", "label": "生成Markdown", "hash": "sha256:tokura-draft-md", "status": "保存済み"},
            {"type": "draft_html", "label": "プレビューHTML", "hash": "sha256:tokura-draft-html", "status": "保存済み"},
        ],
        "editor_html": _sample_report_body(
            "monthly_2026-04_tokura_v3_report.html",
            "<article><h1>十倉 未希さま 月次学習レポート</h1><p>サンプルレポートを読み込めませんでした。</p></article>",
        ),
    },
}

_DEMO_JOB_DATA["mrj_demo_001"] = _DEMO_JOB_DATA["mrj_demo_takafuji"]


class DemoJob(dict[str, Any]):
    def __setitem__(self, key: str, value: Any) -> None:
        if key == "public_id":
            data = _DEMO_JOB_DATA.get(value, _DEMO_JOB_DATA["mrj_demo_001"]).copy()
            if value not in _DEMO_JOB_DATA:
                data["public_id"] = value
            dict.clear(self)
            dict.update(self, data)
            return
        super().__setitem__(key, value)


def workshop_job(public_id: str = "mrj_demo_001") -> dict[str, Any]:
    data = _DEMO_JOB_DATA.get(public_id, _DEMO_JOB_DATA["mrj_demo_001"])
    return DemoJob(data.copy())


def workshop_jobs_context() -> dict[str, Any]:
    jobs = [
        workshop_job("mrj_demo_001"),
        workshop_job("mrj_demo_suzuki"),
        workshop_job("mrj_demo_tokura"),
    ]
    return {
        "page_title": "レポート工房",
        "role_label": "管理者",
        "jobs": [
            {
                "public_id": job["public_id"],
                "target_month": job["target_month"],
                "household": job["household"],
                "status": job["status"],
                "prompt_version": job["prompt_version"],
                "model": job["resolved_model"],
                "validation": f"errors {job['validation_summary']['errors']} / warnings {job['validation_summary']['warnings']}",
                "href": f"/mock/monthly-report-workshop/jobs/{job['public_id']}",
            }
            for job in jobs
        ],
        "metrics": [
            {"label": "実行中", "value": "1", "tone": "warning"},
            {"label": "デモジョブ", "value": "3", "tone": "normal"},
            {"label": "検証エラー", "value": "1", "tone": "error"},
            {"label": "平均生成", "value": "2.4分", "tone": "normal"},
        ],
    }


def workshop_home_context() -> dict[str, Any]:
    jobs_context = workshop_jobs_context()
    return {
        "page_title": "月次レポート生成ツール",
        "subtitle": "単体MVP",
        "primary_actions": [
            {
                "label": "新規生成を始める",
                "href": "/mock/monthly-report-workshop/jobs/new",
                "kind": "primary",
            },
            {
                "label": "ジョブ一覧を見る",
                "href": "/mock/monthly-report-workshop/jobs",
                "kind": "secondary",
            },
        ],
        "metrics": jobs_context["metrics"],
        "recent_jobs": jobs_context["jobs"],
        "flow_steps": [
            {"label": "ソース指定", "note": "対象月・世帯・Sheets / Docs URL"},
            {"label": "取得確認", "note": "hash・サイズ・取得失敗を確認"},
            {"label": "生成", "note": "OpenRouterで草稿作成"},
            {"label": "検証・推敲", "note": "規約エラーを見ながら編集"},
        ],
    }


def workshop_new_context() -> dict[str, Any]:
    return {
        "page_title": "新規ジョブ作成",
        "role_label": "管理者",
        "target_month": "2026-04",
        "household": "高藤さま（匿名デモ）",
        "spreadsheet_url": "https://docs.google.com/spreadsheets/d/demo-spreadsheet",
        "doc_url": "https://docs.google.com/document/d/demo-doc",
        "templates": ["pattern_b"],
    }


def workshop_detail_context() -> dict[str, Any]:
    return {
        "page_title": "ジョブ詳細",
        "role_label": "管理者",
        "job": workshop_job(),
    }


def workshop_editor_context() -> dict[str, Any]:
    job = workshop_job()
    return {
        "page_title": "プレビュー・推敲",
        "role_label": "管理者",
        "job": job,
    }
