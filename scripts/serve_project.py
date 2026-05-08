#!/usr/bin/env python3
"""
プロジェクトルートを静的配信する。Python 標準の http.server は .txt に charset を付けず、
Windows + Chrome で日本語が文字化けするため、text/plain / html / md に UTF-8 を明示する。

使い方（プロジェクトルートで）:
  python scripts/serve_project.py
  python scripts/serve_project.py 8765

ブラウザ例:
  http://127.0.0.1:8765/docs/samples/monthly-reports/tools/monthly_report_full_editor.html
    （月次レポート全文エディタ。file:// 直開きではサンプル fetch が不可）
  http://127.0.0.1:8765/samples/reports/demo_household_takafuji/sources/01_教師MTG_20260217.md

送付エクスポート（暗号化 HTML）の自動 URL 発行（開発用・エディタと同一パス as 本番）:
  POST /api/monthly-protected-upload  （互換: /__ea/monthly-protected-upload）
  Body: 暗号化 HTML（UTF-8）全文
  Response: {"ok": true, "url": "http://127.0.0.1:8765/docs/.../tools/_published/protected_xxx.html"}
  保存先は docs/samples/monthly-reports/tools/_published/ （.gitignore 対象）。
  ※127.0.0.1 のみ待受。Vercel 本番では同パスの Serverless + Blob（BLOB_READ_WRITE_TOKEN 要）。
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

ALLOWED_PROTECTED_UPLOAD_PATHS = frozenset(
    {"/api/monthly-protected-upload", "/__ea/monthly-protected-upload"}
)
MAX_PROTECTED_UPLOAD = 12 * 1024 * 1024
REL_PUBLISHED = Path("docs/samples/monthly-reports/tools/_published")


class UTF8StaticHandler(SimpleHTTPRequestHandler):
    extensions_map = SimpleHTTPRequestHandler.extensions_map.copy()
    extensions_map.update(
        {
            ".txt": "text/plain; charset=utf-8",
            ".md": "text/markdown; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".htm": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
        }
    )

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path not in ALLOWED_PROTECTED_UPLOAD_PATHS:
            self.send_error(404, "Not Found")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return
        if length <= 0 or length > MAX_PROTECTED_UPLOAD:
            self.send_error(400, "Invalid body size")
            return
        body = self.rfile.read(length)
        try:
            body.decode("utf-8")
        except UnicodeDecodeError:
            self.send_error(400, "Body must be UTF-8")
            return
        token = secrets.token_urlsafe(14).replace(".", "_")
        name = f"protected_{token}.html"
        out_dir = ROOT / REL_PUBLISHED
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / name
        out_path.write_bytes(body)
        host = self.headers.get("Host", f"127.0.0.1:{self.server.server_address[1]}")
        public_url = f"http://{host}/docs/samples/monthly-reports/tools/_published/{name}"
        payload = json.dumps({"ok": True, "url": public_url}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = HTTPServer(("127.0.0.1", port), UTF8StaticHandler)
    print(f"Serving {ROOT} at http://127.0.0.1:{port}/  (UTF-8 for .txt/.html/.md)")
    print(
        "  Protected HTML upload (dev): POST http://127.0.0.1:"
        f"{port}/api/monthly-protected-upload"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
