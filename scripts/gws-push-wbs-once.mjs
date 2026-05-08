/**
 * One-shot: WBS シートへ再構成した WBS を書き込み。
 * P1a〜P1d / P3 / P4 / 横串ガバナンス の構成。
 * docs/project/面談学習計画レポート標準化_WBS.md に準拠。
 * 2026-04-09: フェーズ再構成・体制修正・AI技術方針追加。
 */
import { spawnSync } from 'child_process';

const RUN_GWS =
  process.env.GWS_RUN_JS ||
  'C:/Users/yohay/AppData/Roaming/npm/node_modules/@googleworkspace/cli/run-gws.js';
const SPREADSHEET_ID = '1SM9kTEDDNz0zDAvsmXV0MaX14CpQg90BJQPcdHD40JM';
const SHEET = 'WBS';

const E = '';

function runGws(values, range) {
  const paramsObj = {
    spreadsheetId: SPREADSHEET_ID,
    range: `${SHEET}!${range}`,
    valueInputOption: 'USER_ENTERED',
  };
  const params = JSON.stringify(paramsObj);
  const jsonBody = JSON.stringify({ values });
  const r = spawnSync(process.execPath, [
    RUN_GWS, 'sheets', 'spreadsheets', 'values', 'update',
    '--params', params, '--json', jsonBody,
  ], { encoding: 'utf8', shell: false, windowsHide: true, maxBuffer: 10 * 1024 * 1024 });
  if (r.error) throw r.error;
  if (r.status !== 0) {
    console.error(r.stdout, r.stderr);
    process.exit(r.status ?? 1);
  }
  try {
    const j = JSON.parse(r.stdout || '{}');
    console.log(JSON.stringify({ updated: j.updatedRange, rows: j.updatedRows }, null, 2));
  } catch {
    console.log(r.stdout);
  }
}

function rowPhase(no, name) {
  return [String(no), name, E, E, E, E, E, E, E, E, E, E];
}
function rowChu(no, chu) {
  return [String(no), E, chu, E, E, E, E, E, E, E, E, E];
}
function rowSho(no, sho) {
  return [String(no), E, E, sho, E, E, E, E, E, E, E, E];
}
function rowTask(no, task, status, owner, rel, start, end, doc, note) {
  return [String(no), E, E, E, task, status, owner, rel, start, end, doc, note];
}

let n = 0;
const rows = [
  // ==========================================================
  // P1a テンプレ決定・手動パイロット
  // ==========================================================
  rowPhase(++n, 'P1a テンプレ決定・手動パイロット [M1,M2]'),

  rowChu(++n, 'テンプレ選定'),
  rowSho(++n, 'パターン比較'),
  rowTask(++n,
    '4パターン（A〜D）の比較評価・推奨案決定',
    '進行中', '原口', '藤井・元山',
    '2026-04-02', '2026-04-16', 'src/reports/', 'HTML 4種試作済み。来週決定'),
  rowSho(++n, '採用パターン確定'),
  rowTask(++n,
    '関係者レビュー → 採用パターン1つに確定',
    '未着手', '原口', '藤井・元山',
    '', '', '', 'P1aの最初のマイルストーン'),

  rowChu(++n, '手動パイロット'),
  rowSho(++n, '素材収集'),
  rowTask(++n,
    '藤井さんの直近面談1件の3ソース（MTG記録・面談記録・学習計画表）を手動で収集',
    '未着手', '原口', '藤井',
    '', '', 'ワークフロー.md', '3ソース準拠'),
  rowSho(++n, 'レポート手動作成'),
  rowTask(++n,
    '確定テンプレに実データを手動で流し込み、HTMLレポート1件を作成',
    '未着手', '原口', '藤井',
    '', '', '', 'テンプレ確定後すぐ着手'),
  rowSho(++n, '品質レビュー'),
  rowTask(++n,
    '藤井さんが内容を確認し「送れる品質か」を判定、修正点フィードバック',
    '未着手', '藤井', '原口',
    '', '', '', '品質基準の言語化の起点にする'),
  rowSho(++n, 'パイロット配信'),
  rowTask(++n,
    '簡易方式（Drive限定共有 or パスワードページ）で配信 → 反応収集',
    '未着手', '原口', '藤井・元山',
    '', '', '', '本番セキュリティ（ワンタイムURL）はP1bで開発'),

  // ==========================================================
  // P1b AI生成＋品質検証 / セキュリティ開発
  // ==========================================================
  rowPhase(++n, 'P1b AI生成＋品質検証 / セキュリティ開発 [M3,M4]'),

  rowChu(++n, 'AI生成（Gemini単体）'),
  rowSho(++n, 'プロンプト設計'),
  rowTask(++n,
    '3ソース＋システム指示→レポート生成のプロンプト設計・テスト',
    '未着手', '原口', '藤井',
    '', '', '', 'P1aの品質フィードバックを反映'),
  rowSho(++n, 'テンプレエンジン'),
  rowTask(++n,
    'AI出力→採用テンプレHTMLへの自動流し込みエンジン開発',
    '未着手', '原口', '',
    '', '', '', ''),
  rowSho(++n, '品質チェック'),
  rowTask(++n,
    '品質チェックリスト策定（数値一致・ソース準拠・トーン）＋自動検証ロジック',
    '未着手', '原口', '藤井',
    '', '', '', '肝 「ほぼそのまま送れる」の定義'),
  rowSho(++n, '複数件検証'),
  rowTask(++n,
    '3〜5件のレポートをAI生成し、藤井さんの修正率を計測',
    '未着手', '原口', '藤井',
    '', '', '', '修正率20%以下が目標'),

  rowChu(++n, 'File Search設計（並行）'),
  rowSho(++n, 'ストア設計'),
  rowTask(++n,
    '生徒ごとのFile Searchストア構成設計（月次蓄積・過去レポート格納）',
    '未着手', '原口', '',
    '', '', '', 'P1b後期〜P1cで切替時に使う'),
  rowSho(++n, '時系列対応'),
  rowTask(++n,
    'File Search導入・過去データとの時系列比較（線の可視化）の実装',
    '未着手', '原口', '',
    '', '', '', '2ヶ月目以降のレポートで必要'),

  rowChu(++n, 'セキュリティ開発（並行）'),
  rowSho(++n, '要件定義'),
  rowTask(++n,
    'ワンタイムURL方式の要件定義',
    '完了', '原口', '',
    '2026-04-02', '2026-04-02', 'T1-3', 'セキュリティ要件定義書作成済み'),
  rowSho(++n, '認証バックエンド'),
  rowTask(++n,
    'トークン生成・検証API、HTTPS強制、アクセスログ',
    '未着手', '原口', '',
    '', '', 'T1-3', ''),
  rowSho(++n, '閲覧ページ'),
  rowTask(++n,
    '保護者向けレポート閲覧ページ（レスポンシブ）',
    '未着手', '原口', '',
    '', '', '', 'ワンタイムURLクリック→レポート表示'),

  rowChu(++n, 'DB設計（並行）'),
  rowSho(++n, 'スキーマ'),
  rowTask(++n,
    '生徒・教師・レポート履歴・トークンのDB設計',
    '未着手', '原口', '',
    '', '', '', 'P1cマイページの前提'),

  // ==========================================================
  // P1c マイページ開発
  // ==========================================================
  rowPhase(++n, 'P1c マイページ開発 [M5]'),

  rowChu(++n, '社内管理画面'),
  rowSho(++n, 'レポート一覧'),
  rowTask(++n,
    'ご家庭×教師ごとのレポート一覧・ステータス管理画面',
    '未着手', '原口', '藤井',
    '', '', '', ''),
  rowSho(++n, '編集画面'),
  rowTask(++n,
    'AI生成レポートの編集UI（WYSIWYG or Markdown）',
    '未着手', '原口', '藤井',
    '', '', '', '藤井さんが自分で修正できる'),
  rowSho(++n, '承認・送信'),
  rowTask(++n,
    '確認→承認→ワンタイムURL発行→メール送信の一連フロー',
    '未着手', '原口', '藤井・元山',
    '', '', '', ''),

  rowChu(++n, '文字起こし手動アップロード'),
  rowSho(++n, 'アップロード機能'),
  rowTask(++n,
    '管理画面から文字起こしファイルを手動アップロード→生徒に紐付け',
    '未着手', '原口', '藤井',
    '', '', '', 'この段階では自動取り込み不要'),

  rowChu(++n, 'ご家庭ビュー'),
  rowSho(++n, 'マイページ'),
  rowTask(++n,
    'ご家庭×教師ごとの過去レポート閲覧ページ',
    '未着手', '原口', '',
    '', '', '', '保護者が過去のレポートも見返せる'),

  // ==========================================================
  // P1d 配信自動化＋取り込み自動化
  // ==========================================================
  rowPhase(++n, 'P1d 配信自動化＋取り込み自動化 [M6]'),

  rowChu(++n, 'メール配信'),
  rowSho(++n, '自動送信'),
  rowTask(++n,
    'レポート確定→ワンタイムURL付きメール自動送信',
    '未着手', '原口', '',
    '', '', '', 'SendGrid等'),
  rowSho(++n, '送信履歴・開封'),
  rowTask(++n,
    '送信履歴・開封確認・統計ダッシュボード',
    '未着手', '原口', '元山',
    '', '', '', ''),

  rowChu(++n, '文字起こし自動取り込み'),
  rowSho(++n, '命名規則'),
  rowTask(++n,
    '文字起こしファイルの命名規則統一（生徒番号_教師番号_種別_日付）',
    '進行中', '元山', '藤井',
    '2026-04-02', '', '議事録', '肝 04-02決定'),
  rowSho(++n, '教師周知'),
  rowTask(++n,
    '教師・スタッフへの命名規則説明と遵守確認',
    '未着手', '元山', '藤井',
    '', '', '', ''),
  rowSho(++n, 'Drive権限'),
  rowTask(++n,
    '本山さん・藤井さんのレコーディングフォルダへのアクセス権限取得',
    '進行中', '原口', '元山',
    '2026-04-02', '', '議事録', ''),
  rowSho(++n, '自動取り込みエンジン'),
  rowTask(++n,
    'Google Drive API連携・ファイル自動検知・パース・DB格納',
    '未着手', '原口', '',
    '', '', 'DESIGN.md', 'src/auto_import/ に設計ドキュメントあり'),

  rowChu(++n, '教師ルール'),
  rowSho(++n, '発言ルール'),
  rowTask(++n,
    '教師に固有名詞（単元名等）を明確に発言してもらうルール導入',
    '進行中', '元山', '藤井',
    '2026-04-02', '', '議事録', '文字起こし精度向上が目的'),

  // ==========================================================
  // P3 週次指導報告の自動化
  // ==========================================================
  rowPhase(++n, 'P3 週次指導報告の自動化 [M7]'),

  rowChu(++n, '設計'),
  rowSho(++n, 'パイロット範囲'),
  rowTask(++n,
    'First stepの対象教師・クラス・教科の合意',
    '未着手', '元山', '藤井・原口',
    '', '', '議事録', 'PJC卒業要件③'),
  rowSho(++n, 'フロー設計'),
  rowTask(++n,
    '録画→文字起こし→報告書→共有の設計叩き台',
    '未着手', '原口', '元山',
    '', '', '', '文字起こし可否の技術確認が前提'),

  rowChu(++n, '開発'),
  rowSho(++n, '報告書生成'),
  rowTask(++n,
    'P1bの生成エンジンを週次報告テンプレに適用',
    '未着手', '原口', '',
    '', '', '', 'P1b完了後に着手'),
  rowSho(++n, '自動配信'),
  rowTask(++n,
    '承認プロセス省略の全自動送付パイプライン',
    '未着手', '原口', '元山',
    '', '', '', '請求書が事実上の承認'),

  // ==========================================================
  // P4 無料見積もり診断サービス
  // ==========================================================
  rowPhase(++n, 'P4 無料見積もり診断サービス [M8]'),

  rowChu(++n, '設計'),
  rowSho(++n, '要件'),
  rowTask(++n,
    '要件・フロー設計（答案提供→AI分析レポート無料提供）',
    '未着手', '原口', '元山',
    '', '', 'PJC', ''),

  rowChu(++n, '開発'),
  rowSho(++n, 'MVP'),
  rowTask(++n,
    '診断レポート生成・提供の仕組み開発',
    '未着手', '原口', '',
    '', '', '', ''),

  // ==========================================================
  // 横串: ガバナンス
  // ==========================================================
  rowPhase(++n, '横串: ガバナンス'),

  rowChu(++n, '品質定義'),
  rowSho(++n, '品質基準'),
  rowTask(++n,
    '要約「品質の正体」の定義と評価尺度',
    '未着手', '原口', '藤井',
    '', '', '議事録', '肝 P1bの品質チェックと連動'),

  rowChu(++n, '未決クローズ'),
  rowSho(++n, '棚卸し'),
  rowTask(++n,
    '未決事項一覧（法務・権限・SLA・承認フロー等）のオーナー・期限設定',
    '未着手', '原口', '元山',
    '', '', '課題一覧JSON', '肝 PJC卒業要件④'),

  rowChu(++n, '法務・権限'),
  rowSho(++n, '確認'),
  rowTask(++n,
    '文字起こし・録画の保存先・権限・同意の法務確認',
    '未着手', '元山', '原口',
    '', '', '', ''),

  rowChu(++n, '要件定義'),
  rowSho(++n, '整備'),
  rowTask(++n,
    'レポート自動化システム要件定義書',
    '完了', '原口', '',
    '2026-04-02', '2026-04-02', '要件定義書', 'v1.0作成済み'),
];

runGws([['更新日', '2026-04-09']], 'A2:B2');
runGws([['起点日', '2026-03-26']], 'K3:L3');
runGws([['docs/project/面談学習計画レポート標準化_PJC.md']], 'E4');

const lastRow = 5 + rows.length;
runGws(rows, `A6:L${lastRow}`);

const CLEAR_FROM = lastRow + 1;
const CLEAR_TO = 130;
if (CLEAR_FROM <= CLEAR_TO) {
  const emptyRows = Array.from({ length: CLEAR_TO - CLEAR_FROM + 1 }, () =>
    Array(12).fill('')
  );
  runGws(emptyRows, `A${CLEAR_FROM}:L${CLEAR_TO}`);
}

console.log(`\nDone. ${rows.length} rows (NO.1〜${n}) written (A6:L${lastRow}). Cleared A${CLEAR_FROM}:L${CLEAR_TO}.`);
