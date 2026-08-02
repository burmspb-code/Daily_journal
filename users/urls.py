"""
Маршруты (URL) приложения управления пользователями (users).
"""

from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from users.views import UserRegisterView, EmailConfirmationSentView, EmailConfirmView

# Пространство имен для URL-адресов приложения
app_name = "users"

urlpatterns = [
    # Маршрут для регистрации нового пользователя (template_name убран, так как он есть во views)
    path(
        "register/",
        UserRegisterView.as_view(),
        name="register",
    ),
    # Маршрут для входа
    path(
        "login/",
        LoginView.as_view(template_name="users/login.html"),
        name="login",
    ),
    # Маршрут для выхода
    path(
        "logout/",
        LogoutView.as_view(next_page="daily:task_list"),
        name="logout",
    ),
    # Маршрут для показа сообщения «Проверьте почту»
    path(
        "email-confirmation-sent/",
        EmailConfirmationSentView.as_view(),
        name="email_confirmation_sent",
    ),
    # Динамический маршрут, который принимает uid и токен из письма
    path(
        "email-confirm/<str:uidb64>/<str:token>/",
        EmailConfirmView.as_view(),
        name="email_confirm",
    ),
    # Маршруты для сброса пароля (стандартные Django)
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
]
