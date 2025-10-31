"""
subscriptions アプリケーションのためのビジネスロジックをまとめたサービスモジュール。

このモジュールは、ニュース記事の取得、メール送信、送信ログの記録など、
コマンドやビューから共通して利用される機能を提供します。
"""
import feedparser
import requests
from urllib.parse import quote
from datetime import datetime, timezone, timedelta

from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.db import transaction

from users.models import User
from news.models import Article, SentArticleLog
from subscriptions.models import QuerySet


def get_published_date_from_entry(entry):
    """
    feedparserのentryからタイムゾーン付きのdatetimeオブジェクトを取得する。
    published_parsedがなければNoneを返す。
    """
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        dt_naive = datetime(*entry.published_parsed[:6])
        return dt_naive.replace(tzinfo=timezone.utc)
    return None


def fetch_rss_feed(query: str, timeout: int = 10):
    """
    指定されたクエリでGoogle NewsからRSSフィードを取得し、解析する。

    Args:
        query (str): 検索クエリ文字列。
        timeout (int): リクエストのタイムアウト秒数。

    Returns:
        feedparser.FeedParserDict or None: 解析されたフィードオブジェクト。
                                            取得に失敗した場合はNoneを返す。
    """
    encoded_query = quote(query)
    base_url = (f"https://news.google.com/rss/search?"
                f"q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja")

    try:
        response = requests.get(base_url, timeout=timeout)
        response.raise_for_status()
        return feedparser.parse(response.content)
    except requests.exceptions.RequestException:
        return None


def _build_query_with_date(query_str: str, after_days: int) -> str:
    """
    クエリ文字列に日付フィルターを追加する。
    """
    if after_days > 0:
        limit_date = datetime.now() - timedelta(days=after_days)
        after_date_str = limit_date.strftime('%Y-%m-%d')
        return f"{query_str} after:{after_date_str}"
    return query_str


def _process_feed_entries(entries, after_days: int, max_articles: int, user: User = None, persist: bool = False):
    """
    フィードエントリーを処理してArticleオブジェクトのリストを生成する内部関数。

    Args:
        entries (list): feedparserのエントリーリスト。
        after_days (int): 何日前までの記事を取得するか。
        max_articles (int): 取得する記事の最大数。
        user (User, optional): 送信済みか確認するためのユーザー。Noneならチェックしない。
        persist (bool): Trueの場合、ArticleをDBに保存する。

    Returns:
        list[Article]: Articleオブジェクトのリスト。
    """
    articles = []
    for entry in entries:
        if len(articles) >= max_articles:
            break

        published_date = get_published_date_from_entry(entry)

        if after_days > 0 and published_date:
            threshold_date = datetime.now(timezone.utc) - timedelta(days=after_days)
            if published_date < threshold_date:
                continue

        article_instance = None
        if persist:
            article_instance, _ = Article.objects.get_or_create(
                url=entry.link,
                defaults={
                    'title': entry.title,
                    'published_date': published_date
                }
            )
        else:
            # DB検索またはインスタンス作成のみ
            article_instance = Article.objects.filter(url=entry.link).first()
            if not article_instance:
                article_instance = Article(
                    url=entry.link,
                    title=entry.title,
                    published_date=published_date
                )
        
        # ユーザーが指定されていて、かつ送信済みでない場合のみ追加
        if user and SentArticleLog.objects.filter(user=user, article=article_instance).exists():
            continue

        articles.append(article_instance)
            
    return articles


def fetch_articles_for_preview(query_str: str, after_days: int, max_articles: int):
    """
    プレビュー用に新しいニュース記事を取得する。DBへの保存は行わない。

    Args:
        query_str (str): 検索クエリ文字列。
        after_days (int): 何日前までの記事を取得するかの日数。
        max_articles (int): 取得する記事の最大数。

    Returns:
        tuple[str, list[Article]]: 実際に使用したクエリ文字列と、Articleオブジェクトのリスト。
    """
    query_with_date = _build_query_with_date(query_str, after_days)

    feed = fetch_rss_feed(query_with_date, timeout=5)
    if not feed:
        return query_with_date, []

    articles = _process_feed_entries(
        entries=feed.entries, 
        after_days=after_days, 
        max_articles=max_articles, 
        persist=False
    )
    return query_with_date, articles


def fetch_articles_for_queryset(queryset: QuerySet, user: User, after_days_override: int = None, dry_run: bool = False):
    """
    一つのQuerySetから新しいニュース記事を取得する。

    Args:
        queryset (QuerySet): ニュースを取得するためのQuerySetオブジェクト。
        user (User): 記事が既に送信されたかを判断するためのUserオブジェクト。
        after_days_override (int, optional): querysetの設定を上書きする日数。デフォルトはNone。
        dry_run (bool): Trueの場合、DBへの書き込みは行わない。

    Returns:
        tuple[str, list[Article]]: 実際に使用したクエリ文字列と、見つかったArticleオブジェクトのリスト。
    """
    after_days = after_days_override if after_days_override is not None else queryset.after_days

    query_with_date = _build_query_with_date(queryset.query_str, after_days)

    feed = fetch_rss_feed(query_with_date)
    if not feed:
        return query_with_date, []

    articles = _process_feed_entries(
        entries=feed.entries,
        after_days=after_days,
        max_articles=queryset.max_articles,
        user=user,
        persist=(not dry_run)
    )
    return query_with_date, articles


def send_digest_email(user: User, querysets_with_articles: list):
    """
    ニュースダイジェストメールを送信する。
    
    Args:
        user (User): 送信先のユーザー。
        querysets_with_articles (list): クエリセット名と記事リストの辞書のリスト。
    """
    current_site = Site.objects.get_current()
    site_url = f'http://{current_site.domain}'

    # トラッキングURLを記事オブジェクトに付与
    for item in querysets_with_articles:
        for article in item['articles']:
            tracking_path = reverse('news:track_click', kwargs={'pk': article.pk})
            article.tracking_url = site_url + tracking_path

    context = {
        'user': user,
        'querysets_with_articles': querysets_with_articles,
        'site_url': site_url,
    }

    plain_body = render_to_string('news/email/news_digest_email.txt', context)
    html_body = render_to_string('news/email/news_digest_email.html', context)

    send_mail(
        subject='【News Dispatcher】今日のニュースダイジェスト',
        message=plain_body,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        fail_silently=False,
        html_message=html_body,
    )


@transaction.atomic
def log_sent_articles(user: User, articles: list):
    """
    送信済み記事をDBに記録する。
    
    Args:
        user (User): 送信先のユーザー。
        articles (list[Article]): 送信したArticleオブジェクトのリスト。
    """
    for article in set(articles):
        # 冪等性を確保するためにget_or_createを使用
        SentArticleLog.objects.get_or_create(user=user, article=article)
