"""Глобальный конфигурационный файл маршрутов (URL) всего проекта."""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from users.forms import CustomSetPasswordForm

urlpatterns = [
    path("admin/", admin.site.urls),
    # Профессиональное подключение: изолируем приложение под своим префиксом
    path("daily/", include("daily.urls", namespace="daily")),
    # Профессиональное подключение: изолируем приложение под своим префиксом
    path("users/", include("users.urls", namespace="users")),
    # ПРОФЕССИОНАЛЬНО: Перенаправляем пустой корень сайта на наше приложение
    path("", RedirectView.as_view(url="/daily/", permanent=True)),
    # === МАРШРУТЫ АВТОДОКУМЕНТАЦИИ API ===
    # Скачивание файла схемы (нужно для работы панелей)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Интерактивная панель Swagger UI (Рекомендуется)
    path(
        "api/docs/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # Альтернативная панель Redoc
    path(
        "api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"
    ),
]

# Алиас БЕЗ namespace для django.contrib.auth.forms.PasswordResetForm
urlpatterns += [
    path(
        "users/password-reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="users/password_reset_confirm.html",
            success_url="/users/password-reset/complete/",
            form_class=CustomSetPasswordForm,
        ),
        name="password_reset_confirm",
    ),
]
