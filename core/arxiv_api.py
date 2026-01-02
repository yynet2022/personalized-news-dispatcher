from __future__ import annotations

import logging
import urllib.parse

# from pprint import pprint
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
import httpx

logger = logging.getLogger(__name__)

# https://info.arxiv.org/help/api/user-manual.html
_BASE_URL = "https://export.arxiv.org/api/query?"


class FetchError(Exception):
    pass


def _get_published_date_from_entry(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt_naive = datetime(*entry.published_parsed[:6])
        return dt_naive.replace(tzinfo=timezone.utc)
    return None


def _fetch_atom_feed(query: str, count: int = 3, timeout: int = 10):
    # パラメータを辞書で定義
    params = {
        "search_query": query,  # all: 全文検索
        "start": 0,
        "max_results": count,
        "sortBy": "submittedDate",  # ソート基準（提出日）
        "sortOrder": "descending",  # ソート順（新しい順）
    }

    # パラメータを URL エンコードして最終URLを構築
    url = _BASE_URL + urllib.parse.urlencode(params, safe=":")
    logger.debug(f" URL: {url}")

    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return feedparser.parse(response.text)


def _process_feed_entries(entries, max_articles: int, after_days: int):
    threshold_date = datetime.now(timezone.utc) - timedelta(days=after_days)
    logger.debug(f" threshold_date: {threshold_date}")
    articles: list[dict[str, Any]] = []
    for entry in entries:
        if len(articles) >= max_articles:
            break

        published_date = _get_published_date_from_entry(entry)
        if after_days > 0 and published_date:
            if published_date < threshold_date:
                logger.debug(f" Older: {published_date}: skip.")
                continue

        article = {
            "title": entry.title.strip(),
            "link": entry.link.strip(),
            "published_date": published_date,
        }
        articles.append(article)
    return articles


def search_arxiv(query: str, max_articles: int = 5, after_days: int = 30):
    try:
        feed = _fetch_atom_feed(query, count=min(max_articles * 2, 100))
        logger.info(f" {len(feed.entries)} entries found.")
        return _process_feed_entries(
            feed.entries, max_articles=max_articles, after_days=after_days
        )
    except httpx.RequestError as e:
        message = f"Failed to fetch ATOM feed for query '{query}': {e}"
        logger.error(message)
        raise FetchError(message) from e
    except httpx.HTTPStatusError as e:
        message = (
            f"HTTP Error occurred: {e}. Status Code: {e.response.status_code}"
        )
        logger.error(message)
        raise FetchError(message) from e
    except Exception as e:
        message = f"An unexpected error occurred: {e}"
        logger.error(message)
        raise FetchError(message) from e
    return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for i, a in enumerate(search_arxiv("BiCS", after_days=0)):
        print(f"\n#{i+1}")
        print(f" Title: {a['title']}")
        print(f" URL: {a['link']}")
        print(f" Date: {a['published_date']}")
