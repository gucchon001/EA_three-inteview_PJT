# LLM設計書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールのLLM設計
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `functional-spec.md`, `data-design.md`, `test-plan.md`
- 最終更新: 2026-05-16

## 方針

- 当面はOpenRouter中心で構築する。
- 本文生成は品質優先モデル、抽出・分類・下準備は廉価モデルに分ける。
- 呼び出しは薄い抽象に閉じ、マルチプロバイダ前提の過剰設計はしない。
- プロンプトはリポジトリ内のファイル断片として管理し、コード内の長文字列を避ける。
- レポート本文生成の既定は固定モデルとする。OpenRouter Auto Router `openrouter/auto` は、管理者向けのチューニング・比較用オプションとして許可する。
- Google Docs/Sheets由来の本文は信頼済み命令として扱わない。ソース本文は根拠データとして区切り、システム指示、本文規約、対象範囲、送付可否を上書きできないことをプロンプトと検証で固定する。

## 環境変数

| 変数 | 用途 | 必須 |
|---|---|---:|
| `OPENROUTER_API_KEY` | OpenRouter APIキー | 必須 |
| `OPENROUTER_MODEL_REPORT` | レポート本文生成モデル | 必須 |
| `OPENROUTER_MODEL_LIGHT` | 抽出・分類・下準備モデル | 推奨 |
| `OPENROUTER_MODEL` | 後方互換フォールバック | 任意 |
| `OPENROUTER_ENABLE_AUTO_ROUTER` | `openrouter/auto` を管理者向け選択肢に出すか | 任意 |
| `OPENROUTER_TIMEOUT` | OpenRouter呼び出しタイムアウト秒 | 任意 |
| `OPENROUTER_MAX_TOKENS` | 疎通確認・MVP初期の出力上限 | 任意 |

## モデル用途

| prompt_kind | 用途 | モデル |
|---|---|---|
| `report` | 月次レポート本文生成 | Sonnet / Opus相当 |
| `light` | 構造化抽出、タグ付け、下準備 | 廉価モデル |
| `repair` | 検証エラー修正 | MVPでは任意 |
| `auto_experiment` | Auto Router比較 | `openrouter/auto` |

## Auto Router

OpenRouterのAuto Routerは `openrouter/auto` を指定すると、プロンプトに応じてOpenRouter側がモデルを選ぶ。実際に使われたモデルはレスポンスの `model` 属性に返るため、チューニング比較では必ず保存する。

### 採用方針

- 既定の本文生成には使わない。
- 管理者向けのモデル選択・再生成・A/B比較で使えるようにする。
- 一般ユーザーにはAuto Routerや任意モデル選択を公開しない。
- Auto Router利用時は、`requested_model = "openrouter/auto"` と `resolved_model = response.model` の両方を保存する。
- 料金はルーティングされた実モデルに応じるため、コスト集計では `resolved_model` を使う。

### 使わない場面

- ゴールデンフィクスチャの回帰確認。
- 厳密な再現性が必要な配布直前生成。
- モデル差分を原因分析したい固定比較。

## プロンプト構成

推奨配置:

```text
src/eb_app/prompts/monthly/
  report_system.md
  report_user.md
  tone_family_facing.md
  validation_repair.md
  prompt_version.txt
```

`build_messages` は、静的POCの `scripts/monthly_report_draft_openrouter.py` にある `build_prompts` と意味がずれないようにする。合流時の正本補助は [HANDOFF_STATIC_POC_TUNING.md](HANDOFF_STATIC_POC_TUNING.md) とする。

現在の実装では、`src/eb_app/monthly_reports/llm_messages.py` の `build_monthly_report_messages` を共通関数とし、静的POCの `build_prompts` はこの関数を呼ぶ薄いラッパにしている。工房workerも同じ関数を呼ぶ前提で、塊順は `tests/test_monthly_report_llm_messages.py` で固定する。

### build_messagesの塊順

1. system断片: artifact別の禁止事項、複数生徒MTGでの混入禁止、本文規約の守り方
2. コンテンツ契約: `monthly_pattern_b_content.template.md` 全文
3. 対象レポートのスコープ: `prompt_scope_notes`。静的POCの `--bundle-scope-reminder` / レシピ `prompts.scope_reminder` に対応する正式フィールド
4. 根拠ソース: presetに合わせた `_gws_*.json` と `.txt` の束ね。MTGは `.txt` があれば同名 `.json` を重複投入しない
5. 構造参考: `structure_from_ideal` のときはideal HTMLまたは構造HTMLをHTMLごと渡す
6. 語感参考: ideal HTMLをプレーン化したもの。事実転載は禁止し、文体・見出し粒度の参考に限定する
7. artifact別指示: `html` / `md` など出力形式ごとの追指示

system断片には、ソース本文・MTGメモ・Sheetsセル内に含まれる命令文、リンク、内部メモ、モデル操作指示を開発者指示として扱わないことを明記する。根拠ソースは事実抽出の材料であり、出力形式・対象範囲・送付可否・秘密情報の扱いを変更できない。

### 単一ソース化方針

実装では、静的POCの `build_prompts` を写経して別実装にせず、まず `src/eb_app/monthly_reports/llm_messages.py` のような共通モジュールへ抽出する。CLI側は薄いラッパとしてその共通関数を呼び、工房workerも同じ関数を使う方針を第一候補とする。

レシピ `prompts.scope_reminder` は工房ジョブでは `prompt_scope_notes` に変換する。初期投入はレシピ由来 + 手入力可能とし、householdメタからの自動生成は後続に回す。

## prompt_version

`prompt_version` は人間が読める運用版として、以下の形式で採番する。

```text
monthly-report-vYYYYMMDD.N
```

例:

```text
monthly-report-v20260513.1
monthly-report-v20260513.2
monthly-report-v20260520.1
```

Git SHA、template hash、source hash、app versionは `prompt_version` とは別に保存する。これにより、UIや運用会話では読みやすい版名を使い、監査・再現性ではhash類を使う。

## パイプライン

```text
fetch_sources
  -> bundle_sources
  -> build_messages
  -> call_openrouter
  -> validate_draft
  -> persist_artifacts
```

現在のコード上の入口は `src/eb_app/monthly_reports/workflow.py`。`run_monthly_report_job` は保存済みソースを束ね、共通 `build_monthly_report_messages`、provider、決定的検証、artifact保存、stage更新を1ジョブで実行する。

非同期worker境界としては `src/eb_app/monthly_reports/worker.py` の `run_next_queued_monthly_report_job` を用意している。Storeの `claim_next_queued_job` が `queued` jobを `running/fetch_sources` へclaimし、claim済みjobは `run_claimed_monthly_report_job` で二重startせず同じLLMパイプラインへ入る。

providerは以下を用意済み:

- `StaticMonthlyReportProvider`: provider mock。`POST /api/monthly-reports/jobs/{job_id}/run-mock` とテストで使う
- `OpenRouterMonthlyReportProvider`: OpenRouter `chat/completions` 用の薄いHTTP provider。HTTPモック単体テストで、APIキーを例外メッセージへ含めないこと、`resolved_model` をレスポンスから返すことを確認済み。工房本体の `/run-openrouter` から実ネットワーク通電済み

## ログ・メタ

ジョブごとに以下を `llm_call_logs` へ保存する。Mock/Postgres storeと `GET /api/monthly-reports/jobs/{job_id}/llm-calls` で確認できる。本文やプロンプト全文は保存・返却せず、hashとメタだけを扱う。

- `provider`
- `requested_model`
- `resolved_model`
- `prompt_kind`
- `prompt_version`
- `sources_hash`
- `template_hash`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `finish_reason`
- `error_type`

本文やプロンプト全文はCloud Loggingへ出さず、必要ならhashとサイズのみをログへ出す。provider失敗時も `error_type = provider_call_failed` のログを残し、APIキーや本文断片をエラーメッセージに含めない。Cloud Logging向け構造化ログはallowlist方式で生成し、`job_id`, `stage`, `prompt_kind`, `provider`, `requested_model`, `resolved_model`, `prompt_version`, `request_hash`, `response_hash`, `latency_ms`, token数、`finish_reason`, `error_type`, `rule_id` などのメタだけを出す。

## 決定的バリデーション

LLMに任せず、コードで検証する。

| rule_id | 内容 |
|---|---|
| `required_headings` | テンプレートから抽出した `## 01...` 形式の必須見出しがdraftに存在する |
| `forbidden_terms` | 配布面禁止語がdraftに存在しない。第一弾は `担当CA`, `教師 MTG`, `NotebookLM` |
| `star_lines_exact` | 星5行が原文一致する |
| `progress_contract` | 学習の進捗データ契約に従う |
| `non_empty_markdown` | Markdownが空でない |
| `multistudent_scope_exclusion` | `prompt_scope_notes` で明示された対象外生徒の呼称がdraftへ混入していない |
| `prompt_injection_terms` | ソース本文に含まれる命令文を検知し、出力がそれに従っていないことを確認する |
| `internal_note_exposure` | 内部メモ、教師MTG固有表現、送付禁止の運用語が家庭向け本文へ露出していない |
| `human_approval_required` | 送付/エクスポート前に承認済み状態がある |

## repair loop

MVPでは自動repair loopを実装しない。検証エラーはユーザーに表示し、手動修正・フィードバック・再生成判断の材料にする。

将来採用する場合は、検証エラーと該当箇所のみを渡し、ソース全文を再送しない設計を優先する。repairの結果は通常生成とは別の `prompt_kind = repair` として保存し、元草稿との差分を追跡できるようにする。

## 未決事項

なし。U-025は、共通Pythonモジュール化を第一候補、`prompts.scope_reminder` の置き場所を `prompt_scope_notes`、初期投入をレシピ由来 + 手入力可能とする方針で解決済み。

## 受け入れ条件

- 本文生成と軽量タスクのモデルが分離されている。
- 生成結果にprompt_version、model、sources_hashが紐づく。
- プロンプト断片がリポジトリ内に置ける設計になっている。
- ソース本文内の命令を信頼せず、対象外生徒・内部メモ・送付禁止語・プロンプトインジェクションを検証できる。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-13 | 初版作成 |
| 2026-05-14 | HANDOFF_STATIC_POC_TUNING.md を踏まえ、静的POCと同じ `build_messages` 塊順と単一ソース化方針を追加 |
| 2026-05-14 | `prompt_scope_notes` を正式フィールド名として反映 |
| 2026-05-14 | `prompt_scope_notes` の初期投入方針をレシピ由来 + 手入力可能に決定 |
| 2026-05-14 | `build_monthly_report_messages` の共通実装パスと塊順テストを反映 |
| 2026-05-14 | `workflow.py` のprovider mock通電とOpenRouter provider抽象を反映 |
| 2026-05-14 | `/run-openrouter` によるOpenRouter実provider通電完了を反映 |
| 2026-05-14 | `llm_call_logs` へのhash/メタ保存と取得APIを反映 |
| 2026-05-14 | worker claim境界とclaim済みjobのLLMパイプライン入口を反映 |
| 2026-05-14 | `multistudent_scope_exclusion` 第一弾を決定的バリデーションへ追加 |
| 2026-05-15 | Cloud Logging向け構造化ログallowlistとworkflowログ接続を反映 |
| 2026-05-14 | `required_headings` 第一弾の実装範囲を決定的バリデーションへ反映 |
| 2026-05-14 | `forbidden_terms` 第一弾の実装範囲を決定的バリデーションへ反映 |
| 2026-05-16 | Google Docs/Sheets本文を信頼済み命令として扱わない方針、プロンプトインジェクション・内部メモ露出・人間承認ゲートの検証観点を追加 |
