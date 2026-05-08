/**
 * プロジェクト全体像（共有用）を Google スプレッドシートに出力し、見出し・表頭・列幅を装飾する。
 * 実行: node scripts/project_overview_to_sheet.mjs
 *
 * 前提: gws 認証済み（gws auth login -s sheets）
 */
import { spawnSync } from 'child_process';
import { writeFileSync } from 'fs';
import { join } from 'path';

const GWS_JS = join(process.env.APPDATA, 'npm', 'node_modules', '@googleworkspace', 'cli', 'run-gws.js');

function runGws(args) {
  const r = spawnSync(process.execPath, [GWS_JS, ...args], {
    encoding: 'utf8',
    maxBuffer: 16 * 1024 * 1024,
    shell: false,
    windowsHide: true,
  });
  if (r.error) throw r.error;
  if (r.status !== 0) throw new Error(r.stderr || r.stdout || `exit ${r.status}`);
  return r.stdout;
}

function createSpreadsheet(title, sheetTitles) {
  const sheets = sheetTitles.map((t, index) => ({
    properties: { title: t, index, gridProperties: { frozenRowCount: 0, columnCount: 12, rowCount: 200 } },
  }));
  const body = JSON.stringify({
    properties: { title },
    sheets,
  });
  return JSON.parse(runGws(['sheets', 'spreadsheets', 'create', '--json', body]));
}

function updateValues(ssId, sheetName, rows) {
  const safeName = sheetName.includes(' ') || /[^A-Za-z0-9_\u0080-\uFFFF]/.test(sheetName)
    ? `'${sheetName.replace(/'/g, "''")}'`
    : sheetName;
  const params = JSON.stringify({
    spreadsheetId: ssId,
    range: `${safeName}!A1`,
    valueInputOption: 'USER_ENTERED',
  });
  const body = JSON.stringify({ values: rows });
  runGws(['sheets', 'spreadsheets', 'values', 'update', '--params', params, '--json', body]);
}

function batchUpdate(ssId, requests) {
  const params = JSON.stringify({ spreadsheetId: ssId });
  const body = JSON.stringify({ requests });
  runGws(['sheets', 'spreadsheets', 'batchUpdate', '--params', params, '--json', body]);
}

// --- 色（0–1）---
const C = {
  titleBg: { red: 0.259, green: 0.522, blue: 0.957 },
  titleFg: { red: 1, green: 1, blue: 1 },
  sectionBg: { red: 0.85, green: 0.918, blue: 0.827 },
  headerBg: { red: 0.855, green: 0.898, blue: 0.945 },
  subBg: { red: 0.97, green: 0.97, blue: 0.97 },
};

function repeatCellRange(sheetId, startRow, endRow, startCol, endCol, format, fields) {
  return {
    repeatCell: {
      range: {
        sheetId,
        startRowIndex: startRow,
        endRowIndex: endRow,
        startColumnIndex: startCol,
        endColumnIndex: endCol,
      },
      cell: { userEnteredFormat: format },
      fields: fields || 'userEnteredFormat',
    },
  };
}

function mergeA1(sheetId, row, colCount) {
  return {
    mergeCells: {
      range: {
        sheetId,
        startRowIndex: row,
        endRowIndex: row + 1,
        startColumnIndex: 0,
        endColumnIndex: colCount,
      },
      mergeType: 'MERGE_ALL',
    },
  };
}

function colWidths(sheetId, widths) {
  return widths.map((pixelSize, i) => ({
    updateDimensionProperties: {
      range: { sheetId, dimension: 'COLUMNS', startIndex: i, endIndex: i + 1 },
      properties: { pixelSize },
      fields: 'pixelSize',
    },
  }));
}

function freezeTopRows(sheetId, n) {
  return {
    updateSheetProperties: {
      properties: {
        sheetId,
        gridProperties: { frozenRowCount: n },
      },
      fields: 'gridProperties.frozenRowCount',
    },
  };
}

function wrapAll(sheetId, rowCount, colCount) {
  return repeatCellRange(
    sheetId,
    0,
    rowCount,
    0,
    colCount,
    { wrapStrategy: 'WRAP', verticalAlignment: 'TOP' },
    'userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment',
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// シート別データ（Markdown 正本に準拠）
// ═══════════════════════════════════════════════════════════════════════════

const sheetNames = [
  '概要',
  '体制',
  '目的と目標',
  '課題_AsIs',
  'ワークフロー',
  '子プロジェクト',
  'マイルストーン',
  'その他',
];

const sh = {
  概要: [
    ['面談ビュー＆レポート標準化プロジェクト — 全体像（共有用）'],
    [],
    ['文書の目的', '関係者がプロジェクトの目的・進め方・マイルストーンを短時間で把握できるようにする。'],
    ['正本', '面談学習計画レポート標準化_PJC.md / 面談学習計画レポート標準化_WBS.md'],
    ['更新日', '2026-04-09'],
    [],
    ['■ プロジェクトの全体像（一言）'],
    [
      '',
      'エデュバルアカデミーにおいて、教師MTG・家庭面談・学習計画を根拠にした月次レポートを、テンプレ標準化 → AI支援 → 編集・承認 → 安全な配信 → 自動取り込みの順で実現し、工数削減・品質安定・顧客価値（アップセル・離脱防止）を同時に高めるプロジェクトです。',
    ],
  ],

  体制: [
    ['■ 体制（who）'],
    ['役割', '担当', '主な責務'],
    ['開発主体・PM', '原口', 'システム開発、AI連携、レポートテンプレ、WBS管理'],
    ['面談実施・品質確認', '藤井', '教師MTG・家庭面談の実施、レポート品質レビュー・修正'],
    ['現場責任者', '元山', '業務フロー決定、運用ルール承認、教師マネジメント'],
  ],

  目的と目標: [
    ['■ 3本柱（ビジネス目的）'],
    ['#', '内容'],
    ['1', 'アップセル促進 — レポート・面談の接触回数と質を高め、追加契約につなげる'],
    ['2', '離脱防止 — 月次ルーチンで定期的な接触を確保し、契約継続率を上げる'],
    ['3', '業務標準化 — 型化・自動化で属人性を減らし、再現可能な運用にする'],
    [],
    ['■ 定量目標（イメージ）'],
    ['指標', '現状（目安）', '目標（方向性）'],
    ['レポート作成時間', '4〜6時間／件', '約30分／件（編集中心）'],
    ['AI生成レポートの修正負荷', '高い（大幅修正が常態化）', '修正率 20%以下 を目安に安定化'],
    [],
    ['■ 親プロジェクト完了のイメージ（卒業条件の要約）'],
    ['・月次レポートの一連パイプライン（取り込み→生成→編集→配信）が実運用で回る'],
    ['・週次指導報告の自動化（P3）が設計・実証に入る'],
    ['・品質基準が言語化され、AI出力の修正率が目標水準で安定'],
    ['・未決事項（法務・権限・SLA 等）がオーナー付きで棚卸しされる'],
  ],

  課題_AsIs: [
    ['■ 現在の課題（AsIs）'],
    ['工数', '面談準備・レポート化に 4〜6時間／件かかり、上期の最大ボトルネックになりやすい'],
    ['属人性', '面談メモ・体裁がバラつき、テンプレとツールが分散'],
    ['顧客コミュニケーション', 'メール中心で、構造化レポートほどの訴求・追跡がしづらい'],
    ['AI要約の品質', '品質定義が言語化されておらず、藤井さんによる大幅修正が続きやすい'],
    ['データ・運用', '模試・答案・日程などの共有遅延、週次報告の手作業、命名規則のばらつきなど'],
    ['法務・権限', '録画・文字起こしの保存・同意は合意が必要（段階導入）'],
  ],

  ワークフロー: [
    ['■ 月次レポートの「正」とする一次情報（3ソース）'],
    ['ソース', '内容'],
    ['教師MTG記録', '要約・文字起こし'],
    ['家庭面談記録', '面談の記録'],
    ['学習計画表', '最新スナップショット（数値・目標の「正」はここを優先）'],
    [],
    ['■ 現在の流れ（概念・図の代わり）'],
    ['教師MTG・面談・計画表 → メモ・メール・手作業 → 長時間の整形・要約 → メール等で共有'],
    [],
    ['■ 目指す流れ（ToBe）'],
    ['3ソースの整理・取り込み → AIで草案生成 → 藤井さんが編集・承認 → 安全な方法で保護者へ配信'],
    [],
    ['■ 段階メモ'],
    ['P1a（今）', 'テンプレ確定と手動で1件ご家庭へ届け、フィードバックを得る（配信は簡易方式）'],
    ['P1b以降', 'AI生成の品質検証と、本番向けのセキュア配信（ワンタイムURL等）を整備'],
  ],

  子プロジェクト: [
    ['■ 子プロジェクト（フェーズ）一覧'],
    ['Phase', '名称', '目的', 'ゴール（完了のイメージ）', '主な成果物'],
    [
      'P1a',
      'テンプレ決定・手動パイロット',
      '最速で「ご家庭に届く」体験とフィードバックを得る',
      'テンプレ1つに確定し、実データ1件を配信して反応を得る',
      '採用HTMLテンプレ、手動レポート1件、フィードバック記録',
    ],
    [
      'P1b',
      'AI生成＋品質検証／セキュリティ',
      'AIで草案を作り「送れる品質」を測る／安全に届ける基盤を作る',
      '修正率目標を満たす検証＋ワンタイムURL等の基盤',
      'プロンプト、品質チェック、認証・閲覧・DB設計',
    ],
    [
      'P1c',
      'マイページ',
      '社内とご家庭で、編集から送信までを画面で完結させる',
      '管理画面＋ご家庭ビューで運用可能',
      '一覧・編集・承認・送信、過去閲覧、手動アップロード',
    ],
    [
      'P1d',
      '配信自動化＋取り込み自動化',
      '件数が増えても破綻しない運用にする',
      '自動取り込み＋メール自動配信が安定',
      'Drive連携、命名規則運用、配信ログ等',
    ],
    [
      'P3',
      '週次指導報告の自動化',
      '週次の報告をルーチン化し離脱防止に寄与',
      '週次報告の自動送付が回る',
      'P1bエンジン流用、対象範囲の合意',
    ],
    [
      'P4',
      '無料見積もり診断（後段）',
      'データ蓄積を活かし新規導線を作る',
      'MVPが1件動く',
      '診断フロー、レポート試作',
    ],
    [],
    ['横串（全フェーズ）', '品質定義、法務・権限、未決事項のオーナー管理'],
    [],
    ['■ フェーズ依存関係（概要）'],
    ['P1a → P1b → P1c → P1d →（P4 は後段）'],
    ['P1b → P3（並行し得る）'],
    ['※ P4 は P1/P3 のデータ蓄積を見ながら後段で着手'],
  ],

  マイルストーン: [
    ['■ 全体マイルストーン（M1〜M8）'],
    ['#', 'マイルストーン', 'Phase', '完了基準', '目標時期'],
    ['M1', 'テンプレ確定', 'P1a', '4パターンから1つに確定、関係者合意', '2026-04-16'],
    ['M2', '手動パイロット配信', 'P1a', '実データ1件をご家庭に配信しフィードバック取得', '2026-04-末'],
    ['M3', 'AI生成品質合格', 'P1b', 'AI生成→藤井さん修正率20%以下を3件以上で達成', '2026-05-末'],
    ['M4', 'セキュリティ基盤完成', 'P1b', 'ワンタイムURL認証・閲覧・DBが揃う', '2026-06-中'],
    ['M5', 'マイページリリース', 'P1c', '社内＋ご家庭で編集〜送信が画面完結', '2026-07-中'],
    ['M6', '自動化パイプライン稼働', 'P1d', '自動取り込み＋メール自動配信が月10件規模で安定', '2026-08-末'],
    ['M7', '週次報告自動化', 'P3', '週次報告が自動送付される状態', '2026-09-末'],
    ['M8', '診断サービスMVP', 'P4', '答案→AI分析レポート無料提供が1件稼働', '下期'],
    [],
    ['進捗メモ（抜粋）', '2026-04-02 要件定義・セキュリティ要件（T1-3）完了／2026-04-09 フェーズ再構成・HTMLテンプレ4種試作完了'],
  ],

  その他: [
    ['■ AI・セキュリティの方針（要約）'],
    ['項目', '内容'],
    ['AI（段階的）', 'まず Gemini 単体で3ソースから生成・品質検証 → 必要に応じ File Search で時系列・蓄積へ'],
    ['パイロット配信（P1a）', '簡易方式（Drive限定共有 or 簡易パスワード）。最速フィードバック優先'],
    ['本番寄り（P1b〜）', 'ワンタイムURL 等、要件定義（T1-3）に沿った配信'],
    [],
    ['■ スコープ外（当面）'],
    ['・三者面談の新規プロセス立ち上げ（別扱い）'],
    ['・教材・教師連携の大型立ち上げ、採点システム本体（別プロジェクト）'],
    [],
    ['■ 関連ドキュメント'],
    ['面談学習計画レポート標準化_PJC.md', '親PJC（詳細）'],
    ['P1a_テンプレ決定・手動パイロット_PJC.md', '現在の子PJC'],
    ['月次レポート生成ワークフロー.md', '3ソース運用の手順'],
    ['プロジェクト計画_全体概要.md', '計画・リスクの補足'],
    [],
    ['■ スライド化'],
    ['推奨', 'Marp: docs/project/プロジェクト全体像_共有用_slides.md → PDF 出力（日本語・体裁固定）'],
    ['参考', 'NotebookLM スタジオは英語寄り・画像品質に限界あり。Marp を正とする運用が無難'],
  ],
};

function sheetIdMap(createResponse) {
  const map = {};
  for (const s of createResponse.sheets || []) {
    const t = s.properties?.title;
    const id = s.properties?.sheetId;
    if (t != null && id != null) map[t] = id;
  }
  return map;
}

function buildFormatRequests(ids) {
  const requests = [];

  const padRowCount = (rows) => Math.max(rows.length + 5, 40);

  // --- 概要 ---
  const id0 = ids['概要'];
  requests.push(mergeA1(id0, 0, 6));
  requests.push(
    repeatCellRange(id0, 0, 1, 0, 6, {
      backgroundColor: C.titleBg,
      horizontalAlignment: 'CENTER',
      textFormat: { bold: true, foregroundColor: C.titleFg, fontSize: 13 },
    }),
  );
  requests.push(repeatCellRange(id0, 6, 7, 0, 6, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(wrapAll(id0, padRowCount(sh.概要), 6));
  requests.push(...colWidths(id0, [220, 520, 120, 120, 120, 120]));

  // --- 体制 ---
  const id1 = ids['体制'];
  requests.push(repeatCellRange(id1, 0, 1, 0, 3, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id1, 1, 2, 0, 3, { backgroundColor: C.headerBg, textFormat: { bold: true } }));
  requests.push(wrapAll(id1, padRowCount(sh.体制), 3));
  requests.push(freezeTopRows(id1, 2));
  requests.push(...colWidths(id1, [160, 100, 480]));

  // --- 目的と目標 ---
  const id2 = ids['目的と目標'];
  requests.push(repeatCellRange(id2, 0, 1, 0, 2, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id2, 1, 2, 0, 2, { backgroundColor: C.headerBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id2, 7, 8, 0, 3, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id2, 8, 9, 0, 3, { backgroundColor: C.headerBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id2, 12, 13, 0, 1, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(wrapAll(id2, padRowCount(sh.目的と目標), 3));
  requests.push(...colWidths(id2, [40, 520, 400]));

  // --- 課題 ---
  const id3 = ids['課題_AsIs'];
  requests.push(repeatCellRange(id3, 0, 1, 0, 2, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id3, 1, 7, 0, 1, { backgroundColor: C.subBg, textFormat: { bold: true } }));
  requests.push(wrapAll(id3, padRowCount(sh.課題_AsIs), 2));
  requests.push(...colWidths(id3, [140, 720]));

  // --- ワークフロー ---
  const id4 = ids['ワークフロー'];
  requests.push(repeatCellRange(id4, 0, 1, 0, 2, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id4, 1, 2, 0, 2, { backgroundColor: C.headerBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id4, 6, 7, 0, 1, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id4, 9, 10, 0, 1, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id4, 12, 13, 0, 2, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(wrapAll(id4, padRowCount(sh.ワークフロー), 2));
  requests.push(...colWidths(id4, [200, 660]));

  // --- 子プロジェクト ---
  const id5 = ids['子プロジェクト'];
  requests.push(repeatCellRange(id5, 0, 1, 0, 5, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id5, 1, 2, 0, 5, { backgroundColor: C.headerBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id5, 16, 17, 0, 5, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(wrapAll(id5, padRowCount(sh.子プロジェクト), 5));
  requests.push(freezeTopRows(id5, 2));
  requests.push(...colWidths(id5, [72, 200, 220, 260, 260]));

  // --- マイルストーン ---
  const id6 = ids['マイルストーン'];
  requests.push(repeatCellRange(id6, 0, 1, 0, 5, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id6, 1, 2, 0, 5, { backgroundColor: C.headerBg, textFormat: { bold: true } }));
  requests.push(wrapAll(id6, padRowCount(sh.マイルストーン), 5));
  requests.push(freezeTopRows(id6, 2));
  requests.push(...colWidths(id6, [56, 160, 72, 320, 120]));

  // --- その他 ---
  const id7 = ids['その他'];
  requests.push(repeatCellRange(id7, 0, 1, 0, 2, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id7, 1, 2, 0, 2, { backgroundColor: C.headerBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id7, 6, 7, 0, 1, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id7, 10, 11, 0, 2, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(repeatCellRange(id7, 16, 17, 0, 2, { backgroundColor: C.sectionBg, textFormat: { bold: true } }));
  requests.push(wrapAll(id7, padRowCount(sh.その他), 2));
  requests.push(...colWidths(id7, [280, 580]));

  return requests;
}

// ═══════════════════════════════════════════════════════════════════════════
// メイン
// ═══════════════════════════════════════════════════════════════════════════

const bookTitle = '面談レポート標準化_プロジェクト全体像_2026-04-09';

console.log('スプレッドシートを作成中...');
const ss = createSpreadsheet(bookTitle, sheetNames);
const ssId = ss.spreadsheetId;
const ssUrl = ss.spreadsheetUrl;
console.log(`作成: ${ssUrl}`);

const ids = sheetIdMap(ss);
for (const name of sheetNames) {
  if (ids[name] === undefined) console.warn('警告: sheetId が見つかりません:', name);
}

console.log('セルに書き込み中...');
for (const name of sheetNames) {
  updateValues(ssId, name, sh[name]);
  console.log(`  ${name}`);
}

console.log('書式を適用中（batchUpdate）...');
batchUpdate(ssId, buildFormatRequests(ids));

const out = { spreadsheetId: ssId, spreadsheetUrl: ssUrl, title: bookTitle, updated: new Date().toISOString() };
writeFileSync('scripts/project_overview_sheet_result.json', JSON.stringify(out, null, 2), 'utf8');

console.log('\n完了。URL:', ssUrl);
console.log('結果: scripts/project_overview_sheet_result.json');
