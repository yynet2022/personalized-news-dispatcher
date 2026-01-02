import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView as AuthLogoutView
from django.core.cache import cache
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

# from django.http import HttpResponse
from django.views import View
from django.views.generic import FormView, TemplateView

from .forms import EmailLoginForm, UserSettingsForm
from .models import LoginToken, User

logger = logging.getLogger(__name__)


class LoginView(View):
    def get(self, request, *args, **kwargs):
        form = EmailLoginForm()
        return render(request, "users/login.html", {"form": form})

    def post(self, request, *args, **kwargs):
        # Rate Limiting Logic
        ip = request.META.get("REMOTE_ADDR")
        cache_key = f"login_attempt_{ip}"
        attempts = cache.get(cache_key, 0)

        if attempts >= 5:
            logger.warning(f"Rate limit exceeded for IP: {ip}")
            return render(
                request,
                "users/login.html",
                {
                    "form": EmailLoginForm(),
                    "error_message": "ログイン試行回数が多すぎます。しばらく待ってから再試行してください。",
                },
            )

        cache.set(cache_key, attempts + 1, 60)  # Expires in 60 seconds

        next_url = request.GET.get("next")
        if next_url:
            request.session["next"] = next_url
        else:
            # Ensure 'next' is not carried over from a previous login
            request.session.pop("next", None)

        form = EmailLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]

            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                logger.info(f"New user registration attempted for: {email}")
                user = User.objects.create_user(email=email, is_active=False)

            token = secrets.token_urlsafe(32)
            LoginToken.objects.create(user=user, token=token)

            login_url = request.build_absolute_uri(
                reverse("users:authenticate", kwargs={"token": token})
            )

            try:
                send_mail(
                    subject=f"[{settings.PROJECT_NAME}] ログインURLのお知らせ",
                    message=f"以下のリンクをクリックしてログインしてください。\n\n{login_url}",
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[user.email],
                )
                return render(request, "users/login_link_sent.html")
            except Exception as e:
                logger.error(
                    f"Failed to send login email to {user.email}: {e}",
                )
                logger.debug(
                    f"Failed to send login email to {user.email}: {e}",
                    exc_info=True,
                )
                messages.error(request, f"メール送信に失敗しました: {e}")

        return render(request, "users/login.html", {"form": form})


class AuthenticateView(View):
    def get(self, request, token, *args, **kwargs):
        try:
            login_token = LoginToken.objects.get(token=token)

            # トークンの有効期限（例：30分）を設定
            expiration_limit = timedelta(minutes=30)

            # 現在時刻とトークン作成時刻を比較
            if timezone.now() - login_token.created_at > expiration_limit:
                # 期限切れの場合はトークンを削除してエラーページ表示
                login_token.delete()
                return render(
                    request,
                    "users/login_failed.html",
                    {
                        "message": "このログインリンクは有効期限が切れています。"
                    },
                )

        except LoginToken.DoesNotExist:
            return render(
                request,
                "users/login_failed.html",
                {"message": "無効なリンクです。"},
            )

        user = login_token.user

        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

        user.backend = "django.contrib.auth.backends.ModelBackend"

        login(request, user)

        login_token.delete()

        next_url = request.session.pop("next", None)
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        else:
            return redirect("subscriptions:queryset_list")


class LogoutView(AuthLogoutView):
    next_page = "users:login"


class UserSettingsView(LoginRequiredMixin, FormView):
    """
    ユーザー設定（優先言語）を更新するためのビュー
    """

    template_name = "users/user_settings.html"
    form_class = UserSettingsForm
    success_url = reverse_lazy("users:user_settings_success")

    def get_initial(self):
        """フォームの初期値を設定する"""
        return {"preferred_language": self.request.user.preferred_language}

    def form_valid(self, form):
        """フォームが有効な場合にユーザー情報を更新する"""
        user = self.request.user
        user.preferred_language = form.cleaned_data["preferred_language"]
        user.save()
        return super().form_valid(form)


class UserSettingsSuccessView(LoginRequiredMixin, TemplateView):
    """
    ユーザー設定の更新成功ページを表示するビュー
    """

    template_name = "users/user_settings_success.html"
