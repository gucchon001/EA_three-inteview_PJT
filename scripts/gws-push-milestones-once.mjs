/**
 * One-shot: マイルストーンシートへ全体マイルストーンを書き込み。
 * 親PJC のマイルストーン表に準拠。
 * 2026-04-09 初版。
 */
import { spawnSync } from 'child_process';

const RUN_GWS =
  process.env.GWS_RUN_JS ||
  'C:/Users/yohay/AppData/Roaming/npm/node_modules/@googleworkspace/cli/run-gws.js';
const SPREADSHEET_ID = '1SM9kTEDDNz0zDAvsmXV0MaX14CpQg90BJQPcdHD40JM';
const SHEET = 'マイルストーン';

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

const header = [
  ['面談ビュー＆レポート標準化 PJ — 全体マイルストーン'],
  ['更新日: 2026-04-09'],
  [],
  ['#', 'マイルストーン', 'Phase', '完了基準', '目標時期', 'ステータス', '子PJCリンク'],
];

const milestones = [
  ['M1', 'テンプレ確定', 'P1a', '4パターンから1つに確定、関係者合意', '2026-04-16', '進行中', 'P1a子PJC'],
  ['M2', '手動パイロット配信', 'P1a', '実データ1件のレポートをご家庭に配信しフィードバック取得', '2026-04-末', '未着手', 'P1a子PJC'],
  ['M3', 'AI生成品質合格', 'P1b', 'AI生成→藤井さん修正率20%以下を3件以上で達成', '2026-05-末', '未着手', '（P1b子PJC）'],
  ['M4', 'セキュリティ基盤完成', 'P1b', 'ワンタイムURL認証バックエンド・閲覧ページ・DB完成', '2026-06-中', '未着手', '（P1b子PJC）'],
  ['M5', 'マイページリリース', 'P1c', '社内管理画面＋ご家庭ビューで編集〜送信が画面完結', '2026-07-中', '未着手', '（P1c子PJC）'],
  ['M6', '自動化パイプライン稼働', 'P1d', '文字起こし自動取り込み＋メール自動配信が10件/月で安定稼働', '2026-08-末', '未着手', '（P1d子PJC）'],
  ['M7', '週次報告自動化', 'P3', 'P1bエンジン流用で週次報告が全自動送付される状態', '2026-09-末', '未着手', '（P3子PJC）'],
  ['M8', '診断サービスMVP', 'P4', '答案→AI分析レポート無料提供の仕組みが1件稼働', '下期', '未着手', '（P4子PJC）'],
];

const depHeader = [
  [],
  ['フェーズ依存関係'],
  ['P1a → P1b → P1c → P1d'],
  ['P1b → P3（エンジン流用）'],
  ['P1/P3 → P4（データ蓄積後）'],
  [],
  ['セキュリティ方針'],
  ['Phase', '方式', '理由'],
  ['P1a（パイロット）', '簡易方式（Drive限定共有 or パスワードページ）', 'フィードバック最速取得が目的。1件のみ'],
  ['P1b〜', 'ワンタイムURL認証（T1-3準拠）', '本番セキュリティ基盤'],
];

runGws(header, 'A1:G4');
runGws(milestones, 'A5:G12');
runGws(depHeader, 'A14:C23');

console.log('\nDone. Milestones written to sheet.');
