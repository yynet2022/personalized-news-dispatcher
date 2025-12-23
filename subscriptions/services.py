import logging
import asyncio
from typing import Union, Tuple, List

from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.contrib.sites.models import Site
from django.template.loader import render_to_string

from users.models import User
from news.models import Article
from subscriptions.models import QuerySet
from subscriptions.fetchers import (
    ArticleFetcher, CiNiiFetcher, GoogleNewsFetcher, ArXivFetcher)
from core.translation import translate_content

logger = logging.getLogger(__name__)


def send_articles_email(
    user: User,
    querysets_with_articles: list,
    subject: str,
    template_name: str,
    enable_translation: bool = True
):
    """
    汎用的な記事ダイジェストメールを送信する。
    """
    current_site = Site.objects.get_current()
    site_url = f'http://{current_site.domain}'
    logger.debug(f'site_url: {site_url}')

    # トラッキングURLを記事オブジェクトに付与
    for item in querysets_with_articles:
        for article in item['articles']:
            tracking_path = reverse('news:track_click',
                                    kwargs={'pk': article.pk})
            article.tracking_url = site_url + tracking_path

    context = {
        'user': user,
        'querysets_with_articles': querysets_with_articles,
        'site_url': site_url,
        'project_name': settings.PROJECT_NAME,
    }

    plain_body = render_to_string(f'{template_name}.txt', context)
    html_body = render_to_string(f'{template_name}.html', context)

    # 翻訳ロジック
    final_should_translate = enable_translation
    if final_should_translate:
        queryset = querysets_with_articles[0].get('queryset')
        # Google News の場合のみ、言語が一致しない場合に翻訳を実行
        if queryset and queryset.source == QuerySet.SOURCE_GOOGLE_NEWS:
            country_data = settings.COUNTRY_CONFIG.get(queryset.country)
            country_lang = country_data['lang'] if country_data else None
            user_lang = getattr(user, 'preferred_language', None)
            if country_lang and user_lang and country_lang == user_lang:
                final_should_translate = False  # 言語が一致したので翻訳不要
        else:
            final_should_translate = False  # Google News 以外は翻訳しない

    if final_should_translate:
        target_language = getattr(
            user, 'preferred_language', settings.DEFAULT_LANGUAGE)

        async def translate_bodies():
            """非同期で本文とHTMLを翻訳する。"""
            plain_body_task = asyncio.to_thread(
                translate_content, plain_body, target_language=target_language
            )
            html_body_task = asyncio.to_thread(
                translate_content, html_body, target_language=target_language
            )
            translated_plain, translated_html = await asyncio.gather(
                plain_body_task, html_body_task
            )
            return translated_plain, translated_html

        plain_body, html_body = asyncio.run(translate_bodies())
        # logger.debug(f'plain_body> {plain_body}')
        # logger.debug(f'html_body> {html_body}')

    send_mail(
        subject=subject,
        message=plain_body,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        fail_silently=False,
        html_message=html_body,
    )


def send_recommendation_email(user: User, recommendations: list):
    """
    おすすめ記事のメールを送信する。

    Args:
        user (User): 送信先のユーザー。
        recommendations (list): おすすめ記事と読者数の辞書のリスト。
    """
    current_site = Site.objects.get_current()
    site_url = f'http://{current_site.domain}'
    logger.debug(f'site_url: {site_url}')

    # トラッキングURLを記事オブジェクトに付与
    for item in recommendations:
        article = item['article']
        tracking_path = reverse('news:track_click',
                                kwargs={'pk': article.pk})
        article.tracking_url = site_url + tracking_path

    context = {
        'user': user,
        'recommendations': recommendations,
        'site_url': site_url,
        'project_name': settings.PROJECT_NAME,
    }

    subject = f'[{settings.PROJECT_NAME}] Popular Articles You Might Like'
    plain_body = render_to_string(
        'subscriptions/email/recommendation_email.txt', context)
    html_body = render_to_string(
        'subscriptions/email/recommendation_email.html', context)

    send_mail(
        subject=subject,
        message=plain_body,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        fail_silently=False,
        html_message=html_body,
    )


def get_fetcher_for_queryset(queryset: QuerySet, user: User) -> ArticleFetcher:
    """QuerySetのsourceに応じて適切なArticleFetcherインスタンスを返す。"""
    if queryset.source == QuerySet.SOURCE_GOOGLE_NEWS:
        return GoogleNewsFetcher(queryset, user)
    elif queryset.source == QuerySet.SOURCE_CINII:
        return CiNiiFetcher(queryset, user)
    elif queryset.source == QuerySet.SOURCE_ARXIV:
        return ArXivFetcher(queryset, user)
    else:
        raise ValueError(f"Unsupported queryset source: {queryset.source}")


def fetch_articles_for_subscription(
    queryset: QuerySet, user: User,
    after_days_override: Union[int, None] = None,
    dry_run: bool = False,
    enable_translation: bool = True
) -> Tuple[str, List[Article]]:
    """
    QuerySetに対応したFetcherを使い、未読の記事を取得する。
    これは今後、記事取得のメインの入り口となる。
    """
    fetcher = get_fetcher_for_queryset(queryset, user)
    return fetcher.fetch_articles(dry_run=dry_run,
                                  after_days_override=after_days_override,
                                  enable_translation=enable_translation)
