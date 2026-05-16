# アクティビティ図

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールの業務・画面・API横断フロー補助資料
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `workflow-spec.md`, `functional-spec.md`, `screen-design.md`, `api-definition.md`, `data-design.md`
- 最終更新: 2026-05-14

## 決定事項

- MVPはFastAPI + Jinja2 + HTMXで実装し、長時間生成はDBジョブ + HTMXポーリングで扱う。
- Sheets / Docs / DriveはユーザーOAuthでサーバ取得する。
- 生成パイプラインは `fetch_sources` → `bundle` → `build_messages` → `call_llm` → `validate` → `persist` の段階で扱う。
- 検証エラーはMVPでは自動repair loopへ送らず、草稿・検証結果・フィードバックを保存して人手の推敲へ戻す。

## 標準アクティビティ

```mermaid
flowchart TD
    start((開始))
    finish((終了))

    subgraph user[ユーザー]
        U1[Googleログイン]
        U2[対象月・世帯・ソースURLを入力]
        U3[取得済みソースを確認]
        U4[生成開始]
        U5[進捗を確認]
        U6[草稿をプレビュー・推敲]
        U7[検証結果を確認]
        U8[フィードバックを保存]
    end

    subgraph ui[Jinja2 + HTMX 画面]
        S00[MR-S00 MVPトップ]
        S01[MR-S01 ジョブ一覧]
        S02[MR-S02 新規ジョブ作成]
        S03[MR-S03 ソース確認]
        S04[MR-S04 ジョブ詳細]
        S05[MR-S05 プレビュー・推敲]
        F01[status fragment polling]
        F02[preview fragment]
        F03[validation fragment]
    end

    subgraph api[FastAPI]
        A1[Supabase Authセッション検証]
        A2[tomonokai-corp.com ドメイン検証]
        A3[入力検証]
        A4[ソース取得要求]
        A5[同時実行ジョブ数チェック]
        A6[ジョブ作成 queued]
        A7[ジョブ状態取得]
        A8[フィードバック保存]
    end

    subgraph job[生成ジョブ]
        J1[fetch_sources]
        J2[bundle]
        J3[build_messages]
        J4[call_llm]
        J5[validate]
        J6[persist]
        J7[succeeded]
    end

    subgraph external[外部サービス]
        G1[Google Sheets / Docs / Drive API]
        L1[OpenRouter]
    end

    subgraph db[Supabase Postgres]
        D1[(monthly_report_jobs)]
        D2[(monthly_report_sources)]
        D3[(monthly_report_artifacts)]
        D4[(monthly_report_validations)]
        D5[(monthly_report_feedback)]
        D6[(llm_call_logs / audit_logs)]
    end

    start --> U1 --> A1
    A1 --> A2
    A2 -->|OK| S00
    A2 -->|NG| E403[403 ドメイン外]
    S00 --> S01
    E403 --> finish

    S01 --> U2 --> S02 --> A3
    A3 -->|不正| E422[入力エラー表示]
    E422 --> S02
    A3 -->|OK| A4 --> J1
    J1 --> G1 --> D2 --> S03

    S03 --> U3
    U3 -->|再取得| A4
    U3 -->|生成開始| U4 --> A5
    A5 -->|3件以上| E429[同時実行上限メッセージ]
    E429 --> S01
    A5 -->|3件未満| A6 --> D1 --> S04

    S04 --> F01 --> A7 --> D1 --> U5
    A6 --> J2 --> D2
    J2 --> J3 --> D6
    J3 --> J4 --> L1 --> D6
    J4 --> D3 --> J5
    J5 --> D4 --> J6 --> J7 --> D1

    J7 --> F02 --> S05
    J7 --> F03 --> U7
    S05 --> U6 --> A8 --> D5
    U7 -->|修正が必要| S05
    U7 -->|問題なし| U8 --> A8 --> finish
```

## 例外・分岐アクティビティ

```mermaid
flowchart TD
    start((ジョブ実行中))

    start --> C1{ユーザーがキャンセル?}
    C1 -->|はい| C2[cancel_requestedに更新]
    C2 --> C3[実行中stageの終了を待つ]
    C3 --> C4[cancelledとして保存]
    C4 --> end_cancel((中止))
    C1 -->|いいえ| P1[次のstageへ進む]

    P1 --> E1{OAuth失効?}
    E1 -->|はい| E2[failed / oauth_expiredを保存]
    E2 --> E3[再ログイン・再連携を表示]
    E3 --> end_failed((失敗))
    E1 -->|いいえ| E4{ソース取得失敗?}

    E4 -->|はい| E5[失敗ソースをsnapshotとして保存]
    E5 --> E6[ソース確認画面で再取得導線を表示]
    E6 --> end_source((ソース確認へ戻る))
    E4 -->|いいえ| E7{LLMタイムアウト?}

    E7 -->|はい| E8[failed / llm_timeoutを保存]
    E8 --> E9[失敗stageと再実行導線を表示]
    E9 --> end_failed
    E7 -->|いいえ| E10{検証エラーあり?}

    E10 -->|はい| E11[草稿とvalidation warning/errorを保存]
    E11 --> E12[プレビュー・推敲画面で人手修正]
    E12 --> end_edit((推敲へ))
    E10 -->|いいえ| E13[succeededとして保存]
    E13 --> end_success((完了))
```

## 画面遷移との対応

| アクティビティ | 画面 | API / fragment | 主な保存先 |
|---|---|---|---|
| ログイン・ドメイン検証 | ログイン / 403 | 認証基盤側 | `audit_logs` |
| 新規ジョブ入力 | MR-S02 | `POST /api/monthly-reports/jobs` | `monthly_report_jobs` |
| ソース取得・確認 | MR-S03 | 後続実装 | `monthly_report_sources` |
| 進捗確認 | MR-S04 | `GET /monthly-reports/jobs/{job_id}/fragments/status` | `monthly_report_jobs` |
| 草稿表示 | MR-S05 | `GET /monthly-reports/jobs/{job_id}/fragments/preview` | `monthly_report_artifacts` |
| 検証結果表示 | MR-S04 / MR-S05 | `GET /monthly-reports/jobs/{job_id}/fragments/validation` | `monthly_report_validations` |
| フィードバック保存 | MR-S05 | `POST /api/monthly-reports/jobs/{job_id}/feedback` または fragment POST | `monthly_report_feedback` |

## 未決事項

なし。ソース確認APIの詳細は `api-definition.md` の今後の拡張で具体化する。

## 受け入れ条件

- 標準フローが `workflow-spec.md` の login から feedback までを表現している。
- ユーザー、画面、API、ジョブ、外部サービス、DBの責務境界が読める。
- 429、OAuth失効、ソース取得失敗、LLMタイムアウト、検証エラー、キャンセルの例外分岐がある。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-14 | 初版作成 |
