# Personalized News Dispatcher システム仕様書

## 1. 概要 (Overview)

**Personalized News Dispatcher** は、ユーザーの関心事に基づいてインターネット上のニュースや学術論文を自動収集し、パーソナライズされたダイジェストメールを配信するエージェントシステムである。
Google News、CiNii Research（日本の学術論文）、arXiv（海外のプレプリント）という異なる性質の情報源を横断的に検索し、ユーザーの優先言語に合わせて自動翻訳を行うことで、言語や情報源の壁を超えた情報収集を支援する。

認証システムにはパスワードレスの「マジックリンク」を採用し、セキュリティとユーザビリティの両立を図っている。

## 2. 技術スタック (Tech Stack)

### 2.1. バックエンド
*   **言語**: Python 3.9 以上
*   **フレームワーク**: Django 5.2 (または 4.2 LTS)
*   **データベース**: SQLite (開発・小規模運用), PostgreSQL/MySQL (推奨)
*   **非同期処理**: Python `asyncio` (外部API呼び出しの並列化に使用)
*   **HTTPクライアント**: `httpx` (非同期対応)
*   **RSS解析**: `feedparser`

### 2.2. AI・翻訳・外部API
*   **Generative AI**:
    *   Google Gemini API (`google-generativeai`) - **優先利用**
    *   OpenAI API (`openai`) - フォールバックとして利用可能
*   **ニュースソース**:
    *   Google News (RSS Feed)
    *   CiNii Research (OpenSearch API)
    *   arXiv (Atom API)

### 2.3. フロントエンド
*   **テンプレートエンジン**: Django Templates (DTL)
*   **CSSフレームワーク**: Bootstrap 5 (推定)

## 3. システムアーキテクチャ

本システムは Django の「MTV (Model-Template-View)」パターンに基づき、以下のアプリケーションで責務を分割している。

| アプリ名 | 役割 | 主な担当機能 |
| :--- | :--- | :--- |
| **config** | プロジェクト設定 | 全体設定 (`settings.py`), ルーティング (`urls.py`), WSGI/ASGI設定 |
| **core** | 共通基盤 | 外部APIラッパー (`google_news_api`, `cinii_api`, `arxiv_api`), 翻訳サービス (`translation.py`), 共通モデル |
| **users** | ユーザー管理 | カスタムUserモデル, マジックリンク認証 (`LoginToken`), 認証ビュー |
| **subscriptions** | 購読管理 | 検索条件 (`QuerySet`), 記事取得ロジック (`fetchers.py`), メール配信サービス (`services.py`), 定期実行コマンド |
| **news** | 記事管理 | 記事データ (`Article`), 配信ログ (`SentArticleLog`), クリック計測 (`ClickLog`) |

## 4. データモデル設計

### 4.1. ユーザー管理 (`users`)

**Model: User**
*   メールアドレスを識別子とするカスタムユーザーモデル。
*   **フィールド**:
    *   `id`: UUID (PK)
    *   `email`: EmailField (Unique, Usernameとして使用)
    *   `preferred_language`: CharField (翻訳ターゲット言語。例: "Japanese")
    *   `is_active`, `is_staff`: 権限フラグ

**Model: LoginToken**
*   マジックリンク認証用の一時トークン。
*   **フィールド**:
    *   `user`: ForeignKey(User)
    *   `token`: CharField (Unique)
    *   `created_at`: DateTimeField

### 4.2. 購読設定 (`subscriptions`)

**Model: QuerySet**
*   ユーザーが設定する検索条件のセット。
*   **フィールド**:
    *   `user`: ForeignKey(User)
    *   `name`: CharField (セット名)
    *   `source`: CharField (google_news / cinii / arxiv)
    *   `auto_send`: BooleanField (自動配信のON/OFF)
    *   `query_str`: TextField (自動生成される検索クエリ)
    *   **ソース固有設定**:
        *   `large_category` (Google News用カテゴリ)
        *   `country` (Google News用対象国)
        *   `cinii_keywords` (M2M)
        *   `arxiv_keywords` (M2M)
    *   **フィルタ設定**:
        *   `additional_or_keywords`: OR検索用キーワード
        *   `refinement_keywords`: 絞り込み/除外キーワード
        *   `after_days`: 取得対象期間（過去N日）
        *   `max_articles`: 1回あたりの最大取得数

**Master Models (Keywords)**
*   `LargeCategory`, `UniversalKeywords`, `CurrentKeywords`, `RelatedKeywords`, `CiNiiKeywords`, `ArXivKeywords`
*   ユーザーが選択可能なキーワードのマスターデータ。正規化処理 (`NormalizeNameMixin`) を持つ。

### 4.3. 記事・ログ管理 (`news`)

**Model: Article**
*   取得した記事の実体。URLで一意性を担保する。
*   **フィールド**:
    *   `id`: UUID (PK)
    *   `url`: URLField (Unique)
    *   `title`: CharField
    *   `published_date`: DateTimeField

**Model: SentArticleLog**
*   「誰に」「どの記事を」送ったかの履歴。重複送信防止に使用される。
*   **フィールド**:
    *   `user`: ForeignKey(User)
    *   `article`: ForeignKey(Article)
    *   `sent_at`: DateTimeField
*   **制約**: `(user, article)` でユニーク。

**Model: ClickLog**
*   メール内のリンククリック計測用。
*   **フィールド**:
    *   `user`, `article`, `clicked_at`

## 5. 機能仕様詳細

### 5.1. 認証機能 (Magic Link)
1.  **ログイン申請**: ユーザーはメールアドレスのみを入力。
2.  **トークン生成**: システムは `LoginToken` を生成し、認証用URLを含むメールを送信。
3.  **検証**: ユーザーがURLをクリックすると、トークンの有効性を検証し、セッションを確立。トークンは使用後に削除または無効化される。

### 5.2. 記事収集ロジック (`subscriptions.fetchers`)
Strategy Pattern を採用し、ソースごとに `ArticleFetcher` の具象クラスを実装している。

*   **共通フロー**:
    1.  `QuerySet` から検索クエリ文字 (`query_str`) とフィルタ条件 (`after_days` 等) を取得。
    2.  `SentArticleLog` を参照し、既に送信済みの記事URLリストを取得（除外用）。
    3.  各API/フィードからデータを取得。
    4.  **タイトル翻訳 (Optional)**: `asyncio` を用いて、記事タイトルのリストをバッチ翻訳する。
    5.  `Article` モデルとしてDBに保存（重複時は既存レコードを取得）。
    6.  未送信の記事リストを返す。

*   **GoogleNewsFetcher**:
    *   `rss/search` エンドポイントを使用。
    *   `feedparser` で解析。
    *   検索クエリに `after:YYYY-MM-DD` を付与して期間フィルタリング。
*   **CiNiiFetcher**:
    *   `opensearch/v2/articles` APIを使用。
    *   `appid` (API Key) が必要。
*   **ArXivFetcher**:
    *   `export.arxiv.org/api/query` APIを使用。
    *   `atom` 形式のレスポンスを `feedparser` で解析。

### 5.3. 自動翻訳機能 (`core.translation`)
ユーザーの「優先言語」設定に基づき、コンテンツを翻訳する。

*   **優先順位**: Gemini API が利用可能な場合は Gemini を優先し、不可の場合は OpenAI API を使用する。
*   **並列処理**: 多数の記事タイトルを翻訳する際は、リスト形式のJSONプロンプトを生成し、一括翻訳することでAPIコール数を削減・高速化している。
*   **HTML対応**: メール本文などのHTMLコンテンツの翻訳時は、HTMLタグ構造を維持しつつ、テキスト部分のみを翻訳するようプロンプトで指示する。

### 5.4. メール配信
*   **自動配信**: 管理コマンド `send_articles` を定期実行（cron等）することで実現。
    *   `users` アプリの `active` なユーザーかつ `auto_send=True` の `QuerySet` を対象とする。
*   **手動配信**: Web UI上から即時配信をトリガー可能。
*   **フォーマット**: HTMLメールとプレーンテキストのマルチパート配信。

## 6. 外部インターフェース仕様

### 6.1. Google News RSS
*   Endpoint: `https://news.google.com/rss/search`
*   Params: `q={query}`, `hl={lang}`, `gl={country}`, `ceid={country}:{lang}`

### 6.2. CiNii Research OpenSearch API
*   Endpoint: `https://cir.nii.ac.jp/opensearch/v2/articles`
*   Params: `q={keyword}`, `count={num}`, `appid={ID}`, `format=json`

### 6.3. arXiv API
*   Endpoint: `https://export.arxiv.org/api/query`
*   Params: `search_query={query}`, `start={start}`, `max_results={num}`, `sortBy=submittedDate`, `sortOrder=descending`

## 7. ディレクトリ構成

```text
project_root/
├── config/                  # プロジェクト設定
│   ├── settings.py          # 設定ファイル (.secrets.toml読み込み)
│   └── urls.py              # URLルーティング
├── core/                    # コア機能
│   ├── google_news_api.py   # Google News RSS取得
│   ├── cinii_api.py         # CiNii API連携
│   ├── arxiv_api.py         # arXiv API連携
│   ├── translation.py       # AI翻訳ロジック (Gemini/OpenAI)
│   └── services.py          # 共通サービス関数
├── news/                    # 記事データ管理
│   └── models.py            # Article, SentArticleLog
├── subscriptions/           # 購読管理
│   ├── fetchers.py          # 記事取得ロジック (Fetcher Pattern)
│   ├── services.py          # メール生成・送信ロジック
│   ├── models.py            # QuerySet, Keyword Masters
│   └── management/commands/ # 管理コマンド
│       └── send_articles.py # 定期配信用バッチ
├── users/                   # ユーザー認証
│   └── models.py            # CustomUser, LoginToken
└── templates/               # HTMLテンプレート
```

## 8. 運用・デプロイ

### 8.1. 必須環境変数 / Secrets
`.secrets.toml` ファイルにて以下のキーを管理する。

*   `SECRET_KEY`: Django Secret Key
*   `GEMINI_API_KEY`: Google Gemini API Key (翻訳用)
*   `OPENAI_API_KEY`: OpenAI API Key (翻訳用・フォールバック)
*   `CINII_APP_ID`: CiNii API Application ID

### 8.2. 定期タスク (Cron)
自動配信を有効にするには、以下のコマンドを定期的に（例：毎朝8時、または数時間おきに）実行する設定が必要。

```bash
python manage.py send_articles --interval 5
```

### 8.3. 開発コマンド
*   **開発サーバー起動**: `python manage.py runserver`
*   **記事収集テスト (Dry Run)**: `python manage.py send_articles --dry-run`
*   **翻訳機能テスト**: `python manage.py test_translation` (coreアプリ内に存在する場合)
