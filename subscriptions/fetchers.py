import asyncio
import logging
import math
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Union

from django.conf import settings
from django.utils import timezone as django_timezone

from core.arxiv_api import search_arxiv
from core.cinii_api import search_cinii_research
from core.google_news_api import FetchError as GoogleFetchError
from core.google_news_api import search_google_news
from core.translation import translate_titles_batch
from news.models import Article, SentArticleLog
from subscriptions.models import QuerySet
from users.models import User

logger = logging.getLogger(__name__)


class FeedFetchError(Exception):
    """記事フィードの取得に関する共通のエラーを示すカスタム例外"""

    pass


class ArticleFetcher(ABC):
    """
    ニュースソースから記事を取得するためのインターフェースを定義する抽象基底クラス。
    """

    def __init__(self, queryset: QuerySet, user: User):
        self.queryset = queryset
        self.user = user
        self.sent_article_urls = set(
            SentArticleLog.objects.filter(user=user).values_list(
                "article__url", flat=True
            )
        )
        logger.debug(f"{self.__class__.__name__}: {queryset.name}")
        logger.info(f"{len(self.sent_article_urls)} sent articles exist.")

    def is_sent_article(self, url: str) -> bool:
        """指定されたURLの記事が既に送信済みか判定する"""
        return url in self.sent_article_urls

    def save_articles(
        self,
        articles_data: List[Dict],
        dry_run: bool = False,
        batch_size: int = settings.TRANSLATION_BATCH_SIZE,
        target_language: str = None,
    ) -> List[Article]:
        """
        辞書リストから記事オブジェクトを作成または取得する共通メソッド。
        target_languageが指定されている場合のみ、タイトルの一括翻訳を行う。
        asyncioを用いて並列処理を行う。

        Args:
            articles_data (List[Dict]): 記事データのリスト。
                各要素は {'title': str, 'url': str, 'published_date': datetime}
            dry_run (bool): Trueの場合、DBへの保存は行わない。
            batch_size (int): 翻訳時のバッチサイズ。
            target_language (str): 翻訳先の言語。Noneの場合は翻訳しない。

        Returns:
            List[Article]: Articleオブジェクトのリスト。
        """
        valid_articles_data = []

        # 1. 保存対象の抽出
        for data in articles_data:
            url = data.get("url")
            title = data.get("title")

            if not url or not title:
                continue

            if self.is_sent_article(url):
                continue

            valid_articles_data.append(data)

        if not valid_articles_data:
            return []

        # 2. タイトルの翻訳 (必要な場合のみ)
        if target_language:
            titles = [d["title"] for d in valid_articles_data]
            translated_titles = []

            async def process_translation_tasks():
                num_titles = len(titles)
                if num_titles == 0:
                    return []

                num_batches = math.ceil(num_titles / batch_size)
                base_size = num_titles // num_batches
                remainder = num_titles % num_batches

                tasks = []
                start_index = 0

                for i in range(num_batches):
                    # 余りを前のバッチから順に分配してサイズを決定
                    current_batch_size = (
                        base_size + 1 if i < remainder else base_size
                    )
                    end_index = start_index + current_batch_size

                    batch = titles[start_index:end_index]
                    logger.info(
                        f"Queuing translation batch {i + 1}/{num_batches} "
                        f"(size: {len(batch)})"
                    )

                    tasks.append(
                        asyncio.to_thread(
                            translate_titles_batch, batch, target_language
                        )
                    )
                    start_index = end_index

                # 全タスクを並列実行
                results = await asyncio.gather(*tasks)

                flat_results = []
                for batch_result in results:
                    flat_results.extend(batch_result)
                return flat_results

            if titles:
                try:
                    translated_titles = asyncio.run(
                        process_translation_tasks()
                    )
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                    translated_titles = loop.run_until_complete(
                        process_translation_tasks()
                    )

            # 翻訳結果の反映
            if len(translated_titles) == len(valid_articles_data):
                for i, data in enumerate(valid_articles_data):
                    data["title"] = translated_titles[i]
            else:
                logger.warning(
                    "Translated titles count mismatch. Using original titles."
                )

        # 3. 保存処理
        saved_articles = []
        for data in valid_articles_data:
            url = data["url"]
            title = data["title"]
            published_date = data.get("published_date")

            if dry_run:
                article = Article(
                    url=url, title=title, published_date=published_date
                )
            else:
                article, _ = Article.objects.get_or_create(
                    url=url,
                    defaults={
                        "title": title,
                        "published_date": published_date,
                    },
                )

            saved_articles.append(article)

        return saved_articles

    @abstractmethod
    def fetch_articles(
        self,
        dry_run: bool = False,
        after_days_override: Union[int, None] = None,
        enable_translation: bool = True,
    ) -> Tuple[str, List[Article]]:
        """
        記事を取得し、Articleオブジェクトのリストを返す。

        Args:
            dry_run (bool): Trueの場合、DBへのArticleの保存は行わない。
            after_days_override (int | None): querysetの設定を上書きする日数。
            enable_translation (bool): 翻訳機能を有効にするかどうか。

        Returns:
            Tuple[str, List[Article]]:
                - 実際に使用したクエリ文字列。
                - 見つかったArticleオブジェクトのリスト。
        """
        raise NotImplementedError


class GoogleNewsFetcher(ArticleFetcher):
    """Google Newsから記事を取得するためのFetcher。"""

    def fetch_articles(
        self,
        dry_run: bool = False,
        after_days_override: Union[int, None] = None,
        enable_translation: bool = True,
    ) -> Tuple[str, List[Article]]:
        after_days = (
            after_days_override
            if after_days_override is not None
            else self.queryset.after_days
        )

        # 実際に使用したクエリ文字列を構築して返すため (API内部でも構築されるが、呼び出し元への返却用)
        query_str = self.queryset.query_str
        query_with_date = query_str
        if after_days > 0:
            limit_date = django_timezone.now() - timedelta(days=after_days)
            after_date_str = limit_date.strftime("%Y-%m-%d")
            query_with_date = f"{query_str} after:{after_date_str}"

        logger.debug(f"after_days: {after_days}")

        try:
            results = search_google_news(
                query=self.queryset.query_str,
                country=self.queryset.country,
                after_days=after_days,
                max_articles=self.queryset.max_articles,
            )
        except GoogleFetchError as e:
            # FeedFetchErrorでラップして再送出
            raise FeedFetchError(str(e)) from e

        logger.info(f"{len(results)} entries found.")

        articles_data = []
        for item in results:
            url = item.get("link")
            title = item.get("title")
            published_date = item.get("published_date")

            if self.is_sent_article(url):
                continue

            articles_data.append(
                {"title": title, "url": url, "published_date": published_date}
            )

        # 言語判定とターゲット言語の設定
        target_language = None
        if enable_translation:
            user_lang = getattr(
                self.user, "preferred_language", settings.DEFAULT_LANGUAGE
            )
            country_config = settings.COUNTRY_CONFIG.get(self.queryset.country)
            article_lang = country_config["lang"] if country_config else None

            if article_lang and article_lang != user_lang:
                target_language = user_lang

        articles = self.save_articles(
            articles_data, dry_run=dry_run, target_language=target_language
        )
        return query_with_date, articles


class CiNiiFetcher(ArticleFetcher):
    """CiNii Researchから記事を取得するためのFetcher。"""

    def _parse_date_string(self, date_str: str) -> Union[datetime, None]:
        if not date_str:
            return None
        try:
            if len(date_str) == 4:
                return datetime(
                    int(date_str), 1, 1, 0, 0, 0, tzinfo=timezone.utc
                )
            elif len(date_str) == 7:
                return datetime(
                    int(date_str[:4]),
                    int(date_str[5:7]),
                    1,
                    0,
                    0,
                    0,
                    tzinfo=timezone.utc,
                )
            elif len(date_str) >= 10:
                try:
                    return datetime.fromisoformat(date_str).astimezone(
                        timezone.utc
                    )
                except ValueError:
                    dt_naive = datetime.strptime(date_str[:10], "%Y-%m-%d")
                    return dt_naive.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not parse date string '{date_str}': {e}")
            return None

    def fetch_articles(
        self,
        dry_run: bool = False,
        after_days_override: Union[int, None] = None,
        enable_translation: bool = True,
    ) -> Tuple[str, List[Article]]:
        search_keyword = self.queryset.query_str
        if not search_keyword:
            return "", []

        after_days = (
            after_days_override
            if after_days_override is not None
            else self.queryset.after_days
        )

        earliest_date = django_timezone.now() - timedelta(days=after_days)

        start_year = None
        if after_days > 0:
            start_year = earliest_date.year

        try:
            # import httpx はこのファイルのトップレベルからは削除されているため
            # 必要なら再インポートするか、cinii_apiのエラーハンドリングに依存する。
            # ここでは cinii_api が httpx の例外をそのまま出す可能性があるため
            # FeedFetchError で包む必要があるが、httpx を import せずに捕捉するのは難しい。
            # cinii_api 側で捕捉していない場合はここでもエラーになる。
            # とりあえず既存の実装に合わせるため、httpx エラーの捕捉が必要なら import httpx が必要。
            # しかし今回のリファクタリングで api 側に寄せたい。
            # search_cinii_research は httpx エラーを投げる可能性があるので、
            # ここで try-except Exception で受けて FeedFetchError にする。
            cinii_results = search_cinii_research(
                keyword=search_keyword,
                count=min(self.queryset.max_articles * 3, 200),
                start_year=start_year,
                appid=settings.CINII_APP_ID,
            )
        except Exception as e:
            # 厳密には httpx.RequestError などだが、依存を減らすため汎用的に受ける
            raise FeedFetchError(f"Error fetching CiNii feed: {e}") from e

        items = cinii_results.get("items", [])
        logger.info(f"{len(items)} entries found.")

        articles_data = []
        for item in items:
            if len(articles_data) >= self.queryset.max_articles:
                break

            url = item.get("link", {}).get("@id")
            title = item.get("title")

            published_date = self._parse_date_string(
                item.get("prism:publicationDate")
            )

            if not published_date:
                continue

            if after_days > 0 and published_date < earliest_date:
                continue

            if self.is_sent_article(url):
                continue

            articles_data.append(
                {"title": title, "url": url, "published_date": published_date}
            )

        # 言語判定
        target_language = None
        if enable_translation:
            user_lang = getattr(
                self.user, "preferred_language", settings.DEFAULT_LANGUAGE
            )
            # CiNiiは日本語とみなす
            if user_lang != settings.COUNTRY_CONFIG["JP"]["lang"]:
                target_language = user_lang

        articles = self.save_articles(
            articles_data, dry_run=dry_run, target_language=target_language
        )
        return search_keyword, articles


class ArXivFetcher(ArticleFetcher):
    """arXivから記事を取得するためのFetcher。"""

    def fetch_articles(
        self,
        dry_run: bool = False,
        after_days_override: Union[int, None] = None,
        enable_translation: bool = True,
    ) -> Tuple[str, List[Article]]:
        search_keyword = self.queryset.query_str
        if not search_keyword:
            return "", []

        after_days = (
            after_days_override
            if after_days_override is not None
            else self.queryset.after_days
        )

        try:
            # search_arxiv は内部で FetchError (custom) を投げる可能性がある
            # ここで import 済みの FetchError を使うかどうかだが、
            # arxiv_api.py の FetchError は import されていない。
            # core.arxiv_api から FetchError も import する手もあるが、
            # Exception で受けて FeedFetchError に統一するのがシンプル。
            arxiv_results = search_arxiv(
                query=search_keyword,
                max_articles=min(self.queryset.max_articles * 3, 100),
                after_days=after_days,
            )
        except Exception as e:
            raise FeedFetchError(f"Error fetching arXiv feed: {e}") from e

        logger.info(f"{len(arxiv_results)} entries found.")

        articles_data = []
        for item in arxiv_results:
            if len(articles_data) >= self.queryset.max_articles:
                break

            url = item.get("link")
            title = item.get("title")
            published_date = item.get("published_date")

            if self.is_sent_article(url):
                continue

            # after_days のフィルタリングは search_arxiv 内で既に行われている

            articles_data.append(
                {"title": title, "url": url, "published_date": published_date}
            )

        # 言語判定
        target_language = None
        if enable_translation:
            user_lang = getattr(
                self.user, "preferred_language", settings.DEFAULT_LANGUAGE
            )
            # arXivは英語とみなす
            if user_lang != settings.COUNTRY_CONFIG["US"]["lang"]:
                target_language = user_lang

        articles = self.save_articles(
            articles_data, dry_run=dry_run, target_language=target_language
        )
        return search_keyword, articles
