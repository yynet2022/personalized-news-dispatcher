import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Union
import feedparser
import httpx
from urllib.parse import quote_plus
from datetime import datetime, timezone, timedelta

from django.conf import settings
from django.utils import timezone as django_timezone
from users.models import User
from news.models import Article, SentArticleLog
from subscriptions.models import QuerySet
from core.cinii_api import search_cinii_research
from core.arxiv_api import search_arxiv


logger = logging.getLogger(__name__)


class FeedFetchError(Exception):
    """記事フィードの取得に関する共通のエラーを示すカスタム例外"""
    pass


class ArticleFetcher(ABC):
    """
    ニュースソースから記事を取得するためのインターフェースを定義する抽象基底クラス。
    """
    @abstractmethod
    def fetch_articles(
        self,
        queryset: QuerySet,
        user: User,
        dry_run: bool = False,
        after_days_override: Union[int, None] = None
    ) -> Tuple[str, List[Article]]:
        """
        指定されたQuerySetに基づいて、ユーザーが未読の記事を取得する。

        Args:
            queryset (QuerySet): 記事取得の条件を定義したQuerySetオブジェクト。
            user (User): 記事が既に送信されたかを判断するためのUserオブジェクト。
            dry_run (bool): Trueの場合、DBへのArticleの保存は行わない。
            after_days_override (int | None): querysetの設定を上書きする日数。

        Returns:
            Tuple[str, List[Article]]:
                - 実際に使用したクエリ文字列。
                - 見つかったArticleオブジェクトのリスト。
        """
        raise NotImplementedError


class GoogleNewsFetcher(ArticleFetcher):
    """Google Newsから記事を取得するためのFetcher。"""

    def _get_published_date_from_entry(self, entry):
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt_naive = datetime(*entry.published_parsed[:6])
            return dt_naive.replace(tzinfo=timezone.utc)
        return None

    def _fetch_rss_feed(self, query: str, country_code: str,
                        timeout: int = 10):
        google_news_params = {
            'JP': {'hl': 'ja', 'gl': 'JP', 'ceid': 'JP:ja'},
            'US': {'hl': 'en', 'gl': 'US', 'ceid': 'US:en'},
            'CN': {'hl': 'zh-CN', 'gl': 'CN', 'ceid': 'CN:zh-Hans'},
            'KR': {'hl': 'ko', 'gl': 'KR', 'ceid': 'KR:ko'},
        }
        params = google_news_params.get(country_code, google_news_params['JP'])

        logger.debug(f'query: {query}')
        encoded_query = quote_plus(query)
        base_url = (f"https://news.google.com/rss/search?"
                    f"q={encoded_query}&hl={params['hl']}&"
                    f"gl={params['gl']}&ceid={params['ceid']}")

        try:
            response = httpx.get(
                base_url, timeout=timeout, follow_redirects=True)
            response.raise_for_status()
            return feedparser.parse(response.content)
        except httpx.RequestError as e:
            error_message = (f"Failed to fetch RSS feed for query '{query}' "
                             f"from country '{country_code}': {e}")
            logger.error(error_message)
            raise FeedFetchError(error_message) from e

    def _build_query_with_date(self, query_str: str, after_days: int) -> str:
        if after_days > 0:
            limit_date = django_timezone.now() - timedelta(days=after_days)
            after_date_str = limit_date.strftime('%Y-%m-%d')
            return f"{query_str} after:{after_date_str}"
        return query_str

    def _process_feed_entries(self, entries,
                              after_days: int, max_articles: int,
                              user: User, persist: bool) -> List[Article]:
        articles = []
        logger.info(f'{len(entries)} entries found.')
        threshold_date = django_timezone.now() - timedelta(days=after_days)
        for entry in entries:
            if len(articles) >= max_articles:
                break

            published_date = self._get_published_date_from_entry(entry)

            if after_days > 0 and published_date:
                if published_date < threshold_date:
                    logger.debug(f'Older: {published_date}: skip.')
                    continue

            if persist:
                article_instance, _ = Article.objects.get_or_create(
                    url=entry.link,
                    defaults={
                        'title': entry.title,
                        'published_date': published_date
                    }
                )
                if not SentArticleLog.objects.filter(
                        user=user, article=article_instance).exists():
                    articles.append(article_instance)
            else:
                article_instance = Article(
                    url=entry.link,
                    title=entry.title,
                    published_date=published_date
                )
                if not Article.objects.filter(url=entry.link).exists() or \
                   not SentArticleLog.objects.filter(
                       user=user, article__url=entry.link).exists():
                    articles.append(article_instance)

        return articles

    def fetch_articles(
        self,
        queryset: QuerySet,
        user: User,
        dry_run: bool = False,
        after_days_override: Union[int, None] = None
    ) -> Tuple[str, List[Article]]:
        logger.debug(f"Fetching Google News for queryset: {queryset.name}")

        after_days = after_days_override \
            if after_days_override is not None else queryset.after_days
        query_with_date = self._build_query_with_date(
            queryset.query_str, after_days)
        logger.debug(f'after_days: {after_days}')

        feed = self._fetch_rss_feed(
            query_with_date, country_code=queryset.country)

        articles = self._process_feed_entries(
            entries=feed.entries,
            after_days=after_days,
            max_articles=queryset.max_articles,
            user=user,
            persist=(not dry_run)
        )
        return query_with_date, articles


class CiNiiFetcher(ArticleFetcher):
    """CiNii Researchから記事を取得するためのFetcher。"""

    def _parse_date_string(self, date_str: str) -> Union[datetime, None]:
        if not date_str:
            return None
        try:
            if len(date_str) == 4:
                return datetime(int(date_str),
                                1, 1, 0, 0, 0, tzinfo=timezone.utc)
            elif len(date_str) == 7:
                return datetime(int(date_str[:4]), int(date_str[5:7]), 1,
                                0, 0, 0, tzinfo=timezone.utc)
            elif len(date_str) >= 10:
                try:
                    return datetime.fromisoformat(
                        date_str).astimezone(timezone.utc)
                except ValueError:
                    dt_naive = datetime.strptime(date_str[:10], '%Y-%m-%d')
                    return dt_naive.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not parse date string '{date_str}': {e}")
            return None

    def fetch_articles(
        self,
        queryset: QuerySet,
        user: User,
        dry_run: bool = False,
        after_days_override: Union[int, None] = None
    ) -> Tuple[str, List[Article]]:
        logger.debug(f"Fetching CiNii Research for queryset: {queryset.name}")
        search_keyword = queryset.query_str
        if not search_keyword:
            return "", []

        after_days = after_days_override \
            if after_days_override is not None else queryset.after_days

        earliest_date = django_timezone.now() - timedelta(days=after_days)

        start_year = None
        if after_days > 0:
            start_year = earliest_date.year

        try:
            cinii_results = search_cinii_research(
                keyword=search_keyword,
                count=min(queryset.max_articles * 3, 200),
                start_year=start_year,
                appid=settings.CINII_APP_ID
            )
        except httpx.RequestError as e:
            raise FeedFetchError(
                f"Network error fetching CiNii feed: {e}") from e
        except httpx.HTTPStatusError as e:
            raise FeedFetchError(f"HTTP error fetching CiNii feed: {e}") from e

        items = cinii_results.get('items', [])
        new_articles = []

        sent_article_urls = set(SentArticleLog.objects
                                .filter(user=user)
                                .values_list('article__url', flat=True))

        for item in items:
            if len(new_articles) >= queryset.max_articles:
                break

            url = item.get('link', {}).get('@id')
            title = item.get('title')

            if not url or not title or url in sent_article_urls:
                continue

            published_date = self._parse_date_string(
                item.get('prism:publicationDate'))

            if not published_date:
                continue

            if after_days > 0 and published_date < earliest_date:
                continue

            if not dry_run:
                article, _ = Article.objects.update_or_create(
                    url=url,
                    defaults={'title': title, 'published_date': published_date}
                )
            else:
                article = Article(
                    url=url, title=title, published_date=published_date)

            new_articles.append(article)

        return search_keyword, new_articles


class ArXivFetcher(ArticleFetcher):
    """arXivから記事を取得するためのFetcher。"""

    def fetch_articles(
        self,
        queryset: QuerySet,
        user: User,
        dry_run: bool = False,
        after_days_override: Union[int, None] = None
    ) -> Tuple[str, List[Article]]:
        logger.debug(f"Fetching arXiv for queryset: {queryset.name}")
        search_keyword = queryset.query_str
        if not search_keyword:
            return "", []

        after_days = after_days_override \
            if after_days_override is not None else queryset.after_days

        try:
            arxiv_results = search_arxiv(
                query=search_keyword,
                max_articles=min(queryset.max_articles * 3, 100),
                after_days=after_days
            )
        except httpx.RequestError as e:
            raise FeedFetchError(
                f"Network error fetching arXiv feed: {e}") from e
        except httpx.HTTPStatusError as e:
            raise FeedFetchError(f"HTTP error fetching arXiv feed: {e}") from e

        new_articles = []
        sent_article_urls = set(SentArticleLog.objects.filter(
            user=user).values_list('article__url', flat=True))

        for item in arxiv_results:
            if len(new_articles) >= queryset.max_articles:
                break

            url = item.get('link')
            title = item.get('title')
            published_date = item.get('published_date')

            if not url or not title or not published_date or \
               url in sent_article_urls:
                continue

            # after_days のフィルタリングは search_arxiv 内で既に行われている

            if not dry_run:
                article, created = Article.objects.get_or_create(
                    url=url,
                    defaults={'title': title, 'published_date': published_date}
                )
                if created or not SentArticleLog.objects.filter(
                        user=user, article=article).exists():
                    new_articles.append(article)
            else:
                # dry_run時はDBに存在するかどうかは気にせずインスタンスを作成
                article = Article(
                    url=url, title=title, published_date=published_date)
                new_articles.append(article)

        return search_keyword, new_articles
