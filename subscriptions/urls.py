from django.urls import path
from .views import (
    QuerySetListView,
    QuerySetCreateView,
    QuerySetUpdateView,
    QuerySetDeleteView,
    MediumCategoryApiView,
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

    path('api/medium-categories/', MediumCategoryApiView.as_view(),
         name='api_medium_categories'),
    path('api/news-preview/', NewsPreviewApiView.as_view(),
         name='api_news_preview'),
]
