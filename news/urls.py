from django.urls import path

from .views import TrackClickView

app_name = "news"

urlpatterns = [
    path("track/<uuid:pk>/", TrackClickView.as_view(), name="track_click"),
]
