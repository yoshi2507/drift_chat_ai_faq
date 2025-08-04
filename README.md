# PIP-Maker チャットボット

PIP-Makerの問い合わせ対応を自動化する高度なチャットボットシステムです。

## 🌟 主な機能

- **高精度検索**: ファジーマッチングによる柔軟な質問回答
- **リアルタイム通知**: Slack連携による問い合わせ監視
- **フィードバック機能**: ユーザー満足度の収集・分析
- **統一エラーハンドリング**: 適切なエラーメッセージとログ管理
- **レスポンシブUI**: モバイル対応のモダンなインターフェース

## 🚀 クイックスタート

### 前提条件

- Python 3.11以上
- pip

### インストール

1. **リポジトリのクローン**
```bash
git clone <repository-url>
cd pip-maker-chatbot
```

2. **仮想環境の作成**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. **依存関係のインストール**
```bash
pip install -r requirements.txt
```

4. **環境変数の設定**
```bash
cp .env.example .env
# .envファイルを編集して必要な設定を行う
```

5. **アプリケーションの起動**
```bash
uvicorn src.app:app --reload
```

6. **ブラウザでアクセス**
```
http://localhost:8000
```

## 🔧 開発環境

### 開発用依存関係のインストール
```bash
pip install -r requirements-dev.txt
```

### テストの実行
```bash
pytest tests/
```

### コードフォーマット
```bash
black .
flake8 .
mypy .
```

### Dockerを使用した起動
```bash
docker-compose up --build
```

## 📁 プロジェクト構造

```
├── src/
│   ├── static/
│   │   ├── script.js      # フロントエンドJavaScript
│   │   └── style.css      # スタイルシート
│   ├── app.py             # メインアプリケーション
│   └── qa_data.csv        # Q&Aデータ
├── tests/
│   └── test_app.py        # テストケース
├── config.py              # 設定管理
├── index.html             # フロントエンドHTML
├── requirements.txt       # 本番用依存関係
├── requirements-dev.txt   # 開発用依存関係
├── Dockerfile             # Docker設定
├── docker-compose.yml     # Docker Compose設定
└── .env.example           # 環境変数テンプレート
```

## 🔌 API エンドポイント

### 検索API
```http
POST /api/search
Content-Type: application/json

{
  "question": "PIP-Makerとは何ですか？",
  "category": "general"  // オプション
}
```

### フィードバックAPI
```http
POST /api/feedback
Content-Type: application/json

{
  "conversation_id": "unique-id",
  "rating": "positive",  // "positive" | "negative"
  "comment": "役に立ちました"  // オプション
}
```

### ヘルスチェック
```http
GET /health
```

## ⚙️ 設定

### 環境変数

| 変数名 | 説明 | デフォルト値 |
|--------|------|-------------|
| `CSV_FILE_PATH` | Q&AデータのCSVファイルパス | `qa_data.csv` |
| `SLACK_WEBHOOK_URL` | Slack通知用WebhookURL | なし |
| `SEARCH_SIMILARITY_THRESHOLD` | 検索の類似度閾値 | `0.1` |
| `RATE_LIMIT_PER_MINUTE` | レート制限（分間リクエスト数） | `10` |
| `LOG_LEVEL` | ログレベル | `INFO` |

### CSVデータ形式

```csv
質問,回答,対応カテゴリー,根拠資料,備考
"PIP-Makerとは何ですか？","PIP-Makerは...","general","公式サイト",""
```

## 🔒 セキュリティ

- レート制限による不正利用防止
- 入力値バリデーション
- エラー情報の適切な制御
- CORS設定（本番環境では要設定）

## 📊 監視・ログ

- 構造化ログ出力
- Slack通知連携
- エラートラッキング
- パフォーマンス監視

## 🚧 今後の開発予定

### Phase 2（中期）
- AI/LLM統合（OpenAI GPT-4）
- ベクトル検索（ChromaDB）
- Google Sheets連携
- 高度なUX改善

### Phase 3（長期）
- リアルタイム分析ダッシュボード
- 多言語対応
- CRM連携
- 自動学習機能

## 🤝 コントリビューション

1. フォークしてブランチを作成
2. 変更を実装
3. テストを追加・実行
4. プルリクエストを作成

## 📄 ライセンス

このプロジェクトは [MIT License](LICENSE) の下で公開されています。

## 🆘 サポート

問題や質問がある場合は、[Issues](../../issues) でお知らせください。

---

**PIP-Maker開発チーム**