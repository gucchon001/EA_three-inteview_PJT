# テスト計画書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールのテスト計画
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `functional-spec.md`, `llm-design.md`, `api-definition.md`
- 最終更新: 2026-05-14

## 方針

- LLMプロバイダはモック可能にする。
- 規約違反はLLM評価ではなく、決定的バリデーションで検出する。
- MVPではゴールデンフィクスチャを少数でも作り、回帰検証の足場を作る。
- Phase 1では `pytest` + provider mockを必須とする。
- Phase 3ではPlaywrightを必ず導入し、現行HTML全文エディタ由来の推敲・保存・送付エクスポート体験の品質ゲートにする。
- CIはGitHub Actionsを想定する。Phase 1ではpytestを実行し、Phase 3でPlaywrightを追加する。

## テスト階層

| 種別 | 対象 |
|---|---|
| 単体 | bundle, prompt build, validation, hash, masking |
| 結合 | provider mockを使ったジョブ生成 |
| API | ジョブ作成、状態取得、feedback、429 |
| 画面 | HTMX fragmentの差し替え、エラー表示 |
| E2E | Playwrightによるエディタ、保存、差分、送付エクスポート確認 |
| 手動 | 実案件での生成品質、推敲、フィードバック入力 |

## 最低限の自動テスト

| ID | テスト | 目的 |
|---|---|---|
| T-01 | ソースバンドル切り詰め | サイズ上限とtruncated flag |
| T-02 | 必須見出し検証 | テンプレ順守。第一弾としてテンプレートから抽出した `## 01...` 形式の必須見出し欠落を `required_headings` で検出済み |
| T-03 | 禁止語検出 | 品質規約。第一弾として配布面禁止語 `担当CA`, `教師 MTG`, `NotebookLM` を `forbidden_terms` で検出済み |
| T-04 | 星5行原文一致 | 重要箇所の改変防止 |
| T-05 | provider mockでジョブ成功 | LLMなしでCI可能 |
| T-06 | provider mockでLLM失敗 | 失敗stage保存 |
| T-07 | 1ユーザー3件制限 | 429 |
| T-08 | OAuth認可失敗 | 401/403 |
| T-09 | PIIログ抑止 | OpenRouter、Google Workspace、Google OAuth token refresh、validation失敗時に本文・生ソース・token・secret・外部APIレスポンス本文を外向きエラーへ出さない。Cloud Logging向け実ログ出力もallowlistで検査する |
| T-10 | feedback保存 | チューニング材料保存 |
| T-11 | ローカルモック認証 | `EB_AUTH_MODE=mock` で開発ユーザーとして動く |
| T-12 | 本番mock禁止 | 本番設定でmock認証が有効なら起動失敗 |
| T-13 | Auto Routerメタ保存 | `requested_model=openrouter/auto` と `resolved_model` の両方を保存する。`llm_call_logs` と `/llm-calls` で確認済み |
| T-14 | ジョブキャンセル | `running` ジョブを `cancel_requested` にし、次stageへ進ませない |
| T-15 | 簡易差分 | 生成物と最終編集後HTML/Markdownの差分を表示できる |
| T-16 | build_messages塊順 | 静的POCの `build_prompts` と同じ順で、契約、scope、根拠、構造、語感、artifact指示を組み立てる |
| T-17 | 複数生徒MTG混入防止 | Economics等の複数生徒MTGで対象外の別姓＋様の評価文が家庭向け本文に混入しない。第一弾として `prompt_scope_notes` に明記された `対象外...様` のdraft混入を `multistudent_scope_exclusion` で検出済み |
| T-18 | prompt_scope_notes保存 | `prompts.scope_reminder` 相当がジョブメタとして保存され、再生成時にも引き継がれる |
| T-19 | Google Workspace取得 | `gws` CLIに依存せず、Docs / Sheets REST APIから取得した本文・valuesをソーススナップショットへ保存する |
| T-20 | Google Workspace token秘匿 | Google API失敗時にaccess tokenやGoogle APIレスポンス本文をエラー本文へ含めない |
| T-21 | Google OAuth refresh token暗号化保存 | provider refresh tokenはFernet暗号文として保存し、DBに平文を残さない |
| T-22 | Google OAuth token refresh秘匿 | token endpoint失敗時にclient secret、refresh token、Googleレスポンス本文をエラー本文へ含めない |
| T-23 | Google OAuth credential保存API | 認証済みユーザーに紐づくprovider refresh token保存APIは未認証を拒否し、設定不足時は503にする |
| T-24 | Supabase session Google OAuth保存ブリッジ | Supabase session由来のuser id/provider/email/scopeを検証し、現在ユーザーと一致すると保存し、不一致なら403/422にする |
| T-25 | Supabase JWT検証 | Bearer tokenの署名/audience/email domainを検証し、正常系は200、不正tokenは401、ドメイン外は403、secret未設定は503にする |
| T-26 | ジョブ所有者アクセス制限 | 非mock環境では作成者をJWT subから決め、他ユーザーの一覧・詳細・操作から見えない |
| T-27 | Supabase RLS migration | 主要テーブルでRLSを有効化し、ジョブ所有者とcredential所有者に基づくpolicyが定義されている |

## ゴールデンフィクスチャ

推奨配置:

```text
tests/fixtures/monthly_report/
  demo_sources/
  economics_multi_student_mtg/
  expected_validation/
  provider_responses/
```

匿名化済み入力を使う。実データを使う場合は、氏名やスコアなどの扱いを事前確認する。

静的POC合流の最初のゴールデン候補は、[HANDOFF_STATIC_POC_TUNING.md](HANDOFF_STATIC_POC_TUNING.md) で挙がっている Economics 複数生徒MTG とする。`_gws_doc_teacher_MTG_gemini.txt` を匿名化し、`prompt_scope_notes` により対象生徒・教科だけが家庭向け本文へ反映されることを検証する。

現時点の実装済みフィクスチャ:

```text
tests/fixtures/monthly_reports/economics_multistudent_scope/
  README.md
  _gws_doc_teacher_MTG_gemini.txt
  _gws_SL_lesson_plan_A1-M250_values.json
  _gws_student_A1-Z200_values.json
  expected_prompt_scope_notes.txt
```

このフィクスチャは合成・再構成した匿名データのみを置き、実Google URL、document_id、spreadsheet_id、実名、`REAL_` 付き識別子を含めない。`tests/test_monthly_report_fixtures.py` で匿名化状態を確認し、`tests/test_monthly_report_llm_messages.py` で `prompt_scope_notes` が根拠ソースより前に挿入されることを確認する。

### 匿名化手順

最低限のセキュリティで開始する。

- 氏名は `生徒A`, `保護者A`, `教師A` のように置換する。
- メールアドレス、電話番号、住所、Google Docs/Sheets URL、document_id、spreadsheet_idはダミー値へ置換する。
- 学習進捗の数値はテストに必要なものだけ残し、不要な細かい値は丸める。
- 自由記述に固有名詞が残っていないか目視確認する。
- 匿名化前データはリポジトリに置かない。

## 受け入れテスト

1. テストユーザーでログインする。
2. 対象月とソースを指定する。
3. ソース取得結果を確認する。
4. ジョブを開始する。
5. ジョブが `succeeded` になる。
6. Markdown草稿と検証結果が表示される。
7. フィードバックを保存できる。
8. 保存済みジョブ詳細にprompt_version、model、template_hash、sources_hashが表示される。

## 未決事項

なし。

## 受け入れ条件

- LLM実呼び出しなしで主要テストが通る。
- バリデーションルールが要件と対応している。
- 生成失敗時の調査に必要な情報をテストできる。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-13 | 初版作成 |
| 2026-05-14 | 静的POC合流に必要な build_messages 塊順、複数生徒MTG、prompt_scope_notes のテスト観点を追加 |
| 2026-05-14 | LLM呼び出しメタ保存・取得APIのテスト状況を反映 |
| 2026-05-14 | Economics 複数生徒MTGの匿名化フィクスチャ配置と、プロンプト構築テストへの接続状況を反映 |
| 2026-05-14 | 複数生徒MTG混入防止の第一弾 `multistudent_scope_exclusion` をT-17へ反映 |
| 2026-05-14 | 必須見出し検証の第一弾 `required_headings` をT-02へ反映 |
| 2026-05-14 | 配布面禁止語検出の第一弾 `forbidden_terms` をT-03へ反映 |
| 2026-05-14 | Google Workspace REST API取得とtoken秘匿のテスト観点 T-19 / T-20 を追加 |
| 2026-05-14 | Google provider refresh token暗号化保存とOAuth token refresh秘匿のテスト観点 T-21 / T-22 を追加 |
| 2026-05-14 | Google provider refresh token保存APIのテスト観点 T-23 を追加 |
| 2026-05-14 | Supabase session経由のGoogle provider refresh token保存ブリッジのテスト観点 T-24 を追加 |
| 2026-05-14 | Supabase JWT検証のテスト観点 T-25 を追加 |
| 2026-05-15 | T-09を外向きエラー抑止テストとして具体化し、T-24にprovider/email/scope検証を追加 |
| 2026-05-15 | 非mock環境のジョブ所有者アクセス制限 T-26 を追加 |
| 2026-05-15 | Supabase RLS migrationの静的テスト観点 T-27 を追加 |
| 2026-05-15 | T-09にCloud Logging向け実ログ出力のallowlist検査を追加 |
