# File Search 機能 開発ドキュメント索引

## 位置づけ

- 正本/補助資料の区分: Gemini File Search を使った参照基盤の開発ドキュメント入口
- 起点: 本 README
- 関連文書: `docs/monthly-report-workshop/README.md`, `docs/requirements/v0.3.md`, `docs/web-app/screen-design.md`, `DESIGN.md`
- 最終更新: 2026-05-14

## 機能の目的

IB シラバス・過去の月次レポート・採点ルーブリック等の参照資産を Gemini File Search ストアに集約し、月次レポート工房と将来の指導管理ポータルから RAG で参照できるようにする。狙いは次の3点。

1. **月次レポート品質の底上げ** — シラバス根拠を引いた記述、過去ゴールデンサンプルとのトーン一致
2. **横展開の素地** — ポータルからも同じストアを叩けるようにし、生徒対応・面談前リサーチで再利用
3. **管理性** — 中身が見える・差し替えられる・誰がいつ何を入れたか追える状態を最初から作る

## 正本スタック

| 優先 | 文書 | 役割 |
|---:|---|---|
| 1 | [requirements.md](requirements.md) | スコープ、4ストア構成、display_name 規約、主要決定事項 |
| 2 | [api-definition.md](api-definition.md) | バックエンド API（JSON）と admin UI fragment API |
| 3 | [screen-design.md](screen-design.md) | 管理画面の構成、HTMX 断片、操作導線 |
| 4 | [data-design.md](data-design.md) | Supabase メタテーブル・監査ログ設計 |
| 5 | [security-operations.md](security-operations.md) | 認証（講師/管理者ロール）、Secrets、BOM 対策 |
| 6 | [development-plan.md](development-plan.md) | フェーズ、WBS、完了条件 |

## 関連プロジェクトとの境界

- **monthly-report-workshop** — 月次レポート確定時に `monthly-reports-archive` ストアへ auto-ingest する。File Search 側はストアの管理と検索 API を提供するのみで、レポート生成パイプラインの責務には踏み込まない。
- **指導管理ポータル** — 将来、ポータルからも File Search を叩く。本ドキュメントの API・認証設計はポータル側からも再利用できる前提で書く。
- **OpenRouter LLM ワークフロー** — File Search で取得したチャンクを context にして、生成は OpenRouter 側で行う。File Search は **検索専用、生成は行わない**。

## 主要決定事項（2026-05-14 時点）

1. **ストアは4つに分割**: `ib-syllabus` / `monthly-reports-archive` / `scoring-rubrics` / `internal-handbook`
2. **管理画面はブラウザベース**: 一覧・手動アップロード・削除・取り込み履歴をすべて UI で完結
3. **アクセス制御**: 講師/管理者ロールのみアクセス可
4. **削除**: hard delete のみ（ゴミ箱機能は持たない）
5. **監査ログ**: 誰がいつ何を upload/delete したかを Supabase に保存
6. **検索は Gemini、生成は OpenRouter**: Secret Manager に `GEMINI_API_KEY` と `OPENROUTER_API_KEY` を両方保持

詳細と未決事項は [requirements.md](requirements.md) と development-plan の decision section を参照。

## 更新ルール

- API を変更したら [api-definition.md](api-definition.md) と [screen-design.md](screen-design.md) を同時更新する。
- ストア構成や display_name 規約を変更したら [requirements.md](requirements.md) と [data-design.md](data-design.md) を同時更新する。
- 認証・Secret の扱いを変更したら [security-operations.md](security-operations.md) と [api-definition.md](api-definition.md) を同時更新する。
- フェーズや完了条件を変更したら [development-plan.md](development-plan.md) を更新する。
