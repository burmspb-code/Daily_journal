from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from users.models import CustomUser


class UserRegisterSerializer(serializers.ModelSerializer):
    """Сериализатор для создания нового пользователя."""

    password = serializers.CharField(
        write_only=True,  # Скрываем пароль в ответах
        required=True,  # Поле обязательно
        allow_blank=False,  # Поле не может быть пустым
    )

    class Meta:
        """Класс метаданных."""
        model = CustomUser
        # ЯВНО перечисляем только безопасные поля
        fields = ("username", "email", "password", "phone_number", "avatar")

    def validate_password(self, value):
        """Проверка пароля на соответствие политике безопасности Django."""
        try:
            # Используем стандартные валидаторы из settings.py (длина, символы и т.д.)
            validate_password(value)
        except DjangoValidationError as e:
            # Перехватываем ошибку Django и возвращаем её в формате DRF
            raise serializers.ValidationError(list(e.messages))
        return value

    def create(self, validated_data):
        """Используем кастомный менеджер для безопасного хэширования пароля."""
        # Метод create_user автоматически захеширует пароль перед сохранением
        return CustomUser.objects.create_user(**validated_data)


class EmailVerificationSerializer(serializers.Serializer):
    """Сериализатор для эндпоинта подтверждения регистрации."""

    uidb64 = serializers.CharField(required=True, allow_blank=False)
    token = serializers.CharField(required=True, allow_blank=False)
