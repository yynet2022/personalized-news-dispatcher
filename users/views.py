import secrets
import logging
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth import login
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.views import LogoutView as AuthLogoutView
from .models import User, LoginToken
from .forms import EmailLoginForm

logger = logging.getLogger(__name__)


class LoginView(View):
    def get(self, request, *args, **kwargs):
        form = EmailLoginForm()
        return render(request, 'users/login.html', {'form': form})

    def post(self, request, *args, **kwargs):
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                logger.info(f"New user registration attempted for: {email}")
                user = User.objects.create_user(email=email, is_active=False)

            token = secrets.token_urlsafe(32)
            LoginToken.objects.create(user=user, token=token)

            login_url = request.build_absolute_uri(
                reverse('users:authenticate', kwargs={'token': token})
            )

            send_mail(
                subject='【News Dispatcher】ログインURLのお知らせ',
                message=f'以下のリンクをクリックしてログインしてください。\n\n{login_url}',
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[user.email],
            )

            return render(request, 'users/login_link_sent.html')

        return render(request, 'users/login.html', {'form': form})


class AuthenticateView(View):
    def get(self, request, token, *args, **kwargs):
        try:
            login_token = LoginToken.objects.get(token=token)

            # トークンの有効期限（例：10分）を設定
            expiration_limit = timedelta(minutes=10)

            # 現在時刻とトークン作成時刻を比較
            if timezone.now() - login_token.created_at > expiration_limit:
                # 期限切れの場合はトークンを削除してエラーページ表示
                login_token.delete()
                return render(request, 'users/login_failed.html',
                              {'message': 'このログインリンクは有効期限が切れています。'})

        except LoginToken.DoesNotExist:
            return render(request, 'users/login_failed.html',
                          {'message': '無効なリンクです。'})

        user = login_token.user

        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])

        user.backend = 'django.contrib.auth.backends.ModelBackend'

        login(request, user)

        login_token.delete()

        return redirect('subscriptions:queryset_list')


class LogoutView(AuthLogoutView):
    next_page = 'users:login'
