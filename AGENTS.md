# Personalized News Dispatcher

これは、ユーザーがパーソナライズしたキーワードセットに基づき、News サイトから関連ニュースを自動収集し、ユーザーに HTML メールでダイジェストを配信するシステムです。

## プロジェクト構成

本プロジェクトは Django を用いて構築されており、主要なアプリケーションは以下の通りです。

*   `core`: プロジェクトの基本的な設定や、全アプリケーションで共通して利用されるテンプレート (`base.html`) を提供します。
*   `users`: ユーザー管理を担います。メールアドレスを用いたパスワードレス認証機能を有します。
*   `subscriptions`: ユーザーが購読するニュースのキーワードセット (QuerySet) の管理を行います。ビジネスロジックの多くは `services.py` に実装されています。
*   `news`: 収集したニュース記事、配信ログ、クリックログの管理を行います。

### ディレクトリ構成

```
.
├── config/          # Django プロジェクト設定
├── core/            # 基本的なテンプレート等
├── data/            # 初期データ (カテゴリ情報)
├── log/             # ログファイル
├── news/            # ニュース記事関連
├── subscriptions/   # 購読設定関連 (ビジネスロジックは services.py)
├── users/           # ユーザー認証関連
├── manage.py        # Django 管理コマンド
├── requirements.txt # Python 依存パッケージ
├── Makefile         # 各種コマンドのエイリアス
└── uwsgi.ini        # uWSGI 設定ファイル
```

## 主要機能

*   **ユーザー認証**: メールアドレスとワンタイムトークンを用いたパスワードレス認証を提供します。
*   **QuerySet**: ユーザーはニュース収集の条件を「QuerySet」として複数登録できます。QuerySet は以下の要素から構成されます。
    *   大分類 (例: 経済, IT)
    *   普遍キーワード (例: 金融政策, ソフトウェア)
    *   時事キーワード (例: 日銀会合, WWDC)
    *   関連キーワード
    *   追加のOR検索キーワード (`additional_or_keywords`)
    *   絞り込みキーワード (`refinement_keywords`)
*   **ニュース収集**: 定期実行される `send_daily_news.py` 管理コマンドが、各ユーザーの QuerySet を `subscriptions/services.py` のビジネスロジックに渡します。ロジック内では、QuerySet の各キーワードを組み合わせて検索クエリ (`query_str`) を生成し、Google News の RSS フィードからニュースを収集します。記事の URL をキーに `get_or_create` を用いることで、データベースへの重複登録を防ぎます。
*   **メール配信**: 収集したニュースの中から、`SentArticleLog` を参照して未送信の記事のみを抽出し、HTML 形式のダイジェストメールをユーザーに配信します。
*   **クリック追跡**: メール内のニュースリンクには追跡用の URL が付与され、ユーザーのクリックを記録します。

## データベースモデル

*   `users.User`: ユーザー情報を格納します。
*   `users.LoginToken`: パスワードレス認証用のワンタイムトークンを格納します。
*   `subscriptions.LargeCategory`, `UniversalKeywords`, `CurrentKeywords`, `RelatedKeywords`: ニュースの分類カテゴリを定義します。
*   `subscriptions.QuerySet`: ユーザーが作成したニュース収集条件のセットです。ユーザーが任意に設定するキーワードは、このモデルの `additional_or_keywords` や `refinement_keywords` フィールドに直接格納されます。
*   `news.Article`: 収集したニュース記事の情報を格納します。URL には unique 制約があり、重複を防ぎます。
*   `news.SentArticleLog`: どの記事をどのユーザーに配信したかを記録します。
*   `news.ClickLog`: ユーザーの記事クリックを記録します。