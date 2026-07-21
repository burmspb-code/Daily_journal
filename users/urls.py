"""
Маршруты (URL) приложения управления пользователями (users).
"""

from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views
from .views import UserRegisterView

# Пространство имен для URL-адресов приложения
app_name = "users"

urlpatterns = [
    path("register/", UserRegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(template_name="users/login.html"), name="login"),
    path("logout/", LogoutView.as_view(next_page="daily:task_list"), name="logout"),
    path("email-confirmation-sent/", views.EmailConfirmationSentView.as_view(), name="email_confirmation_sent"),
    # Маршруты для сбора пароля (стандартные Django)
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(template_name="users/password_reset.html"),
        name="password_reset"
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="users/password_reset_done.html"),
        name="password_reset_done"
    ),
]
