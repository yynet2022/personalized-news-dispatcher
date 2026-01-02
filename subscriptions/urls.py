from django.urls import path

from .views import (  # ArXivKeywordsApiView,
    CurrentKeywordsApiView,
    NewsPreviewApiView,
    QuerySetCreateView,
    QuerySetDeleteView,
    QuerySetListView,
    QuerySetUpdateView,
    RelatedKeywordsApiView,
    SendManualEmailApiView,
    ToggleAutoSendView,
    UniversalKeywordsApiView,
    send_manual_email,
)

app_name = "subscriptions"

urlpatterns = [
    # http://.../subscriptions/ というURLに対応
    path("", QuerySetListView.as_view(), name="queryset_list"),
    path("create/", QuerySetCreateView.as_view(), name="queryset_create"),
    path(
        "<uuid:pk>/update/",
        QuerySetUpdateView.as_view(),
        name="queryset_update",
    ),
    path(
        "<uuid:pk>/delete/",
        QuerySetDeleteView.as_view(),
        name="queryset_delete",
    ),
    # 手動メール送信用のURLパターン
    path("<uuid:pk>/send/", send_manual_email, name="queryset_send"),
    path(
        "api/universal-keywords/",
        UniversalKeywordsApiView.as_view(),
        name="api_universal_keywords",
    ),
    path(
        "api/current-keywords/",
        CurrentKeywordsApiView.as_view(),
        name="api_current_keywords",
    ),
    path(
        "api/related-keywords/",
        RelatedKeywordsApiView.as_view(),
        name="api_related_keywords",
    ),
    # path('api/arxiv-keywords/', ArXivKeywordsApiView.as_view(),
    #      name='api_arxiv_keywords'),
    path(
        "api/news-preview/",
        NewsPreviewApiView.as_view(),
        name="api_news_preview",
    ),
    path(
        "api/queryset/<uuid:pk>/toggle-auto-send/",
        ToggleAutoSendView.as_view(),
        name="api_queryset_toggle_auto_send",
    ),
    path(
        "api/queryset/<uuid:pk>/send/",
        SendManualEmailApiView.as_view(),
        name="api_queryset_send",
    ),
]
