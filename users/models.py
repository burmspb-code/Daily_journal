"""
Модуль моделей приложения управления пользователями (users).

Содержит кастомную модель пользователя CustomUser, расширяющую стандартный
функционал Django возможностью хранения номеров телефонов и аватаров.
Использует внешнюю библиотеку django-phonenumber-field для валидации номеров.

Применяется в качестве глобальной модели аутентификации проекта
через настройку AUTH_USER_MODEL в settings.py.
"""

from typing import ClassVar

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from .constants import TARIFF_LIMITS


def validate_telegram_id(value):
    """Дополнительная проверка: Telegram ID не может быть равен 0."""
    if value == 0:
        raise ValidationError("Telegram ID не может быть равен 0.")


class CustomUser(AbstractUser):
    """Кастомная модель пользователя."""

    username = models.CharField(max_length=100, unique=True, help_text="Введите ник")
    email = models.EmailField(
        unique=True, verbose_name="email", help_text="Введите адрес электронной почты"
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

    tg_chat_id = models.BigIntegerField(
        blank=True,
        null=True,
        verbose_name="ID Telegram",
        help_text="Введите ID чата Телеграм",
        validators=[
            # Ограничения по диапазону чисел для PostgreSQL BigIntegerField
            MinValueValidator(-9223372036854775808, message="Слишком маленькое или некорректное число."),
            MaxValueValidator(9223372036854775807, message="Введен слишком длинный ID."),
            # Кастомная функция, чтобы отсечь ноль
            validate_telegram_id
        ]
    )

    USERNAME_FIELD = "username"  # Поле для входа (логин)
    REQUIRED_FIELDS: ClassVar[list[str]] = [
        "email"
    ]  # Что еще спросить при createsuperuser (кроме USERNAME_FIELD и пароля)

    class Meta:
        """Класс метаданных."""

        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"

    def __str__(self):
        return f"{self.username} ({self.email})"


class TariffPlans(models.Model):
    """Тарифные планы для пользователей."""

    class TariffNameChoices(models.TextChoices):
        BASE = "BASE", "Базовый"
        STANDARD = "STANDARD", "Стандартный"
        PREMIUM = "PREMIUM", "Премиум"

    plan_name = models.CharField(
        max_length=15,
        default=TariffNameChoices.BASE,
        choices=TariffNameChoices.choices,
        verbose_name="Тарифный план",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        blank=False,
        on_delete=models.CASCADE,
        related_name="tariff_plan",
        verbose_name="Пользователь",
    )

    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Дата окончания подписки",
    )

    max_tasks = models.PositiveIntegerField(
        blank=True,
        default=50,
        verbose_name="Макс. количество задач на ОДНУ закладку"
    )

    max_bookmarks = models.PositiveIntegerField(
        blank=True,
        default=5,
        verbose_name="Максимальное количество закладок"
    )

    is_archive = models.BooleanField(
        default=False,
        verbose_name="Флаг архивной подписки"
    )

    class Meta:
        """Класс метаданных."""

        verbose_name = "Тарифный план"
        verbose_name_plural = "Тарифные планы"

    def __str__(self):
        return f"{self.user.username} {self.get_plan_name_display()}"

    def save(self, *args, **kwargs):
        """Динамически задаем максимальные значения для задач и закладок."""

        tariff_limits = TARIFF_LIMITS.get(self.plan_name, TARIFF_LIMITS.get("BASE"))

        self.max_tasks = tariff_limits.get("MAX_TASKS", 50)
        self.max_bookmarks = tariff_limits.get("MAX_BOOKMARKS", 5)

        if self.user and self.user.is_superuser:
            self.max_tasks = 500
            self.max_bookmarks = 50

        super().save(*args, **kwargs)


