"""
Сериализаторы приложения управления пользователями (users) для Django REST Framework.

Модуль содержит классы для преобразования данных моделей в формат JSON и обратно,
а также логику комплексной валидации полей при регистрации, авторизации,
просмотре личного профиля и сбросе паролей пользователей.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from users.models import CustomUser

User = get_user_model()


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


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для просмотра и редактирования профиля пользователя."""

    class Meta:
        """Класс метаданных."""

        model = CustomUser
        fields = (
            "id",
            "username",
            "email",
            "phone_number",
            "avatar",
        )
        read_only_fields = ("email",)


class EmailVerificationSerializer(serializers.Serializer):
    """Сериализатор для эндпоинта подтверждения регистрации."""

    uidb64 = serializers.CharField(required=True, allow_blank=False)
    token = serializers.CharField(required=True, allow_blank=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Сериализатор для запроса сброса пароля через REST API.
    Принимает email пользователя, на который будет отправлено письмо.
    """
    email = serializers.EmailField(
        write_only=True,
        help_text="Email-адрес учетной записи, для которой необходимо сбросить пароль."
    )

    def validate_email(self, value):
        """
        Дополнительная валидация email.
        Приводим к нижнему регистру для исключения ошибок разного регистра.
        """
        return value.lower().strip()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Сериализатор для подтверждения сброса пароля через REST API.
    Валидирует UID, токен Django и подготавливает новый пароль к сохранению.
    """
    uid = serializers.CharField(
        write_only=True,
        help_text="Закодированный в base64 идентификатор пользователя (uidb64)."
    )
    token = serializers.CharField(
        write_only=True,
        help_text="Одноразовый защищенный токен восстановления из email-письма."
    )
    new_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Новый пароль, который будет установлен для учетной записи."
    )

    def validate(self, attrs):
        uidb64 = attrs.get('uid')
        token = attrs.get('token')
        new_password = attrs.get('new_password')

        # Декодируем uidb64 и пытаемся найти пользователя в базе данных
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError(
                {"uid": "Неверный идентификатор пользователя или пользователь не существует."}
            )

        # Проверяем, валиден ли токен безопасности для этого конкретного пользователя
        if not default_token_generator.check_token(user, token):
            raise serializers.ValidationError(
                {"token": "Токен восстановления недействителен, изменен или его срок действия истек."}
            )

        # Дополнительно: здесь можно запустить встроенные правила сложности паролей Django
        # from django.contrib.auth.password_validation import validate_password
        # try:
        #     validate_password(new_password, user)
        # except Exception as e:
        #     raise serializers.ValidationError({"new_password": list(e.messages)})

        # Сохраняем проверенные объекты в контекст сериализатора, чтобы View-класс легко их забрал
        self.context["user"] = user
        self.context["new_password"] = new_password

        return attrs
