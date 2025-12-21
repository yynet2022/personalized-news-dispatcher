# Personalized News Dispatcher

ユーザーが定義した検索条件（QuerySet）に基づいて、複数の情報ソース（Google News, CiNii, arXiv）から関連ニュースや論文を自動収集し、HTMLメールでダイジェスト配信するシステムです。

## プロジェクト構成

本プロジェクトは Django (5.x) を用いて構築されています。

### アプリケーション構成

*   `core`: 全体共通のテンプレート、外部API連携モジュール (`arxiv_api.py`, `cinii_api.py`)、翻訳機能などを提供します。
*   `users`: ユーザー管理機能。メールアドレスとマジックリンクを用いたパスワードレス認証を提供します。
*   `subscriptions`: 検索条件 (QuerySet) の管理と、ニュース収集のビジネスロジック (`fetchers.py` 等を利用) を担います。
*   `news`: 収集した記事データ、配信ログ、クリックログを管理します。

### ディレクトリ構成

```
.
├── config/          # Django プロジェクト設定 (.secrets.toml で機密情報を管理)
├── core/            # 共通機能 (APIクライアント, 翻訳, 基底テンプレート)
├── data/            # マスタデータの初期値 (JSON形式)
├── log/             # アプリケーションログ
├── news/            # 記事データ・ログ管理
├── subscriptions/   # 購読設定・記事収集・配信ロジック
├── users/           # ユーザー認証・設定
├── manage.py        # Django 管理コマンド
└── uwsgi.ini        # 本番運用用 uWSGI 設定
```

## 主要機能

### 1. ユーザー認証とセキュリティ
*   **パスワードレス認証**: メールアドレスを入力し、届いた一時的なリンクをクリックするだけでログインできます。
*   **セキュリティ対策**:
    *   **レート制限**: ログイン試行回数を制限し、ブルートフォース攻撃やメール爆撃を防止（IPベース）。
    *   **オープンリダイレクト対策**: ログイン後のリダイレクト先を厳密に検証。
    *   **セキュアな設定**: 本番環境 (`DEBUG=False`) では `SECRET_KEY` の安全性を強制チェック。

### 2. 検索条件 (QuerySet) の管理
ユーザーは「QuerySet」として複数の収集条件を保存できます。

*   **対応ソース**:
    *   **Google News**: 一般的なニュース記事。国別（JP, US, etc.）の設定が可能。
    *   **CiNii Research**: 日本の学術論文。
    *   **arXiv**: プレプリント（物理学、数学、CS等）。
*   **検索パラメータ**:
    *   ソースごとの専用キーワード（大分類、普遍キーワードなど）
    *   `additional_or_keywords`: 自由入力のOR条件キーワード。
    *   `refinement_keywords`: 絞り込み条件（AND / NOT検索）。
    *   取得期間（過去何日分か）や最大取得件数の設定。

### 3. 記事収集と配信 (バッチ処理)
以下の管理コマンドを cron 等で定期実行することで機能します。

*   `python manage.py send_articles`:
    *   全ユーザーの QuerySet を元に、各ソースから最新記事を収集。
    *   `SentArticleLog` を確認し、**未配信の記事のみ**を抽出してメール配信。
    *   重複配信の防止と、APIリクエストの最適化が行われています。

### 4. レコメンデーション
*   `python manage.py send_recommendations`:
    *   ユーザーの過去のクリック履歴 (`ClickLog`) などを分析し、おすすめの記事を配信する機能（開発中/試験運用中）。

### 5. クリック追跡
*   配信メール内のリンクは追跡用URLに変換されており、ユーザーがどの記事に興味を持ったか（クリックしたか）を記録します。

## データベースモデル概要

*   **Users**: `User`, `LoginToken` (認証用)
*   **Subscriptions**:
    *   `QuerySet`: ユーザーごとの検索設定。ソース種別 (`source`) により、参照するキーワードテーブルが変わります。
    *   `LargeCategory`, `UniversalKeywords`, `CurrentKeywords`, `CiNiiKeywords`, `ArXivKeywords`: 各種マスタデータ。
*   **News**:
    *   `Article`: 記事本体。URLを一意のキーとして管理。
    *   `SentArticleLog`: 配信履歴。
    *   `ClickLog`: ユーザーの行動履歴。

## 開発・運用ガイド

### 依存パッケージ
`requirements.txt` を参照。主要なものは以下の通り。
*   `Django`: Webフレームワーク
*   `httpx`: 高速なHTTPクライアント (非同期対応)
*   `feedparser`: RSS/Atomフィードの解析
*   `tomli`: 設定ファイル (.secrets.toml) の読み込み

### 初期セットアップ
1.  依存ライブラリのインストール: `pip install -r requirements.txt`
2.  データベース構築: `python manage.py migrate`
3.  マスタデータの投入:
    *   `python manage.py update_categories` (Google News用)
    *   `python manage.py update_cinii_keywords`
    *   `python manage.py update_arxiv_keywords`
4.  設定ファイル: `config/.secrets.toml` を作成し、APIキー等を設定（`settings.py` 参照）。
