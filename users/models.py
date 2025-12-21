# users/models.py
import uuid
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


# ----------------------------------------------------------------------
# 1. 専用のUserManagerを作成
# ----------------------------------------------------------------------
class CustomUserManager(BaseUserManager):
    """
    'username'フィールドの代わりに'email'を使用するためのカスタムユーザーマネージャー
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        # 上で定義した create_user メソッドを呼び出す
        return self.create_user(email, password, **extra_fields)


# settings.py から言語の選択肢を動的に生成
LANGUAGES = set(data['lang'] for data in settings.COUNTRY_CONFIG.values())
LANGUAGE_CHOICES = sorted([(lang, lang) for lang in LANGUAGES])


# ----------------------------------------------------------------------
# 2. 作成したUserManagerをUserモデルに適用
# ----------------------------------------------------------------------
class User(AbstractUser):
    username = None  # usernameは使わない
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField('メールアドレス', unique=True)
    preferred_language = models.CharField(
        '優先言語',
        max_length=50,
        choices=LANGUAGE_CHOICES,
        default=settings.DEFAULT_LANGUAGE,
        help_text='AI翻訳で利用する優先言語'
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def get_display_name(self):
        n = self.get_full_name()
        if n:
            return n
        return self.email

    def __str__(self):
        return self.email


# users/models.py
class LoginToken(models.Model):
    """
    ログイン用のワンタイムトークンを保存するモデル
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             verbose_name='ユーザー')
    token = models.CharField('トークン', max_length=255, unique=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)

    def __str__(self):
        return f'{self.user.email} - {self.token}'
