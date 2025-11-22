from django.urls import path
from .views import (
    LoginView,
    AuthenticateView,
    LogoutView,
    UserSettingsView,
    UserSettingsSuccessView
)

app_name = 'users'

urlpatterns = [
    # http://.../users/login/ というURLに対応
    path('login/', LoginView.as_view(), name='login'),

    # http://.../users/authenticate/<token>/ というURLに対応
    path('authenticate/<str:token>/', AuthenticateView.as_view(),
         name='authenticate'),

    # http://.../users/logout/ というURLに対応
    path('logout/', LogoutView.as_view(), name='logout'),

    # http://.../users/settings/ というURLに対応
    path('settings/', UserSettingsView.as_view(), name='user_settings'),

    # http://.../users/settings/success/ というURLに対応
    path('settings/success/', UserSettingsSuccessView.as_view(),
         name='user_settings_success'),
]
