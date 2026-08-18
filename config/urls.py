"""Глобальный конфигурационный файл маршрутов (URL) всего проекта."""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


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
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Интерактивная панель Swagger UI (Рекомендуется)
    path('api/docs/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # Альтернативная панель Redoc
    path('api/docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
