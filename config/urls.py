# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Профессиональное подключение: изолируем приложение под своим префиксом
    path("daily/", include("daily.urls", namespace="daily")),
    # Профессиональное подключение: изолируем приложение под своим префиксом
    path("users/", include("users.urls", namespace="users")),
    # ПРОФЕССИОНАЛЬНО: Перенаправляем пустой корень сайта на наше приложение
    path("", RedirectView.as_view(url="/daily/", permanent=True)),
]
