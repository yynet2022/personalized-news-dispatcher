# Personalized News Dispatcher

ユーザーがパーソナライズしたキーワードセットに基づき、News サイト（Google News, CiNii, arXiv）から関連ニュースや論文を自動収集し、ユーザーに HTML メールでダイジェストを配信するシステムです。

## 動作環境

*   **Python 3.9 以上**
*   Django 5.x

## 主要機能

1.  **ユーザー認証**
    *   メールアドレスとマジックリンクを用いたパスワードレス認証。
2.  **パーソナライズされた記事収集**
    *   **Google News**: 一般ニュース（国別設定可）
    *   **CiNii Research**: 日本の学術論文
    *   **arXiv**: プレプリント（物理、数学、CS等）
    *   ユーザーは複数の検索条件（QuerySet）を保存可能。
3.  **自動配信**
    *   定期的なバッチ処理により、未読の最新記事のみをメール配信。
4.  **インタラクション**
    *   メール内のリンククリックを追跡し、興味関心を記録（レコメンデーション機能への応用）。

## セットアップ手順

1.  **リポジトリのクローン**
    ```bash
    git clone <repository-url>
    cd personalized-news-dispatcher
    ```

2.  **依存ライブラリのインストール**
    ```bash
    pip install -r requirements.txt
    ```

3.  **データベース構築**

    ```bash

    python manage.py makemigrations

    python manage.py migrate

    ```



4.  **マスタデータの投入**

    ```bash

    python manage.py update_categories data/categories.json          # Google News用カテゴリ

    python manage.py update_cinii_keywords data/cinii_keywords.json  # CiNii用キーワード

    python manage.py update_arxiv_keywords data/arxiv_keywords.json  # arXiv用キーワード

    ```



5.  **環境設定**

    `config/.secrets.toml` を作成し、必要なAPIキーや設定を記述してください（`config/settings.py` 参照）。



6.  **開発サーバーの起動**

    ```bash

    python manage.py runserver

    ```



## 運用（バッチ処理）



記事の収集と配信を行うには、以下のコマンドを定期実行（cron等）します。



```bash

# 記事の収集と通常配信

python manage.py send_articles



# レコメンデーション記事の配信（試験運用中）

python manage.py send_recommendations

```
