import logging

from django.db import transaction

from news.models import Article, SentArticleLog
from users.models import User

logger = logging.getLogger(__name__)


@transaction.atomic
def log_sent_articles(user: User, articles: list[Article]):
    """
    ユーザーに送信した記事をSentArticleLogに記録する。
    パフォーマンス向上のため bulk_create を使用し、重複は無視する。

    Args:
        user (User): 送信先のユーザー。
        articles (list[Article]): 送信したArticleオブジェクトのリスト。
    """
    # 送信する記事のIDのセットを作成
    article_ids = {article.id for article in articles}

    # すでにログに記録されている記事のIDを取得
    existing_article_ids = set(
        SentArticleLog.objects.filter(
            user=user, article_id__in=article_ids
        ).values_list("article_id", flat=True)
    )

    # まだ記録されていない新しい記事のIDを特定
    new_article_ids = article_ids - existing_article_ids

    # 新しいログエントリを準備
    logs_to_create = [
        SentArticleLog(user=user, article_id=article_id)
        for article_id in new_article_ids
    ]

    # bulk_createで一括登録
    if logs_to_create:
        SentArticleLog.objects.bulk_create(logs_to_create)
        logger.info(
            f"Logged {len(logs_to_create)} "
            f"new sent articles for {user.email}."
        )
