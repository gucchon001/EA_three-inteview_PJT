# Google Drive API連携設計書

## 概要
教師ミーティング・家庭面談の文字起こしファイルをGoogle Driveから自動的に取得し、システムに取り込むためのAPI連携システム。

## 要件

### 機能要件
1. **ファイル検出**: 指定フォルダ内の新規・更新ファイルを検出
2. **メタデータ抽出**: ファイル名から生徒番号・教師番号・面談種別・日付を抽出
3. **コンテンツ取得**: テキストファイルの内容を読み込み
4. **処理状態管理**: 取り込み済み・未処理・エラー状態の管理
5. **エラーハンドリング**: API制限・ネットワークエラーへの対応

### 非機能要件
1. **信頼性**: 99.9%の可用性（Google Drive APIの制限内）
2. **パフォーマンス**: 100ファイル/分の処理能力
3. **セキュリティ**: 最小権限の原則、認証情報の安全な管理
4. **監査**: 操作ログの完全な記録

## システム設計

### アーキテクチャ
```
Google Drive API連携システム
├── Drive Monitor (監視モジュール)
│   ├── Folder Watcher (フォルダ監視)
│   ├── Change Detection (変更検出)
│   └── Webhook Handler (Webhook処理)
├── File Processor (ファイル処理)
│   ├── Parser (パーサー)
│   ├── Validator (バリデータ)
│   └── Transformer (変換器)
├── Data Manager (データ管理)
│   ├── State Manager (状態管理)
│   ├── Queue Manager (キュー管理)
│   └── Retry Manager (再試行管理)
└── Integration Layer (統合層)
    ├── Database Interface (DBインターフェース)
    ├── Notification Service (通知サービス)
    └── Audit Logger (監査ロガー)
```

### データフロー
```
1. 定期監視 or Webhookトリガー
   ↓
2. Google Drive APIでファイル一覧取得
   ↓
3. 命名規則に基づくファイルフィルタリング
   ↓
4. メタデータ抽出（生徒番号、教師番号など）
   ↓
5. ファイル内容のダウンロード
   ↓
6. データ検証・変換
   ↓
7. データベースへの保存
   ↓
8. 処理状態の更新
   ↓
9. 通知（成功/失敗）
```

## 命名規則

### ファイル名フォーマット
```
{生徒番号}_{教師番号}_{面談種別}_{日付}.{拡張子}
```

### 例
```
STU001_TCH003_教師MTG_20260402.txt
STU001_TCH003_保護者面談_20260402.txt
STU001_TCH003_三者面談_20260402.txt
```

### フィールド定義
| フィールド | 形式 | 例 | 説明 |
|-----------|------|-----|------|
| 生徒番号 | 英数字3-10文字 | STU001 | 生徒を一意に識別するコード |
| 教師番号 | 英数字3-10文字 | TCH003 | 教師を一意に識別するコード |
| 面談種別 | 日本語文字列 | 教師MTG, 保護者面談, 三者面談 | 面談の種類 |
| 日付 | YYYYMMDD | 20260402 | 面談実施日 |
| 拡張子 | txt, md, docx | txt | ファイル形式 |

## API設計

### Google Drive API使用スコープ
```javascript
// 必要なスコープ
const SCOPES = [
  'https://www.googleapis.com/auth/drive.readonly', // 読み取り専用
  'https://www.googleapis.com/auth/drive.metadata.readonly' // メタデータ読み取り
];
```

### エンドポイント設計
```javascript
// 疑似REST API設計
GET  /api/drive/folders           // 監視フォルダ一覧
POST /api/drive/folders           // 監視フォルダ追加
GET  /api/drive/files             // ファイル一覧
GET  /api/drive/files/{id}        // ファイル詳細
POST /api/drive/sync              // 手動同期実行
GET  /api/drive/status            // 同期状態
GET  /api/drive/logs              // 操作ログ
```

## 実装詳細

### 認証方式
1. **サービスアカウント** (推奨)
   - サーバー間通信に最適
   - キーファイルによる認証
   - ドメイン全体の委任可能

2. **OAuth 2.0**
   - ユーザー認証が必要な場合
   - リフレッシュトークン管理が必要

### 監視方式
1. **ポーリング方式** (基本)
   ```javascript
   // 定期実行（例: 5分間隔）
   setInterval(async () => {
     await checkForNewFiles();
   }, 5 * 60 * 1000);
   ```

2. **Webhook方式** (推奨)
   ```javascript
   // Google Driveの変更通知をサブスクライブ
   // リアルタイム性が高いが設定が複雑
   ```

3. **ハイブリッド方式**
   - 通常はポーリング
   - 高頻度変更時はWebhook

### ファイル処理パイプライン
```javascript
class FileProcessingPipeline {
  async processFile(fileId) {
    try {
      // 1. メタデータ取得
      const metadata = await this.getFileMetadata(fileId);
      
      // 2. 命名規則検証
      if (!this.validateFilename(metadata.name)) {
        throw new Error('Invalid filename format');
      }
      
      // 3. メタデータ抽出
      const extracted = this.extractMetadata(metadata.name);
      
      // 4. ファイル内容取得
      const content = await this.downloadFile(fileId);
      
      // 5. 内容検証
      if (!this.validateContent(content)) {
        throw new Error('Invalid file content');
      }
      
      // 6. データ変換
      const transformed = this.transformContent(content, extracted);
      
      // 7. データベース保存
      await this.saveToDatabase(transformed);
      
      // 8. 状態更新
      await this.updateProcessingStatus(fileId, 'completed');
      
      return transformed;
      
    } catch (error) {
      // エラーハンドリング
      await this.handleProcessingError(fileId, error);
      throw error;
    }
  }
}
```

## エラーハンドリング

### 想定されるエラー
1. **API制限エラー** (Quota Exceeded)
2. **ネットワークエラー** (Timeout, Connection Error)
3. **認証エラー** (Token Expired, Invalid Credentials)
4. **ファイル形式エラー** (Invalid Format, Encoding Issue)
5. **命名規則エラー** (Invalid Filename Pattern)

### 再試行戦略
```javascript
class RetryStrategy {
  constructor(maxRetries = 3, baseDelay = 1000) {
    this.maxRetries = maxRetries;
    this.baseDelay = baseDelay;
  }
  
  async execute(operation) {
    let lastError;
    
    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error;
        
        // 再試行不可能なエラー
        if (this.isNonRetriableError(error)) {
          break;
        }
        
        // 指数バックオフ
        const delay = this.baseDelay * Math.pow(2, attempt - 1);
        await this.sleep(delay);
      }
    }
    
    throw lastError;
  }
  
  isNonRetriableError(error) {
    // 認証エラー、命名規則エラーなどは再試行しない
    return error.code === 401 || // 認証エラー
           error.code === 403 || // 権限エラー
           error.name === 'ValidationError'; // 検証エラー
  }
}
```

## セキュリティ設計

### 認証情報管理
1. **環境変数**による設定
2. **シークレットマネージャー**の利用（本番環境）
3. **キーファイル**の安全な保管

### アクセス制御
1. **最小権限の原則**: 読み取り専用権限のみ
2. **フォルダ制限**: 特定フォルダのみアクセス可能
3. **IP制限**: 特定IPからのアクセスのみ許可

### データ保護
1. **転送中の暗号化**: HTTPS/TLS必須
2. **保存時の暗号化**: 個人情報の暗号化保存
3. **アクセスログ**: すべてのアクセスを記録

## 監視・運用

### 監視指標
1. **処理件数**: 成功/失敗/スキップ件数
2. **処理時間**: 平均/最大処理時間
3. **API使用量**: クォータ使用率
4. **エラー率**: エラー発生率
5. **キューサイズ**: 未処理ファイル数

### アラート条件
1. **エラー率**が5%を超えた場合
2. **処理遅延**が30分を超えた場合
3. **APIクォータ**が80%を超えた場合
4. **未処理ファイル**が100件を超えた場合

### ログ設計
```javascript
// 構造化ログの例
{
  "timestamp": "2026-04-02T12:00:00Z",
  "level": "INFO",
  "service": "drive-importer",
  "operation": "file_processing",
  "file_id": "1ABC123DEF456",
  "filename": "STU001_TCH003_教師MTG_20260402.txt",
  "student_id": "STU001",
  "teacher_id": "TCH003",
  "meeting_type": "教師MTG",
  "date": "2026-04-02",
  "status": "completed",
  "processing_time_ms": 1234,
  "file_size_bytes": 10240,
  "content_length": 2456
}
```

## 設定例

### 環境変数
```bash
# Google API設定
GOOGLE_DRIVE_FOLDER_IDS=フォルダID1,フォルダID2
GOOGLE_SERVICE_ACCOUNT_KEY=base64エンコードされたキーファイル
GOOGLE_APPLICATION_CREDENTIALS=/path/to/keyfile.json

# アプリケーション設定
FILE_PATTERN='^([A-Z0-9]+)_([A-Z0-9]+)_(.+)_(\\d{8})\\.(txt|md|docx)$'
POLLING_INTERVAL_MINUTES=5
MAX_RETRY_ATTEMPTS=3
BATCH_SIZE=50

# データベース設定
DATABASE_URL=postgresql://user:pass@localhost/dbname
```

### 設定ファイル
```yaml
# config/drive-importer.yaml
google_drive:
  folders:
    - id: "フォルダID1"
      name: "本山さんフォルダ"
      pattern: "*.txt"
    - id: "フォルダID2"
      name: "藤井さんフォルダ"
      pattern: "*.txt,*.md"
  
  polling:
    interval_minutes: 5
    batch_size: 50
  
  retry:
    max_attempts: 3
    backoff_multiplier: 2
    initial_delay_ms: 1000
  
  validation:
    filename_pattern: "^([A-Z0-9]+)_([A-Z0-9]+)_(.+)_(\\d{8})\\.(txt|md|docx)$"
    min_file_size_kb: 1
    max_file_size_mb: 10
    allowed_encodings: ["UTF-8", "Shift_JIS"]
  
  notifications:
    success: false
    failure: true
    channels: ["slack", "email"]
```

## デプロイメント

### コンテナ化
```dockerfile
# Dockerfile
FROM node:18-alpine

WORKDIR /app

# 依存関係インストール
COPY package*.json ./
RUN npm ci --only=production

# アプリケーションコピー
COPY . .

# 非rootユーザー
USER node

# 起動
CMD ["node", "src/server.js"]
```

### Kubernetes設定
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: drive-importer
spec:
  replicas: 2
  selector:
    matchLabels:
      app: drive-importer
  template:
    metadata:
      labels:
        app: drive-importer
    spec:
      containers:
      - name: importer
        image: drive-importer:latest
        env:
        - name: GOOGLE_SERVICE_ACCOUNT_KEY
          valueFrom:
            secretKeyRef:
              name: google-credentials
              key: service-account-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

## テスト戦略

### 単体テスト
1. **パーサーテスト**: 命名規則の解析テスト
2. **バリデーションテスト**: ファイル検証ロジックテスト
3. **エラーハンドリングテスト**: 再試行ロジックテスト

### 統合テスト
1. **Google Drive APIモック**: 実際のAPI呼び出しなしでのテスト
2. **エンドツーエンドテスト**: 完全な処理パイプラインのテスト
3. **負荷テスト**: 大量ファイル処理のテスト

### 受け入れテスト
1. **実際のGoogle Drive環境**: テスト用フォルダでの動作確認
2. **命名規則準拠テスト**: 実際のファイル名でのテスト
3. **エッジケーステスト**: 特殊なファイル形式・サイズでのテスト

## 開発ロードマップ

### Phase 1: 基本機能 (〜2026年4月中旬)
- [ ] Google Drive API連携の基本実装
- [ ] 命名規則パーサーの実装
- [ ] 単純なポーリング方式の実装
- [ ] 基本エラーハンドリング

### Phase 2: 高度な機能 (〜2026年4月下旬)
- [ ] Webhook方式の実装
- [ ] 高度な再試行ロジック
- [ ] バッチ処理の最適化
- [ ] 詳細な監視・ロギング

### Phase 3: 本番対応 (〜2026年5月上旬)
- [ ] セキュリティ強化
- [ ] パフォーマンス最適化
- [ ] 障害復旧機能
- [ ] 本番環境デプロイ

---

*最終更新: 2026年4月2日*  
*バージョン: 1.0*