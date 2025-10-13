from django.urls import path
from .views import LoginView, AuthenticateView, LogoutView

app_name = 'users'

urlpatterns = [
    # http://.../users/login/ というURLに対応
    path('login/', LoginView.as_view(), name='login'),
    
    # http://.../users/authenticate/<token>/ というURLに対応
    path('authenticate/<str:token>/', AuthenticateView.as_view(), name='authenticate'),

    # http://.../users/logout/ というURLに対応
    path('logout/', LogoutView.as_view(), name='logout'),
]
