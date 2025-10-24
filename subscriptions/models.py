import uuid
import unicodedata
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from users.models import User

def validate_no_forbidden_chars(value):
    forbidden_chars = [
        ' ', '　', # スペース
        '・', '/', # 区切り文字
        '(', ')', '（', '）', '[', ']', '【', '】', '{', '}', '「', '」', # 括弧
        '+', '-', '*', '&', '|', '!', '~', # 検索演算子
        '\\', '$', '^', '=', '<', '>', '?', '@', ':', ';', ',', '.', '"', "'" # その他
    ]
    for char in forbidden_chars:
        if char in value:
            raise ValidationError(
                _('"%(char)s" は使用できません。複数のキーワードをまとめたり、別名を入れたりしないでください。'),
                params={'char': char},
            )

def normalize_text(text):
    """全角英数字を半角に変換する"""
    if not isinstance(text, str):
        return text
    # 全角英数字を半角に変換
    normalized_text = unicodedata.normalize('NFKC', text)
    return normalized_text


class NormalizeNameMixin(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.name = normalize_text(self.name)
        super().save(*args, **kwargs)


class LargeCategory(NormalizeNameMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('大分類名', max_length=50, unique=True, validators=[validate_no_forbidden_chars])

    def __str__(self):
        return self.name


class UniversalKeywords(NormalizeNameMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    large_category = models.ForeignKey(LargeCategory, on_delete=models.CASCADE)
    name = models.CharField('普遍キーワード', max_length=50, validators=[validate_no_forbidden_chars])
    description = models.CharField('説明', max_length=255, blank=True, null=True)

    def __str__(self):
        return f'{self.large_category.name} - {self.name}'


class CurrentKeywords(NormalizeNameMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    large_category = models.ForeignKey(LargeCategory, on_delete=models.CASCADE)
    name = models.CharField('時事キーワード', max_length=50, validators=[validate_no_forbidden_chars])
    description = models.CharField('説明', max_length=255, blank=True, null=True)

    def __str__(self):
        return f'{self.large_category.name} - {self.name}'


class RelatedKeywords(NormalizeNameMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    large_category = models.ForeignKey(LargeCategory, on_delete=models.CASCADE)
    name = models.CharField('関連キーワード', max_length=100, unique=True, validators=[validate_no_forbidden_chars])
    description = models.CharField('説明', max_length=255, blank=True, null=True)

    def __str__(self):
        return f'{self.large_category.name} - {self.name}'


class CustomKeywords(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    keywords = models.TextField(
        '任意単語',
        help_text='Google検索と同じ形式で入力 (例: "Python" -Django)')

    def __str__(self):
        return self.keywords


class QuerySet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField('セット名', max_length=100)
    query_str = models.TextField('クエリ文字列', editable=False,
                                 help_text='ユーザ選択により自動生成')

    large_category = models.ForeignKey(
        LargeCategory,
        on_delete=models.PROTECT,
        verbose_name='大分類'
    )

    universal_keywords = models.ManyToManyField(
        UniversalKeywords,
        blank=True,
        verbose_name='普遍キーワード'
    )

    current_keywords = models.ManyToManyField(
        CurrentKeywords,
        blank=True,
        verbose_name='時事キーワード'
    )

    related_keywords = models.ManyToManyField(
        RelatedKeywords,
        blank=True,
        verbose_name='関連キーワード'
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
