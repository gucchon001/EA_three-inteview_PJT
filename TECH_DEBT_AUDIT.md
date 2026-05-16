# TECH_DEBT_AUDIT.md

初回試行監査（`tech-debt-audit` スキル準拠）。リポジトリ: `EA_three-inteview_PJT`（`ea-report-prototypes`）。日付: 2026-05-10。

---

## Executive summary

- **Critical 1**: ローカル `config/` に GCP サービスアカウント鍵ファイルが置かれ、`private_key` を含む（`.gitignore` で除外されているがワークスペース・バックアップ・転送経路での漏えいリスクは残る）。
- **High 1**: 自動テスト・CI がなく、公開 API と大量ドキュメント改訂のみが品質ゲートになっている。
- **High 2**: `monthly-protected-upload` が `Access-Control-Allow-Origin: *` で POST を受けつけ、認証なく Blob への書き込み経路になりうる（DoS／クォータ枯渇の観点）。
- **Medium 複数**: ルート `README.md` がなくオンボーディングが `docs/` 分散、`vercel.json` の静的ルートが個別ファイル名でハードコード、Python が鍵ファイルパス固定。
- **Low**: `package.json` にスクリプト・開発用ツール未定義、`npm audit` は依存が極少で問題検出なし。
- Git ヒストリーは浅く、直近変更は Sheets 移行ドキュメントとサンプル JSON の膨張が中心（`HANDOFF.md` と整合）。

---

## Architectural mental model

本リポジトリは **（1）Vercel 上のごく少数の Node サーバ関数**（Blob への暗号化 HTML アップロードとインライン配信）、**（2）静的テンプレート**（`src/reports/templates/**`）、**（3）Sheets→Web 移行のためのドキュメント＋調査スクリプト（Python）**、**（4）開発用フィクスチャ JSON (`data/` など)** で構成されている。HANDOFF が示す将来的な **FastAPI + Supabase アプリ本体は別フェーズ**であり、この倉庫はプロトタイプ・調査・アーティファクト保存の側面が強い。

---

## Findings table

| ID | Category | File:Line | Severity | Effort | Description | Recommendation |
|----|----------|-----------|----------|--------|--------------|----------------|
| F001 | Security hygiene | `config/gen-lang-client-0360012476-457924b0f2ae.json:5` | Critical | M | SA JSON に `private_key` が含まれる。.gitignore にパターンはあるがファイルはリポジトリ作業ツリーに存在する。 | 鍵を **ロール／無効化**し、ワークスペースから削除。以降は GCP 推奨の ADC / Secret Manager / 環境変数のみ。コミット履歴を一度だけ確認し、過去に追跡されていた場合は追加対応。 |
| F002 | Security hygiene | `.gitignore:6-7` | Low | S | SA ファイルを明示的に ignore しておりポリシーは明文化されている。 | 維持。新規環境セットアップ手順で「ファイルを置くな」を README で再掲するとよい。 |
| F003 | Test debt | （該当なし） | High | M | `*test*` ファイルやテストディレクトリが見つからない。API とスクリプトの回帰に頼れない。 | アップロード API の単体テスト（境界バイト、`id` 形式、環境変数未設定時）。Python は `inventory` の小さな検出関数からスナップショットテスト。 |
| F004 | Security hygiene | `api/monthly-protected-upload.js:51-54` | High | M | OPTIONS/POST で `Access-Control-Allow-Origin: *`。ブラウザ外からでも POST できる構成になりやすく、トークン付き環境での悪用で Blob が消費されうる。 | 許可オリジンをホワイトリスト化するか、**共有秘密ヘッダ**／レートリミット／Vercel 側の保護と組み合わせて設計書に根拠を残す。 |
| F005 | Documentation drift | `docs/README.md:6-11` | Medium | S | `project/`・`meetings/` 等の構成を説明するが、この README の「サブフォルダ一覧」と実ツリーが一致しているかだけはメンテ依存。ルート README がない。 | ルートに 10 行前後のリンク付き概要（HANDOFF と `docs/README` への誘導）を追加。 |
| F006 | Consistency rot | （ルート README 欠如） | Medium | S | 新規参加者がエントリポイントを迷う。 | ルート `README.md` で目的・実行方法（どの Phase）・機密ファイル禁止を 1 画面にまとめる。 |
| F007 | Config / coupling | `scripts/sheets-survey/fetch_all.py:26-27` | Medium | S | SA ファイルパスとスプレッドシート ID がコードにハードコード。 | `GOOGLE_APPLICATION_CREDENTIALS` または環境変数でパス参照。Spreadsheet ID も環境変数に。 |
| F008 | Dep & config debt | `package.json:1-7` | Low | S | 依存は `@vercel/blob` のみ。`scripts` や `engines` がない。 | `engines` と最低限の `lint`/`test` を追加するか、`docs` に「Node 検証コマンド」節を置く。 |
| F009 | Architectural decay | `vercel.json:29-39` | Medium | M | `/monthly_2026-04_*` など個別 HTML への `routes` がベタ書き。テンプレ追加のたびに設定変更が必要。 | パターンマッチや命名規約に統一してルート増殖を抑制。 |
| F010 | Performance & hygiene | `data/*.json`、`docs/sheets-migration/sample-extracts/`（多数ファイル） | Low | L | 大きな JSON がリポ内にあり clone/IDE が重くなりやすい。 | Git LFS 検討、またはサンプル削減と「ダウンロード手順」への切り出し。 |
| F011 | Error handling | `api/monthly-protected-upload.js:93-96` | Low | S | 失敗時は `console.error` と汎用 500 のみ（構造化ログなし）。 | 相関 ID・最小限の構造化ログ（鍵値はマスク）。 |
| F012 | Type & contract debt | （該当薄） | Low | S | Plain JS で型契約なし。現規模では許容だが公開 API が増えると負債になる。 | 公開エンドポイントが増えたら入力スキーマ（zod 等）を検討。 |

---

## Top 5（優先順）

1. **F001** — サービスアカウント鍵をローテーションし、(a) 作業ツリーから除去 (b) 取得経路を ADC/Secret に一本化。(c) 履歴・fork・バックアップに残っていないか確認。
2. **F004** — アップロード API の公開面を再設計（オリジン制限または追加認証）。
3. **F003** — アップロードと id 検証の最小自動テストを追加し regressions を防ぐ。
4. **F007** — Python 調査ツールからハードコードパス・ID を切り離し、環境変数へ。
5. **F009** — `vercel.json` の静的ルートの一般化またはドキュメント化（なぜベタ書きかの理由と移行計画）。

---

## Quick wins（チェックリスト）

- [ ] F002: HANDOFF の近くまたはルート README で「SA JSON をコミットしない」を再記載。
- [ ] F006: ルート `README.md` 追加（3 リンク + 機密ポリシー 1 行）。
- [ ] F008: `package.json` に `engines` を記載。
- [ ] F011: アップロード失敗ログにリクエスト id（ヘッダで受け付け）を含める検討。

---

## Things that look bad but are actually fine（必須セクション）

- **`vercel.json` の `"builds"` 配列**はモダンな単一構成ではなく読みにくいが、**少数ファイルの明示ビルド**としてプロトタイプでは合理的で、問題の証拠にはならない。
- **`inline` GET で `Blob` に `token` でアクセス`**しているように見えるが、**パスが推測困難なランダム id に限定され** `ID_RE` で検証されている（推測 brute force は別途評価）。
- **`readBody` がメモリに全文収集**：`MAX_BYTES` でキャップされているため、このエンドポイントの要件内では許容だが、サイズ増ならストリーム化を検討。

---

## Open questions for the maintainer

- `config/gen-lang-client-*.json` は **過去どのブランチでも一度も追跡されていない**か（`git rev-list --all -- config/...` で確認済みであると安心）。
- `monthly-protected-*` は **社内のみ**の利用か、それとも広いオリジンからのブラウザ利用を想定しているか（それで F004 の受容可否が変わる）。
- `HANDOFF.md` で言及の **本番 FastAPI アプリ**：この repo に統合するかモノレポ化するか、境界を明示したい。

---

## メタ（試行運用）

- スタック検出: Node（`package.json` + `api/*.js`）、Python（`scripts/sheets-survey`）、Vercel（`vercel.json`）。
- 実行ツール: `npm audit`（0 vulnerabilities）、`git log`／ディレクトリマップ、`rg` による秘密っぽいパターン走査。
- 本ドキュメントは **パイロット**であり、再利用時は FINDING を `NEW`/`RESOLVED` で管理するとよい。
