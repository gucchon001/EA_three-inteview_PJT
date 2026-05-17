from __future__ import annotations

from pathlib import Path

Message = dict[str, str]

PROMPT_FRAGMENT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "monthly"


def _read_monthly_prompt_fragment(name: str) -> str:
    return (PROMPT_FRAGMENT_DIR / name).read_text(encoding="utf-8").strip()


def build_monthly_report_messages(
    *,
    artifact: str,
    template_path: Path,
    bundle: str,
    ideal_plain: str,
    structure_html: str,
    rules_excerpt_path: Path | None = None,
    prompt_scope_notes: str | None = None,
) -> list[Message]:
    template_text = template_path.read_text(encoding="utf-8", errors="replace")
    canonical_system = _read_monthly_prompt_fragment("report_system.md")
    canonical_tone = _read_monthly_prompt_fragment("tone_family_facing.md")
    validation_repair = _read_monthly_prompt_fragment("validation_repair.md")
    tone = ""
    if rules_excerpt_path and rules_excerpt_path.is_file():
        tone = "\n--- family-facing-tone.md（抜粋） ---\n" + rules_excerpt_path.read_text(
            encoding="utf-8", errors="replace"
        )

    if artifact == "html":
        artifact_guidance = _read_monthly_prompt_fragment("artifact_html.md")
        system_parts: list[str] = [
            canonical_system,
            canonical_tone,
            artifact_guidance,
            validation_repair,
            "あなたは塾の担当教師側のライターです。根拠ソースに無い事実・数値・評価は書かない。",
            "**同一 MTG に複数生徒または複数教科が混在**しても、テンプレ（コンテンツ契約）に定めるとおり対象生徒・主題教科に関係しない文は事実として採らないこと。",
            "出力は**完全な1ファイルの UTF-8 HTML**（Markdown 禁止）。ブラウザでそのまま表示できる単一ページ。",
            "構造レイアウト（必須）：`structure-html` の **DOM 順・sec-num 01〜05・各 h2 見出し文言・class 名** を最大限コピーする。参考に無いトップレベルセクション（例: 「学習の進捗」専用の節・sec-num 06/07）を**新設しない**。",
            "**05 の h2 は参考 HTML と同じく「今後の授業計画」** とする。DATA_CONTRACT_05 風のトピック一覧 plan-table（Number and Algebra / Functions … の長大表）や、それを主とする独立セクションは**出さない**（テンプレ／参考に明示がある場合を除く）。",
            "**03 授業内容の表（重要）**：学習単元列は参考 `structure-html` の **HTML 形を優先**する。"
            "`<span class=\"unit-main\">` や `<div class=\"unit-subtopics\">`、日本語ラベル（例: 「微分の基礎・連鎖律」）による要約行は**使わない**。",
            "03 の行内容は根拠ソースの lesson plan に合わせつつ、**見た目は参考の 3 行パターン**に揃える："
            "（1）4/02 は **1 行**で `Probability — Unit test 2` に相当する短い表記（`Statistics & Probability` で始める長文タイトルは避ける）。"
            "（2）4/13・4/30 は **`Calculus` を第1行**とし、サブ話題は **`&lt;br&gt;&lt;span style=\"font-size: 12.6667px;\"&gt;` … `&lt;/span&gt;`** の **1 ブロック**に **スラッシュ `/` 区切り**で列挙（参考 HTML と同型）。**`/` の前後にスペースを入れない**（`Limits/The gradient/...` のように詰める）。"
            "（3）4/30 行は参考どおり **`&lt;span style=\"background-color: rgb(245, 247, 250);\"&gt;` でセル全体を包んでもよい**。"
            "（4）**別途 `div` や二段目の `unit-subtopics` で注釈を増やさない**。学校テストの補足が必要でも **括弧短句1つ**に収めるか省略。",
            "構造・CSS：style ブロックは参考 HTML と同等（同一 class セレクタ）を目指す。",
            "コンテンツ契約（Markdown ファイル）どおりに節構成・項目を書く。その内容は根拠ソースからのみ。",
            "**ideal のプレーンテキストは語感・文長のみ**に利用し、理想側の文言を根拠なしで事実として転記しないこと。",
            "第三者調査調の語（「記載があります」連発など）は禁止。",
            "「担当CA」「教師 MTG」「Gemini メモ」「NotebookLM」を配布文言に書かず、担当者は「担当」。",
            "先頭コメントには `monthly-report-revision:` を1行だけ含め、モデル・日付などを簡潔に。",
            tone.strip(),
        ]
        instruct = (
            artifact_guidance
            + "\n"
            "上記ソースのみを根拠に、Pattern B の**HTML 全体**を一括出力する。\n"
            "- **03 授業内容**：`data-table` の学習単元 `<td>` は **参考 HTML と同じマークアップ型**にする。"
            " **禁止**: `class=\"unit-main\"` / `class=\"unit-subtopics\"` / 任意の `<div class=\"unit-subtopics\">`。"
            " **必須**: 4/02 は **プレーンテキスト1セル**で `Probability — Unit test 2` 型（em dash `—`）。"
            " 4/13・4/30 は `Calculus` + `br` + `span style=\"font-size: 12.6667px;\"` 内に英語トピックを **`/` で連結**（**スラッシュ前後に空白を入れない**。例 `The chain rule/The product rule`）。"
            " 4/30 は参考通り `rgb(245, 247, 250)` の外側 `span` 使用可。\n"
            "- **03 直下の理解度★の目安**はテンプレ指定の原文どおり。`<b>` / `<span style=\"font-size: 9pt;\">` の入れ方は参考 HTML に合わせる。\n"
            "- **02** の mood 表は進捗・意欲・宿題の 3 行。\n"
            "コードフェンスや説明文は出力しない。"
        )
    else:
        artifact_guidance = _read_monthly_prompt_fragment("artifact_markdown.md")
        system_parts = [
            canonical_system,
            canonical_tone,
            artifact_guidance,
            validation_repair,
            "あなたは塾の担当教師側のライターです。入力はすべて「根拠ソース」であり、ソースに無いことは創作しない。",
            "**同一 MTG に複数生徒または複数教科が混在**しても、テンプレ（コンテンツ契約）に定めるとおり対象外の文は採用しない。",
            "出力は「月次 Pattern B」の正本 Markdown 案。フロントマター（YAML）から始める。",
            "文体・禁止語・セクション構成は、渡されたコンテンツ契約ファイルに完全準拠する。",
            "第三者調査調の語（「記載があります」「挙がっております」「推奨されております」だけの連続など）は禁止。",
            "【出力絶対禁止語】以下の文字列はソース・テンプレートのどこに出現していても出力に1文字も書いてはならない: 「担当CA」「教師 MTG」「教師MTG」「Gemini メモ」「NotebookLM」。"
            "担当者の呼称は「担当」または「講師」を使う。違反があれば採用されない。",
            "【テンプレート注記の転記禁止】コンテンツ契約（テンプレート）の括弧書きコメント（「こう書かない」「禁止」「可」「配布 HTML の表では〜」「社内のみ〜」等の注記）は構造のガイドラインとして読むだけで出力に転記してはならない。"
            "特に表のセル内にある指示文（例：「担当CA という語は配布しない」など）は家庭向け本文に出さないこと。",
            tone.strip(),
        ]
        instruct = (
            artifact_guidance
            + "\n"
            "上記ソースのみを根拠に、`monthly_pattern_b_content.template.md` の構成に沿った"
            " 月次レポート Markdown を一括出力。**03 直下の★の目安5行など、テンプレで原文指定のブロックは改変しない**。"
        )

    system = "\n".join([part for part in system_parts if part])
    user_chunks: list[str] = [
        "## コンテンツ契約（レイアウト・禁止事項の正本）\n\n" + template_text + "\n\n---\n",
    ]
    scope = (prompt_scope_notes or "").strip()
    if scope:
        user_chunks.append(
            "## 対象レポートのスコープ（本生成で必読）\n\n" + scope + "\n\n---\n",
        )
    user_chunks.append("## 根拠ソース\n\n" + bundle + "\n\n---\n")
    if structure_html.strip():
        user_chunks.append(
            "## 構造レイアウト参考（HTML 抜粋・class / セクション順を踏襲）\n\n```html\n"
            + structure_html
            + "\n```\n\n---\n"
        )
    if ideal_plain.strip():
        user_chunks.append(
            "## 語感・文長の参考（プレーンテキスト。**事実として採用禁止**）\n\n"
            + ideal_plain
            + "\n\n---\n"
        )
    user_chunks.append("## 指示\n\n" + instruct)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_chunks)},
    ]
