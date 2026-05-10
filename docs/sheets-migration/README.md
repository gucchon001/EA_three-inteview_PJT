# Sheets Migration（Phase -1 成果物）

EB塾のオンライン塾運営で使われている Google Sheets「★新【EB塾】【2026年度】指導モニタリング管理表」を Web アプリへ移行するための、**パターン抽出フェーズ（Phase -1）の成果物一式**。

実装は Phase 3（並行運用フェーズ）で着手する。

---

## ファイル一覧

| ファイル | 役割 | 入力 / 出力 |
|---|---|---|
| [parser-spec.md](parser-spec.md) | **パーサー仕様書 v0.1**。本フェーズの中核。Phase 3 実装の入力 | — |
| [anchors.md](anchors.md) | 7ブロックのアンカー文字列・期待行レンジ | — |
| [normalization-rules.md](normalization-rules.md) | 教師名・科目名・学年・真偽値・月の正規化ルール | — |
| [tab-inventory.csv](tab-inventory.csv) | 35タブ × 検出結果マトリクス | inventory.py の出力 |
| [variants.json](variants.json) | 表記ゆれの全数（teacher 36 / subject 17 / grade 8） | inventory.py の出力 |
| [sample-extracts/](sample-extracts/) | 全 38 タブの生 JSON（fixture として再利用可） | fetch_all.py の出力 |

---

## 関連スクリプト（[../../scripts/sheets-survey/](../../scripts/sheets-survey/)）

| スクリプト | 役割 |
|---|---|
| `probe_access.py` | SA でスプレッドシートにアクセス可能か確認 |
| `fetch_all.py` | 全タブのフルスナップショットを sample-extracts/ に保存 |
| `inspect_anchors.py` | 高頻度ラベル抽出でアンカー候補を提示 |
| `inventory.py` | tab-inventory.csv と variants.json を生成 |

---

## 再実行手順

```powershell
# 1. SA アクセス確認
python scripts/sheets-survey/probe_access.py

# 2. 全タブ取得（sample-extracts/ を更新）
python scripts/sheets-survey/fetch_all.py

# 3. インベントリ再生成
python scripts/sheets-survey/inventory.py
```

前提: 対象スプレッドシートを SA `699555092496-compute@developer.gserviceaccount.com` に「閲覧者」共有しておく。

---

## 主要な発見

1. **38 タブ確定**: 生徒個別 35 + マスター 2 + 原本テンプレ 1
2. **3 つの形式クラスタ**:
   - A型（旧/簡素）: 49〜54行・merges 53〜86 — 8 タブ
   - B型（中庸）: 49〜52行・merges 84〜97 — 8 タブ
   - C型（拡張）: 63〜67行・merges 60〜90 — 17 タブ
   - 三者面談ブロック非搭載: 2 タブ（近添・伴場）
3. **教師名表記ゆれ 36 種**：苗字のみ・全角半角空白混在・大文字小文字
4. **科目名表記ゆれ 17 種**：括弧前空白の有無・全角空白
5. **学年表記ゆれ 8 種**：半角／全角／DP 併記
6. **既知の制約**: 指導報告書チェックボックスのデフォルト `FALSE` と明示 `FALSE` は区別不可

---

## Phase 0 へ持ち越す PO 確認事項

[parser-spec.md §10](parser-spec.md) を参照。
- 教師の苗字単独表記の手動マッピング UI 要否
- `Math(HL)` のレベル＆種別不明な科目表記の扱い
- 独自列で取り込むべき情報があるか
- 退職教師が canonical にない場合の運用
- 並行運用期間中のインポート頻度
- dryrun の差分閾値
