import uuid
from django.db import models
from django.conf import settings
from users.models import User

class LargeCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('大分類名', max_length=50, unique=True)

    def __str__(self):
        return self.name

class MediumCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    large_category = models.ForeignKey(LargeCategory, on_delete=models.CASCADE)
    name = models.CharField('中分類名', max_length=50)
    is_trending = models.BooleanField('トレンド(AI生成)', default=False)

    def __str__(self):
        return f'{self.large_category.name} - {self.name}'

class CustomKeywords(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    keywords = models.TextField('任意単語', help_text='Google検索と同じ形式で入力 (例: "Python" -Django)')

    def __str__(self):
        return self.keywords

class QuerySet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField('セット名', max_length=100)
    query_str = models.TextField('クエリ文字列', editable=False, help_text='ユーザ選択により自動生成')

    # --- ▼▼▼ この large_category の定義が決定的な修正点です ▼▼▼ ---
    # null=True, blank=True を削除し、on_delete を PROTECT に変更
    large_category = models.ForeignKey(
        LargeCategory, 
        on_delete=models.PROTECT, # 関連する大分類が削除されるのを防ぐ
        verbose_name='大分類'
    )
    # --- ▲▲▲ ここまで ▲▲▲ ---

    medium_categories = models.ManyToManyField(
        MediumCategory, 
        blank=True, 
        verbose_name='中分類'
    )
    custom_keywords = models.ManyToManyField(
        CustomKeywords, 
        blank=True, 
        verbose_name='任意単語'
    )

    class Meta:
        unique_together = ('user', 'name')

    def __str__(self):
        return self.name
