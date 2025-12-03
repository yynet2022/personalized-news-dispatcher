from django.contrib import admin
from .models import Article, SentArticleLog, ClickLog


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """
    記事モデルの管理サイト設定
    """
    list_display = ('title', 'published_date')
    search_fields = ('title',)
    list_filter = ('published_date',)


@admin.register(SentArticleLog)
class SentArticleLogAdmin(admin.ModelAdmin):
    """
    配信済み記事ログモデルの管理サイト設定
    """
    list_display = ('user', 'article', 'sent_at')
    list_filter = ('user', 'sent_at',)
    raw_id_fields = ('user', 'article',)


@admin.register(ClickLog)
class ClickLogAdmin(admin.ModelAdmin):
    """
    クリックログモデルの管理サイト設定
    """
    list_display = ('user', 'article', 'clicked_at')
    list_filter = ('user', 'clicked_at',)
    raw_id_fields = ('user', 'article',)
