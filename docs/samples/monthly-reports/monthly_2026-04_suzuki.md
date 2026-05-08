---
title: 月次レポート（鈴木 謙吾さま・2026年4月発行）— 初版アーカイブ
period: "2026-03"
student_code: "73594"
student_name: "鈴木 謙吾"
notebook_id: "8d0e1e72-2137-485e-a524-826ba11d359c"
map_revision_date: "2026-04-21"
review_status: superseded
---

> **ファイル分割のお知らせ（2026-04-21）**  
> - **配布用レポート本文**: [monthly_2026-04_suzuki_report.md](monthly_2026-04_suzuki_report.md) / [monthly_2026-04_suzuki_report.html](monthly_2026-04_suzuki_report.html)  
> - **内部用（ソース・推敲・チェック）**: [monthly_2026-04_suzuki_sources.md](monthly_2026-04_suzuki_sources.md)  
> 以下は初版の単一ファイル構成のまま残しています（参照用）。

# 月次レポート（2026年3月対象・鈴木 謙吾）

本ファイルは一次ソース（学習計画スプレ `student`・`lesson plan`、Google Doc「学習計画表とMTG記録」およびリンク先「3月MTG議事録」）から**転記できる範囲のみ**記載している。推測は書かない。

<span style="color:#c0392b;font-weight:bold">【赤字の凡例】読み取れない項目・未取得のデータ・人間確認が必須な矛盾・AI要約である旨を示す。</span>

---

## レイアウトと Pattern B の対応（転記用）

配布 HTML は [monthly_2026-04_suzuki.html](monthly_2026-04_suzuki.html)。転記時はメタ行・推敲ログを載せない。

---

## 一次ソースメタ

| 項目 | 値 |
|------|-----|
| 学習計画表スプレッドシート ID | `1PwCEU459GnXVuqE72N_rP9ojtwTWZ-p6ij_mAr1v1bE` |
| 参照シート | `student`（gid 1227932684）、`lesson plan` |
| gws 取得例 | `student!A1:J80`、`'lesson plan'!A1:H45`（2026-04-21 取得） |
| 教師 MTG の参照先 | Google Doc `1FZJFsKOR9Q9c2CPHA-OcP3lmQuBzdjK3aiC1GPdkePQ`（Doc タイトル上「3月MTG議事録」へのリンク経由） |
| 留保 | <span style="color:#c0392b;font-weight:bold;">Drive に別ファイル「73594 鈴木さま 学習計画表 Math AI(HL)」があるが、本レポートでは未取得のため Math AI 科目の計画表・授業ログは記載していない。</span> |

---

## データソース対応表（月次マップ）

| ブロック | MD 見出し | データソース（マップ表記） | 取得方法 |
|----------|-----------|---------------------------|----------|
| ①基本情報 | 01 基本情報 | 学習計画表_student sheet | gws |
| ②学校の試験 | 02 学校の試験 | 学習計画表_student sheet 等 | gws + MTG要約（限定事実） |
| ③塾での様子 | 02 塾での様子 | 教師 mtg の議事録 | gws Doc→リンク先 MTG（Gemini 要約） |
| ③授業内容 | 03 授業内容 | 学習計画表＋教師 mtg の議事録 | gws `lesson plan` + MTG |
| ④課題・アドバイス | 04 課題とアドバイス | 教師 mtg の議事録 | 同上 |
| ⑤学習の進捗 | 05 学習の進捗 | 学習計画表 | gws `lesson plan`（Physics HL のみ） |
| ⑥今後の授業計画 | 06 今後の授業計画 | 学習計画表＋教師 mtg の議事録 | gws + MTG |

---

## 01 基本情報

**根拠ソース（月次マップ）**: 学習計画表_student sheet  
**取得方法**: gws `spreadsheets.values.get`（`student!A1:J80`、見出しと値ブロックはスプレ上で離れた位置にあるため行を突合）

| 項目 | 値 |
|------|-----|
| 生徒番号 | 73594（`student` シート転記） |
| 生徒名 | 鈴木 謙吾（同） |
| 教師名 | 森田 大翔（同） |
| 担当者名 | 藤井（同。フルネームの記載なし）<span style="color:#c0392b;font-weight:bold;">※姓のみのため正式表記は未確認</span> |
| 科目（シート上の「科目」行） | Physics(HL)（同）<span style="color:#c0392b;font-weight:bold;">※別欄では HL に English B, Physics, Math AI と複数科目の列挙あり。「科目」行は Physics(HL) のみのため、レポート対象範囲は塾側 Physics 指導に限定して記載。</span> |
| 志望大学（シート） | ミュンヘン工科大学(TUM)（同） |
| 受験校その他 | カールスルーエ工科大学(KIT)、早稲田大学 理工学部（英語学位）（`student` 転記） |
| 在籍校 | Frankfurt International School（同） |
| IB 合計スコア | スプレ記載: `mid semester 29/42` および `29/42`（合計欄）（同）。<span style="color:#c0392b;font-weight:bold;">「目標合計点」の別セルは本取得範囲では確認できず未記載。</span> |
| 科目スコア / Physics(HL) | 5/7（同） |

---

## 学校の試験について

**根拠ソース（月次マップ）**: 学習計画表_student sheet  
**取得方法**: gws

| 項目 | 値 |
|------|-----|
| 学校のテスト（スプレのラベル） | `26年5月末　end of exam`（`student` シート転記） |
| mock / final（スプレ） | mock exam `2027 Jan`、final exam `2027 May`（同） |
| <span style="color:#c0392b;font-weight:bold;">2026年4月度レポート対象期間（3月）に対応する「学校試験の日程・得点」の専用欄</span> | <span style="color:#c0392b;font-weight:bold;">`student` シートの上記取得範囲に明示なし。MTGメモに「B5の試験が週の火曜日に実施、結果は未出」等の言及はあるが時系列照合用の確定日付がメモ内に無いため本文には転記しない。</span> |

---

## 02 塾での様子

**根拠ソース（月次マップ）**: 教師 mtg の議事録  
**取得方法**: Google Doc `1FZJFsKOR9Q9c2CPHA-OcP3lmQuBzdjK3aiC1GPdkePQ` の本文（会議ツール＋Gemini による自動要約）

<span style="color:#c0392b;font-weight:bold;">本節の根拠文書は会議の自動要約であり、その末尾に「Gemini が生成したメモの内容の正確性をご確認ください」とある。運用では教師・CA の事実確認後に配布すること。</span>

<span style="color:#c0392b;font-weight:bold;">スプレの教師名「森田 大翔」と MTG 見出しの「Taiga Morita」の同一性は本データから証明できないため、以下では MTG に記載された表記をそのまま用いつつ、基本情報の表とは整合確認が必要と注記する。</span>

### 学習進捗（三段階アイコン等）

- MTG要約（概要）:**授業時間は 1 人 30 分で計 1.5 時間に設定された**との記載がある。
- MTG要約:**トピック B の単元理解は「レベルで約 2.5 と非常に高い」とされる一方、トピック A は単元理解は難しくなくても難易度が上がるため試験対策として練習が必要**と記載がある。
- MTG要約:**春休み中の授業では復習と予習を組み合わせ、とくにトピック A に苦手意識があるため 3月29日と4月5日の授業では A2・A3 の復習に重点を置く**旨が記載されている。
- MTG要約:**3月15日の授業では A1・B1・B5 の試験の復習練習**が行われた、**3月22日にも同様の復習**、**3月29日にはトピック B 全体の復習や練習テストの計画**がある、との記載がある。
- MTG要約（試験結果）:**「鈴木さんが B1、B3 および B4 の試験で A7 を取得した」**との一文がある。<span style="color:#c0392b;font-weight:bold;">別段落では「B1、B3、B4 の試験で 7 を取得」と表現されており記載が一致しない。本レポートでは数値表記を断定せず、担当者による原資料照合を要請する。</span>

### 学習意欲・宿題

- MTG要約:**宿題は授業で終わらなかった練習問題に加え、Taiga Morita 氏から数問出題され、正答率はおおよそ 7〜8 割**との記載がある。
- MTG要約:**推奨の練習問題サイトで自律的に学習している**ため、**多量の宿題は不要との判断**がある、との記載がある。

**NLMクエリ要約**: 未使用（一次 Doc を gws で直接取得）。

---

## 03 授業内容

**根拠ソース（月次マップ）**: 学習計画表 ＋ 教師 mtg の議事録  
**取得方法**: gws `lesson plan`、MTG要約（上記）

<span style="color:#c0392b;font-weight:bold;">下表の「塾進捗」列はスプレの列名「進捗」のセル値を転記している。列名「理解度」はスプレに存在しない。</span>

| 授業日（2026年3月） | 学習単元（`lesson plan` の Subtopic 列の原文） | 学校 | 塾（進捗列） |
|---------------------|-----------------------------------------------|------|-------------|
| 2026/03/01 | B.5 Current and circuits 1 | 済 | 済 |
| 2026/03/08 | B.5 Current and circuits 2；B.5 Current and circuits 3 | 済 | 済 |
| 2026/03/15 | A.1 Kinematics 1；A.1 Kinematics 2；B.1 Thermal energy transfers 1；B.1 Thermal energy transfers 2；B.5 Current and circuits 1；B.5 Current and circuits 2；B.5 Current and circuits 3 | 済 | 済 |
| 2026/03/22 | A.1 Kinematics 1；A.1 Kinematics 2；B.1 Thermal energy transfers 1；B.1 Thermal energy transfers 2；B.5 Current and circuits 1；B.5 Current and circuits 2；B.5 Current and circuits 3 | 済 | 済 |
| 2026/03/29 | A.1 Kinematics 1；A.1 Kinematics 2；A.2 Forces and momentum 1；A.2 Forces and momentum 2；A.2 Forces and momentum 3；A.3 Work, energy and power 1；A.3 Work, energy and power 2；A.3 Work, energy and power 3 | 済 | 済 |

<span style="color:#c0392b;font-weight:bold;">「Review (practice test A.1-A3 )」行は、当該行の「授業日」セルに `2026/03/29` のみが入り他列が空欄のため、**同日に Review 単体のみ実施したかはスプレからは断定しない**（MTG には「3/29 にトピック B 全体の復習や練習テストの計画」とあるが、スプレ行との1対1照合は未実施）。</span>

### 当塾での所見

- MTG要約:**春休み中の授業回は復習2回・予習1回のペース**で進める、との合意が記載されている。
- MTG要約:**4月12日の最後の授業では C1 の最初の部分の予習**を行う、との記載がある。

**NLMクエリ要約**: 使用せず。

---

## 04 課題とアドバイス

**根拠ソース（月次マップ）**: 教師 mtg の議事録  
**取得方法**: MTG Doc（Gemini 要約）

- MTG要約:**トピック A の発展問題への対応が春休みの課題**とある。
- MTG要約:**トピック A は苦手意識があるため基本の徹底に加え、ExamMate 等の試験に近い問題への取り組みを続ける**ことが助言として記載されている。
- <span style="color:#c0392b;font-weight:bold;">「ミスの種類と原因」など月次案フォーマットの細目が MTG メモに見当たらない箇所は記載を欠く（推測しない）。</span>

**NLMクエリ要約**: 使用せず。

---

## 05 学習の進捗

**根拠ソース（月次マップ）**: 学習計画表  
**取得方法**: gws `lesson plan`（**Physics HL スプレシートのみ**）

Physics（`lesson plan`）において、Topic A・B の大部分で「学校」「進捗」列に「済」が入っている行が多数ある（2026-04-21 取得）。  
<span style="color:#c0392b;font-weight:bold;">Math AI 別ファイルは未取得のため数学の進捗表は出さない。</span>  
<span style="color:#c0392b;font-weight:bold;">Topic C 付近は一部セルが空欄であり、未実施・未入力の判別はできないため断定しない。</span>

---

## 07 今後の授業計画

**根拠ソース（月次マップ）**: 学習計画表（表）＋教師 mtg の議事録（本文）  
**取得方法**: gws + MTG Doc

| 時期（スプレ「授業日」列より抜粋） | 計画内容（Subtopic） |
|----------------------------------|---------------------|
| 2026/04/19 | C.1 Simple harmonic motion 1（`lesson plan`） |
| 2026/04/26 | C.1 Simple harmonic motion 2 |
| 2026/05/03 | C.2 Wave model, Wave phenomena 1 |
| 2026/05/10 等 | C.3 関連行（詳細はスプレを参照） |

### 方針・お願い（MTG ベース）

MTG「次のステップ」欄に次が列挙されている（要約文の抜粋・箇条書き）。

- **Taiga Morita 氏**: 今後の授業用に **2 時間分の予約枠を確保する**。
- **Taiga Morita 氏**: **鈴木様へメール**し、**学校の先生からシラバスや今後の予定を入手できるか確認する**。
- **藤井葉奈 氏**: **3 者面談後**、進路・最終目標などを確認し **Slack で森田氏に共有する**（<span style="color:#c0392b;font-weight:bold;">「森田」とスプレの「森田 大翔」の関係は上記のとおり未検証</span>）。

---

## 推敲ログ（3 回）

### 第 1 回（事実・数値・出所）

| 項目 | 内容 |
|------|------|
| 実施日 | 2026-04-21 |
| 担当 | Cursor エージェント（AI） |
| 変更サマリー | gws で `student`・`lesson plan`、Doc 2 本を取得。表の「7」「A7」表記の矛盾・教師名表記の不一致を赤字で明示。Math AI ファイルは未取得と明記。 |
| 未解決 | MTG が Gemini 要約のため原担任による音声・議事との照合が必要。 |

### 第 2 回（文体・長さ）

| 項目 | 内容 |
|------|------|
| 実施日 | 2026-04-21 |
| 担当 | Cursor エージェント（AI） |
| 変更サマリー | 保護者向け敬体に統一。取得できなかった見出しは「推測せず」赤字注記に置換。 |
| 未解決 | 02・04・07 の分量が MTG 依存のため、配布前に人間の加筆が望ましい。 |

### 第 3 回（保護者視点・次アクション）

| 項目 | 内容 |
|------|------|
| 実施日 | 2026-04-21 |
| 担当 | Cursor エージェント（AI） |
| 変更サマリー | MTG「次のステップ」を家庭が把握できるよう 06 に集約。シラバス・学校予定の確認は担当者経由のフォローが主であることを明記。 |
| 未解決 | 家庭側の具体的アクションは MTG 本文に限定的。必要なら面談後に追記。 |

---

## 人間チェック（承認前）

- [ ] **月次マップ**: 各 `##` の「根拠ソース」がマップの表記と一致している
- [ ] **数値・日付**: 学習計画表・MTG 原資料と一致している（**B1〜B4 の得点表記の矛盾を解消**）
- [ ] **マップ外記載なし** / **IB 表記** / **個人情報** / **推敲 3 回** / **配布**

**承認**

| 項目 | 内容 |
|------|------|
| 承認者 | |
| 日付 | |
| コメント | |
