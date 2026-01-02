import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import feedparser
import httpx

logger = logging.getLogger(__name__)


class FetchError(Exception):
    pass


def _get_published_date_from_entry(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt_naive = datetime(*entry.published_parsed[:6])
        return dt_naive.replace(tzinfo=timezone.utc)
    return None


def _fetch_rss_feed(query: str, country_code: str, timeout: int = 10):
    google_news_params = {
        "JP": {"hl": "ja", "gl": "JP", "ceid": "JP:ja"},
        "US": {"hl": "en", "gl": "US", "ceid": "US:en"},
        "CN": {"hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"},
        "KR": {"hl": "ko", "gl": "KR", "ceid": "KR:ko"},
    }
    # デフォルトはJP
    params = google_news_params.get(country_code, google_news_params["JP"])

    logger.debug(f"query: {query}")
    encoded_query = quote_plus(query)
    base_url = (
        f"https://news.google.com/rss/search?"
        f"q={encoded_query}&hl={params['hl']}&"
        f"gl={params['gl']}&ceid={params['ceid']}"
    )

    try:
        response = httpx.get(base_url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        return feedparser.parse(response.content)
    except httpx.RequestError as e:
        error_message = (
            f"Failed to fetch RSS feed for query '{query}' "
            f"from country '{country_code}': {e}"
        )
        logger.error(error_message)
        raise FetchError(error_message) from e
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        logger.error(error_message)
        raise FetchError(error_message) from e


def search_google_news(
    query: str,
    country: str = "JP",
    after_days: Optional[int] = None,
    max_articles: int = 100,
) -> List[Dict]:
    """
    Google Newsを検索し、記事リストを返す。

    Args:
        query (str): 検索クエリ
        country (str): 国コード (JP, US, CN, KR)
        after_days (int | None): 指定した日数以内の記事のみ取得
        max_articles (int): 最大取得件数

    Returns:
        List[Dict]: 記事情報のリスト。
                    keys: 'title', 'link', 'published_date'
    """
    # 日付フィルタリング用のクエリ加工
    final_query = query
    if after_days is not None and after_days > 0:
        limit_date = datetime.now(timezone.utc) - timedelta(days=after_days)
        after_date_str = limit_date.strftime("%Y-%m-%d")
        final_query = f"{query} after:{after_date_str}"
        logger.debug(f"after_days: {after_days} -> {final_query}")

    try:
        feed = _fetch_rss_feed(final_query, country_code=country)
    except FetchError:
        return []

    logger.info(f"{len(feed.entries)} entries found.")

    articles = []
    threshold_date = None
    if after_days is not None and after_days > 0:
        threshold_date = datetime.now(timezone.utc) - timedelta(
            days=after_days
        )

    for entry in feed.entries:
        if len(articles) >= max_articles:
            break

        published_date = _get_published_date_from_entry(entry)

        # クエリで after: を指定しても厳密ではない場合があるため、ここでもチェック
        if threshold_date and published_date:
            if published_date < threshold_date:
                logger.debug(f"Older: {published_date}: skip.")
                continue

        articles.append(
            {
                "title": entry.title,
                "link": entry.link,
                "published_date": published_date,
            }
        )

    return articles
