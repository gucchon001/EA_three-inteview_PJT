# レポートテンプレートエンジン設計書

## 概要
教師ミーティングの文字起こしデータと学習計画表データを入力として、HTML形式のレポートを生成するテンプレートエンジン。AI生成ロジックと連携し、編集ワークフローをサポートする。

## 設計方針
1. **シンプルなテンプレート言語**: 開発者・デザイナー双方が理解しやすい構文
2. **データ駆動**: JSON形式のデータをテンプレートにバインド
3. **拡張性**: 新しいセクション・コンポーネントの追加が容易
4. **パフォーマンス**: 高速なレンダリングとキャッシュ機能

## システム構成

### コンポーネント
```
Template Engine
├── Template Parser (テンプレート解析)
├── Data Binder (データバインディング)
├── Component Renderer (コンポーネントレンダリング)
├── Style Injector (スタイル注入)
└── Output Generator (出力生成)
```

### データフロー
```
1. 入力データ (JSON)
   ├── 生徒情報
   ├── 学習進捗データ
   ├── 教師ミーティング文字起こし
   └── 学習計画表データ

2. テンプレート選択
   ├── パターンA (レスポンシブ)
   ├── パターンB (PDF代替)
   └── パターンC (簡易HTML)

3. レンダリング処理
   ├── 変数置換
   ├── 条件分岐
   ├── ループ処理
   └── コンポーネント展開

4. 出力
   └── HTMLファイル + CSS + JavaScript
```

## テンプレート言語仕様

### 基本構文
```html
<!-- 変数出力 -->
{{ student.name }}
{{ progress.average_score }}

<!-- 条件分岐 -->
{% if progress.score >= 70 %}
  <div class="good">優秀な成績です</div>
{% else %}
  <div class="needs-improvement">さらなる努力が必要です</div>
{% endif %}

<!-- ループ -->
{% for unit in completed_units %}
  <li>{{ unit.name }} (正答率: {{ unit.correct_rate }}%)</li>
{% endfor %}

<!-- コンポーネント -->
{% component "progress_bar" value=75 max=100 label="正答率" %}

<!-- インクルード -->
{% include "section_header" title="学習成果" number=1 %}
```

### データモデル
```json
{
  "report": {
    "id": "RPT-202603-STU001",
    "date": "2026-04-02",
    "period": "2026年3月"
  },
  "student": {
    "id": "STU001",
    "name": "小林 慧",
    "grade": "高校2年"
  },
  "teacher": {
    "id": "TCH003",
    "name": "池田 健太郎"
  },
  "progress": {
    "average_score": 75,
    "previous_score": 60,
    "improvement": 15,
    "completed_units": [
      {"name": "微分法の応用", "correct_rate": 80},
      {"name": "積分法の基礎計算", "correct_rate": 70},
      {"name": "三角関数のグラフと性質", "correct_rate": 75}
    ]
  },
  "analysis": {
    "target_score": 7,
    "current_score": 6,
    "remaining_weeks": 8,
    "required_sessions": 32,
    "completed_sessions": 27,
    "shortage_sessions": 5,
    "bottleneck_units": ["積分法の応用問題"]
  },
  "plans": [
    {
      "id": "plan_a",
      "title": "現状維持",
      "description": "現在の指導頻度を維持し、自学自習の徹底管理で不足分を補います。",
      "price": 0,
      "features": ["週1回・60分授業の継続", "宿題の質と量の最大化", "月1回の進捗確認面談"],
      "risk": "学習の進捗が自己管理能力に強く依存します。",
      "recommended": false
    },
    {
      "id": "plan_b",
      "title": "指導時間の延長",
      "description": "逆算分析で判明した5回分の不足を確実に解消する最適解です。",
      "price": 5000,
      "features": ["週1回・90分授業（30分延長）", "演習量の確保と忘却防止", "Past Paper対策の早期開始", "週次進捗レポート配信"],
      "risk": null,
      "recommended": true
    }
  ],
  "meeting": {
    "available_dates": [
      {"date": "2026-04-10", "time": "18:00", "format": "オンライン（Zoom）"},
      {"date": "2026-04-12", "time": "10:00", "format": "オンライン（Zoom）"},
      {"date": "2026-04-13", "time": "14:00", "format": "対面（弊アカデミー）"}
    ]
  }
}
```

## コンポーネントライブラリ

### 基本コンポーネント
1. **セクションヘッダー**: 番号付きのセクションタイトル
2. **進捗バー**: 数値の視覚化
3. **カード**: 情報のグルーピング
4. **テーブル**: データ表
5. **プランオプション**: A/B/C案の表示
6. **タイムライン**: 時系列データの可視化
7. **認証バナー**: セキュリティ通知

### コンポーネント定義例
```html
<!-- components/progress_bar.html -->
<div class="progress-component">
  <div class="progress-label">
    <span>{{ label }}</span>
    <span>{{ value }}%</span>
  </div>
  <div class="progress-bar">
    <div class="progress-fill" style="width: {{ value }}%"></div>
  </div>
  {% if previous_value %}
    <div class="progress-change">
      前月比: 
      <span class="{% if value > previous_value %}positive{% else %}negative{% endif %}">
        {{ value - previous_value }}%
      </span>
    </div>
  {% endif %}
</div>
```

## 実装アーキテクチャ

### バックエンド (Node.js/Python)
```javascript
// 疑似コード
class TemplateEngine {
  constructor(templateDir, componentDir) {
    this.templateDir = templateDir;
    this.componentDir = componentDir;
    this.cache = new Map();
  }
  
  async render(templateName, data) {
    // 1. テンプレート読み込み
    const template = await this.loadTemplate(templateName);
    
    // 2. コンポーネント解決
    const resolved = await this.resolveComponents(template);
    
    // 3. データバインディング
    const bound = this.bindData(resolved, data);
    
    // 4. レンダリング
    const html = this.generateHTML(bound);
    
    // 5. スタイル注入
    const styled = this.injectStyles(html);
    
    return styled;
  }
  
  // その他のメソッド...
}
```

### フロントエンド (JavaScript)
```javascript
// クライアントサイドレンダリング用
class ClientTemplateEngine {
  constructor() {
    this.components = {};
  }
  
  registerComponent(name, template) {
    this.components[name] = template;
  }
  
  render(template, data) {
    // 軽量なクライアントサイドレンダリング
    // 編集プレビューなどで使用
  }
}
```

## ディレクトリ構造
```
src/reports/template_engine/
├── engine/                    # エンジンコア
│   ├── parser.js
│   ├── binder.js
│   ├── renderer.js
│   └── cache.js
├── templates/                 # テンプレートファイル
│   ├── pattern_a/
│   │   ├── base.html
│   │   ├── sections/
│   │   └── styles.css
│   ├── pattern_b/
│   └── pattern_c/
├── components/                # 再利用コンポーネント
│   ├── progress_bar.html
│   ├── section_header.html
│   ├── plan_card.html
│   └── timeline.html
├── data/                     # データスキーマ・サンプル
│   ├── schema.json
│   └── sample_data.json
└── utils/                    # ユーティリティ
    ├── validation.js
    └── formatters.js
```

## 統合ポイント

### AI生成システム連携
1. **入力**: AIが生成した構造化データ (JSON)
2. **処理**: テンプレートエンジンでHTML化
3. **出力**: 編集可能なHTML + メタデータ

### 編集ワークフロー
1. **初期生成**: AI + テンプレートエンジンで初期レポート作成
2. **編集**: WYSIWYGエディタで修正
3. **再生成**: 編集データをテンプレートエンジンで再レンダリング

### 認証システム連携
1. **レポート生成**: テンプレートエンジンでHTML作成
2. **認証コード埋め込み**: 生成HTMLに認証情報を追加
3. **配信**: 認証付きURLでアクセス可能に

## パフォーマンス最適化

### キャッシュ戦略
1. **テンプレートキャッシュ**: コンパイル済みテンプレートをメモリに保持
2. **コンポーネントキャッシュ**: 頻繁に使用するコンポーネントを事前読み込み
3. **出力キャッシュ**: 同じデータでの再レンダリングを回避

### レンダリング最適化
1. **インクリメンタルレンダリング**: 変更部分のみ再レンダリング
2. **非同期コンポーネント読み込み**: 大規模コンポーネントの遅延読み込み
3. **CSS/JSの最適化**: クリティカルCSSのインライン化

## セキュリティ考慮事項

### 入力検証
1. **XSS対策**: 自動エスケープ処理
2. **インジェクション対策**: テンプレート構文のサニタイズ
3. **データ検証**: 入力データのスキーマ検証

### 出力保護
1. **コンテンツセキュリティポリシー**: CSPヘッダーの自動生成
2. **サニタイズ**: ユーザー入力の適切なエスケープ
3. **認証統合**: 認証コードによるアクセス制御

## 開発ロードマップ

### Phase 1: 基本エンジン (〜2026年4月中旬)
- [ ] テンプレートパーサーの実装
- [ ] データバインディング機能
- [ ] 基本コンポーネントの作成
- [ ] 単体テストの作成

### Phase 2: 高度な機能 (〜2026年4月下旬)
- [ ] 条件分岐・ループ機能
- [ ] コンポーネントシステム
- [ ] キャッシュ機能
- [ ] パフォーマンス最適化

### Phase 3: 統合 (〜2026年5月上旬)
- [ ] AIシステム連携
- [ ] 編集ワークフロー統合
- [ ] 認証システム連携
- [ ] 本番環境デプロイ

## テスト戦略

### 単体テスト
- テンプレートパーサーの正確性
- データバインディングの検証
- コンポーネントレンダリングのテスト

### 統合テスト
- エンドツーエンドのレポート生成
- AIシステムとの連携テスト
- 編集ワークフローのテスト

### パフォーマンステスト
- 大量データでのレンダリング速度
- 同時アクセス対応能力
- メモリ使用量の監視

---

*最終更新: 2026年4月2日*  
*バージョン: 1.0*