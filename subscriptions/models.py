import uuid
import unicodedata
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from users.models import User


def validate_no_forbidden_chars(value):
    # '+', '-', '&' は OK と変更。
    forbidden_chars = [
        ' ', '　',  # スペース
        '・', '/',  # 区切り文字
        '(', ')', '（', '）', '[', ']', '【', '】', '{', '}', '「', '」',  # 括弧
        '*', '|', '!', '~',  # 検索演算子
        '\\', '$', '^', '=', '<', '>', '?', '@', ':', ';', ',', '.', '"', "'",
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
    name = models.CharField('大分類名', max_length=50, unique=True,
                            validators=[validate_no_forbidden_chars])

    def __str__(self):
        return self.name


class CiNiiKeywords(NormalizeNameMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('キーワード', max_length=100, unique=True)
    description = models.CharField('説明', max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class ArXivKeywords(NormalizeNameMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('キーワード', max_length=100, unique=True)
    description = models.CharField('説明', max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class UniversalKeywords(NormalizeNameMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    large_category = models.ForeignKey(LargeCategory, on_delete=models.CASCADE)
    name = models.CharField('普遍キーワード', max_length=50,
                            validators=[validate_no_forbidden_chars])
    description = models.CharField('説明', max_length=255,
                                   blank=True, null=True)

    class Meta:
        unique_together = ('large_category', 'name')

    def __str__(self):
        return f'{self.large_category.name} - {self.name}'


class CurrentKeywords(NormalizeNameMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    large_category = models.ForeignKey(LargeCategory, on_delete=models.CASCADE)
    name = models.CharField('時事キーワード', max_length=50,
                            validators=[validate_no_forbidden_chars])
    description = models.CharField('説明', max_length=255,
                                   blank=True, null=True)

    class Meta:
        unique_together = ('large_category', 'name')

    def __str__(self):
        return f'{self.large_category.name} - {self.name}'


class RelatedKeywords(NormalizeNameMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    large_category = models.ForeignKey(LargeCategory, on_delete=models.CASCADE)
    name = models.CharField('関連キーワード', max_length=100,
                            validators=[validate_no_forbidden_chars])
    description = models.CharField('説明', max_length=255,
                                   blank=True, null=True)

    class Meta:
        unique_together = ('large_category', 'name')

    def __str__(self):
        return f'{self.large_category.name} - {self.name}'


# settings.py の COUNTRY_NAME_MAP から国の選択肢を動的に生成
COUNTRIES = sorted(
    [(code, data['name']) for code, data in settings.COUNTRY_CONFIG.items()]
)


class QuerySet(models.Model):
    # ニュースソースの選択肢
    SOURCE_GOOGLE_NEWS = 'google_news'
    SOURCE_CINII = 'cinii'
    SOURCE_ARXIV = 'arxiv'
    SOURCE_CHOICES = [
        (SOURCE_GOOGLE_NEWS, 'Google News'),
        (SOURCE_CINII, 'CiNii Research'),
        (SOURCE_ARXIV, 'arXiv'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField('セット名', max_length=100)
    source = models.CharField(
        'ニュースソース',
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_GOOGLE_NEWS,
        help_text='どちらのニュースソースから記事を取得するかを選択します。'
    )
    auto_send = models.BooleanField('メール自動配信', default=True)
    query_str = models.TextField('クエリ文字列', editable=False,
                                 help_text='ユーザ選択により自動生成')

    # --- Google News 専用フィールド ---
    large_category = models.ForeignKey(
        LargeCategory,
        on_delete=models.PROTECT,
        verbose_name='大分類',
        null=True, blank=True,
        help_text='ニュースソースが「Google News」の場合に選択します。'
    )

    country = models.CharField(
        '国',
        max_length=2,
        choices=COUNTRIES,
        default='JP',
        blank=True,
        help_text='ニュースソースが「Google News」の場合に選択します。'
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

    # --- CiNii Research 専用フィールド ---
    cinii_keywords = models.ManyToManyField(
        'CiNiiKeywords',
        blank=True,
        verbose_name='CiNiiキーワード',
        help_text='ニュースソースが「CiNii Research」の場合に選択します。'
    )

    # --- arXiv 専用フィールド ---
    arxiv_keywords = models.ManyToManyField(
        'ArXivKeywords',
        blank=True,
        verbose_name='arXivキーワード',
        help_text='ニュースソースが「arXiv」の場合に選択します。'
    )

    # --- 共通フィールド ---
    additional_or_keywords = models.CharField(
        'OR追加キーワード',
        max_length=255,
        blank=True,
        default='',
        help_text='OR条件で追加したいキーワードをスペース区切りで入力します (例: AI 機械学習)'
    )

    refinement_keywords = models.CharField(
        '絞り込みキーワード',
        max_length=255,
        blank=True,
        default='',
        help_text='さらにキーワードで絞り込む場合に入力します (例: "Python" -Django)'
    )

    after_days = models.IntegerField(
        "取得日数（日）",
        default=2,
        validators=[MinValueValidator(0)],
        help_text="何日前までの記事を取得するか。0を指定すると無制限になります。"
    )

    max_articles = models.IntegerField(
        "最大記事数",
        default=20,
        validators=[MinValueValidator(1)],
        help_text="一度に取得する記事の最大数。"
    )

    class Meta:
        unique_together = ('user', 'name')

    def __str__(self):
        return self.name
