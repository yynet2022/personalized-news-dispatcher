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


def fetch_articles_for_queryset(queryset: QuerySet, user: User, after_days: int = 2, dry_run: bool = False):
    """
    一つのQuerySetから新しいニュース記事を取得する。

    Args:
        queryset (QuerySet): ニュースを取得するためのQuerySetオブジェクト。
        user (User): 記事が既に送信されたかを判断するためのUserオブジェクト。
        after_days (int): 何日前までの記事を取得するかの日数。0以下で無制限。
        dry_run (bool): Trueの場合、DBへの書き込みは行わない。

    Returns:
        list[Article]: 新しく見つかったArticleオブジェクトのリスト。
    """
    query_with_date = queryset.query_str
    if after_days > 0:
        limit_date = datetime.now() - timedelta(days=after_days)
        after_date_str = limit_date.strftime('%Y-%m-%d')
        query_with_date += f" after:{after_date_str}"

    feed = fetch_rss_feed(query_with_date)
    if not feed:
        return []
    new_articles = []

    for entry in feed.entries:
        published_date = get_published_date_from_entry(entry)

        if after_days > 0 and published_date:
            threshold_date = datetime.now(timezone.utc) - timedelta(days=after_days)
            if published_date < threshold_date:
                continue

        article = None
        if dry_run:
            # dry-run時はDB検索のみ、またはインスタンス作成のみ
            article = Article.objects.filter(url=entry.link).first()
            if not article:
                article = Article(
                    url=entry.link,
                    title=entry.title,
                    published_date=published_date
                )
        else:
            # 通常時はDBに保存
            article, _ = Article.objects.get_or_create(
                url=entry.link,
                defaults={
                    'title': entry.title,
                    'published_date': published_date
                }
            )

        # ユーザーに送信済みでなければリストに追加
        if article and not SentArticleLog.objects.filter(user=user, article=article).exists():
            new_articles.append(article)
            
    return new_articles


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
