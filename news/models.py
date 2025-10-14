import uuid
from django.db import models
from django.conf import settings


class Article(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField('記事URL', unique=True, max_length=1024)
    title = models.CharField('記事タイトル', max_length=255)
    published_date = models.DateTimeField('発行日', null=True, blank=True)

    def __str__(self):
        return self.title


class SentArticleLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    sent_at = models.DateTimeField('配信日時', auto_now_add=True)

    class Meta:
        unique_together = ('user', 'article')


class ClickLog(models.Model):
    """
    ユーザーの記事クリックを記録するモデル
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    clicked_at = models.DateTimeField('クリック日時', auto_now_add=True)

    def __str__(self):
        return f'{self.user.email} clicked on {self.article.title}'
