"""
Модуль моделей приложения управления пользователями (users).

Содержит кастомную модель пользователя CustomUser, расширяющую стандартный
функционал Django возможностью хранения номеров телефонов и аватаров.
Использует внешнюю библиотеку django-phonenumber-field для валидации номеров.

Применяется в качестве глобальной модели аутентификации проекта
через настройку AUTH_USER_MODEL в settings.py.
"""

from django.contrib.auth.models import AbstractUser
from phonenumber_field.modelfields import PhoneNumberField
from django.db import models


class CustomUser(AbstractUser):
    """Кастомная модель пользователя."""
    username = models.CharField(
        max_length=100,
        unique=True,
        help_text="Введите ник"
    )
    email = models.EmailField(
        unique=True,
        verbose_name="email",
        help_text="Введите адрес электронной почты"
    )
    phone_number = PhoneNumberField(
        blank=True,
        null=True,
        unique=True,
        verbose_name="Номер телефона",
        help_text="Введите номер телефона",
    )
    avatar = models.ImageField(
        null=True,
        blank=True,
        upload_to="avatars",
        verbose_name="Аватар",
        help_text="Загрузите аватар",
    )

    USERNAME_FIELD = 'username'  # Поле для входа (логин)
    REQUIRED_FIELDS = ['email']  # Что еще спросить при createsuperuser (кроме USERNAME_FIELD и пароля)

    class Meta:
        """Класс метаданных."""
        verbose_name="пользователь"
        verbose_name_plural="пользователи"

    def __str__(self):
        return f"{self.username} ({self.email})"
