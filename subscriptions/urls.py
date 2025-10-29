from django.urls import path
from .views import (
    QuerySetListView,
    QuerySetCreateView,
    QuerySetUpdateView,
    QuerySetDeleteView,
    send_manual_email,
    UniversalKeywordsApiView,
    CurrentKeywordsApiView,
    RelatedKeywordsApiView,
    NewsPreviewApiView,
)

app_name = 'subscriptions'

urlpatterns = [
    # http://.../subscriptions/ というURLに対応
    path('', QuerySetListView.as_view(), name='queryset_list'),

    path('create/', QuerySetCreateView.as_view(), name='queryset_create'),
    path('<uuid:pk>/update/', QuerySetUpdateView.as_view(),
         name='queryset_update'),
    path('<uuid:pk>/delete/', QuerySetDeleteView.as_view(),
         name='queryset_delete'),

    # 手動メール送信用のURLパターン
    path('<uuid:pk>/send/', send_manual_email, name='queryset_send'),

    path('api/universal-keywords/', UniversalKeywordsApiView.as_view(),
         name='api_universal_keywords'),
    path('api/current-keywords/', CurrentKeywordsApiView.as_view(),
         name='api_current_keywords'),
    path('api/related-keywords/', RelatedKeywordsApiView.as_view(),
         name='api_related_keywords'),
    path('api/news-preview/', NewsPreviewApiView.as_view(),
         name='api_news_preview'),
]
