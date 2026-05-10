# scripts/sheets-survey

Phase -1（パターン抽出）用の使い捨て調査スクリプト。本番パーサーは別途実装する。

## 前提

- Python 3.10+
- 認証: `config/gen-lang-client-0360012476-457924b0f2ae.json`（SA）
  - 対象スプレッドシートを SA に「閲覧者」で共有しておくこと
  - SA email: `699555092496-compute@developer.gserviceaccount.com`

## 依存

```powershell
pip install -r scripts/sheets-survey/requirements.txt
```

すでにグローバル Python に `googleapiclient` / `google-auth` が入っている場合は省略可。

## 使い方

```powershell
# 1. アクセス確認
python scripts/sheets-survey/probe_access.py

# 2. 全タブのフルスナップショットを保存
python scripts/sheets-survey/fetch_all.py
# → docs/sheets-migration/sample-extracts/{idx}_{title}.json

# 3. インベントリ生成（後続ステップ）
# python scripts/sheets-survey/inventory.py
```

## 対象

- spreadsheetId: `1inBUyjKQbFEH1tt-XnauWFKJqRU21F-GQGEzleLJLbA`
- タイトル: ★新【EB塾】【2026年度】指導モニタリング管理表
- 期待タブ数: 38（生徒個別35 + マスター2 + 原本テンプレ1）
