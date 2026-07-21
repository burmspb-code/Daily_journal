"""
Модуль представлений (views) приложения управления пользователями (users).

Содержит контроллеры для аутентификации, авторизации и регистрации
пользователей на основе кастомной модели CustomUser. Реализует логику
валидации регистрационных данных, интеграцию с сервисами капчи
и перенаправление пользователей на этапы подтверждения учетных записей.
"""

from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from .forms import CustomUserCreateForm
from .models import CustomUser


class UserRegisterView(CreateView):
    """Представление для регистрации нового пльзователя."""
    model = CustomUser
    form_class = CustomUserCreateForm
    template_name = 'users/register.html'
    success_url = reverse_lazy("users:email_confirmation_sent")


class EmailConfirmationSentView(TemplateView):
    """Статическая страница с уведомлением об отправке письма."""

    template_name = 'users/email_confirmation_sent.html'

