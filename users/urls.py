"""
Маршрутизация (URL) приложения управления пользователями (users).

Включает в себя маршруты для стандартного веб-интерфейса (HTML-страницы)
и версионируемые эндпоинты REST API v1 (JSON).
"""

from django.contrib.auth import views as auth_views
from django.urls import path
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view, inline_serializer
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import serializers
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from users.apps import UsersConfig
from users.views import (
    EmailConfirmationSentView,
    EmailConfirmView,
    UserMeAPIView,
    UserPasswordResetAPIView,
    UserPasswordResetConfirmAPIView,
    UserProfileUpdateView,
    UserRegisterAPIView,
    UserRegisterView,
    UserTokenObtainPairView,
    UserVerifyEmailAPIView,
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
    path(
        "profile/",
        UserProfileUpdateView.as_view(),
        name="profile"
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
        extend_schema_view(
            post=extend_schema(
                summary="Обновление JWT-токена доступа (Access Token)",
                description="Принимает валидный `refresh` токен и возвращает новую пару токенов.",
                responses={
                    200: inline_serializer(
                        name="TokenRefreshResponse",
                        fields={
                            "access": serializers.CharField(),
                            "refresh": serializers.CharField(required=False)
                        }
                    ),
                    401: inline_serializer(
                        name="TokenRefreshErrorResponse",
                        fields={"detail": serializers.CharField(default="Token is invalid or expired")}
                    )
                },
                tags=["Аутентификация"],
            )
        )(TokenRefreshView.as_view()),
        name="api_token_refresh",
    ),
    path(
        "api/v1/auth/logout/",
        extend_schema_view(
            post=extend_schema(
                summary="Выход из системы (Инвалидация токена)",
                description=(
                    "Принимает `refresh` токен и заносит его в черный список базы данных. "
                    "После этого токен становится недействительным."
                ),
                responses={
                    200: inline_serializer(
                        name="TokenBlacklistSuccessResponse",
                        fields={} # Пустой JSON {} при успешном выходе
                    ),
                    401: inline_serializer(
                        name="TokenBlacklistErrorResponse",
                        fields={"detail": serializers.CharField(default="Token is invalid or expired")}
                    )
                },
                examples=[
                    OpenApiExample(
                        name="Успешный выход",
                        value={},
                        response_only=True,
                        status_codes=["200"],
                    )
                ],
                tags=["Аутентификация"],
            )
        )(TokenBlacklistView.as_view()),
        name="api_token_blacklist",
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
    # Схема API в формате OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Интерактивный интерфейс Swagger UI
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    # Альтернативный интерфейс Redoc
    path(
        "api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"
    ),
]
