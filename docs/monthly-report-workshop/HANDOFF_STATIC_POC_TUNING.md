# 静的 POC／ローカル OpenRouter でのチューニング → レポート工房への合流入り口（他エージェント向け）

## 位置づけ

- **正本/補助資料の区分**: 補助（実装済みワークの写経用）。工房の単一真実ではなく、「いま repo にある POC 実装と設計書のギャップを埋めるための引き継ぎ」。
- **起点**: [`agents.md`](../../agents.md)（エージェント分担）、[`AUTOMATION_NORTH_STAR.md`](AUTOMATION_NORTH_STAR.md)（北極星）。
- **関連文書**: [`README.md`](README.md)、[`llm-design.md`](llm-design.md)、[`api-definition.md`](api-definition.md)、[`functional-spec.md`](functional-spec.md)、[`test-plan.md`](test-plan.md)、[`decision-log.md`](decision-log.md)。
- **最終更新**: 2026-05-14

この文書は **別チャット／別エージェントがレポート工房を実装・ドキュメント化する際** に先に読む想定です。詳細コードはすべてリポジトリ内パスへ委譲し、ここでは **何が決まり／何が未移植か** と **読む順** のみまとめる。

---

## 目的（読者ごとのゴール）

| 読者 | この文書で得られること |
|------|-------------------------|
| **Documentation Lead** | 静的 POC と工房の線引き、`prompt_version`／テンプレ／CLI の三面待ちがあること |
| **LLM／バックエンド実装者** | 現行の `build_prompts` と同等のメッセージ構成をジョブ worker に載せる条件 |
| **QA** | Economics 複数生徒 MTG のゴールデン検証の種 |
| **API 設計** | ジョブに載せたい **`scope_reminder` 相当**のメタ（将来フィールド）の必要性 |

---

## 推奨読み順（他エージェント向け最短パス）

1. [`agents.md`](../../agents.md) §1 最優先・§3 自分のロール。
2. [`AUTOMATION_NORTH_STAR.md`](AUTOMATION_NORTH_STAR.md)（静的 POC と工房の関係）。
3. **本文書** §3〜§6。
4. 担当に応じて [`llm-design.md`](llm-design.md)、[`api-definition.md`](api-definition.md)、[`functional-spec.md`](functional-spec.md) を読み、ギャップを `decision-log.md` に上げる。

---

## 決定事項（本ハンドオフで前提にしてよいこと）

1. **本文規約の正本** は引き続き [`docs/samples/monthly-reports/monthly_pattern_b_content.template.md`](../../samples/monthly-reports/monthly_pattern_b_content.template.md) であり、複数生徒が同一 Doc に現れるときの運用規約（氏名での対象確定／**別姓＋様の段落除外**／文頭が対象 ○○様のブロック優先、`--bundle-scope-reminder` との併用）は **このテンプレに含まれる**。
2. **静的 POC のレイアウト寄せ** は `ideal_html` + `structure-from-ideal` が北極星側で固定されている（例: [`docs/samples/monthly-reports/fixtures/tokura_2026-04_user_ideal.html`](../../samples/monthly-reports/fixtures/tokura_2026-04_user_ideal.html)）。工房実装でも同種のパラメータ（理想 HTML と構造）をジョブに持てるようにする余地がある。
3. **OpenRouter ローカル生成** は `scripts/monthly_report_draft_openrouter.py` が実体。環境変数 `OPENROUTER_API_KEY`、`OPENROUTER_MODEL_REPORT` 等は [`agents.md`](../../agents.md) / [`llm-design.md`](llm-design.md) と整合すること。
4. **再現レシピ** は [`docs/samples/monthly-reports/fixtures/report_recipes/*.recipe.json`](../../samples/monthly-reports/fixtures/report_recipes/README.md)。`prompts.scope_reminder` が CLI の `--bundle-scope-reminder` に渡る。

---

## 実装・成果物一覧（静的 POC 側で「もう動いている」もの）

### 規約・文体

| 項目 | パス・備考 |
|------|------------|
| Pattern B 本文テンプレ正本（複数生徒 MTG／文頭 ○○様の節あり） | `docs/samples/monthly-reports/monthly_pattern_b_content.template.md` |
| 家庭向け文体（複数 MTG で文頭様ルールへの言及） | `.cursor/skills/monthly-report-notebooklm-patterns/references/family-facing-tone.md` |
| Cursor ルール（北極星要約） | `.cursor/rules/monthly-report-north-star.mdc` |

### CLI・レシピ

| 項目 | パス・備考 |
|------|------------|
| OpenRouter で MD/HTML を生成するスクリプト。`build_prompts` に **`scope_reminder`**、system に複数生徒混線警告 | `scripts/monthly_report_draft_openrouter.py`（`--bundle-scope-reminder`） |
| レシピ → 上記スクリプト起動。**`prompts.scope_reminder`** を渡す | `scripts/monthly_report_run_recipe.py` |
| ソースプリセット | `scripts/monthly_report_source_presets.json`（`pattern_b_gws_sl` 等） |
| レシピ例・README | `docs/samples/monthly-reports/fixtures/report_recipes/`（`hirayama_economics_pattern_b_shell.recipe.json`、`tokura_v5_*`、`hirayama_physics_*` 等） |

### データ取得（開発・検証）

| 項目 | パス・備考 |
|------|------------|
| gws で Sheets/Docs を取得 | `scripts/fetch_monthly_gws_sources.py`（`--range-sl-lesson` でタブ名上書き可） |
| Doc JSON → TXT | `scripts/gws_doc_json_to_plaintext.py` |
| **Economics**：ブックの SL はタブ名 **`lesson plan`**（`【SL】lesson plan` ではない場合あり） | `samples/reports/household_hirabayashi_economics/sources/README.md` |
| Physics：タブ **`lesson plan`** が Physics 用別ブック | `samples/reports/household_hirabayashi/sources/README.md` |

### 静的配布・エディタ（検証軌道）

| 項目 | パス・備考 |
|------|------------|
| サンプル HTML 正本群 | `docs/samples/monthly-reports/monthly_*_report.html` |
| マニフェスト・revision | `docs/samples/monthly-reports/reports-manifest.json` |
| 全文エディタ（サンプルボタンに **平山（Economics）** `hirayama_economics`） | `docs/samples/monthly-reports/tools/monthly_report_full_editor.html` |
| Vercel にコピー | `node scripts/sync_monthly_reports_to_vercel.mjs` → `src/reports/templates/monthly-reports/` |
| 静的ルート | ルート [`vercel.json`](../../vercel.json) に各 `*_report.html` が列挙 |

### モデル検証メモ（Economics）

- 同一 MTG に **平林様** と **飯村様** が混在する Doc をソースに、`scope_reminder` で **Economics／平林のみ** と **文頭様ルール**を明示。
- 生成 HTML（Sonnet 既定）：家庭向け本文に **飯村様固有の評価・対策文言は混入なし**。管理者向け `.admin-only` に注意書きあり（運用確認用）。
- **Opus への切り替え** は必須ではない。総括のみで氏名が出ない複雑 Doc で逸脱した場合に `rerun` で検討、で足りる想定。

---

## 詳細：`build_prompts` の構造（工房側で再現すべき入力順）

静的ツール側のユーザー塊組み立て順は概念的に以下。工房の **`build_messages`** と **二重ソース**になるため、共通モジュール化または仕様での明示が必要です。

1. **コンテンツ契約**：`monthly_pattern_b_content.template.md`（全文）
2. **対象レポートのスコープ**（任意）：`--bundle-scope-reminder` / レシピ `prompts.scope_reminder`
3. **根拠ソース**：preset に合わせた `_gws_*.json` と `.txt` の束ね（MTG は `.txt` があれば `.json` は重複回避で除外済み）
4. **構造参考**：`structure_from_ideal` で ideal HTML を HTML ごと構造入力に
5. **語感参考**：ideal のプレーン化（事実転載禁止）
6. **指示**：artifact（html/md）ごとの追指示

system 側にはartifact別の禁止事項および **複数生徒 MTG での混入禁止** が含まれる。

---

## 工房（agents.md／api-definition）との差分・合流ポイント

| 静的 POC であるもの | 工房で必要な対応 |
|---------------------|-------------------|
| `recipe.json` と `prompt_version` の名前が未対応付け | ジョブ作成時 **`prompt_version` + template_hash + source_bundle_hash** を [`api-definition.md`](api-definition.md) どおり保存し、静的レシピ ID を決定ログで対応付け推奨 |
| `bundle_scope_reminder` が CLI のみ | ジョブ JSON に **`mtg_discriminator`／`prompt_scope_notes` 等の任意フィールド**を追加するか、household メタから自動生成するか **未決**（[`decision-log.md`](decision-log.md) U-025 参照） |
| `gws` ローカル取得 | OAuth によるサーバ fetch に置換。出力ファイル規約 **`_gws_*`** は再利用しやすい |
| Sonnet で十分なケースもある | **`model_report` 既定**は Sonnet、そのままでよい |

---

## リスク・注意（合流時に踏み外しやすい点）

| リスク | 説明 |
|--------|------|
| **プロンプト二重管理** | `monthly_report_draft_openrouter.py` の長文 system とテンプレの更新が **`llm-design.md` の断片管理方式** と食い違うとチューニングが二度手間になる |
| **`prompt_version` の境界** | テンプレ改定のみ／Python のみ／scope のみを同一版に含めるかを決めないと比較不能 |
| **PII とログ** | Economics MTG に複数氏名。Cloud Logging に **生バンドルを出さない**（既定方針は `decision-log.md`） |
| **静的エディタ vs 工房エディタ** | 両方「エディタ」で利用者が迷う。**本番ワークフローは工房**と README に明示する |
| **取得レンジのゆれ** | Economics と Physics で **スプレッドシート ID・タブ名が異なる**。工房は `spreadsheet_id` + range 明示が必須 |

---

## 未決事項（本ハンドオフから起票）

| ID | 場所 | 論点 |
|----|------|------|
| U-025 | [`decision-log.md`](decision-log.md) | 静的 `scripts/monthly_report_draft_openrouter.py` と工房 worker の **`build_messages` をどう単一ソース化するか**（共有 Python モジュール vs 仕様のみ一致） |

（その他、`scope_reminder` をジョブ API のどこに載せるかは U-025 とセットで論じる）

---

## 受け入れ条件（静的チューニングが「工房に取り込まれた」と言える状態）

以下を満たすと、静的 POC と工房が意味で揃ったと見なせる。

1. [`llm-design.md`](llm-design.md) に **本ファイル §「build_prompts の構造」** と同等の塊順が明示されていること。
2. ジョブに **template／scope／bundle／structure／ideal／artifact** が欠けないことを [`functional-spec.md`](functional-spec.md) または API で追跡できること。
3. **複数生徒 MTG のゴールデン** が [`test-plan.md`](test-plan.md) に載ること（Economics `_gws_doc_teacher_MTG_gemini.txt` がフィクスチャ候補）。
4. `decision-log.md` の U-025 が **解決**または **意図的な二重ソース許容** が記録されていること。

---

## 改訂履歴

| 日付 | 内容 |
|------|------|
| 2026-05-14 | 初版（静的 POC チューニング〜Economics を他エージェントへ渡す統合ハンドオフとして作成） |
