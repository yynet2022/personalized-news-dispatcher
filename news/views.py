from django.shortcuts import get_object_or_404, redirect
from django.views import View
# from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Article, ClickLog


class TrackClickView(View):
    def get(self, request, pk, *args, **kwargs):
        # どの記事がクリックされたかを取得
        article = get_object_or_404(Article, pk=pk)

        if request.user.is_authenticated:
            # クリックログを記録 (既に存在する場合は重複させない)
            # なお、update_or_create() はダメ。クリック時間は更新させない。
            # recommendations 機能で重複させないため。
            ClickLog.objects.get_or_create(user=request.user, article=article)

        # ユーザーを本来の記事URLにリダイレクト
        return redirect(article.url)
