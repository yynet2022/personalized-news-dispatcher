# users/models.py
from __future__ import annotations

import uuid
from typing import Any, Optional

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ----------------------------------------------------------------------
# 1. 専用のUserManagerを作成
# ----------------------------------------------------------------------
class CustomUserManager(BaseUserManager["User"]):
    """
    'username'フィールドの代わりに'email'を使用するためのカスタムユーザーマネージャー
    """

    def create_user(
        self, email: str, password: Optional[str] = None, **extra_fields: Any
    ) -> User:
        if not email:
            raise ValueError("Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: Optional[str] = None, **extra_fields: Any
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        # 上で定義した create_user メソッドを呼び出す
        return self.create_user(email, password, **extra_fields)


# settings.py から言語の選択肢を動的に生成
LANGUAGES = set(data["lang"] for data in settings.COUNTRY_CONFIG.values())
LANGUAGE_CHOICES = sorted([(lang, lang) for lang in LANGUAGES])


# ----------------------------------------------------------------------
# 2. 作成したUserManagerをUserモデルに適用
# ----------------------------------------------------------------------
class User(AbstractBaseUser, PermissionsMixin):
    """
    AbstractUserを使用せず、AbstractBaseUserとPermissionsMixinを継承して再定義。
    これにより username フィールドを排除し、objects マネージャーの型競合を解決する。
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("メールアドレス", unique=True)

    # AbstractUser から必要なフィールドを再定義
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_(
            "Designates whether the user can log into this admin site."
        ),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    preferred_language = models.CharField(
        "優先言語",
        max_length=50,
        choices=LANGUAGE_CHOICES,
        default=settings.DEFAULT_LANGUAGE,
        help_text="AI翻訳で利用する優先言語",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def get_display_name(self) -> str:
        n = self.get_full_name()
        if n:
            return n
        return self.email

    def get_full_name(self) -> str:
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = "%s %s" % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self) -> str:
        """Return the short name for the user."""
        return self.first_name

    def __str__(self) -> str:
        return self.email


class LoginToken(models.Model):
    """
    ログイン用のワンタイムトークンを保存するモデル
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="ユーザー"
    )
    token = models.CharField("トークン", max_length=255, unique=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.token}"
