"""
Маршрутизация (URL) приложения управления пользователями (users).

Включает в себя маршруты для стандартного веб-интерфейса (HTML-страницы)
и версионируемые эндпоинты REST API v1 (JSON).
"""

from django.contrib.auth import views as auth_views
from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from users.apps import UsersConfig
from users.views import (
    EmailConfirmationSentView,
    EmailConfirmView,
    UserRegisterAPIView,
    UserRegisterView,
    UserVerifyEmailAPIView,
    UserPasswordResetAPIView,
    UserPasswordResetConfirmAPIView,
    UserMeAPIView,
    UserTokenObtainPairView,
)

# Пространство имен для URL-адресов приложения
app_name = UsersConfig.name

urlpatterns = [
    # =========================================================================
    # ВЕБ-ИНТЕРФЕЙС (HTML СТРАНИЦЫ ДЛЯ БРАУЗЕРА)
    # =========================================================================
    # Регистрация и подтверждение почты
    path("register/", UserRegisterView.as_view(), name="register"),
    path(
        "email-confirmation-sent/",
        EmailConfirmationSentView.as_view(),
        name="email_confirmation_sent",
    ),
    path(
        "email-confirm/<str:uidb64>/<str:token>/",
        EmailConfirmView.as_view(),
        name="email_confirm",
    ),
    # Вход и выход из системы (Сессии)
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="users/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="daily:task_list"),
        name="logout",
    ),
    # Полный цикл сброса пароля через сайт (Все 4 обязательных шага Django)
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(template_name="users/password_reset.html"),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="users/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="users/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="users/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    # =========================================================================
    # REST API V1 (ДЛЯ МОБИЛЬНЫХ ПРИЛОЖЕНИЙ И ФРОНТЕНДА)
    # =========================================================================
    # Аутентификация и сессии (JWT)
    path(
        "api/v1/auth/login/", UserTokenObtainPairView.as_view(), name="api_token_obtain"
    ),
    path(
        "api/v1/auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="api_token_refresh",
    ),
    path(
        "api/v1/auth/logout/", TokenBlacklistView.as_view(), name="api_token_blacklist"
    ),
    # Регистрация и верификация через API
    path("api/v1/register/", UserRegisterAPIView.as_view(), name="api_register"),
    path(
        "api/v1/email-verify/",
        UserVerifyEmailAPIView.as_view(),
        name="api_email_verify",
    ),
    # Личный кабинет (Будет возвращать GET профиля и обрабатывать PATCH/PUT)
    path("api/v1/me/", UserMeAPIView.as_view(), name="api_user_me"),
    # Сброс пароля через API (Ожидают POST-запросы с JSON-данными)
    path(
        "api/v1/password-reset/",
        UserPasswordResetAPIView.as_view(),
        name="api_password_reset",
    ),
    path(
        "api/v1/password-reset/confirm/",
        UserPasswordResetConfirmAPIView.as_view(),
        name="api_password_reset_confirm",
    ),
]
