from django.contrib import admin

from .models import (
    LargeCategory,
    UniversalKeywords,
    CurrentKeywords,
    RelatedKeywords,
    QuerySet,
    CiNiiKeywords,
)


@admin.register(LargeCategory)
class LargeCategoryAdmin(admin.ModelAdmin):
    """
    大分類モデルの管理サイト設定
    """
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(UniversalKeywords)
class UniversalKeywordsAdmin(admin.ModelAdmin):
    """
    普遍キーワードモデルの管理サイト設定
    """
    list_display = ('name', 'large_category', 'description')
    search_fields = ('name', 'description')
    list_filter = ('large_category',)


@admin.register(CurrentKeywords)
class CurrentKeywordsAdmin(admin.ModelAdmin):
    """
    時事キーワードモデルの管理サイト設定
    """
    list_display = ('name', 'large_category', 'description')
    search_fields = ('name', 'description')
    list_filter = ('large_category',)


@admin.register(RelatedKeywords)
class RelatedKeywordsAdmin(admin.ModelAdmin):
    """
    関連キーワードモデルの管理サイト設定
    """
    list_display = ('name', 'large_category', 'description')
    search_fields = ('name', 'description')
    list_filter = ('large_category',)


@admin.register(QuerySet)
class QuerySetAdmin(admin.ModelAdmin):
    """
    クエリセットモデルの管理サイト設定
    """
    list_display = ('name', 'user', 'source', 'auto_send')
    search_fields = ('name', 'user__email')
    list_filter = ('user', 'auto_send', 'source', 'large_category', 'country')
    raw_id_fields = ('user',)
    filter_horizontal = (
        'universal_keywords', 'current_keywords', 'related_keywords',
        'cinii_keywords'
    )


@admin.register(CiNiiKeywords)
class CiNiiKeywordsAdmin(admin.ModelAdmin):
    """
    CiNiiキーワードモデルの管理サイト設定
    """
    list_display = ('name', 'description')
    search_fields = ('name',)
